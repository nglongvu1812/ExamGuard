import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  DatabaseBackup,
  FilePlus2,
  RefreshCw,
  ShieldAlert,
  Users,
  Wifi,
} from "lucide-react";
import type { HealthResponse, NetworkStatusResponse } from "../../api/client";

interface DashboardPageProps {
  health: HealthResponse | null;
  network: NetworkStatusResponse | null;
  networkError: string | null;
  onSelectIp: (ip: string) => void;
  onRefresh: () => void;
}

export function DashboardPage({
  health,
  network,
  networkError,
  onSelectIp,
  onRefresh,
}: DashboardPageProps) {
  const [copiedUrl, setCopiedUrl] = useState(false);

  const handleCopy = async () => {
    if (!network?.selected_url) return;
    try {
      await navigator.clipboard.writeText(network.selected_url);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch {
      // Clipboard might be restricted in plain HTTP LAN contexts
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Bảng điều khiển giáo viên
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Vận hành phòng thi LAN nội bộ không cần Internet. Mọi dữ liệu bài làm lưu tại máy chủ cục bộ.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            <span>Làm mới</span>
          </button>
          <Link
            to="/exams/new"
            className="inline-flex items-center gap-2 rounded-lg bg-[#1E3A5F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#162C49]"
          >
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            <span>Tạo bài kiểm tra</span>
          </Link>
        </div>
      </div>

      {/* Onboarding 3 steps for first-time teacher */}
      <section
        aria-label="Quy trình chuẩn bị phòng thi"
        className="rounded-xl border border-slate-200 bg-white p-5"
      >
        <h2 className="text-base font-semibold text-slate-900">
          Quy trình 3 bước tổ chức kiểm tra
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Link
            to="/classes"
            className="group flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50 p-4 transition-colors hover:border-[#1E3A5F] hover:bg-white"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-[#1E3A5F]">
                <Users className="h-4 w-4" aria-hidden="true" />
                <span>Bước 1: Nhập danh sách lớp</span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Nhập file Excel/CSV danh sách học sinh với mã học sinh cố định.
              </p>
            </div>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[#0F766E]">
              Quản lý lớp học <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          </Link>

          <Link
            to="/questions"
            className="group flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50 p-4 transition-colors hover:border-[#1E3A5F] hover:bg-white"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-[#1E3A5F]">
                <BookOpen className="h-4 w-4" aria-hidden="true" />
                <span>Bước 2: Nhập & duyệt đề thi</span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Chuyển đổi file Word/PDF, giữ nguyên hình ảnh và công thức toán học.
              </p>
            </div>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[#0F766E]">
              Mở ngân hàng đề <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          </Link>

          <Link
            to="/exams/new"
            className="group flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50 p-4 transition-colors hover:border-[#1E3A5F] hover:bg-white"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-[#1E3A5F]">
                <DatabaseBackup className="h-4 w-4" aria-hidden="true" />
                <span>Bước 3: Mở phòng & giám sát</span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Cấu hình thời gian, trộn đề, duyệt học sinh vào phòng qua mã QR LAN.
              </p>
            </div>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[#0F766E]">
              Cấu hình bài thi <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          </Link>
        </div>
      </section>

      {/* Live LAN QR & Server Status */}
      <div className="grid gap-6 lg:grid-cols-5">
        <section className="rounded-xl border border-slate-200 bg-white p-5 lg:col-span-3">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Wifi className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
              <span>Địa chỉ kết nối mạng LAN cho học sinh</span>
            </h2>
            <Link to="/lan-help" className="text-xs font-medium text-[#1E3A5F] hover:underline">
              Hướng dẫn khắc phục mạng
            </Link>
          </div>

          {networkError ? (
            <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-semibold">Không lấy được thông tin mạng LAN</p>
                <p className="mt-1 text-xs">{networkError}</p>
              </div>
            </div>
          ) : network ? (
            <div className="mt-4 space-y-4">
              {network.interfaces.length > 0 ? (
                <div>
                  <label
                    htmlFor="lan-interface-select"
                    className="block text-xs font-medium text-slate-700"
                  >
                    Chọn card mạng đang kết nối Wi-Fi/Router lớp học
                  </label>
                  <select
                    id="lan-interface-select"
                    value={
                      network.interfaces.find((i) => network.selected_url.includes(i.ip))?.ip ?? ""
                    }
                    onChange={(e) => onSelectIp(e.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    {network.interfaces.map((iface) => (
                      <option key={iface.ip} value={iface.ip}>
                        {iface.name} — {iface.ip} {iface.recommended ? "(Khuyên dùng)" : ""}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                  Chưa phát hiện địa chỉ LAN ngoài localhost. Hãy kết nối laptop vào Wi-Fi/Router lớp học.
                </p>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-xs text-slate-500">Đường dẫn học sinh truy cập trên điện thoại</p>
                  <p className="font-mono-data mt-0.5 text-sm font-semibold text-slate-900">
                    {network.selected_url}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  {copiedUrl ? "Đã sao chép" : "Sao chép link"}
                </button>
              </div>

              <ul className="space-y-1.5 text-xs text-slate-600">
                {network.firewall_guide.slice(0, 2).map((tip) => (
                  <li key={tip} className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#0F766E]" aria-hidden="true" />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Đang dò tìm địa chỉ mạng LAN...</p>
          )}
        </section>

        <section className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-5 text-center lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-900">Mã QR vào phòng thi</h2>
          <p className="mt-1 text-xs text-slate-500">Học sinh mở Camera quét mã (không cần Internet)</p>
          {network?.qr_svg ? (
            <div
              className="mt-4 flex h-48 w-48 items-center justify-center rounded-lg border border-slate-200 bg-white p-2 [&>svg]:h-full [&>svg]:w-full"
              dangerouslySetInnerHTML={{ __html: network.qr_svg }}
              aria-label={`Mã QR truy cập ${network.selected_url}`}
            />
          ) : (
            <div className="mt-4 flex h-48 w-48 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 text-xs text-slate-500">
              Chưa có mã QR
            </div>
          )}
          {health ? (
            <p className="font-mono-data mt-3 text-[11px] text-slate-500">
              Cổng phục vụ: {network?.port ?? 8000} · DB: {health.db_ok ? "Khỏe mạnh" : "Lỗi"}
            </p>
          ) : null}
        </section>
      </div>
    </div>
  );
}
