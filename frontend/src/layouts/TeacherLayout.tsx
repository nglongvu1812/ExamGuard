import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  DatabaseBackup,
  FilePlus2,
  Home,
  Printer,
  ShieldCheck,
  Smartphone,
  Users,
  Wifi,
} from "lucide-react";
import type { HealthResponse } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";

interface TeacherLayoutProps {
  health: HealthResponse | null;
  healthError: string | null;
  children: ReactNode;
}

const NAV_ITEMS = [
  { to: "/", label: "Tổng quan", icon: Home, end: true },
  { to: "/classes", label: "Lớp học", icon: Users, end: false },
  { to: "/questions", label: "Ngân hàng đề", icon: BookOpen, end: false },
  { to: "/exams/new", label: "Tạo bài kiểm tra", icon: FilePlus2, end: false },
  { to: "/paper", label: "Đề giấy & OMR", icon: Printer, end: false },
  { to: "/results", label: "Lịch sử & Kết quả", icon: BarChart3, end: false },
  { to: "/settings", label: "Sao lưu / Cài đặt", icon: DatabaseBackup, end: false },
  { to: "/lan-help", label: "Trợ giúp LAN", icon: Wifi, end: false },
];

export function TeacherLayout({ health, healthError, children }: TeacherLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 lg:flex">
      <aside
        aria-label="Điều hướng giáo viên"
        className="w-full shrink-0 border-b border-slate-200 bg-white lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#1E3A5F] text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight text-slate-900">ExamGuard</p>
              <p className="text-xs text-slate-500">Phòng thi LAN nội bộ</p>
            </div>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto p-3 lg:flex-col">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[#1E3A5F] text-white"
                    : "text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden border-t border-slate-200 p-4 lg:block">
          <NavLink
            to="/join"
            className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            <Smartphone className="h-4 w-4" aria-hidden="true" />
            <span>Mở giao diện Học sinh</span>
          </NavLink>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {health ? (
              <>
                <StatusBadge
                  tone={health.status === "ok" ? "success" : "warning"}
                  label={health.status === "ok" ? "Máy chủ sẵn sàng" : "Cần kiểm tra DB"}
                  detail={`v${health.app_version}`}
                />
                <StatusBadge
                  tone="info"
                  label={`SQLite ${health.db_journal_mode.toUpperCase()}`}
                  detail="Offline LAN"
                />
              </>
            ) : healthError ? (
              <StatusBadge tone="danger" label="Mất kết nối máy chủ" detail={healthError} />
            ) : (
              <StatusBadge tone="neutral" label="Đang kiểm tra máy chủ..." />
            )}
          </div>
          <span className="font-mono-data text-xs text-slate-500">
            Classroom Mode · Không cần Internet
          </span>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
