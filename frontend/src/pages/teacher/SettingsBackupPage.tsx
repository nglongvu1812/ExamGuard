import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, DatabaseBackup, HardDrive, KeyRound, Lock, ShieldCheck } from "lucide-react";
import {
  authApi,
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

  // Teacher PIN Change State
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [pinLoading, setPinLoading] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);
  const [pinNotice, setPinNotice] = useState<string | null>(null);

  const handleChangePin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPin.trim() || !newPin.trim()) {
      setPinError("Vui lòng điền đầy đủ mã PIN hiện tại và mã PIN mới.");
      return;
    }
    if (newPin.trim().length < 4) {
      setPinError("Mã PIN mới phải có ít nhất 4 ký tự.");
      return;
    }
    if (newPin !== confirmPin) {
      setPinError("Mã PIN mới và xác nhận mã PIN không khớp nhau.");
      return;
    }

    setPinLoading(true);
    setPinError(null);
    setPinNotice(null);
    try {
      const res = await authApi.changeTeacherPin(currentPin.trim(), newPin.trim());
      setPinNotice(res.message);
      setCurrentPin("");
      setNewPin("");
      setConfirmPin("");
    } catch (err) {
      setPinError(err instanceof Error ? err.message : "Đổi mã PIN thất bại.");
    } finally {
      setPinLoading(false);
    }
  };

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

      {/* Teacher PIN Security Card */}
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-[#1E3A5F]">
            <KeyRound className="h-4 w-4" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">Bảo mật Quản trị & Đổi mã PIN Giáo viên</h2>
            <p className="text-xs text-slate-500">
              Mã PIN dùng để đăng nhập vào Bàn làm việc Giáo viên, ngăn chặn các thiết bị khác xâm nhập trái phép.
            </p>
          </div>
        </div>

        <form onSubmit={(e) => void handleChangePin(e)} className="mt-4 max-w-xl space-y-4">
          {pinError ? (
            <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              {pinError}
            </div>
          ) : null}

          {pinNotice ? (
            <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
              {pinNotice}
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label htmlFor="current-pin" className="block text-xs font-medium text-slate-700">
                Mã PIN hiện tại
              </label>
              <input
                id="current-pin"
                type="password"
                value={currentPin}
                onChange={(e) => setCurrentPin(e.target.value)}
                placeholder="Mặc định: 123456"
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="new-pin" className="block text-xs font-medium text-slate-700">
                Mã PIN mới
              </label>
              <input
                id="new-pin"
                type="password"
                value={newPin}
                onChange={(e) => setNewPin(e.target.value)}
                placeholder="Tối thiểu 4 ký tự"
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="confirm-pin" className="block text-xs font-medium text-slate-700">
                Xác nhận PIN mới
              </label>
              <input
                id="confirm-pin"
                type="password"
                value={confirmPin}
                onChange={(e) => setConfirmPin(e.target.value)}
                placeholder="Nhập lại mã PIN mới"
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-slate-500">
              Mã PIN ban đầu mặc định là <code className="font-mono text-amber-700 font-semibold">123456</code>
            </span>
            <button
              type="submit"
              disabled={pinLoading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A5F] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#162a45] disabled:opacity-50"
            >
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{pinLoading ? "Đang lưu..." : "Cập nhật mã PIN"}</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
