import { useCallback, useEffect, useState } from "react";
import { CheckCheck, RefreshCw, RotateCcw, ShieldCheck, Users } from "lucide-react";
import {
  roomApi,
  rosterApi,
  type ClassroomDTO,
  type IssuedInviteResponse,
  type RoomRosterEntryDTO,
  type RoomSummaryDTO,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

export function WaitingRoomPage() {
  const [classes, setClasses] = useState<ClassroomDTO[]>([]);
  const [rooms, setRooms] = useState<RoomSummaryDTO[]>([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [title, setTitle] = useState("Kiểm tra 15 phút");
  const [activeRoom, setActiveRoom] = useState<RoomSummaryDTO | null>(null);
  const [invites, setInvites] = useState<IssuedInviteResponse[]>([]);
  const [roster, setRoster] = useState<RoomRosterEntryDTO[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBase = useCallback(async () => {
    try {
      const [clsList, roomList] = await Promise.all([rosterApi.listClasses(), roomApi.listRooms()]);
      setClasses(clsList);
      setRooms(roomList);
      if (clsList.length > 0 && !selectedClassId) {
        setSelectedClassId(clsList[0]?.id ?? "");
      }
      if (roomList.length > 0 && !activeRoom) {
        setActiveRoom(roomList[0] ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu phòng chờ.");
    }
  }, [selectedClassId, activeRoom]);

  const loadRoster = useCallback(async (examId: string) => {
    try {
      const list = await roomApi.getRoomRoster(examId);
      setRoster(list);
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

  const handleOpenRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClassId) return;
    try {
      const res = await roomApi.createRoom(selectedClassId, title, 900);
      setActiveRoom(res.room);
      setInvites(res.invites);
      setNotice(`Đã mở phòng chờ ${res.room.room_code} và tạo ${res.invites.length} mã mời cá nhân.`);
      await loadBase();
      await loadRoster(res.room.exam_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể mở phòng chờ.");
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
          Phòng chờ & Duyệt học sinh vào thi
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Tạo mã phòng, phát mã mời cá nhân và xác nhận đúng học sinh trong lớp trước khi bắt đầu.
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

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Mở phòng chờ mới</h2>
        <form onSubmit={handleOpenRoom} className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="room-class" className="block text-xs font-medium text-slate-700">
              Lớp học
            </label>
            <select
              id="room-class"
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="mt-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.student_count} HS)
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="room-title" className="block text-xs font-medium text-slate-700">
              Tên bài kiểm tra
            </label>
            <input
              id="room-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={!selectedClassId}
            className="rounded-lg bg-[#1E3A5F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#162C49] disabled:opacity-50"
          >
            Tạo phòng chờ & mã mời
          </button>
        </form>

        {rooms.length > 0 ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-500">Phòng gần đây:</span>
            {rooms.slice(0, 5).map((r) => (
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
                {r.room_code} · {r.title}
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {invites.length > 0 ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-sm font-bold text-amber-950">
            Mã tham gia cá nhân vừa cấp cho phòng {activeRoom?.room_code} (Chỉ hiển thị một lần)
          </h2>
          <p className="mt-1 text-xs text-amber-800">
            Hệ thống chỉ lưu bản băm bảo mật trong cơ sở dữ liệu. Hãy lưu hoặc phát mã dưới đây cho học sinh.
          </p>
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
                  Phòng {activeRoom.room_code} — {activeRoom.title}
                </span>
              </h2>
            </div>
            <div className="flex items-center gap-2">
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
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white"
              >
                <CheckCheck className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Duyệt tất cả chờ</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Mã HS</th>
                  <th className="py-2 pr-4">Họ tên</th>
                  <th className="py-2 pr-4">Trạng thái</th>
                  <th className="py-2 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {roster.map((entry) => (
                  <tr key={entry.student_id}>
                    <td className="font-mono-data py-2.5 pr-4 font-medium">{entry.roster_code}</td>
                    <td className="py-2.5 pr-4">{entry.full_name}</td>
                    <td className="py-2.5 pr-4">
                      {entry.attempt_state === "READY" ? (
                        <StatusBadge tone="success" label="Đã duyệt vào phòng" />
                      ) : entry.attempt_state === "PENDING_APPROVAL" ? (
                        <StatusBadge tone="warning" label="Chờ giáo viên duyệt" />
                      ) : (
                        <StatusBadge tone="neutral" label="Chưa đăng nhập" />
                      )}
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
