import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Image as ImageIcon,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { studentResultApi, type StudentPublishedResultDTO } from "../../api/client";
import { RichContentBlocks } from "../../components/RichContentBlocks";
import { StatusBadge } from "../../components/StatusBadge";

interface StudentResultPageProps {
  studentToken: string;
  onLeave: () => void;
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function StudentResultPage({ studentToken, onLeave }: StudentResultPageProps) {
  const [result, setResult] = useState<StudentPublishedResultDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<"pdf" | "png" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadResult = useCallback(async () => {
    try {
      setError(null);
      const data = await studentResultApi.getMyResult(studentToken);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Chưa thể tải kết quả công bố."
      );
    } finally {
      setLoading(false);
    }
  }, [studentToken]);

  useEffect(() => {
    void loadResult();
  }, [loadResult]);

  const handleDownloadPdf = async () => {
    try {
      setDownloading("pdf");
      setError(null);
      const { blob, filename } = await studentResultApi.downloadReceiptPdf(studentToken);
      triggerDownload(blob, filename ?? "bien_nhan_examguard.pdf");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được biên nhận PDF.");
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadSharePng = async () => {
    try {
      setDownloading("png");
      setError(null);
      const { blob, filename } = await studentResultApi.downloadShareCardPng(studentToken);
      triggerDownload(blob, filename ?? "the_chia_se_examguard.png");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được thẻ chia sẻ PNG.");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0F766E] text-white">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </div>
            <span className="text-sm font-bold text-slate-900">Kết quả đã công bố</span>
          </div>
          <button
            type="button"
            onClick={() => void loadResult()}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Cập nhật</span>
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl px-4 py-6 space-y-5">
        {error ? (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
            Đang tải kết quả và đáp án đã công bố...
          </div>
        ) : result ? (
          <>
            {result.superseded_previous ? (
              <div
                role="status"
                className="flex items-start gap-2.5 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
              >
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
                <div>
                  <p className="font-bold">
                    Có kết quả cập nhật (Biên nhận v{result.receipt_version})
                  </p>
                  <p className="mt-0.5 text-xs text-amber-900">
                    Điểm số hoặc đáp án chuẩn vừa được giáo viên chấm lại. Biên nhận cũ đã được thay thế bởi bản mới nhất này.
                    {result.regrade_reason ? ` Lý do: ${result.regrade_reason}` : ""}
                  </p>
                </div>
              </div>
            ) : null}

            <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-mono-data text-xs font-semibold text-slate-500">
                    PHÒNG {result.room_code} · {result.roster_code}
                  </p>
                  <h1 className="mt-1 text-xl font-bold text-slate-900">{result.student_name}</h1>
                  <p className="text-sm text-slate-600">{result.exam_title}</p>
                </div>

                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-right">
                  <p className="text-xs font-medium text-emerald-800">Điểm chính thức</p>
                  <p className="font-mono-data text-3xl font-extrabold text-[#0F766E]">
                    {result.score_10.toFixed(2)} <span className="text-base font-semibold">/ 10</span>
                  </p>
                  <p className="text-xs text-emerald-900">
                    Đúng {result.raw_correct}/{result.total_questions} câu
                  </p>
                </div>
              </div>

              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600 space-y-1">
                <p>
                  Mã biên nhận:{" "}
                  <span className="font-mono-data font-bold text-slate-900">
                    {result.receipt_code} (v{result.receipt_version})
                  </span>
                </p>
                <p className="font-mono-data break-all">
                  Mã băm đối chiếu (SHA-256): {result.document_sha256.slice(0, 32)}…
                </p>
              </div>

              <div className="grid gap-2.5 sm:grid-cols-2">
                <button
                  type="button"
                  disabled={downloading !== null}
                  onClick={() => void handleDownloadPdf()}
                  className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-[#1E3A5F] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#162C49] disabled:opacity-60"
                >
                  <Download className="h-4 w-4" aria-hidden="true" />
                  <span>
                    {downloading === "pdf" ? "Đang tạo PDF..." : "Tải biên nhận PDF"}
                  </span>
                </button>
                <button
                  type="button"
                  disabled={downloading !== null}
                  onClick={() => void handleDownloadSharePng()}
                  className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-60"
                >
                  <ImageIcon className="h-4 w-4 text-[#0F766E]" aria-hidden="true" />
                  <span>
                    {downloading === "png"
                      ? "Đang tạo ảnh..."
                      : "Tải thẻ chia sẻ PNG (ẩn thông tin nhạy cảm)"}
                  </span>
                </button>
              </div>
            </section>

            {/* Answer Breakdown Review */}
            <section className="space-y-3">
              <h2 className="text-base font-bold text-slate-900">
                Xem lại từng câu & Đáp án chuẩn
              </h2>
              {result.questions.map((q) => (
                <article
                  key={q.question_version_id}
                  className={`rounded-xl border bg-white p-4 space-y-3 ${
                    q.is_correct ? "border-emerald-200" : "border-red-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-slate-900">
                      Câu {q.position}
                    </span>
                    <StatusBadge
                      tone={q.is_correct ? "success" : "danger"}
                      label={q.is_correct ? "Trả lời đúng" : "Chưa chính xác"}
                      icon={
                        q.is_correct ? (
                          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                        ) : (
                          <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                        )
                      }
                    />
                  </div>

                  <div className="text-sm text-slate-800">
                    <RichContentBlocks blocks={q.blocks} />
                  </div>

                  <div className="space-y-1.5">
                    {q.options.map((opt) => {
                      const picked = q.selected_option_ids.includes(opt.option_id);
                      const isKey = q.correct_option_ids.includes(opt.option_id);
                      return (
                        <div
                          key={opt.option_id}
                          className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${
                            isKey && picked
                              ? "border-emerald-400 bg-emerald-50 text-emerald-950"
                              : isKey
                              ? "border-emerald-300 bg-emerald-50/50 text-emerald-900"
                              : picked
                              ? "border-red-300 bg-red-50 text-red-900"
                              : "border-slate-200 bg-white text-slate-700"
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <span className="font-mono-data font-bold">
                              {opt.display_label}.
                            </span>
                            <div>
                              <RichContentBlocks blocks={opt.blocks} />
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs font-semibold">
                            {picked ? (
                              <span className="rounded bg-slate-200 px-2 py-0.5 text-slate-800">
                                Bạn chọn
                              </span>
                            ) : null}
                            {isKey ? (
                              <span className="rounded bg-emerald-200 px-2 py-0.5 text-emerald-950">
                                Đáp án đúng
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </article>
              ))}
            </section>
          </>
        ) : null}

        <button
          type="button"
          onClick={onLeave}
          className="min-h-[44px] w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700"
        >
          Thoát về màn hình nhập mã
        </button>
      </main>
    </div>
  );
}
