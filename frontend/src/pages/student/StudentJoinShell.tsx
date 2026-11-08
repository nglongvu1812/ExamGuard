import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import { roomApi, type AttemptStatusResponse, type HealthResponse } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { StudentExamPage } from "./StudentExamPage";
import { StudentResultPage } from "./StudentResultPage";

interface StudentJoinShellProps {
  health: HealthResponse | null;
  healthError: string | null;
}

function getOrCreateBrowserKey(): string {
  const storageKey = "eg_browser_key";
  const existing = window.localStorage.getItem(storageKey);
  if (existing && existing.length >= 8) return existing;
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  window.localStorage.setItem(storageKey, generated);
  return generated;
}

export function StudentJoinShell({ health, healthError }: StudentJoinShellProps) {
  const [roomCode, setRoomCode] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [inviteSecret, setInviteSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [studentToken, setStudentToken] = useState<string | null>(() =>
    window.sessionStorage.getItem("eg_student_token")
  );
  const [attempt, setAttempt] = useState<AttemptStatusResponse | null>(null);

  useEffect(() => {
    if (!studentToken) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await roomApi.getMyAttempt(studentToken);
        if (!cancelled) {
          setAttempt(res);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Phiên học sinh bị ngắt.");
          window.sessionStorage.removeItem("eg_student_token");
          setStudentToken(null);
          setAttempt(null);
        }
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [studentToken]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!roomCode.trim() || !studentCode.trim() || !inviteSecret.trim()) {
      setError("Vui lòng nhập đầy đủ mã phòng, mã học sinh và mã tham gia cá nhân.");
      return;
    }
    try {
      setSubmitting(true);
      setError(null);
      const browserKey = getOrCreateBrowserKey();
      const res = await roomApi.joinRoom(
        roomCode.trim(),
        studentCode.trim(),
        inviteSecret.trim(),
        browserKey
      );
      window.sessionStorage.setItem("eg_student_token", res.attempt_token);
      setStudentToken(res.attempt_token);
      setAttempt(res.attempt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể vào phòng thi.");
    } finally {
      setSubmitting(false);
    }
  };

  const refreshNow = useCallback(async () => {
    if (!studentToken) return;
    try {
      const res = await roomApi.getMyAttempt(studentToken);
      setAttempt(res);
      setError(null);
    } catch {
      // keep existing UI state gracefully
    }
  }, [studentToken]);

  const handleLeave = () => {
    window.sessionStorage.removeItem("eg_student_token");
    setStudentToken(null);
    setAttempt(null);
  };

  const handleTokenRefreshed = useCallback((newToken: string) => {
    window.sessionStorage.setItem("eg_student_token", newToken);
    setStudentToken(newToken);
  }, []);

  if (attempt && studentToken && attempt.exam_status === "PUBLISHED") {
    return <StudentResultPage studentToken={studentToken} onLeave={handleLeave} />;
  }

  if (
    attempt &&
    studentToken &&
    attempt.exam_status === "RUNNING" &&
    (attempt.state === "READY" ||
      attempt.state === "ACTIVE" ||
      attempt.state === "LOCKED_PENDING_REVIEW" ||
      attempt.state === "ENDED_WITH_REVIEW")
  ) {
    return (
      <StudentExamPage
        studentToken={studentToken}
        attemptId={attempt.attempt_id}
        examId={attempt.exam_id}
        initialAttemptState={attempt.state}
        initialIncidentReason={attempt.incident_reason ?? null}
        studentName={attempt.student_name}
        rosterCode={attempt.roster_code}
        onTokenRefreshed={handleTokenRefreshed}
        onSubmitted={() => void refreshNow()}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-md items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1E3A5F] text-white">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </div>
            <span className="text-sm font-bold text-slate-900">ExamGuard Học sinh</span>
          </div>

          {health ? (
            <StatusBadge
              tone="success"
              label="Đã kết nối LAN"
              icon={<Wifi className="h-3.5 w-3.5" aria-hidden="true" />}
            />
          ) : (
            <StatusBadge
              tone="danger"
              label="Mất kết nối"
              detail={healthError ?? undefined}
              icon={<WifiOff className="h-3.5 w-3.5" aria-hidden="true" />}
            />
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-md px-4 py-6">
        {attempt ? (
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-mono-data text-xs font-semibold text-slate-500">
                  PHÒNG {attempt.room_code} · {attempt.roster_code}
                </p>
                <h1 className="mt-1 text-xl font-bold text-slate-900">{attempt.student_name}</h1>
                <p className="text-sm text-slate-600">{attempt.exam_title}</p>
              </div>
            </div>

            {attempt.state === "SUBMITTED" ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 space-y-2">
                <div className="flex items-center gap-2 font-semibold">
                  <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>Bài làm đã được nộp lên máy chủ</span>
                </div>
                <p className="text-xs leading-relaxed">
                  Thời gian ghi nhận:{" "}
                  <span className="font-mono-data">{attempt.submitted_at ?? "Đã xác nhận"}</span>. Điểm số và đáp án chỉ mở sau khi giáo viên công bố kết quả toàn lớp.
                </p>
              </div>
            ) : attempt.state === "PENDING_APPROVAL" ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 space-y-2">
                <div className="flex items-center gap-2 font-semibold">
                  <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>Đang chờ giáo viên xác nhận vào phòng</span>
                </div>
                <p className="text-xs leading-relaxed">
                  Màn hình tự động cập nhật khi giáo viên bấm duyệt. Không tắt trình duyệt.
                </p>
              </div>
            ) : (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 space-y-2">
                <p className="font-semibold">Đã được duyệt vào phòng thi</p>
                <p className="text-xs leading-relaxed">
                  Vui lòng giữ nguyên màn hình này. Bài thi sẽ tự động mở ngay khi giáo viên nhấn bắt đầu.
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleLeave}
              className="min-h-[44px] w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700"
            >
              Thoát về màn hình nhập mã
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h1 className="text-xl font-bold text-slate-900">Vào phòng kiểm tra</h1>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
              Nhập mã phòng và thông tin do giáo viên cung cấp. Đảm bảo điện thoại đang kết nối đúng Wi-Fi phòng thi.
            </p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <div>
                <label htmlFor="room-code" className="block text-sm font-medium text-slate-800">
                  Mã phòng thi
                </label>
                <input
                  id="room-code"
                  type="text"
                  autoComplete="off"
                  placeholder="Ví dụ: AB12CD"
                  value={roomCode}
                  onChange={(e) => setRoomCode(e.target.value)}
                  className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base uppercase text-slate-900"
                />
              </div>

              <div>
                <label htmlFor="student-code" className="block text-sm font-medium text-slate-800">
                  Mã học sinh
                </label>
                <input
                  id="student-code"
                  type="text"
                  autoComplete="off"
                  placeholder="Ví dụ: HS001"
                  value={studentCode}
                  onChange={(e) => setStudentCode(e.target.value)}
                  className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base uppercase text-slate-900"
                />
              </div>

              <div>
                <label htmlFor="invite-secret" className="block text-sm font-medium text-slate-800">
                  Mã tham gia cá nhân
                </label>
                <input
                  id="invite-secret"
                  type="text"
                  autoComplete="off"
                  placeholder="Mã 6 ký tự từ giáo viên"
                  value={inviteSecret}
                  onChange={(e) => setInviteSecret(e.target.value)}
                  className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base uppercase text-slate-900"
                />
              </div>

              {error ? (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                >
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="min-h-[48px] w-full rounded-lg bg-[#1E3A5F] px-4 py-3 text-base font-semibold text-white hover:bg-[#162C49] disabled:opacity-60"
              >
                {submitting ? "Đang xác thực..." : "Gửi yêu cầu vào phòng"}
              </button>
            </form>
          </div>
        )}

        <p className="mt-4 text-center text-xs text-slate-500">
          Hoạt động 100% trong mạng nội bộ lớp học · Không dùng dữ liệu di động
        </p>
      </main>
    </div>
  );
}
