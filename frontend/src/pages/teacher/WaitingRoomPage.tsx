import { useCallback, useEffect, useState } from "react";
import {
  CheckCheck,
  Clock,
  PauseCircle,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Square,
  Users,
} from "lucide-react";
import {
  examApi,
  questionApi,
  roomApi,
  rosterApi,
  type ApprovedQuestionDTO,
  type ClassroomDTO,
  type IssuedInviteResponse,
  type RoomRosterEntryDTO,
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
  const [classes, setClasses] = useState<ClassroomDTO[]>([]);
  const [bankQuestions, setBankQuestions] = useState<ApprovedQuestionDTO[]>([]);
  const [rooms, setRooms] = useState<RoomSummaryDTO[]>([]);

  // 4-step exam wizard state
  const [selectedClassId, setSelectedClassId] = useState("");
  const [title, setTitle] = useState("Kiểm tra 15 phút");
  const [durationMin, setDurationMin] = useState(15);
  const [selectedQIds, setSelectedQIds] = useState<string[]>([]);
  const [shuffleQuestions, setShuffleQuestions] = useState(true);
  const [shuffleOptions, setShuffleOptions] = useState(true);

  const [activeRoom, setActiveRoom] = useState<RoomSummaryDTO | null>(null);
  const [invites, setInvites] = useState<IssuedInviteResponse[]>([]);
  const [roster, setRoster] = useState<RoomRosterEntryDTO[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBase = useCallback(async () => {
    try {
      const [clsList, bankList, roomList] = await Promise.all([
        rosterApi.listClasses(),
        questionApi.listBank(),
        roomApi.listRooms(),
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
      if (roomList.length > 0 && !activeRoom) {
        setActiveRoom(roomList[0] ?? null);
      } else if (activeRoom) {
        const refreshed = roomList.find((r) => r.exam_id === activeRoom.exam_id);
        if (refreshed) setActiveRoom(refreshed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu cấu hình phòng thi.");
    }
  }, [selectedClassId, activeRoom, selectedQIds.length]);

  const loadRoster = useCallback(async (examId: string) => {
    try {
      const [list, roomList] = await Promise.all([
        roomApi.getRoomRoster(examId),
        roomApi.listRooms(),
      ]);
      setRoster(list);
      setRooms(roomList);
      const updated = roomList.find((r) => r.exam_id === examId);
      if (updated) setActiveRoom(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được trạng thái thí sinh.");
    }
  }, []);

  useEffect(() => {
    void loadBase();
  }, [loadBase]);

  useEffect(() => {
    if (!activeRoom) return;
    void loadRoster(activeRoom.exam_id);
    const timer = setInterval(() => void loadRoster(activeRoom.exam_id), 3000);
    return () => clearInterval(timer);
  }, [activeRoom, loadRoster]);

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
      await loadRoster(res.exam.exam_id);
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
      await loadRoster(activeRoom.exam_id);
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
      await loadRoster(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tạm dừng.");
    }
  };

  const handleResumeExam = async () => {
    if (!activeRoom) return;
    try {
      await examApi.resumeExam(activeRoom.exam_id);
      setNotice("Đã tiếp tục bài thi và cộng bù thời gian tạm dừng.");
      await loadRoster(activeRoom.exam_id);
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
      await loadRoster(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể đóng phòng thi.");
    }
  };

  const handleApprove = async (attemptId: string) => {
    if (!activeRoom) return;
    try {
      await roomApi.approveAttempt(activeRoom.exam_id, attemptId);
      await loadRoster(activeRoom.exam_id);
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
      await loadRoster(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi duyệt hàng loạt.");
    }
  };

  const handleResetDevice = async (entry: RoomRosterEntryDTO) => {
    if (!activeRoom || !entry.attempt_id) return;
    const reason = window.prompt(
      `Nhập lý do đặt lại thiết bị cho ${entry.full_name} (${entry.roster_code}):`,
      "Đổi máy dự phòng do thiết bị cũ lỗi kết nối"
    );
    if (!reason || reason.trim().length < 3) return;
    try {
      await roomApi.resetDevice(activeRoom.exam_id, entry.attempt_id, reason.trim());
      setNotice(`Đã đặt lại thiết bị cho ${entry.roster_code} (đã ghi nhật ký kiểm tra).`);
      await loadRoster(activeRoom.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đặt lại được thiết bị.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Tạo bài kiểm tra & Điều hành phòng thi
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          4 bước nhanh: Chọn lớp · Chọn câu hỏi đã duyệt · Cấu hình thời gian/trộn đề · Mở phòng & Bắt đầu.
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Users className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
                <span>
                  Phòng {activeRoom.room_code} — {activeRoom.title} ({activeRoom.question_count ?? 0} câu)
                </span>
              </h2>
              <div className="mt-1 flex items-center gap-2 text-xs">
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
                  Còn lại: {formatClock(activeRoom.remaining_s ?? activeRoom.duration_s)}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void loadRoster(activeRoom.exam_id)}
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
                <button
                  type="button"
                  disabled={(activeRoom.question_count ?? 0) === 0}
                  onClick={() => void handleStartExam()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Bắt đầu làm bài</span>
                </button>
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
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Mã HS</th>
                  <th className="py-2 pr-4">Họ tên</th>
                  <th className="py-2 pr-4">Trạng thái</th>
                  <th className="py-2 pr-4">Tiến độ đã lưu</th>
                  <th className="py-2 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {roster.map((entry) => (
                  <tr key={entry.student_id}>
                    <td className="font-mono-data py-2.5 pr-4 font-medium">{entry.roster_code}</td>
                    <td className="py-2.5 pr-4">{entry.full_name}</td>
                    <td className="py-2.5 pr-4">
                      {entry.attempt_state === "SUBMITTED" ? (
                        <StatusBadge tone="success" label="Đã nộp bài" />
                      ) : entry.attempt_state === "ACTIVE" ? (
                        <StatusBadge tone="info" label="Đang làm bài" />
                      ) : entry.attempt_state === "READY" ? (
                        <StatusBadge tone="success" label="Đã duyệt vào phòng" />
                      ) : entry.attempt_state === "PENDING_APPROVAL" ? (
                        <StatusBadge tone="warning" label="Chờ giáo viên duyệt" />
                      ) : (
                        <StatusBadge tone="neutral" label="Chưa đăng nhập" />
                      )}
                    </td>
                    <td className="font-mono-data py-2.5 pr-4 text-xs text-slate-700">
                      {entry.attempt_id
                        ? `${entry.answered_count ?? 0}/${activeRoom.question_count ?? 0} câu (Rev #${entry.latest_revision ?? 0})`
                        : "—"}
                    </td>
                    <td className="py-2.5 text-right">
                      <div className="inline-flex gap-2">
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
                        {entry.attempt_id && entry.device_bound ? (
                          <button
                            type="button"
                            onClick={() => void handleResetDevice(entry)}
                            className="inline-flex items-center gap-1 rounded border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
                          >
                            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>Đặt lại thiết bị</span>
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
    </div>
  );
}
