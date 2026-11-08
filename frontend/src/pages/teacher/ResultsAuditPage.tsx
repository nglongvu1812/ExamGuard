import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  Award,
  CheckCircle2,
  Download,
  FileCheck2,
  History,
  KeyRound,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  auditApi,
  examApi,
  resultsApi,
  type AuditVerifyResponse,
  type ExamDetailDTO,
  type StudentPhucKhaoTraceDTO,
  type TeacherResultsOverviewDTO,
} from "../../api/client";
import { RichContentBlocks } from "../../components/RichContentBlocks";
import { StatusBadge } from "../../components/StatusBadge";

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ResultsAuditPage() {
  const [searchParams] = useSearchParams();
  const initialExamId = searchParams.get("examId") ?? "";

  const [exams, setExams] = useState<ExamDetailDTO[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<string>(initialExamId);
  const [overview, setOverview] = useState<TeacherResultsOverviewDTO | null>(null);
  const [auditReport, setAuditReport] = useState<AuditVerifyResponse | null>(null);

  const [searchText, setSearchText] = useState("");
  const [showKeyEditor, setShowKeyEditor] = useState(false);
  const [editingKeys, setEditingKeys] = useState<Record<string, string[]>>({});
  const [regradeReason, setRegradeReason] = useState("");
  const [publishConfirmOpen, setPublishConfirmOpen] = useState(false);

  const [traceDrawer, setTraceDrawer] = useState<StudentPhucKhaoTraceDTO | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadExamsList = useCallback(async () => {
    try {
      const list = await examApi.listExams();
      setExams(list);
      if (!selectedExamId && list.length > 0) {
        const closedOrHigher =
          list.find((ex) =>
            ["CLOSED", "REVIEWED", "PUBLISHED"].includes(ex.status)
          ) ?? list[0];
        if (closedOrHigher) setSelectedExamId(closedOrHigher.exam_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách kỳ thi.");
    }
  }, [selectedExamId]);

  const loadExamOverview = useCallback(async (examId: string) => {
    if (!examId) return;
    try {
      setError(null);
      const data = await resultsApi.getExamResults(examId);
      setOverview(data);
      const keyMap: Record<string, string[]> = {};
      for (const q of data.questions) {
        keyMap[q.question_version_id] = [...q.correct_option_ids];
      }
      setEditingKeys(keyMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được kết quả kỳ thi.");
    }
  }, []);

  const loadAuditVerification = useCallback(async () => {
    try {
      const rep = await auditApi.verifyChain();
      setAuditReport(rep);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể kiểm tra chuỗi Audit.");
    }
  }, []);

  useEffect(() => {
    void loadExamsList();
    void loadAuditVerification();
  }, [loadExamsList, loadAuditVerification]);

  useEffect(() => {
    if (selectedExamId) {
      void loadExamOverview(selectedExamId);
    }
  }, [selectedExamId, loadExamOverview]);

  const filteredStudents = useMemo(() => {
    if (!overview) return [];
    const q = searchText.trim().toLowerCase();
    if (!q) return overview.students;
    return overview.students.filter(
      (s) =>
        s.roster_code.toLowerCase().includes(q) ||
        s.full_name.toLowerCase().includes(q)
    );
  }, [overview, searchText]);

  const handleRunInitialGrading = async () => {
    if (!selectedExamId) return;
    try {
      setBusy(true);
      setError(null);
      const res = await resultsApi.gradeOrRegrade(selectedExamId, {
        reason: "Chấm điểm tự động toàn bộ bài nộp",
      });
      setNotice(
        `Đã hoàn tất đợt chấm #${res.run_number} cho ${res.scored_count} bài nộp.`
      );
      await loadExamOverview(selectedExamId);
      await loadAuditVerification();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chấm điểm thất bại.");
    } finally {
      setBusy(false);
    }
  };

  const handleReviewConfirm = async () => {
    if (!selectedExamId) return;
    if (
      !window.confirm(
        "Xác nhận ĐÃ KIỂM TRA đáp án chuẩn và tình trạng bài nộp của toàn bộ học sinh (Chuyển sang REVIEWED)?"
      )
    ) {
      return;
    }
    try {
      setBusy(true);
      setError(null);
      await resultsApi.reviewExam(
        selectedExamId,
        "Giáo viên kiểm tra và xác nhận kết quả trước công bố"
      );
      setNotice("Đã chuyển trạng thái kỳ thi sang REVIEWED (Sẵn sàng công bố).");
      await loadExamsList();
      await loadExamOverview(selectedExamId);
      await loadAuditVerification();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể duyệt kết quả.");
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmPublish = async () => {
    if (!selectedExamId) return;
    try {
      setBusy(true);
      setError(null);
      const res = await resultsApi.publishExam(selectedExamId);
      setPublishConfirmOpen(false);
      setNotice(
        `Đã CÔNG BỐ điểm & đáp án (PUBLISHED) và phát hành ${res.receipts_issued} biên nhận cá nhân.`
      );
      await loadExamsList();
      await loadExamOverview(selectedExamId);
      await loadAuditVerification();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể công bố kết quả.");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmitRegradeWithKeys = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExamId || !overview) return;
    if (regradeReason.trim().length < 3) {
      setError("Bắt buộc nhập lý do sửa đáp án / chấm lại (tối thiểu 3 ký tự).");
      return;
    }
    const changedKeys: Record<string, string[]> = {};
    for (const q of overview.questions) {
      const edited = editingKeys[q.question_version_id] ?? [];
      const origSet = new Set(q.correct_option_ids);
      const same =
        edited.length === origSet.size && edited.every((id) => origSet.has(id));
      if (!same) {
        changedKeys[q.question_version_id] = edited;
      }
    }
    if (
      !window.confirm(
        overview.exam.status === "PUBLISHED"
          ? "Kỳ thi ĐÃ CÔNG BỐ. Chấm lại sẽ tạo ScoreVersion mới và phát hành ReceiptVersion thay thế biên nhận cũ cho học sinh. Tiếp tục?"
          : "Xác nhận chạy đợt chấm mới (ScoreVersion mới + lưu nhật ký kiểm toán)?"
      )
    ) {
      return;
    }
    try {
      setBusy(true);
      setError(null);
      const res = await resultsApi.gradeOrRegrade(selectedExamId, {
        reason: regradeReason.trim(),
        updated_keys: Object.keys(changedKeys).length > 0 ? changedKeys : undefined,
      });
      setRegradeReason("");
      setShowKeyEditor(false);
      setNotice(
        `Đã chấm lại (Lần #${res.run_number}) cho ${res.scored_count} bài nộp` +
          (res.receipts_updated > 0
            ? ` và cập nhật ${res.receipts_updated} biên nhận mới.`
            : ".")
      );
      await loadExamOverview(selectedExamId);
      await loadAuditVerification();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chấm lại thất bại.");
    } finally {
      setBusy(false);
    }
  };

  const handleExportXlsx = async () => {
    if (!selectedExamId) return;
    try {
      setBusy(true);
      const { blob, filename } = await resultsApi.downloadExcel(selectedExamId);
      triggerBrowserDownload(blob, filename ?? "bang_diem_examguard.xlsx");
      setNotice("Đã tải xuống bảng điểm Excel (có bảo vệ công thức CWE-1236).");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không xuất được file Excel.");
    } finally {
      setBusy(false);
    }
  };

  const handleOpenTrace = async (studentId: string) => {
    if (!selectedExamId) return;
    try {
      setError(null);
      const trace = await resultsApi.getStudentTrace(selectedExamId, studentId);
      setTraceDrawer(trace);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được hồ sơ phúc khảo.");
    }
  };

  const examInfo = overview?.exam;
  const stats = overview?.stats;
  const canGradeOrReview = examInfo?.status === "CLOSED";
  const canRegrade = examInfo ? ["CLOSED", "REVIEWED", "PUBLISHED"].includes(examInfo.status) : false;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Chấm điểm, Công bố Kết quả & Phúc khảo
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Kết quả chỉ hiển thị cho học sinh sau bước Duyệt (REVIEWED) và Công bố (PUBLISHED). Mọi lần chấm lại đều tạo phiên bản mới bất biến.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="select-result-exam" className="text-xs font-medium text-slate-600">
            Kỳ thi:
          </label>
          <select
            id="select-result-exam"
            value={selectedExamId}
            onChange={(e) => setSelectedExamId(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            {exams.length === 0 ? (
              <option value="">Chưa có kỳ thi nào</option>
            ) : (
              exams.map((ex) => (
                <option key={ex.exam_id} value={ex.exam_id}>
                  [{ex.room_code}] {ex.title} — {ex.status}
                </option>
              ))
            )}
          </select>
        </div>
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

      {overview && examInfo && stats ? (
        <>
          {/* T7 Review & Publish Workflow Gate Bar */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono-data rounded bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-700">
                    PHÒNG {examInfo.room_code}
                  </span>
                  <h2 className="text-lg font-bold text-slate-900">{examInfo.title}</h2>
                  <StatusBadge
                    tone={
                      examInfo.status === "PUBLISHED"
                        ? "success"
                        : examInfo.status === "REVIEWED"
                        ? "info"
                        : examInfo.status === "CLOSED"
                        ? "warning"
                        : "neutral"
                    }
                    label={
                      examInfo.status === "PUBLISHED"
                        ? "ĐÃ CÔNG BỐ (PUBLISHED)"
                        : examInfo.status === "REVIEWED"
                        ? "ĐÃ DUYỆT CHỜ CÔNG BỐ (REVIEWED)"
                        : examInfo.status === "CLOSED"
                        ? "ĐÃ ĐÓNG PHÒNG CHỜ DUYỆT (CLOSED)"
                        : examInfo.status
                    }
                  />
                </div>
                <p className="text-xs text-slate-600">
                  Lớp {examInfo.classroom_name} · {examInfo.question_count} câu hỏi ·{" "}
                  {overview.grade_runs.length > 0
                    ? `Đợt chấm gần nhất #${overview.grade_runs[0]?.run_number} (${overview.grade_runs[0]?.reason})`
                    : "Chưa chạy chấm điểm"}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {canGradeOrReview ? (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleRunInitialGrading()}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                    >
                      <Award className="h-4 w-4 text-[#1E3A5F]" aria-hidden="true" />
                      <span>Chạy chấm điểm</span>
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleReviewConfirm()}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A5F] px-4 py-2 text-xs font-semibold text-white hover:bg-[#162C49] disabled:opacity-50"
                    >
                      <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                      <span>Duyệt kết quả (REVIEWED)</span>
                    </button>
                  </>
                ) : null}

                {examInfo.status === "REVIEWED" ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setPublishConfirmOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#0F766E] px-4 py-2 text-xs font-semibold text-white hover:bg-[#0D625B] disabled:opacity-50"
                  >
                    <Send className="h-4 w-4" aria-hidden="true" />
                    <span>Công bố điểm & Đáp án (PUBLISHED)</span>
                  </button>
                ) : null}

                {canRegrade ? (
                  <button
                    type="button"
                    onClick={() => setShowKeyEditor((v) => !v)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2 text-xs font-semibold text-amber-900"
                  >
                    <KeyRound className="h-4 w-4" aria-hidden="true" />
                    <span>Đáp án chuẩn & Chấm lại</span>
                  </button>
                ) : null}

                <button
                  type="button"
                  disabled={busy || overview.grade_runs.length === 0}
                  onClick={() => void handleExportXlsx()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  <Download className="h-4 w-4 text-emerald-700" aria-hidden="true" />
                  <span>Tải Excel (.xlsx)</span>
                </button>
              </div>
            </div>

            {!["CLOSED", "REVIEWED", "PUBLISHED"].includes(examInfo.status) ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                Phòng thi hiện ở trạng thái <strong>{examInfo.status}</strong>. Vui lòng đóng phòng thu bài trước khi chấm điểm và công bố để đảm bảo không lộ đáp án sớm.
              </div>
            ) : null}

            {examInfo.unresolved_attempts > 0 ? (
              <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
                <span>
                  Có <strong>{examInfo.unresolved_attempts}</strong> học sinh có phiên làm bài nhưng chưa có bản nộp hoàn chỉnh (ví dụ kết thúc sau xác minh chưa có đáp án).
                </span>
              </div>
            ) : null}

            {/* Answer Key Review & Versioned Regrade Editor */}
            {showKeyEditor && canRegrade ? (
              <form
                onSubmit={handleSubmitRegradeWithKeys}
                className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 space-y-4"
              >
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Xác nhận / Điều chỉnh Đáp án chuẩn & Chấm lại toàn lớp
                  </h3>
                  <p className="text-xs text-slate-600">
                    Mọi thay đổi tạo phiên bản AnswerKeyVersion & ScoreVersion mới. Không ghi đè lịch sử cũ.
                  </p>
                </div>

                <div className="max-h-72 overflow-y-auto space-y-2.5 pr-1">
                  {overview.questions.map((q) => (
                    <div
                      key={q.question_version_id}
                      className="rounded-lg border border-slate-200 bg-white p-3 text-xs space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800">
                          Câu #{q.position} (Trọng số {q.weight} · Key v{q.key_version_number})
                        </span>
                        {q.key_history.length > 1 ? (
                          <span className="rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
                            Đã sửa key {q.key_history.length - 1} lần
                          </span>
                        ) : null}
                      </div>
                      <div className="text-slate-700">
                        <RichContentBlocks blocks={q.blocks} />
                      </div>
                      <div className="grid gap-1.5 sm:grid-cols-2">
                        {q.options.map((opt) => {
                          const selected = (
                            editingKeys[q.question_version_id] ?? []
                          ).includes(opt.option_id);
                          return (
                            <label
                              key={opt.option_id}
                              className={`flex items-center gap-2 rounded border px-2.5 py-1.5 cursor-pointer ${
                                selected
                                  ? "border-emerald-500 bg-emerald-50 text-emerald-950 font-semibold"
                                  : "border-slate-200 bg-slate-50 text-slate-700"
                              }`}
                            >
                              <input
                                type="radio"
                                name={`key-${q.question_version_id}`}
                                checked={selected}
                                onChange={() =>
                                  setEditingKeys((prev) => ({
                                    ...prev,
                                    [q.question_version_id]: [opt.option_id],
                                  }))
                                }
                              />
                              <span>
                                <strong>{opt.label}.</strong>{" "}
                                {opt.blocks.map((b) => b.text ?? b.latex ?? "[Ảnh]").join(" ")}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap items-end gap-3">
                  <div className="flex-1 min-w-[240px]">
                    <label htmlFor="regrade-reason" className="block text-xs font-semibold text-slate-800">
                      Lý do chấm lại / sửa đáp án (Bắt buộc, lưu vào Audit):
                    </label>
                    <input
                      id="regrade-reason"
                      type="text"
                      required
                      minLength={3}
                      placeholder="Ví dụ: Điều chỉnh đáp án câu 2 theo biên bản tổ bộ môn"
                      value={regradeReason}
                      onChange={(e) => setRegradeReason(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={busy}
                    className="rounded-lg bg-[#1E3A5F] px-4 py-2 text-xs font-semibold text-white hover:bg-[#162C49] disabled:opacity-50"
                  >
                    Lưu đáp án & Chấm lại ngay
                  </button>
                </div>
              </form>
            ) : null}
          </section>

          {/* Statistical Summary Cards */}
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Đã chấm / Sĩ số</p>
              <p className="font-mono-data mt-1 text-2xl font-bold text-slate-900">
                {stats.graded_count}/{stats.total_students}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Chưa nộp: {stats.unsubmitted_count}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Điểm trung bình</p>
              <p className="font-mono-data mt-1 text-2xl font-bold text-[#1E3A5F]">
                {stats.mean_score.toFixed(2)}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">Thang điểm 10</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Trung vị (Median)</p>
              <p className="font-mono-data mt-1 text-2xl font-bold text-slate-900">
                {stats.median_score.toFixed(2)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Cao nhất / Thấp nhất</p>
              <p className="font-mono-data mt-1 text-2xl font-bold text-[#0F766E]">
                {stats.max_score.toFixed(2)}{" "}
                <span className="text-base font-normal text-slate-400">
                  / {stats.min_score.toFixed(2)}
                </span>
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">Phổ điểm</p>
              <p className="font-mono-data mt-1 text-xs text-slate-700 leading-relaxed">
                Giỏi ≥8: <strong>{stats.bins.excellent}</strong> · Khá:{" "}
                <strong>{stats.bins.good}</strong>
                <br />
                TB: <strong>{stats.bins.average}</strong> · Yếu:{" "}
                <strong>{stats.bins.below_average}</strong>
              </p>
            </div>
          </section>

          {/* T8 Grade Table & Phúc khảo entry */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-slate-900">
                Bảng điểm chi tiết lớp học
              </h2>
              <div className="relative w-full max-w-xs">
                <Search
                  className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  type="text"
                  placeholder="Tìm mã HS hoặc họ tên..."
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-9 pr-3 text-sm"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <th className="py-2 pr-4">Mã HS</th>
                    <th className="py-2 pr-4">Họ tên</th>
                    <th className="py-2 pr-4">Trạng thái bài</th>
                    <th className="py-2 pr-4">Số câu đúng</th>
                    <th className="py-2 pr-4">Điểm (/10)</th>
                    <th className="py-2 pr-4">Phiên bản / Biên nhận</th>
                    <th className="py-2 text-right">Phúc khảo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredStudents.map((st) => (
                    <tr key={st.student_id}>
                      <td className="font-mono-data py-2.5 pr-4 font-semibold text-slate-900">
                        {st.roster_code}
                      </td>
                      <td className="py-2.5 pr-4">{st.full_name}</td>
                      <td className="py-2.5 pr-4 text-xs text-slate-700">{st.status_label}</td>
                      <td className="font-mono-data py-2.5 pr-4 text-xs">
                        {st.raw_correct !== null
                          ? `${st.raw_correct}/${st.total_questions}`
                          : "—"}
                      </td>
                      <td className="font-mono-data py-2.5 pr-4 font-bold text-[#1E3A5F]">
                        {st.score_10 !== null ? st.score_10.toFixed(2) : "—"}
                      </td>
                      <td className="font-mono-data py-2.5 pr-4 text-xs text-slate-600">
                        {st.score_version > 0 ? (
                          <span>
                            Điểm v{st.score_version}
                            {st.regrade_count > 0 ? ` (chấm lại ${st.regrade_count}x)` : ""}
                            {st.receipt_version > 0 ? ` · BN v${st.receipt_version}` : ""}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => void handleOpenTrace(st.student_id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          <History className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>Xem vết phúc khảo</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      {/* Audit Hash Chain Integrity Panel */}
      <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {auditReport?.valid ? (
              <ShieldCheck className="h-5 w-5 text-emerald-700" aria-hidden="true" />
            ) : (
              <ShieldAlert className="h-5 w-5 text-red-700" aria-hidden="true" />
            )}
            <h2 className="text-base font-semibold text-slate-900">
              Nhật ký Kiểm toán & Xác minh Chuỗi SHA-256
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {auditReport ? (
              <StatusBadge
                tone={auditReport.valid ? "success" : "danger"}
                label={
                  auditReport.valid
                    ? `Chuỗi Audit hợp lệ (${auditReport.event_count} sự kiện)`
                    : `Cảnh báo: Sai lệch tại sự kiện #${auditReport.broken_event_id}`
                }
              />
            ) : null}
            <button
              type="button"
              onClick={() => void loadAuditVerification()}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
            >
              Kiểm tra lại chuỗi
            </button>
          </div>
        </div>
        {auditReport ? (
          <>
            <p className="text-xs text-slate-500">{auditReport.limitation_note}</p>
            <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-3 space-y-1.5 text-xs">
              {auditReport.recent_events.slice(0, 12).map((ev) => (
                <div
                  key={ev.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 pb-1 last:border-none"
                >
                  <div>
                    <span className="font-mono-data font-bold text-slate-800">
                      #{ev.id} {ev.action}
                    </span>{" "}
                    <span className="text-slate-500">
                      ({ev.actor_type}:{ev.actor_id} → {ev.target_type})
                    </span>
                  </div>
                  <span className="font-mono-data text-[11px] text-slate-500">
                    {ev.event_hash.slice(0, 12)}… · {ev.created_at}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </section>

      {/* Irreversible Publish Confirmation Modal */}
      {publishConfirmOpen && examInfo ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Xác nhận Công bố Điểm & Đáp án?
            </h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              Khi chuyển phòng <strong>{examInfo.room_code}</strong> sang{" "}
              <strong>PUBLISHED</strong>, toàn bộ học sinh đã nộp bài sẽ xem được điểm số, biên nhận PDF/PNG và{" "}
              <strong>đáp án chuẩn chính thức</strong>. Thao tác tiết lộ đáp án không thể thu hồi lại trên trình duyệt đã xem.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPublishConfirmOpen(false)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleConfirmPublish()}
                className="rounded-lg bg-[#0F766E] px-4 py-2 text-xs font-semibold text-white"
              >
                {busy ? "Đang phát hành..." : "Xác nhận Công bố"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Phúc khảo Student Trace Drawer Modal */}
      {traceDrawer ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/50"
        >
          <div className="flex h-full w-full max-w-2xl flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Hồ sơ Phúc khảo — {traceDrawer.student.roster_code} ·{" "}
                  {traceDrawer.student.full_name}
                </h3>
                <p className="font-mono-data text-xs text-slate-500">
                  Seed trộn đề: {traceDrawer.permutation_seed ?? "—"} · Snapshot SHA-256:{" "}
                  {traceDrawer.submission?.snapshot_hash.slice(0, 20) ?? "Chưa nộp"}…
                </p>
              </div>
              <button
                type="button"
                aria-label="Đóng hồ sơ phúc khảo"
                onClick={() => setTraceDrawer(null)}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
              {/* Score & Receipt Versions */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                  <h4 className="font-bold uppercase text-slate-600">Lịch sử Điểm (ScoreVersions)</h4>
                  {traceDrawer.score_versions.length === 0 ? (
                    <p className="text-slate-500">Chưa có bản ghi điểm.</p>
                  ) : (
                    traceDrawer.score_versions.map((sv) => (
                      <div key={sv.id} className="rounded border border-slate-200 bg-white p-2">
                        <div className="flex justify-between font-semibold">
                          <span>
                            v{sv.version}: {sv.score_10.toFixed(2)}/10 ({sv.raw_correct}/
                            {sv.total_questions})
                          </span>
                          <span className={sv.is_current ? "text-emerald-700" : "text-slate-400"}>
                            {sv.is_current ? "Hiện hành" : "Đã thay thế"}
                          </span>
                        </div>
                        <p className="text-slate-600 mt-0.5">Lý do: {sv.reason}</p>
                      </div>
                    ))
                  )}
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                  <h4 className="font-bold uppercase text-slate-600">Biên nhận (ReceiptVersions)</h4>
                  {traceDrawer.receipt_versions.length === 0 ? (
                    <p className="text-slate-500">Chưa phát hành biên nhận.</p>
                  ) : (
                    traceDrawer.receipt_versions.map((rv) => (
                      <div key={rv.id} className="rounded border border-slate-200 bg-white p-2">
                        <div className="flex justify-between font-semibold">
                          <span className="font-mono-data">
                            {rv.receipt_code} (v{rv.version})
                          </span>
                          <span className={rv.is_current ? "text-emerald-700" : "text-slate-400"}>
                            {rv.is_current ? "Hiện hành" : "Hết hiệu lực"}
                          </span>
                        </div>
                        <p className="font-mono-data text-[11px] text-slate-500">
                          SHA-256: {rv.document_sha256.slice(0, 24)}…
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Per-question permutation & answer comparison */}
              <div className="space-y-2">
                <h4 className="font-bold uppercase text-slate-600">
                  Chi tiết bài làm theo đúng thứ tự đề học sinh đã thấy
                </h4>
                {traceDrawer.questions.map((q) => (
                  <div
                    key={q.question_version_id}
                    className={`rounded-lg border p-3 space-y-2 ${
                      q.is_correct
                        ? "border-emerald-200 bg-emerald-50/40"
                        : "border-red-200 bg-red-50/30"
                    }`}
                  >
                    <div className="flex items-center justify-between font-semibold">
                      <span>
                        Câu hiển thị #{q.seen_position} (Key v{q.key_version_number})
                      </span>
                      <StatusBadge
                        tone={q.is_correct ? "success" : "danger"}
                        label={q.is_correct ? "Đúng" : "Chưa đúng"}
                        icon={
                          q.is_correct ? (
                            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                          ) : undefined
                        }
                      />
                    </div>
                    <RichContentBlocks blocks={q.blocks} />
                    <div className="space-y-1">
                      {q.options.map((opt) => (
                        <div
                          key={opt.option_id}
                          className={`flex items-center justify-between rounded border px-2.5 py-1 ${
                            opt.is_correct_option && opt.selected
                              ? "border-emerald-400 bg-emerald-100/70"
                              : opt.is_correct_option
                              ? "border-emerald-300 bg-white"
                              : opt.selected
                              ? "border-red-300 bg-red-100/60"
                              : "border-slate-200 bg-white"
                          }`}
                        >
                          <span>
                            <strong>{opt.seen_label}.</strong>{" "}
                            <span className="text-slate-400">(Gốc {opt.original_label})</span>{" "}
                            {opt.blocks.map((b) => b.text ?? b.latex ?? "[Ảnh]").join(" ")}
                          </span>
                          <span className="font-semibold">
                            {opt.selected ? "HS chọn" : ""}{" "}
                            {opt.is_correct_option ? "· Đáp án chuẩn" : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Revisions & Telemetry */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5">
                <h4 className="font-bold uppercase text-slate-600">
                  Nhật ký lưu đáp án ({traceDrawer.answer_revisions.length} rev) & Tín hiệu kết nối ({traceDrawer.presence_events.length})
                </h4>
                {traceDrawer.incidents.map((inc) => (
                  <p key={inc.id} className="text-amber-900">
                    • Sự cố [{inc.state}] {inc.summary}
                    {inc.resolution_reason ? ` → Xử lý: ${inc.resolution_reason}` : ""}
                  </p>
                ))}
                {traceDrawer.answer_revisions.slice(-10).map((rev) => (
                  <p key={rev.revision} className="font-mono-data text-slate-600">
                    Rev #{rev.revision} ({rev.committed_at}) → [{rev.selected_option_ids.join(", ")}]
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
