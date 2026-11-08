import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, ShieldAlert, ShieldCheck, Smartphone } from "lucide-react";
import { authApi } from "../../api/client";

interface TeacherLoginPageProps {
  onLoginSuccess?: () => void;
}

export function TeacherLoginPage({ onLoginSuccess }: TeacherLoginPageProps) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim()) {
      setError("Vui lòng nhập mã PIN quản trị giáo viên.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await authApi.teacherLogin(pin.trim());
      if (onLoginSuccess) {
        onLoginSuccess();
      } else {
        navigate("/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-12 text-slate-100">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[#1E3A5F] shadow-lg ring-1 ring-white/10">
            <ShieldCheck className="h-9 w-9 text-blue-300" aria-hidden="true" />
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-white">
            ExamGuard — Quản trị Giáo viên
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Khu vực bảo mật dành riêng cho Giáo viên trên máy chủ phòng thi
          </p>
        </div>

        <div className="rounded-2xl border border-slate-700/60 bg-slate-800/90 p-6 shadow-xl backdrop-blur-sm sm:p-8">
          <form onSubmit={(e) => void handleLogin(e)} className="space-y-4">
            {error ? (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300"
              >
                <ShieldAlert className="h-4 w-4 shrink-0 text-red-400 mt-0.5" aria-hidden="true" />
                <span>{error}</span>
              </div>
            ) : null}

            <div>
              <label htmlFor="teacher-pin" className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Mã PIN Quản trị
              </label>
              <div className="relative mt-1.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <KeyRound className="h-4 w-4" aria-hidden="true" />
                </div>
                <input
                  id="teacher-pin"
                  type="password"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="Nhập mã PIN giáo viên..."
                  autoFocus
                  autoComplete="current-password"
                  className="block w-full rounded-lg border border-slate-600 bg-slate-900/80 py-2.5 pl-10 pr-3 font-mono text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <p className="mt-2 text-xs text-slate-400">
                Mã PIN ban đầu mặc định: <code className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-amber-300">123456</code> (có thể thay đổi trong phần Cài đặt).
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="inline-flex w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50"
            >
              {loading ? "Đang xác thực..." : "Mở Bàn làm việc Giáo viên"}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-700" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-slate-800 px-2 text-slate-400">Hoặc</span>
            </div>
          </div>

          <div className="text-center">
            <Link
              to="/join"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/60 px-3.5 py-2 text-xs font-medium text-slate-300 transition hover:bg-slate-700 hover:text-white"
            >
              <Smartphone className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <span>Chuyển sang Màn hình thi của Học sinh (/join)</span>
            </Link>
          </div>
        </div>

        <p className="text-center text-xs text-slate-500">
          ExamGuard LAN Offline-First • Hệ thống chỉ cho phép quản trị trên máy chủ cục bộ hoặc có mật khẩu xác thực.
        </p>
      </div>
    </div>
  );
}
