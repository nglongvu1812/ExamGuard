import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BookOpen, CheckCircle2, FileUp, ShieldCheck } from "lucide-react";
import {
  questionApi,
  type ApprovedQuestionDTO,
  type ImportJobResponse,
  type QuestionDraftDTO,
} from "../../api/client";
import { RichContentBlocks } from "../../components/RichContentBlocks";
import { StatusBadge } from "../../components/StatusBadge";

const WARNING_LABELS: Record<string, string> = {
  ANSWER_NOT_FOUND: "Chưa tìm thấy đáp án đúng — giáo viên cần chọn",
  MULTIPLE_KEYS_DETECTED: "Nhiều phương án được đánh dấu — cần xác minh",
  INSUFFICIENT_OPTIONS: "Thiếu phương án trả lời (< 2 phương án)",
  EMPTY_QUESTION_BODY: "Thiếu nội dung câu hỏi",
  MATH_FALLBACK_IMAGE: "Công thức dạng ảnh cũ/MathType",
  MATH_PARSE_WARNING: "Cần rà soát lại hiển thị công thức OMML",
  EXTERNAL_IMAGE_BLOCKED: "Đã chặn ảnh liên kết ngoài Internet",
  MISSING_IMAGE_BINARY: "Thiếu tệp ảnh bên trong file Word",
};

