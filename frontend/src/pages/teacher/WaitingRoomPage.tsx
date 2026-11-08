import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertCircle,
  Award,
  CheckCheck,
  Clock,
  Eye,
  Lock,
  PauseCircle,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sliders,
  Square,
  Trash2,
  Users,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import {
  ensureTeacherToken,
  examApi,
  monitoringApi,
  questionApi,
  roomApi,
  rosterApi,
  type ApprovedQuestionDTO,
  type AttemptTimelineResponse,
  type ClassroomDTO,
  type IssuedInviteResponse,
  type MonitoringPolicyDTO,
  type RoomMonitoringSnapshotDTO,
  type RoomSummaryDTO,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function WaitingRoomPage() {
  const { examId: routeExamId } = useParams<{ examId?: string }>();
  const [classes, setClasses] = useState<ClassroomDTO[]>([]);
  const [bankQuestions, setBankQuestions] = useState<ApprovedQuestionDTO[]>([]);
  const [rooms, setRooms] = useState<RoomSummaryDTO[]>([]);

  // Step 1-4 Wizard state (including configurable monitoring policy!)
  const [selectedClassId, setSelectedClassId] = useState("");
  const [title, setTitle] = useState("Kiểm tra 15 phút");
  const [durationMin, setDurationMin] = useState(15);
  const [selectedQIds, setSelectedQIds] = useState<string[]>([]);
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);
  const [policyDraft, setPolicyDraft] = useState<MonitoringPolicyDTO>({
    heartbeat_s: 3,
    suspected_s: 5,
    disconnect_s: 15,
    lock_after_s: 30,
    grace_submit_s: 30,
  });

  // Live Monitoring T5/T6 State
  const [activeRoom, setActiveRoom] = useState<RoomSummaryDTO | null>(null);
  const [invites, setInvites] = useState<IssuedInviteResponse[]>([]);
  const [snapshot, setSnapshot] = useState<RoomMonitoringSnapshotDTO | null>(null);
  const [wsLive, setWsLive] = useState(false);
  const [showPolicyEditor, setShowPolicyEditor] = useState(false);
  const [livePolicy, setLivePolicy] = useState<MonitoringPolicyDTO | null>(null);

  // Incident & Evidence Timeline Drawer state
  const [drawerTimeline, setDrawerTimeline] = useState<AttemptTimelineResponse | null>(null);
  const [resolutionReason, setResolutionReason] = useState("Đã xác minh sự cố mạng / cho phép thi tiếp");
  const [extendMinutes, setExtendMinutes] = useState(5);

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBase = useCallback(async () => {
    try {
      const [clsList, bankList, roomList, activeExam] = await Promise.all([
        rosterApi.listClasses(),
        questionApi.listBank(),
        roomApi.listRooms(),
        examApi.getActiveExam().catch(() => null),
      ]);
      setClasses(clsList);
      setBankQuestions(bankList);
      setRooms(roomList);
      if (clsList.length > 0 && !selectedClassId) {
        setSelectedClassId(clsList[0]?.id ?? "");
      }
      if (bankList.length > 0 && selectedQIds.length === 0) {
        setSelectedQIds(bankList.map((b) => b.version_id));
      }

      // Priority 1: Match route param :examId
      if (routeExamId) {
        const fromRoute = roomList.find((r) => r.exam_id === routeExamId);
        if (fromRoute) {
          setActiveRoom(fromRoute);
          return;
        }
      }

      // Priority 2: Keep current active room if valid
      if (activeRoom) {
        const refreshed = roomList.find((r) => r.exam_id === activeRoom.exam_id);
        if (refreshed) {
          setActiveRoom(refreshed);
          return;
        }
      }

      // Priority 3: Auto-select active WAITING or RUNNING exam
      if (activeExam) {
        const matched = roomList.find((r) => r.exam_id === activeExam.exam_id);
        if (matched) {
          setActiveRoom(matched);
          return;
        }
      }

      // Priority 4: Fall back to most recent room
      if (roomList.length > 0 && !activeRoom) {
        setActiveRoom(roomList[0] ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu cấu hình phòng thi.");
    }
  }, [selectedClassId, activeRoom, selectedQIds.length, routeExamId]);

  const loadMonitoringSnapshot = useCallback(async (examId: string) => {
    try {
      const [snap, roomList] = await Promise.all([
        monitoringApi.getSnapshot(examId),
        roomApi.listRooms(),
      ]);
      setSnapshot(snap);
      setLivePolicy(snap.policy);
      setRooms(roomList);
      const updated = roomList.find((r) => r.exam_id === examId);
      if (updated) setActiveRoom(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu giám sát phòng thi.");
    }
  }, []);

  useEffect(() => {
    void loadBase();
  }, [loadBase]);

  // Real-time WebSocket stream + 3s HTTP fallback polling
  useEffect(() => {
    if (!activeRoom) return;
    void loadMonitoringSnapshot(activeRoom.exam_id);
    const pollTimer = setInterval(() => void loadMonitoringSnapshot(activeRoom.exam_id), 3000);

    let ws: WebSocket | null = null;
    let cancelled = false;

    const connectTeacherWs = async () => {
      if (typeof WebSocket === "undefined" || !window.location.host) return;
      try {
        const token = await ensureTeacherToken();
        if (cancelled) return;
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(
          `${proto}//${window.location.host}/ws/v1/room/${encodeURIComponent(activeRoom.exam_id)}?token=${encodeURIComponent(token)}`
        );
        ws.onopen = () => {
          if (!cancelled) setWsLive(true);
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
            if (
              (msg.type === "welcome" || msg.type === "room_snapshot") &&
              msg.snapshot &&
              typeof msg.snapshot === "object"
            ) {
              setSnapshot(msg.snapshot as RoomMonitoringSnapshotDTO);
            }
          } catch {
            // ignore malformed ws message
          }
        };
        ws.onclose = () => {
          if (!cancelled) setWsLive(false);
        };
        ws.onerror = () => {
          if (!cancelled) setWsLive(false);
        };
      } catch {
        setWsLive(false);
      }
    };
    void connectTeacherWs();

    return () => {
      cancelled = true;
      clearInterval(pollTimer);
      if (ws) ws.close();
      setWsLive(false);
    };
  }, [activeRoom, loadMonitoringSnapshot]);

  const toggleQuestion = (versionId: string) => {
    setSelectedQIds((prev) =>
      prev.includes(versionId) ? prev.filter((id) => id !== versionId) : [...prev, versionId]
    );
  };

  const handleCreateExamAndOpenRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClassId) return;
    if (selectedQIds.length === 0) {
      setError("Vui lòng duyệt câu hỏi ở Ngân hàng đề trước và chọn ít nhất 1 câu.");
      return;
    }
    if (
      !window.confirm(
        `Xác nhận mở phòng chờ "${title}" (${durationMin} phút, ${selectedQIds.length} câu)?`
      )
    ) {
      return;
    }
    try {
      setError(null);
      const res = await examApi.createExam({
        classroom_id: selectedClassId,
        title,
        duration_s: Math.max(60, durationMin * 60),
        question_version_ids: selectedQIds,
        shuffle_questions: shuffleQuestions,
        shuffle_options: shuffleOptions,
        policy: { ...policyDraft },
        open_waiting: true,
      });
      setActiveRoom({
        exam_id: res.exam.exam_id,
        classroom_id: res.exam.classroom_id,
        room_code: res.exam.room_code,
        title: res.exam.title,
        duration_s: res.exam.duration_s,
        status: res.exam.status,
        remaining_s: res.exam.remaining_s,
        is_paused: res.exam.is_paused,
        question_count: res.exam.question_count,
      });
      setInvites(res.invites);
      setNotice(
        `Đã mở phòng chờ ${res.exam.room_code} (${res.exam.question_count} câu) và cấp ${res.invites.length} mã mời.`
      );
      await loadMonitoringSnapshot(res.exam.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể mở phòng thi.");
    }
  };

  const handleStartExam = async () => {
    if (!activeRoom) return;
    if (
      !window.confirm(
        `BẮT ĐẦU tính giờ cho phòng ${activeRoom.room_code}? Học sinh đã duyệt sẽ nhận đề ngay lập tức.`
      )
    ) {
      return;
    }
    try {
      setError(null);
      await examApi.startExam(activeRoom.exam_id);
      setNotice(`Phòng ${activeRoom.room_code} ĐÃ BẮT ĐẦU! Đồng hồ máy chủ đang đếm ngược.`);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa thể bắt đầu bài thi.");
    }
  };

  const handlePauseExam = async () => {
    if (!activeRoom) return;
    const reason = window.prompt("Nhập lý do tạm dừng phòng thi:", "Xử lý sự cố Wi-Fi / đọc lại quy chế");
    if (!reason || reason.trim().length < 3) return;
    try {
      await examApi.pauseExam(activeRoom.exam_id, reason.trim());
      setNotice("Đã tạm dừng đồng hồ phòng thi (đã ghi audit).");
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tạm dừng.");
    }
  };

  const handleResumeExam = async () => {
    if (!activeRoom) return;
    try {
      await examApi.resumeExam(activeRoom.exam_id);
      setNotice("Đã tiếp tục bài thi và cộng bù thời gian tạm dừng.");
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tiếp tục.");
    }
  };

  const handleCloseExam = async () => {
    if (!activeRoom) return;
    if (
      !window.confirm(
        `Xác nhận ĐÓNG phòng ${activeRoom.room_code}? Toàn bộ bài chưa nộp sẽ được hệ thống khóa snapshot tự động.`
      )
    ) {
      return;
    }
    try {
      await examApi.closeExam(activeRoom.exam_id, "Giáo viên kết thúc thu bài");
      setNotice(`Phòng ${activeRoom.room_code} đã ĐÓNG và niêm phong toàn bộ bài nộp.`);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đóng phòng thi.");
    }
  };

  const handleCancelExam = async () => {
    if (!activeRoom) return;
    if (
      !window.confirm(
        `Xác nhận HỦY / XÓA phòng chờ ${activeRoom.room_code}? Học sinh sẽ không thể tham gia vào phòng này nữa.`
      )
    ) {
      return;
    }
    try {
      await examApi.cancelExam(activeRoom.exam_id, "Giáo viên hủy phòng chờ cũ");
      setNotice(`Đã hủy thành công phòng chờ ${activeRoom.room_code}.`);
      setInvites([]);
      setSnapshot(null);
      await loadBase();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể hủy phòng chờ.");
    }
  };

  const handleApprove = async (attemptId: string) => {
    if (!activeRoom) return;
    try {
      await roomApi.approveAttempt(activeRoom.exam_id, attemptId);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi duyệt học sinh.");
    }
  };

  const handleApproveAll = async () => {
    if (!activeRoom) return;
    if (!window.confirm("Xác nhận duyệt tất cả học sinh đang ở trạng thái chờ?")) return;
    try {
      const res = await roomApi.approveAll(activeRoom.exam_id);
      setNotice(`Đã duyệt ${res.approved_count} học sinh vào phòng.`);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi duyệt hàng loạt.");
    }
  };

  const handleResetDevice = async (attemptId: string, fullName: string, rosterCode: string) => {
    if (!activeRoom) return;
    const reason = window.prompt(
      `Nhập lý do đặt lại thiết bị cho ${fullName} (${rosterCode}):`,
      "Đổi máy dự phòng do thiết bị cũ lỗi kết nối"
    );
    if (!reason || reason.trim().length < 3) return;
    try {
      await roomApi.resetDevice(activeRoom.exam_id, attemptId, reason.trim());
      setNotice(`Đã đặt lại thiết bị cho ${rosterCode} (đã ghi nhật ký kiểm tra).`);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đặt lại được thiết bị.");
    }
  };

  const handleLockAttempt = async (attemptId: string, rosterCode: string) => {
    if (!activeRoom) return;
    const reason = window.prompt(
      `Nhập lý do tạm khóa để xác minh cho ${rosterCode}:`,
      "Cần kiểm tra thiết bị / xác minh quy chế tại chỗ"
    );
    if (!reason || reason.trim().length < 3) return;
    try {
      await monitoringApi.lockAttempt(activeRoom.exam_id, attemptId, reason.trim());
      setNotice(`Đã tạm khóa phiên của ${rosterCode} để xác minh.`);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tạm khóa được bài.");
    }
  };

  const handleOpenTimeline = async (attemptId: string) => {
    if (!activeRoom) return;
    try {
      setError(null);
      const tl = await monitoringApi.getTimeline(activeRoom.exam_id, attemptId);
      setDrawerTimeline(tl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được chi tiết nhật ký sự cố.");
    }
  };

  const handleResolveIncident = async (action: "unlock" | "extend_time" | "terminate") => {
    if (!activeRoom || !drawerTimeline) return;
    if (resolutionReason.trim().length < 3) {
      setError("Vui lòng nhập lý do xử lý tối thiểu 3 ký tự.");
      return;
    }
    const labelMap = {
      unlock: "Mở lại cho phép học sinh tiếp tục thi",
      extend_time: `Gia hạn thêm ${extendMinutes} phút và mở lại bài`,
      terminate: "Kết thúc & niêm phong các đáp án đã lưu của học sinh này",
    };
    if (!window.confirm(`Xác nhận ${labelMap[action]} cho ${drawerTimeline.roster_code}?`)) {
      return;
    }
    try {
      await monitoringApi.resolveIncident(activeRoom.exam_id, drawerTimeline.attempt_id, {
        action,
        reason: resolutionReason.trim(),
        extend_minutes: action === "extend_time" ? extendMinutes : 0,
      });
      setNotice(`Đã xử lý sự cố cho ${drawerTimeline.roster_code} (đã lưu audit).`);
      setDrawerTimeline(null);
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xử lý sự cố.");
    }
  };

  const handleSaveLivePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRoom || !livePolicy) return;
    try {
      const updated = await monitoringApi.updatePolicy(activeRoom.exam_id, livePolicy);
      setLivePolicy(updated);
      setShowPolicyEditor(false);
      setNotice("Đã cập nhật ngưỡng giám sát cho phòng thi.");
      await loadMonitoringSnapshot(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ngưỡng giám sát không hợp lệ.");
    }
  };

  const rosterEntries = snapshot?.roster ?? [];
  const summary = snapshot?.summary;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Tạo bài kiểm tra & Giám sát phòng thi trực tiếp
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Tín hiệu ngắt mạng hay chuyển tab chỉ mang tính hỗ trợ quan sát, không tự động kết luận gian lận.
        </p>
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
          {notice}
        </div>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="text-base font-semibold text-slate-900">Cấu hình bài kiểm tra mới</h2>
        <form onSubmit={handleCreateExamAndOpenRoom} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label htmlFor="exam-class" className="block text-xs font-medium text-slate-700">
                1. Chọn lớp học
              </label>
              <select
                id="exam-class"
                value={selectedClassId}
                onChange={(e) => setSelectedClassId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              >
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.student_count} HS)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="exam-title" className="block text-xs font-medium text-slate-700">
                2. Tên bài kiểm tra
              </label>
              <input
                id="exam-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label htmlFor="exam-duration" className="block text-xs font-medium text-slate-700">
                3. Thời lượng (phút)
              </label>
              <div className="mt-1 flex items-center gap-1.5">
                {[15, 45, 60].map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setDurationMin(m)}
                    className={`rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${
                      durationMin === m
                        ? "border-[#1E3A5F] bg-[#1E3A5F] text-white"
                        : "border-slate-300 bg-white text-slate-700"
                    }`}
                  >
                    {m}p
                  </button>
                ))}
                <input
                  id="exam-duration"
                  type="number"
                  min={1}
                  max={240}
                  value={durationMin}
                  onChange={(e) => setDurationMin(Math.max(1, Number(e.target.value)))}
                  className="font-mono-data w-20 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-800">
                4. Chọn câu hỏi từ Ngân hàng đề đã duyệt ({selectedQIds.length}/{bankQuestions.length} câu)
              </span>
              <div className="flex gap-3 text-xs">
                <label className="inline-flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={shuffleQuestions}
                    onChange={(e) => setShuffleQuestions(e.target.checked)}
                  />
                  <span>Trộn thứ tự câu</span>
                </label>
                <label className="inline-flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={shuffleOptions}
                    onChange={(e) => setShuffleOptions(e.target.checked)}
                  />
                  <span>Trộn đáp án A/B/C/D</span>
                </label>
              </div>
            </div>

            {bankQuestions.length === 0 ? (
              <p className="text-xs text-amber-800">
                Chưa có câu hỏi nào được duyệt. Vào mục &quot;Ngân hàng đề&quot; để nhập từ file Word trước.
              </p>
            ) : (
              <div className="max-h-36 overflow-y-auto grid gap-1.5 sm:grid-cols-2">
                {bankQuestions.map((q, idx) => (
                  <label
                    key={q.version_id}
                    className="flex items-start gap-2 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedQIds.includes(q.version_id)}
                      onChange={() => toggleQuestion(q.version_id)}
                      className="mt-0.5"
                    />
                    <span className="line-clamp-1">
                      <strong>#{idx + 1}</strong> [{q.bank_name}]{" "}
                      {q.blocks.map((b) => b.text ?? b.latex ?? "[Ảnh]").join(" ")}
                    </span>
                  </label>
                ))}
              </div>
            )}

            <div className="grid gap-2 pt-2 border-t border-slate-200 sm:grid-cols-4 text-xs">
              <label className="block">
                <span className="text-slate-600">Heartbeat (giây)</span>
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={policyDraft.heartbeat_s}
                  onChange={(e) =>
                    setPolicyDraft((p) => ({ ...p, heartbeat_s: Math.max(1, Number(e.target.value)) }))
                  }
                  className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-slate-600">Nghi mất tín hiệu (s)</span>
                <input
                  type="number"
                  min={2}
                  max={120}
                  value={policyDraft.suspected_s}
                  onChange={(e) =>
                    setPolicyDraft((p) => ({ ...p, suspected_s: Math.max(2, Number(e.target.value)) }))
                  }
                  className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-slate-600">Xác nhận mất mạng (s)</span>
                <input
                  type="number"
                  min={5}
                  max={300}
                  value={policyDraft.disconnect_s}
                  onChange={(e) =>
                    setPolicyDraft((p) => ({ ...p, disconnect_s: Math.max(5, Number(e.target.value)) }))
                  }
                  className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                />
              </label>
              <label className="block">
                <span className="text-slate-600">Tự khóa xác minh (s, 0=tắt)</span>
                <input
                  type="number"
                  min={0}
                  max={600}
                  value={policyDraft.lock_after_s}
                  onChange={(e) =>
                    setPolicyDraft((p) => ({ ...p, lock_after_s: Math.max(0, Number(e.target.value)) }))
                  }
                  className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                />
              </label>
            </div>
          </div>

          <button
            type="submit"
            disabled={!selectedClassId || selectedQIds.length === 0}
            className="rounded-lg bg-[#1E3A5F] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#162C49] disabled:opacity-50"
          >
            Mở phòng chờ & Cấp mã mời
          </button>
        </form>

        {rooms.length > 0 ? (
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Phòng thi gần đây:</span>
            {rooms.slice(0, 6).map((r) => (
              <button
                key={r.exam_id}
                type="button"
                onClick={() => setActiveRoom(r)}
                className={`font-mono-data rounded-md border px-2.5 py-1 text-xs ${
                  activeRoom?.exam_id === r.exam_id
                    ? "border-[#1E3A5F] bg-[#1E3A5F] text-white"
                    : "border-slate-300 bg-slate-50 text-slate-700"
                }`}
              >
                {r.room_code} · {r.status}
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {invites.length > 0 ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-sm font-bold text-amber-950">
            Mã tham gia cá nhân cho phòng {activeRoom?.room_code} (Chỉ hiển thị một lần)
          </h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-3 md:grid-cols-4">
            {invites.map((inv) => (
              <div
                key={inv.student_id}
                className="flex items-center justify-between rounded border border-amber-200 bg-white px-3 py-2 text-xs"
              >
                <div>
                  <p className="font-mono-data font-bold text-slate-900">{inv.roster_code}</p>
                  <p className="text-slate-600">{inv.full_name}</p>
                </div>
                <span className="font-mono-data rounded bg-slate-100 px-2 py-1 text-sm font-bold text-[#1E3A5F]">
                  {inv.invite_code}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {activeRoom ? (
        <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          {/* Header & Room Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Users className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
                <span>
                  Phòng {activeRoom.room_code} — {activeRoom.title} ({activeRoom.question_count ?? 0} câu)
                </span>
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <StatusBadge
                  tone={
                    activeRoom.status === "RUNNING"
                      ? activeRoom.is_paused
                        ? "warning"
                        : "success"
                      : activeRoom.status === "CLOSED"
                      ? "neutral"
                      : "info"
                  }
                  label={
                    activeRoom.status === "RUNNING"
                      ? activeRoom.is_paused
                        ? "ĐANG TẠM DỪNG"
                        : "ĐANG THI"
                      : activeRoom.status
                  }
                />
                <span className="font-mono-data inline-flex items-center gap-1 text-slate-700 font-semibold">
                  <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                  Còn lại: {formatClock(snapshot?.remaining_s ?? activeRoom.remaining_s ?? activeRoom.duration_s)}
                </span>
                <StatusBadge
                  tone={wsLive ? "success" : "info"}
                  label={wsLive ? "WebSocket trực tiếp" : "Đồng bộ định kỳ 3s"}
                  icon={
                    wsLive ? (
                      <Wifi className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <RefreshCw className="h-3 w-3" aria-hidden="true" />
                    )
                  }
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setShowPolicyEditor((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
              >
                <Sliders className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Chính sách mạng</span>
              </button>
              <button
                type="button"
                onClick={() => void loadMonitoringSnapshot(activeRoom.exam_id)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Làm mới</span>
              </button>
              <button
                type="button"
                onClick={() => void handleApproveAll()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#0F766E] bg-white px-3 py-1.5 text-xs font-semibold text-[#0F766E]"
              >
                <CheckCheck className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Duyệt tất cả chờ</span>
              </button>
              {activeRoom.status === "WAITING" ? (
                <>
                  <button
                    type="button"
                    disabled={(activeRoom.question_count ?? 0) === 0}
                    onClick={() => void handleStartExam()}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    <Play className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Bắt đầu làm bài</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCancelExam()}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100"
                    title="Hủy phòng chờ hiện tại để tránh xung đột mã phòng"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Hủy phòng chờ này</span>
                  </button>
                </>
              ) : null}
              {activeRoom.status === "RUNNING" ? (
                <>
                  {activeRoom.is_paused ? (
                    <button
                      type="button"
                      onClick={() => void handleResumeExam()}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white"
                    >
                      <Play className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Tiếp tục thi</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void handlePauseExam()}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900"
                    >
                      <PauseCircle className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>Tạm dừng</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleCloseExam()}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-red-700 px-3.5 py-1.5 text-xs font-semibold text-white"
                  >
                    <Square className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Đóng phòng thu bài</span>
                  </button>
                </>
              ) : null}
              {["CLOSED", "REVIEWED", "PUBLISHED"].includes(activeRoom.status) ? (
                <Link
                  to={`/results?examId=${encodeURIComponent(activeRoom.exam_id)}`}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A5F] px-3.5 py-1.5 text-xs font-semibold text-white"
                >
                  <Award className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Chấm điểm & Công bố</span>
                </Link>
              ) : null}
            </div>
          </div>

          {/* T6 Live Stats Strip */}
          {summary ? (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-6">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="text-[11px] text-slate-500">Tổng sĩ số</p>
                <p className="font-mono-data text-lg font-bold text-slate-900">{summary.total_students}</p>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
                <p className="text-[11px] text-emerald-700">Đang làm bài</p>
                <p className="font-mono-data text-lg font-bold text-emerald-900">{summary.active_count}</p>
              </div>
              <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
                <p className="text-[11px] text-blue-700">Đã nộp</p>
                <p className="font-mono-data text-lg font-bold text-blue-900">{summary.submitted_count}</p>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="text-[11px] text-amber-800">Chờ duyệt</p>
                <p className="font-mono-data text-lg font-bold text-amber-900">{summary.pending_count}</p>
              </div>
              <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2">
                <p className="text-[11px] text-amber-800">Mất kết nối</p>
                <p className="font-mono-data text-lg font-bold text-amber-950">
                  {summary.suspected_count + summary.disconnected_count}
                </p>
              </div>
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2">
                <p className="text-[11px] text-red-700">Đang tạm khóa / Sự cố</p>
                <p className="font-mono-data text-lg font-bold text-red-900">
                  {summary.locked_count} ({summary.open_incidents_count})
                </p>
              </div>
            </div>
          ) : null}

          {/* Configurable Grace Policy Panel */}
          {showPolicyEditor && livePolicy ? (
            <form
              onSubmit={handleSaveLivePolicy}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase text-slate-700">
                  Điều chỉnh ngưỡng mất kết nối & tạm khóa (áp dụng ngay)
                </h3>
                <button
                  type="submit"
                  className="rounded bg-[#1E3A5F] px-3 py-1 text-xs font-semibold text-white"
                >
                  Lưu chính sách
                </button>
              </div>
              <div className="grid gap-3 sm:grid-cols-4 text-xs">
                <label className="block">
                  <span>Heartbeat (s)</span>
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={livePolicy.heartbeat_s}
                    onChange={(e) =>
                      setLivePolicy({ ...livePolicy, heartbeat_s: Number(e.target.value) })
                    }
                    className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                  />
                </label>
                <label className="block">
                  <span>Tín hiệu yếu (s)</span>
                  <input
                    type="number"
                    min={2}
                    max={120}
                    value={livePolicy.suspected_s}
                    onChange={(e) =>
                      setLivePolicy({ ...livePolicy, suspected_s: Number(e.target.value) })
                    }
                    className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                  />
                </label>
                <label className="block">
                  <span>Mất kết nối (s)</span>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={livePolicy.disconnect_s}
                    onChange={(e) =>
                      setLivePolicy({ ...livePolicy, disconnect_s: Number(e.target.value) })
                    }
                    className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                  />
                </label>
                <label className="block">
                  <span>Tự khóa (s, 0=tắt)</span>
                  <input
                    type="number"
                    min={0}
                    max={600}
                    value={livePolicy.lock_after_s}
                    onChange={(e) =>
                      setLivePolicy({ ...livePolicy, lock_after_s: Number(e.target.value) })
                    }
                    className="font-mono-data mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1"
                  />
                </label>
              </div>
            </form>
          ) : null}

          {/* Open Incidents Banner */}
          {snapshot && snapshot.open_incidents.length > 0 ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
              <p className="flex items-center gap-1.5 text-xs font-bold text-red-900">
                <AlertCircle className="h-4 w-4" aria-hidden="true" />
                <span>Sự cố đang chờ giáo viên xác minh ({snapshot.open_incidents.length})</span>
              </p>
              <div className="space-y-1.5">
                {snapshot.open_incidents.map((inc) => (
                  <div
                    key={inc.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded border border-red-200 bg-white px-3 py-2 text-xs"
                  >
                    <div>
                      <span className="font-mono-data font-bold text-slate-900">{inc.roster_code}</span>{" "}
                      <strong>{inc.full_name}</strong>: {inc.summary}
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleOpenTimeline(inc.attempt_id)}
                      className="rounded bg-[#1E3A5F] px-2.5 py-1 font-semibold text-white"
                    >
                      Mở xác minh
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {/* Live Monitoring Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Mã HS</th>
                  <th className="py-2 pr-4">Họ tên</th>
                  <th className="py-2 pr-4">Bài làm</th>
                  <th className="py-2 pr-4">Kết nối & Tín hiệu</th>
                  <th className="py-2 pr-4">Tiến độ đã lưu</th>
                  <th className="py-2 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rosterEntries.map((entry) => (
                  <tr key={entry.student_id}>
                    <td className="font-mono-data py-2.5 pr-4 font-medium">{entry.roster_code}</td>
                    <td className="py-2.5 pr-4">
                      <div>{entry.full_name}</div>
                      {entry.extra_time_s > 0 ? (
                        <span className="text-[11px] font-semibold text-[#0F766E]">
                          +{Math.round(entry.extra_time_s / 60)} phút gia hạn
                        </span>
                      ) : null}
                    </td>
                    <td className="py-2.5 pr-4">
                      {entry.attempt_state === "SUBMITTED" ? (
                        <StatusBadge tone="success" label="Đã nộp bài" />
                      ) : entry.attempt_state === "ENDED_WITH_REVIEW" ? (
                        <StatusBadge tone="neutral" label="Kết thúc sau xác minh" />
                      ) : entry.attempt_state === "LOCKED_PENDING_REVIEW" ? (
                        <StatusBadge
                          tone="danger"
                          label="Tạm khóa · Cần xác minh"
                          icon={<Lock className="h-3 w-3" aria-hidden="true" />}
                        />
                      ) : entry.attempt_state === "ACTIVE" ? (
                        <StatusBadge tone="info" label="Đang làm bài" />
                      ) : entry.attempt_state === "READY" ? (
                        <StatusBadge tone="success" label="Đã duyệt vào phòng" />
                      ) : entry.attempt_state === "PENDING_APPROVAL" ? (
                        <StatusBadge tone="warning" label="Chờ duyệt" />
                      ) : (
                        <StatusBadge tone="neutral" label="Chưa vào phòng" />
                      )}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {entry.attempt_id ? (
                          entry.presence_state === "ACTIVE" ? (
                            <StatusBadge
                              tone="success"
                              label={
                                entry.heartbeat_age_s !== null
                                  ? `Ổn định (${entry.heartbeat_age_s}s)`
                                  : "Ổn định"
                              }
                              icon={<Wifi className="h-3 w-3" aria-hidden="true" />}
                            />
                          ) : entry.presence_state === "SUSPECTED" ? (
                            <StatusBadge
                              tone="warning"
                              label={`Tín hiệu yếu (${entry.heartbeat_age_s ?? "?"}s)`}
                              icon={<WifiOff className="h-3 w-3" aria-hidden="true" />}
                            />
                          ) : entry.presence_state === "DISCONNECTED" ? (
                            <StatusBadge
                              tone="danger"
                              label={`Mất kết nối (${entry.heartbeat_age_s ?? "?"}s)`}
                              icon={<WifiOff className="h-3 w-3" aria-hidden="true" />}
                            />
                          ) : (
                            <StatusBadge tone="neutral" label="Chờ tín hiệu" />
                          )
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}

                        {entry.hidden_event_count > 0 ? (
                          <StatusBadge
                            tone="warning"
                            label={`Rời màn hình (${entry.hidden_event_count}) · Cần xác minh`}
                            icon={<Eye className="h-3 w-3" aria-hidden="true" />}
                          />
                        ) : null}
                      </div>
                    </td>
                    <td className="font-mono-data py-2.5 pr-4 text-xs text-slate-700">
                      {entry.attempt_id
                        ? `${entry.answered_count}/${activeRoom.question_count ?? 0} câu (Rev #${entry.latest_revision})`
                        : "—"}
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="inline-flex flex-wrap justify-end gap-1.5">
                        {entry.attempt_id && entry.attempt_state === "PENDING_APPROVAL" ? (
                          <button
                            type="button"
                            onClick={() => void handleApprove(entry.attempt_id!)}
                            className="inline-flex items-center gap-1 rounded bg-[#1E3A5F] px-2.5 py-1 text-xs font-semibold text-white"
                          >
                            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>Duyệt</span>
                          </button>
                        ) : null}
                        {entry.attempt_id && entry.attempt_state === "ACTIVE" ? (
                          <button
                            type="button"
                            onClick={() => void handleLockAttempt(entry.attempt_id!, entry.roster_code)}
                            className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900"
                          >
                            <Lock className="h-3 w-3" aria-hidden="true" />
                            <span>Khóa tạm</span>
                          </button>
                        ) : null}
                        {entry.attempt_id ? (
                          <button
                            type="button"
                            onClick={() => void handleOpenTimeline(entry.attempt_id!)}
                            className={`inline-flex items-center gap-1 rounded px-2.5 py-1 text-xs font-medium ${
                              entry.attempt_state === "LOCKED_PENDING_REVIEW" || entry.open_incident_id
                                ? "bg-red-700 text-white"
                                : "border border-slate-300 bg-white text-slate-700"
                            }`}
                          >
                            <span>
                              {entry.attempt_state === "LOCKED_PENDING_REVIEW" ? "Xử lý sự cố" : "Nhật ký"}
                            </span>
                          </button>
                        ) : null}
                        {entry.attempt_id && entry.device_bound ? (
                          <button
                            type="button"
                            onClick={() =>
                              void handleResetDevice(entry.attempt_id!, entry.full_name, entry.roster_code)
                            }
                            className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-50"
                          >
                            <RotateCcw className="h-3 w-3" aria-hidden="true" />
                            <span>Đổi máy</span>
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {/* Incident & Timeline Drawer Modal */}
      {drawerTimeline ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/50"
        >
          <div className="flex h-full w-full max-w-lg flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Hồ sơ sự cố & Nhật ký tín hiệu — {drawerTimeline.roster_code}
                </h3>
                <p className="text-xs text-slate-600">
                  {drawerTimeline.full_name} · Trạng thái: <strong>{drawerTimeline.attempt_state}</strong> (
                  Mất mạng/nối lại: {drawerTimeline.reconnect_count} · Rời tab: {drawerTimeline.hidden_event_count})
                </p>
              </div>
              <button
                type="button"
                aria-label="Đóng cửa sổ"
                onClick={() => setDrawerTimeline(null)}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              {drawerTimeline.incidents.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase text-slate-500">Sự cố đã ghi nhận</h4>
                  {drawerTimeline.incidents.map((inc) => (
                    <div
                      key={inc.id}
                      className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-semibold">
                        <span>{inc.trigger_type}</span>
                        <span className="font-mono-data">{inc.state}</span>
                      </div>
                      <p className="text-slate-700">{inc.summary}</p>
                      {inc.resolution_reason ? (
                        <p className="text-emerald-800">Xử lý: {inc.resolution_reason}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase text-slate-500">
                  Dòng thời gian tín hiệu (chỉ dùng xác minh kỹ thuật)
                </h4>
                {drawerTimeline.events.length === 0 ? (
                  <p className="text-xs text-slate-500">Chưa có sự kiện bất thường.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs">
                    {drawerTimeline.events.map((ev) => (
                      <li
                        key={ev.id}
                        className="flex items-start justify-between gap-2 rounded border border-slate-100 bg-slate-50 px-3 py-2"
                      >
                        <span className="font-mono-data font-semibold text-slate-800">{ev.event_type}</span>
                        <span className="font-mono-data text-slate-500">{ev.server_time}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {drawerTimeline.attempt_state !== "SUBMITTED" &&
              drawerTimeline.attempt_state !== "ENDED_WITH_REVIEW" ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                  <h4 className="text-xs font-bold uppercase text-slate-700">
                    Quyết định của giáo viên (bắt buộc nhập lý do & lưu audit)
                  </h4>
                  <div>
                    <label htmlFor="incident-reason" className="block text-xs text-slate-600">
                      Lý do xử lý
                    </label>
                    <input
                      id="incident-reason"
                      type="text"
                      value={resolutionReason}
                      onChange={(e) => setResolutionReason(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleResolveIncident("unlock")}
                      className="rounded-lg bg-[#0F766E] px-3 py-2 text-xs font-semibold text-white"
                    >
                      Mở lại làm bài
                    </button>
                    <div className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2">
                      <input
                        type="number"
                        min={1}
                        max={60}
                        value={extendMinutes}
                        onChange={(e) => setExtendMinutes(Math.max(1, Number(e.target.value)))}
                        className="font-mono-data w-12 py-1 text-xs text-center"
                        aria-label="Số phút gia hạn"
                      />
                      <button
                        type="button"
                        onClick={() => void handleResolveIncident("extend_time")}
                        className="py-1.5 pr-1 text-xs font-semibold text-[#1E3A5F]"
                      >
                        Gia hạn (+phút)
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleResolveIncident("terminate")}
                      className="rounded-lg bg-red-700 px-3 py-2 text-xs font-semibold text-white"
                    >
                      Kết thúc & Niêm phong
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
