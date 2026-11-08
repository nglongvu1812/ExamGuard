import { useState } from "react";
import { ShieldCheck, Wifi, WifiOff } from "lucide-react";
import type { HealthResponse } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

interface StudentJoinShellProps {
  health: HealthResponse | null;
  healthError: string | null;
}

export function StudentJoinShell({ health, healthError }: StudentJoinShellProps) {
  const [roomCode, setRoomCode] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [inviteSecret, setInviteSecret] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!roomCode.trim() || !studentCode.trim()) {
      setNotice("Vui lòng nhập đầy đủ mã phòng và mã học sinh.");
      return;
    }
    setNotice(
      "Kết nối máy chủ LAN đã sẵn sàng. Luồng xác thực phòng thi & phê duyệt học sinh sẽ được kích hoạt ở Phase P1."
    );
  };

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
                placeholder="Ví dụ: 12A1-TOAN"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value)}
                className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base text-slate-900"
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
                className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base text-slate-900"
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
                placeholder="Mã 6 ký tự trên phiếu/màn hình"
                value={inviteSecret}
                onChange={(e) => setInviteSecret(e.target.value)}
                className="font-mono-data mt-1.5 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3.5 text-base text-slate-900"
              />
            </div>

            {notice ? (
              <div
                role="status"
                className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900"
              >
                {notice}
              </div>
            ) : null}

            <button
              type="submit"
              className="min-h-[48px] w-full rounded-lg bg-[#1E3A5F] px-4 py-3 text-base font-semibold text-white hover:bg-[#162C49]"
            >
              Gửi yêu cầu vào phòng
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-500">
          Hoạt động 100% trong mạng nội bộ lớp học · Không dùng dữ liệu di động
        </p>
      </main>
    </div>
  );
}
