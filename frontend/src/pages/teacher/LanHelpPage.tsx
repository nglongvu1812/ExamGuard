import { AlertCircle, CheckCircle2, Wifi } from "lucide-react";
import type { NetworkStatusResponse } from "../../api/client";

interface LanHelpPageProps {
  network: NetworkStatusResponse | null;
  onSelectIp: (ip: string) => void;
}

export function LanHelpPage({ network, onSelectIp }: LanHelpPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Trợ giúp kết nối mạng LAN & Firewall
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Hướng dẫn kiểm tra mạng nội bộ khi học sinh không truy cập được trang thi trên điện thoại.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <Wifi className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
          <span>Danh sách card mạng hiện có trên máy giáo viên</span>
        </h2>

        {network && network.interfaces.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Card mạng</th>
                  <th className="py-2 pr-4">Loại</th>
                  <th className="py-2 pr-4">Địa chỉ IP LAN</th>
                  <th className="py-2">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {network.interfaces.map((iface) => (
                  <tr key={iface.ip}>
                    <td className="py-2.5 pr-4 font-medium text-slate-900">{iface.name}</td>
                    <td className="py-2.5 pr-4 text-slate-600">{iface.kind}</td>
                    <td className="font-mono-data py-2.5 pr-4 text-slate-900">{iface.ip}</td>
                    <td className="py-2.5">
                      <button
                        type="button"
                        onClick={() => onSelectIp(iface.ip)}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Dùng địa chỉ này
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Không phát hiện card mạng LAN khả dụng. Kiểm tra Wi-Fi hoặc dây mạng trên laptop.</span>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">
          Danh sách kiểm tra khi học sinh không vào được phòng thi
        </h2>
        <ul className="mt-4 space-y-3 text-sm text-slate-700">
          {(network?.firewall_guide ?? []).map((step) => (
            <li key={step} className="flex items-start gap-2.5">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#0F766E]" aria-hidden="true" />
              <span>{step}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
