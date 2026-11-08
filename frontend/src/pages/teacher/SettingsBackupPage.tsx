import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, DatabaseBackup, HardDrive, ShieldCheck } from "lucide-react";
import {
  backupApi,
  type BackupManifestDTO,
  type HealthResponse,
  type VerifyBackupResponse,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

interface SettingsBackupPageProps {
  health: HealthResponse | null;
}

export function SettingsBackupPage({ health }: SettingsBackupPageProps) {
  const [backups, setBackups] = useState<BackupManifestDTO[]>([]);
  const [creating, setCreating] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verifyReport, setVerifyReport] = useState<VerifyBackupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBackups = useCallback(async () => {
    try {
      const items = await backupApi.listBackups();
      setBackups(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách bản sao lưu.");
    }
  }, []);

  useEffect(() => {
    void loadBackups();
  }, [loadBackups]);

  const handleCreateBackup = async () => {
    try {
      setCreating(true);
      setError(null);
      const created = await backupApi.createBackup();
      setNotice(`Đã tạo bản sao lưu nhất quán "${created.location}" (SHA-256: ${created.sha256.slice(0, 12)}...).`);
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi khi tạo bản sao lưu.");
    } finally {
      setCreating(false);
    }
  };

  const handleVerifyDryRun = async (backupId: string) => {
    try {
      setVerifyingId(backupId);
      setError(null);
      const report = await backupApi.verifyBackupDryRun(backupId);
      setVerifyReport(report);
      setNotice(`Kiểm thử khôi phục (Dry-run) thành công cho "${report.archive_name}".`);
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kiểm thử khôi phục thất bại.");
    } finally {
      setVerifyingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Sao lưu, Khôi phục & Cài đặt hệ thống
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Tạo gói sao lưu đồng bộ SQLite + tệp đề gốc + hình ảnh kèm kiểm tra mã băm SHA-256.
          </p>
        </div>

        <button
          type="button"
          disabled={creating}
          onClick={() => void handleCreateBackup()}
          className="inline-flex items-center gap-2 rounded-lg bg-[#1E3A5F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#162C49] disabled:opacity-50"
        >
          <DatabaseBackup className="h-4 w-4" aria-hidden="true" />
          <span>{creating ? "Đang sao lưu..." : "Tạo bản sao lưu ngay"}</span>
        </button>
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

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-2">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <HardDrive className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
            <span>Trạng thái cơ sở dữ liệu cục bộ</span>
          </h2>
          <p className="text-xs text-slate-600">
            Chế độ ghi nhật ký:{" "}
            <strong className="font-mono-data uppercase">{health?.db_journal_mode ?? "WAL"}</strong> ·
            Thư mục dữ liệu:{" "}
            <strong>{health?.data_dir_writable ? "Có quyền ghi" : "Kiểm tra quyền"}</strong>
          </p>
          <p className="text-xs leading-relaxed text-slate-500">
            Lưu ý quyền riêng tư: Sao lưu chứa thông tin lớp học và bài làm của học sinh. Nên cất giữ bản sao lưu ở ổ đĩa riêng có kiểm soát.
          </p>
        </div>

        {verifyReport ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 space-y-2">
            <h2 className="flex items-center gap-2 text-base font-semibold text-emerald-950">
              <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
              <span>Kết quả kiểm thử khôi phục (Dry-run)</span>
            </h2>
            <p className="font-mono-data text-xs text-emerald-900">
              Tệp: {verifyReport.archive_name} · Schema: {verifyReport.schema_version}
            </p>
            <p className="text-xs text-emerald-800">
              SHA-256: {verifyReport.checksum_valid ? "Khớp 100%" : "Lỗi"} · SQLite quick_check:{" "}
              {verifyReport.sqlite_integrity_ok ? "OK" : "Lỗi"} · Kỳ thi:{" "}
              {verifyReport.record_counts.exams ?? 0} · Bài nộp:{" "}
              {verifyReport.record_counts.submissions ?? 0}
            </p>
          </div>
        ) : null}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Danh sách các bản sao lưu đã tạo</h2>
        {backups.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            Chưa có bản sao lưu nào. Hãy nhấn &quot;Tạo bản sao lưu ngay&quot; trước hoặc sau mỗi ca thi.
          </p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Tên tệp</th>
                  <th className="py-2 pr-4">Schema</th>
                  <th className="py-2 pr-4">Checksum SHA-256</th>
                  <th className="py-2 pr-4">Xác minh</th>
                  <th className="py-2 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {backups.map((b) => (
                  <tr key={b.id}>
                    <td className="font-mono-data py-2.5 pr-4 text-xs font-semibold text-slate-800">
                      {b.location}
                    </td>
                    <td className="font-mono-data py-2.5 pr-4 text-xs text-slate-600">
                      {b.schema_version}
                    </td>
                    <td className="font-mono-data py-2.5 pr-4 text-xs text-slate-500">
                      {b.sha256.slice(0, 16)}...
                    </td>
                    <td className="py-2.5 pr-4">
                      {b.verified_at ? (
                        <StatusBadge tone="success" label="Đã kiểm tra" />
                      ) : (
                        <StatusBadge tone="neutral" label="Chưa kiểm thử" />
                      )}
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        type="button"
                        disabled={verifyingId === b.id}
                        onClick={() => void handleVerifyDryRun(b.id)}
                        className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                        <span>{verifyingId === b.id ? "Đang kiểm..." : "Kiểm thử khôi phục"}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