export function QuestionBankPage() {
  const [tab, setTab] = useState<"review" | "bank">("review");
  const [job, setJob] = useState<ImportJobResponse | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<string>("");
  const [bank, setBank] = useState<ApprovedQuestionDTO[]>([]);
  const [bankName, setBankName] = useState("Ngân hàng chung");
  const [editingStem, setEditingStem] = useState(false);
  const [stemTextEdit, setStemTextEdit] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadBank = useCallback(async () => {
    try {
      const items = await questionApi.listBank();
      setBank(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được ngân hàng đề.");
    }
  }, []);

  useEffect(() => {
    void loadBank();
  }, [loadBank]);

  const handleUploadDocx = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setUploading(true);
      setError(null);
      const imported = await questionApi.importDocx(file);
      setJob(imported);
      setSelectedDraftId(imported.drafts[0]?.id ?? "");
      setNotice(
        `Đã phân tích ${imported.summary.total_questions} câu hỏi từ "${imported.summary.filename}".`
      );
      setTab("review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi import đề thi.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const selectedDraft: QuestionDraftDTO | undefined = job?.drafts.find(
    (d) => d.id === selectedDraftId
  );

  const handleSetCorrectOption = async (draft: QuestionDraftDTO, optionId: string) => {
    try {
      const updated = await questionApi.updateDraft(draft.id, {
        correct_option_ids: [optionId],
      });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              drafts: prev.drafts.map((d) => (d.id === updated.id ? updated : d)),
            }
          : prev
      );
      setNotice(`Đã chọn đáp án đúng cho Câu ${draft.position}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể cập nhật đáp án.");
    }
  };

  const handleOpenStemEdit = (draft: QuestionDraftDTO) => {
    const firstText = draft.blocks.find((b) => b.type === "text")?.text ?? "";
    setStemTextEdit(firstText);
    setEditingStem(true);
  };

  const handleSaveStemEdit = async (draft: QuestionDraftDTO) => {
    try {
      const nonTextBlocks = draft.blocks.filter((b) => b.type !== "text");
      const updatedBlocks = [
        ...(stemTextEdit.trim() ? [{ type: "text", text: stemTextEdit.trim() }] : []),
        ...nonTextBlocks,
      ];
      const updated = await questionApi.updateDraft(draft.id, { blocks: updatedBlocks });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              drafts: prev.drafts.map((d) => (d.id === updated.id ? updated : d)),
            }
          : prev
      );
      setEditingStem(false);
      setNotice(`Đã lưu chỉnh sửa nội dung Câu ${draft.position}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể cập nhật nội dung câu hỏi.");
    }
  };

  const handleApproveOne = async (draft: QuestionDraftDTO) => {
    try {
      await questionApi.approveDraft(draft.id, bankName);
      if (job) {
        const refreshed = await questionApi.getImportJob(job.job_id);
        setJob(refreshed);
      }
      await loadBank();
      setNotice(`Đã duyệt Câu ${draft.position} vào ngân hàng đề.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa đủ điều kiện duyệt câu hỏi.");
    }
  };

  const handleApproveAllReady = async () => {
    if (!job) return;
    try {
      const res = await questionApi.approveReadyInJob(job.job_id, bankName);
      const refreshed = await questionApi.getImportJob(job.job_id);
      setJob(refreshed);
      await loadBank();
      setNotice(
        `Đã duyệt ${res.approved_count} câu hợp lệ. Bỏ qua ${res.skipped_count} câu còn thiếu đáp án/lỗi.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi khi duyệt hàng loạt.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Ngân hàng đề & Trình chuyển đổi Word (.docx)
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Giữ nguyên hình ảnh, bảng biểu và công thức toán OMML. Giáo viên rà soát và duyệt trước khi thi.
          </p>
        </div>

        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-[#1E3A5F] px-4 py-2 text-sm font-semibold text-white hover:bg-[#162C49]">
          <FileUp className="h-4 w-4" aria-hidden="true" />
          <span>{uploading ? "Đang chuyển đổi..." : "Tải đề Word (.docx)"}</span>
          <input type="file" accept=".docx" onChange={handleUploadDocx} className="sr-only" />
        </label>
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

      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab("review")}
          className={`border-b-2 px-4 py-2 text-sm font-semibold ${
            tab === "review"
              ? "border-[#1E3A5F] text-[#1E3A5F]"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Rà soát file vừa nhập ({job?.drafts.length ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setTab("bank")}
          className={`border-b-2 px-4 py-2 text-sm font-semibold ${
            tab === "bank"
              ? "border-[#1E3A5F] text-[#1E3A5F]"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Ngân hàng câu hỏi đã duyệt ({bank.length})
        </button>
      </div>

      {tab === "review" ? (
        !job ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <BookOpen className="mx-auto h-10 w-10 text-slate-400" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-slate-700">
              Chưa có tệp đề nào đang rà soát
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Nhấn nút &quot;Tải đề Word (.docx)&quot; phía trên để trích xuất câu hỏi và kiểm tra đối chiếu.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <span className="font-semibold text-slate-800">{job.summary.filename}</span>
                <StatusBadge tone="info" label={`Tổng: ${job.summary.total_questions} câu`} />
                <StatusBadge
                  tone={job.summary.unknown_key_count > 0 ? "warning" : "success"}
                  label={`Thiếu đáp án: ${job.summary.unknown_key_count}`}
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="Tên bộ đề"
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs"
                />
                <button
                  type="button"
                  onClick={() => void handleApproveAllReady()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-3.5 py-1.5 text-xs font-semibold text-white"
                >
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Duyệt nhanh các câu hợp lệ</span>
                </button>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-12">
              {/* Draft list */}
              <div className="max-h-[600px] space-y-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3 lg:col-span-4">
                {job.drafts.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setSelectedDraftId(d.id)}
                    className={`w-full rounded-lg border p-3 text-left text-xs transition-colors ${
                      selectedDraftId === d.id
                        ? "border-[#1E3A5F] bg-slate-50"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">Câu {d.position}</span>
                      {d.status === "APPROVED" ? (
                        <StatusBadge tone="success" label="Đã duyệt" />
                      ) : d.answer.correct_option_ids.length === 0 ? (
                        <StatusBadge tone="warning" label="Thiếu key" />
                      ) : d.warnings.length > 0 ? (
                        <StatusBadge tone="warning" label="Cần xem" />
                      ) : (
                        <StatusBadge tone="info" label="Sẵn sàng" />
                      )}
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-slate-600">
                      {d.blocks.map((b) => b.text ?? b.latex ?? "[Hình ảnh]").join(" ")}
                    </p>
                  </button>
                ))}
              </div>

              {/* Split view: Source Provenance vs Mobile Rendered Preview */}
              {selectedDraft ? (
                <div className="grid gap-4 lg:col-span-8 md:grid-cols-2">
                  {/* Left: Original source preview + warnings */}
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                    <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">
                      Đối chiếu từ file gốc ({selectedDraft.source.anchors.join(", ")})
                    </h2>
                    <pre className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-3 text-xs leading-relaxed text-slate-700">
                      {selectedDraft.source.raw_preview || "(Không có văn bản thô)"}
                    </pre>
                    {selectedDraft.warnings.length > 0 ? (
                      <div className="space-y-1.5">
                        <p className="text-xs font-semibold text-amber-800">Cảnh báo cần kiểm tra:</p>
                        {selectedDraft.warnings.map((w) => (
                          <div
                            key={w}
                            className="flex items-start gap-1.5 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900"
                          >
                            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            <span>{WARNING_LABELS[w] ?? w}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  {/* Right: Rendered Student Mobile Preview & Key confirmation */}
                  <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <h2 className="text-xs font-bold uppercase tracking-wide text-[#0F766E]">
                        Hiển thị trên điện thoại học sinh
                      </h2>
                      {selectedDraft.status !== "APPROVED" ? (
                        <button
                          type="button"
                          onClick={() => void handleApproveOne(selectedDraft)}
                          className="inline-flex items-center gap-1 rounded bg-[#1E3A5F] px-3 py-1 text-xs font-semibold text-white"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>Duyệt câu này</span>
                        </button>
                      ) : null}
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                      <div className="mb-1 flex items-center justify-between">
                        <p className="text-xs font-bold text-[#1E3A5F]">Câu {selectedDraft.position}</p>
                        {selectedDraft.status !== "APPROVED" ? (
                          <button
                            type="button"
                            onClick={() =>
                              editingStem ? setEditingStem(false) : handleOpenStemEdit(selectedDraft)
                            }
                            className="text-xs font-semibold text-[#1E3A5F] underline"
                          >
                            {editingStem ? "Hủy sửa" : "Sửa nội dung"}
                          </button>
                        ) : null}
                      </div>
                      {editingStem ? (
                        <div className="space-y-2">
                          <textarea
                            rows={3}
                            value={stemTextEdit}
                            onChange={(e) => setStemTextEdit(e.target.value)}
                            className="w-full rounded border border-slate-300 bg-white p-2 text-xs"
                          />
                          <button
                            type="button"
                            onClick={() => void handleSaveStemEdit(selectedDraft)}
                            className="rounded bg-[#0F766E] px-3 py-1 text-xs font-semibold text-white"
                          >
                            Lưu nội dung
                          </button>
                        </div>
                      ) : (
                        <RichContentBlocks blocks={selectedDraft.blocks} />
                      )}
                    </div>

                    <div className="space-y-2">
                      <p className="text-xs font-semibold text-slate-700">
                        Chọn phương án đúng (nhấn để xác nhận):
                      </p>
                      {selectedDraft.options.map((opt) => {
                        const isSelected = selectedDraft.answer.correct_option_ids.includes(
                          opt.option_id
                        );
                        return (
                          <button
                            key={opt.option_id}
                            type="button"
                            disabled={selectedDraft.status === "APPROVED"}
                            onClick={() => void handleSetCorrectOption(selectedDraft, opt.option_id)}
                            className={`flex w-full items-start gap-2.5 rounded-lg border p-2.5 text-left text-sm ${
                              isSelected
                                ? "border-emerald-500 bg-emerald-50"
                                : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                          >
                            <span
                              className={`font-mono-data mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                                isSelected
                                  ? "bg-emerald-600 text-white"
                                  : "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {opt.label}
                            </span>
                            <div className="min-w-0 flex-1">
                              <RichContentBlocks blocks={opt.blocks} />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )
      ) : (
        <div className="space-y-3">
          {bank.map((q, idx) => (
            <div key={q.version_id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span className="font-semibold text-[#1E3A5F]">
                  Câu #{idx + 1} · Bộ đề: {q.bank_name}
                </span>
                <span className="font-mono-data">v{q.version_number} · Bất biến</span>
              </div>
              <div className="mt-2 text-sm">
                <RichContentBlocks blocks={q.blocks} />
              </div>
            </div>
          ))}
          {bank.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
              Ngân hàng đề chưa có câu hỏi nào được duyệt.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
