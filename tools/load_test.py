"""Synthetic 45-client concurrent exam load benchmark against live ExamGuard Uvicorn LAN server.

Usage:
    backend\\.venv\\Scripts\\python.exe tools/load_test.py --clients 45 --questions 20 --rounds 3
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import openpyxl

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = math.floor(idx)
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = idx - lo
    return round(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac, 2)


def _get_process_rss_mb(pid: int) -> float | None:
    """Read real OS Working Set RSS of server process cleanly on Windows/POSIX."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        handle = k32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            return None
        try:
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(float(int(counters.PeakWorkingSetSize)) / (1024 * 1024), 2)
        finally:
            k32.CloseHandle(handle)
    return None


async def _drive_load_clients(
    *,
    base_url: str,
    clients: int,
    questions: int,
    rounds: int,
    server_log_path: Path | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as http:
        started = False
        for _ in range(80):
            try:
                r = await http.get("/api/v1/health")
                if r.status_code == 200:
                    started = True
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.15)
        if not started:
            log_tail = ""
            if server_log_path and server_log_path.is_file():
                log_tail = server_log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"ExamGuard server failed to start for load benchmark:\n{log_tail}")

        t_tok = (await http.post("/api/v1/auth/teacher/local-session")).json()["token"]
        hdrs = {"Authorization": f"Bearer {t_tok}"}

        cls_id = (
            await http.post(
                "/api/v1/classes",
                json={"name": "12A-LoadBench", "academic_year": "2026-2027"},
                headers=hdrs,
            )
        ).json()["id"]

        for i in range(1, clients + 1):
            r = await http.post(
                f"/api/v1/classes/{cls_id}/students",
                json={"roster_code": f"HS{i:03d}", "full_name": f"Học sinh Mẫu {i:03d}"},
                headers=hdrs,
            )
            r.raise_for_status()

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["STT", "Câu hỏi", "A", "B", "C", "D", "Đáp án đúng"])
        for q_i in range(1, questions + 1):
            ws.append(
                [q_i, f"Câu hỏi kiểm tải số {q_i}: Chọn kết quả đúng", "Đúng A", "Sai B", "Sai C", "Sai D", "A"]
            )
        xbuf = io.BytesIO()
        wb.save(xbuf)
        imp = (
            await http.post(
                "/api/v1/questions/import",
                data={"profile": "vn_standard"},
                files={
                    "file": (
                        "load_bank.xlsx",
                        xbuf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                headers=hdrs,
            )
        ).json()
        (
            await http.post(
                f"/api/v1/questions/import/{imp['job_id']}/approve-ready",
                json={"bank_name": "LoadBench"},
                headers=hdrs,
            )
        ).raise_for_status()
        bank = (await http.get("/api/v1/questions/bank", headers=hdrs)).json()
        qvids = [item["version_id"] for item in bank[:questions]]
        assert len(qvids) == questions

        exam_res = (
            await http.post(
                "/api/v1/exams",
                json={
                    "classroom_id": cls_id,
                    "title": f"Load Benchmark {clients} Clients",
                    "duration_s": 1800,
                    "question_version_ids": qvids,
                    "shuffle_questions": True,
                    "shuffle_options": True,
                    "seed": 4242,
                    "open_waiting": True,
                },
                headers=hdrs,
            )
        ).json()
        exam_id = exam_res["exam"]["exam_id"]
        room_code = exam_res["exam"]["room_code"]
        invites = {inv["roster_code"]: inv["invite_code"] for inv in exam_res["invites"]}

        join_latencies: list[float] = []
        save_latencies: list[float] = []
        hb_latencies: list[float] = []
        submit_latencies: list[float] = []
        errors = 0
        student_sessions: list[dict[str, str]] = []

        async def _join_one(idx: int) -> None:
            nonlocal errors
            code = f"HS{idx:03d}"
            t0 = time.perf_counter()
            r = await http.post(
                f"/api/v1/room/{room_code}/join",
                json={
                    "roster_code": code,
                    "invite_code": invites[code],
                    "browser_key": f"bench-browser-{idx:03d}",
                },
            )
            join_latencies.append((time.perf_counter() - t0) * 1000.0)
            if r.status_code != 200:
                errors += 1
                return
            body = r.json()
            student_sessions.append(
                {
                    "roster_code": code,
                    "token": body["attempt_token"],
                    "attempt_id": body["attempt"]["attempt_id"],
                }
            )

        await asyncio.gather(*(_join_one(i) for i in range(1, clients + 1)))

        (await http.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=hdrs)).raise_for_status()
        (await http.post(f"/api/v1/exams/{exam_id}/start", headers=hdrs)).raise_for_status()

        async def _run_student_flow(sess: dict[str, str], s_idx: int) -> None:
            nonlocal errors
            s_hdrs = {"Authorization": f"Bearer {sess['token']}"}
            att_id = sess["attempt_id"]
            r_p = await http.get("/api/v1/attempts/me/paper", headers=s_hdrs)
            if r_p.status_code != 200:
                errors += 1
                return
            qs = r_p.json()["questions"]
            last_ack: dict[str, list[str]] = {}
            rng = random.Random(1000 + s_idx)

            for rnd in range(1, rounds + 1):
                q_pick = qs[rnd % len(qs)]
                opt_pick = rng.choice(q_pick["options"])["option_id"]
                t0 = time.perf_counter()
                r_sv = await http.post(
                    f"/api/v1/attempts/{att_id}/answers",
                    json={
                        "question_version_id": q_pick["question_version_id"],
                        "selected_option_ids": [opt_pick],
                        "idempotency_key": f"load-{s_idx}-r{rnd}",
                    },
                    headers=s_hdrs,
                )
                save_latencies.append((time.perf_counter() - t0) * 1000.0)
                if r_sv.status_code != 200:
                    errors += 1
                else:
                    last_ack[q_pick["question_version_id"]] = [opt_pick]

                t_h = time.perf_counter()
                r_hb = await http.post(f"/api/v1/attempts/{att_id}/heartbeat", headers=s_hdrs)
                hb_latencies.append((time.perf_counter() - t_h) * 1000.0)
                if r_hb.status_code != 200:
                    errors += 1

            t_sub = time.perf_counter()
            r_sub = await http.post(f"/api/v1/attempts/{att_id}/submit", headers=s_hdrs)
            submit_latencies.append((time.perf_counter() - t_sub) * 1000.0)
            if r_sub.status_code != 200:
                errors += 1
                return

            r_sync = await http.get(f"/api/v1/attempts/{att_id}/sync", headers=s_hdrs)
            if r_sync.status_code != 200:
                errors += 1
            else:
                srv_saved = r_sync.json()["saved_answers"]
                for qid, expected_opts in last_ack.items():
                    if srv_saved.get(qid, {}).get("selected_option_ids") != expected_opts:
                        errors += 1

        await asyncio.gather(*(_run_student_flow(sess, i) for i, sess in enumerate(student_sessions)))

        (
            await http.post(
                f"/api/v1/exams/{exam_id}/close",
                json={"reason": "Kết thúc phiên benchmark tải"},
                headers=hdrs,
            )
        ).raise_for_status()
        g_res = await http.post(
            f"/api/v1/results/exams/{exam_id}/grade",
            json={"reason": "Chấm kiểm tải"},
            headers=hdrs,
        )
        g_res.raise_for_status()
        ov = (await http.get(f"/api/v1/results/exams/{exam_id}", headers=hdrs)).json()
        submitted_count = sum(1 for row in ov["students"] if row["submission_id"])

    save_sorted = sorted(save_latencies)
    sub_sorted = sorted(submit_latencies)
    join_sorted = sorted(join_latencies)
    return {
        "mode": "SYNTHETIC_HTTP_CONCURRENT",
        "clients": clients,
        "questions": questions,
        "save_rounds_per_client": rounds,
        "total_answer_saves": len(save_latencies),
        "total_heartbeats": len(hb_latencies),
        "total_submits": len(submit_latencies),
        "submitted_in_db": submitted_count,
        "lost_or_mismatched_acks": errors,
        "join_p50_ms": round(statistics.median(join_sorted), 2) if join_sorted else 0.0,
        "join_p95_ms": _percentile(join_sorted, 95),
        "save_p50_ms": round(statistics.median(save_sorted), 2) if save_sorted else 0.0,
        "save_p95_ms": _percentile(save_sorted, 95),
        "save_max_ms": round(max(save_sorted), 2) if save_sorted else 0.0,
        "submit_p50_ms": round(statistics.median(sub_sorted), 2) if sub_sorted else 0.0,
        "submit_p95_ms": _percentile(sub_sorted, 95),
    }


def run_benchmark(clients: int, questions: int, rounds: int) -> dict[str, Any]:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from desktop.launcher import find_available_port

    port = find_available_port(preferred_port=18700, host="127.0.0.1")
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_str:
        data_dir = Path(tmp_str) / "ExamGuardData"
        server_log_path = Path(tmp_str) / "server_output.log"
        cmd = [
            sys.executable,
            str(ROOT_DIR / "desktop" / "launcher.py"),
            "--no-browser",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--data-dir",
            str(data_dir),
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BACKEND_DIR)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        with server_log_path.open("w", encoding="utf-8") as log_f:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
            )
        try:
            result = asyncio.run(
                _drive_load_clients(
                    base_url=base_url,
                    clients=clients,
                    questions=questions,
                    rounds=rounds,
                    server_log_path=server_log_path,
                )
            )
            result["peak_server_rss_mb"] = _get_process_rss_mb(proc.pid)
            return result
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="ExamGuard Synthetic 45-Client LAN Load Benchmark")
    parser.add_argument("--clients", type=int, default=45)
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    result = run_benchmark(args.clients, args.questions, args.rounds)
    print("LOAD_BENCHMARK=" + json.dumps(result, ensure_ascii=False))
    if result["lost_or_mismatched_acks"] != 0 or result["submitted_in_db"] != args.clients:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
