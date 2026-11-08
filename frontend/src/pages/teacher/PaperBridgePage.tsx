import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Image as ImageIcon,
  Printer,
  ScanLine,
  ShieldCheck,
  Upload,
} from "lucide-react";
import {
  examApi,
  paperApi,
  rosterApi,
  type ExamDetailDTO,
  type OmrScanSubmissionDTO,
  type PaperVersionDTO,
  type StudentDTO,
} from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";

const OMR_ANSWERS = ["A", "B", "C", "D"] as const;

function triggerBlobDownload(blob: Blob, fallbackName: string, serverFilename: string | null) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = serverFilename ?? fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function describeOmrFlag(flag: string): string {
  if (flag === "FIDUCIAL_NOT_FOUND") {
    return "Không nhận diện đủ 4 góc định vị đen trên phiếu — vui lòng rà soát thủ công toàn bộ.";
  }
  if (flag.startsWith("HEADER_STUDENT")) {
    return "Chưa xác định chắc chắn học sinh từ ô SBD — vui lòng chọn đúng học sinh trong danh sách lớp.";
  }
  if (flag.startsWith("HEADER_VERSION")) {
    return "Mã đề trên phiếu chưa khớp hoặc mờ — vui lòng chọn đúng mã đề in.";
  }
  if (flag.endsWith("_AMBIGUOUS")) {
    return `${flag.replace("_AMBIGUOUS", "").replace("Q", "Câu ")}: Có dấu hiệu tô đúp hoặc chênh lệch đậm nhạt thấp.`;
  }
  if (flag.endsWith("_FAINT")) {
    return `${flag.replace("_FAINT", "").replace("Q", "Câu ")}: Nét tô nhạt, cần giáo viên xác nhận.`;
  }
  return flag;
}

export function PaperBridgePage() {
  const [exams, setExams] = useState<ExamDetailDTO[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<string>("");
  const [versions, setVersions] = useState<PaperVersionDTO[]>([]);
  const [scans, setScans] = useState<OmrScanSubmissionDTO[]>([]);
  const [students, setStudents] = useState<StudentDTO[]>([]);
  const [versionCount, setVersionCount] = useState<number>(4);

  const [activeScanId, setActiveScanId] = useState<string>("");
  const [showAlignedPreview, setShowAlignedPreview] = useState<boolean>(true);
  const [scanImageUrl, setScanImageUrl] = useState<string | null>(null);

  const [editStudentId, setEditStudentId] = useState<string>("");
  const [editVersionCode, setEditVersionCode] = useState<string>("");
  const [editAnswers, setEditAnswers] = useState<Record<string, string | null>>({});
  const [confirmReason, setConfirmReason] = useState<string>("Giáo viên kiểm tra và xác nhận phiếu OMR");

  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadExams = useCallback(async () => {
    try {
      const list = await examApi.listExams();
      setExams(list);
      const firstExam = list[0];
      if (!selectedExamId && firstExam) {
        setSelectedExamId(firstExam.exam_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được danh sách kỳ thi.");
    }
  }, [selectedExamId]);

  const loadExamPaperContext = useCallback(async (examId: string, classroomId: string) => {
    if (!examId) return;
    try {
      setError(null);
      const [verRes, scanList, clsStudents] = await Promise.all([
        paperApi.listVersions(examId),
        paperApi.listScans(examId),
        classroomId ? rosterApi.listStudents(classroomId) : Promise.resolve([]),
      ]);
      setVersions(verRes.versions);
      setScans(scanList);
      setStudents(clsStudents.filter((s) => !s.archived));
      const firstScan = scanList[0];
      if (firstScan && !scanList.some((s) => s.scan_id === activeScanId)) {
        setActiveScanId(firstScan.scan_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu đề giấy / OMR.");
    }
  }, [activeScanId]);

  useEffect(() => {
    void loadExams();
  }, [loadExams]);

  const selectedExam = exams.find((e) => e.exam_id === selectedExamId) ?? null;

  useEffect(() => {
    if (selectedExam) {
      void loadExamPaperContext(selectedExam.exam_id, selectedExam.classroom_id);
    }
  }, [selectedExam, loadExamPaperContext]);

  const activeScan = scans.find((s) => s.scan_id === activeScanId) ?? null;

  useEffect(() => {
    if (!activeScan) {
      setScanImageUrl(null);
      return;
    }
    setEditStudentId(activeScan.student_id ?? "");
    setEditVersionCode(activeScan.version_code ?? versions[0]?.version_code ?? "");
    setEditAnswers({ ...activeScan.confirmed_answers });
    setConfirmReason(activeScan.reason || "Giáo viên kiểm tra và xác nhận phiếu OMR");

    let cancelled = false;
    let createdUrl: string | null = null;
    void paperApi
      .fetchScanImage(activeScan.scan_id, showAlignedPreview)
      .then((blob) => {
        if (cancelled) return;
        createdUrl = URL.createObjectURL(blob);
        setScanImageUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return createdUrl;
        });
      })
      .catch(() => {
        if (!cancelled) setScanImageUrl(null);
      });

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [activeScan, showAlignedPreview, versions]);

  const handleGenerateVersions = async () => {
    if (!selectedExam) return;
    try {
      setBusy(true);
      setError(null);
      const res = await paperApi.generateVersions(selectedExam.exam_id, versionCount, 101);
      setVersions(res.versions);
      setNotice(`Đã tạo ${res.versions.length} mã đề giấy giữ nguyên khóa đáp án chuẩn.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể sinh mã đề giấy.");
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadBooklet = async () => {
    if (!selectedExam) return;
    try {
      setBusy(true);
      setError(null);
      const { blob, filename } = await paperApi.downloadBookletPdf(selectedExam.exam_id);
      triggerBlobDownload(blob, `DeGiay_${selectedExam.room_code}.pdf`, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải tệp PDF đề giấy.");
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadOmr = async (fmt: "pdf" | "png") => {
    if (!selectedExam) return;
    try {
      setBusy(true);
      setError(null);
      const { blob, filename } = await paperApi.downloadOmrSheet(selectedExam.exam_id, fmt);
      triggerBlobDownload(blob, `PhieuOMR_${selectedExam.room_code}.${fmt}`, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải phiếu OMR.");
    } finally {
      setBusy(false);
    }
  };

  const handleUploadScan = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedExam) return;
    try {
      setBusy(true);
      setError(null);
      const created = await paperApi.uploadScan(selectedExam.exam_id, file);
      setScans((prev) => [created, ...prev]);
      setActiveScanId(created.scan_id);
      setNotice(
        `Đã quét phiếu OMR (${created.ambiguous_flags.length > 0 ? "có mục cần rà soát" : "nhận diện rõ"}).`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi xử lý ảnh phiếu OMR.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  const handleConfirmScan = async () => {
    if (!activeScan || !selectedExam) return;
    if (!editStudentId) {
      setError("Vui lòng chọn học sinh tương ứng với phiếu OMR trước khi xác nhận.");
      return;
    }
    if (!editVersionCode) {
      setError("Vui lòng chọn Mã đề giấy trước khi xác nhận.");
      return;
    }
    try {
      setBusy(true);
      setError(null);
      const updated = await paperApi.confirmScan(activeScan.scan_id, {
        student_id: editStudentId,
        version_code: editVersionCode,
        confirmed_answers: editAnswers,
        reason: confirmReason,
      });
      setScans((prev) => prev.map((s) => (s.scan_id === updated.scan_id ? updated : s)));
      setNotice(
        updated.regraded
          ? `Đã xác nhận phiếu OMR của ${updated.student_name} và tự động đồng bộ vào Bảng điểm chung.`
          : `Đã lưu bài thi giấy của ${updated.student_name}. Khi đóng phòng và chấm điểm sẽ tự động gộp vào bảng điểm chung.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xác nhận phiếu OMR.");
    } finally {
      setBusy(false);
    }
  };

  const sortedQuestions = activeScan
    ? Object.keys(activeScan.detected_answers).sort((a, b) => Number(a) - Number(b))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Đề giấy, Mã đề & Chấm phiếu OMR offline
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            In đề giấy nhiều mã đề dùng chung ngân hàng câu hỏi, quét ảnh phiếu tô OMR và gộp trực tiếp vào bảng điểm chung.
          </p>
        </div>

        <select
          aria-label="Chọn kỳ thi dùng đề giấy / OMR"
          value={selectedExamId}
          onChange={(e) => setSelectedExamId(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
        >
          {exams.length === 0 ? <option value="">Chưa có kỳ thi nào</option> : null}
          {exams.map((ex) => (
            <option key={ex.exam_id} value={ex.exam_id}>
              {ex.title} ({ex.room_code} · {ex.status})
            </option>
          ))}
        </select>
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

      {selectedExam ? (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  1. Tạo bộ mã đề giấy & Phiếu OMR A4
                </h2>
                <p className="text-xs text-slate-500">
                  Các mã đề tái sử dụng thứ tự đảo xác định theo từng mã đề, đảm bảo đáp án chuẩn luôn khớp.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                  <span>Số mã đề:</span>
                  <input
                    type="number"
                    min={1}
                    max={16}
                    value={versionCount}
                    onChange={(e) => setVersionCount(Math.max(1, Math.min(16, Number(e.target.value) || 1)))}
                    className="w-16 rounded border border-slate-300 px-2 py-1 text-center text-xs"
                  />
                </label>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void handleGenerateVersions()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#1E3A5F] px-3.5 py-2 text-xs font-semibold text-white hover:bg-[#162C49]"
                >
                  <Printer className="h-4 w-4" aria-hidden="true" />
                  <span>Sinh mã đề (101..)</span>
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                disabled={busy || versions.length === 0}
                onClick={() => void handleDownloadBooklet()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50"
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                <span>Tải PDF Đề in + Bảng đáp án</span>
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleDownloadOmr("pdf")}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50"
              >
                <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
                <span>Tải Phiếu tô OMR (PDF A4)</span>
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void handleDownloadOmr("png")}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50"
              >
                <ImageIcon className="h-4 w-4" aria-hidden="true" />
                <span>Tải Phiếu mẫu PNG</span>
              </button>
            </div>

            {versions.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {versions.map((pv) => (
                  <div key={pv.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono-data text-sm font-bold text-[#1E3A5F]">
                        Mã đề {pv.version_code}
                      </span>
                      <StatusBadge tone="info" label={`${pv.question_count} câu`} />
                    </div>
                    <p className="mt-1.5 font-mono-data text-[11px] text-slate-600 line-clamp-2">
                      Đáp án:{" "}
                      {Object.keys(pv.answer_key_map)
                        .sort((a, b) => Number(a) - Number(b))
                        .map((k) => `${k}-${pv.answer_key_map[k]?.[0] ?? "?"}`)
                        .join(" ")}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Nhấn &quot;Sinh mã đề (101..)&quot; để khởi tạo các biến thể đề in chính thức.
              </p>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  2. Quét ảnh phiếu tô OMR & Rà soát thủ công trước khi chấm
                </h2>
                <p className="text-xs text-slate-500">
                  Ảnh chụp phiếu tô được lưu gốc nguyên vẹn (SHA-256). Mọi câu tô nhạt/tô đúp/thiếu góc đều yêu cầu giáo viên xác nhận.
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-[#0F766E] px-4 py-2 text-xs font-semibold text-white hover:bg-[#0D655E]">
                <Upload className="h-4 w-4" aria-hidden="true" />
                <span>Tải ảnh chụp / scan OMR</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/bmp"
                  onChange={handleUploadScan}
                  className="sr-only"
                />
              </label>
            </div>

            <div className="grid gap-6 lg:grid-cols-12">
              <div className="lg:col-span-4 space-y-2">
                <p className="text-xs font-semibold text-slate-700">
                  Danh sách phiếu đã tải lên ({scans.length})
                </p>
                <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
                  {scans.map((s) => (
                    <button
                      key={s.scan_id}
                      type="button"
                      onClick={() => setActiveScanId(s.scan_id)}
                      className={`w-full rounded-lg border p-3 text-left text-xs transition-colors ${
                        activeScanId === s.scan_id
                          ? "border-[#1E3A5F] bg-slate-50"
                          : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-slate-900">
                          {s.student_name ?? `SBD nhận diện: ${s.roster_code_detected || "?"}`}
                        </span>
                        <StatusBadge
                          tone={s.status === "CONFIRMED" ? "success" : "warning"}
                          label={s.status === "CONFIRMED" ? "Đã xác nhận" : "Cần rà soát"}
                        />
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-500">
                        <span>Mã đề: {s.version_code ?? s.version_code_detected ?? "?"}</span>
                        <span>· Độ tin cậy: {Math.round(s.overall_confidence * 100)}%</span>
                      </div>
                    </button>
                  ))}
                  {scans.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
                      <ScanLine className="mx-auto h-6 w-6 text-slate-400" aria-hidden="true" />
                      <p className="mt-2">Chưa có phiếu OMR nào được tải lên.</p>
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="lg:col-span-8">
                {activeScan ? (
                  <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    {activeScan.ambiguous_flags.length > 0 ? (
                      <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 space-y-1">
                        <div className="flex items-center gap-1.5 font-semibold">
                          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                          <span>Các điểm cần giáo viên xác nhận trước khi chốt điểm:</span>
                        </div>
                        <ul className="list-disc pl-5 space-y-0.5">
                          {activeScan.ambiguous_flags.map((f) => (
                            <li key={f}>{describeOmrFlag(f)}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-slate-700">Ảnh đối chiếu phiếu OMR</span>
                          <button
                            type="button"
                            onClick={() => setShowAlignedPreview((v) => !v)}
                            className="text-xs font-semibold text-[#1E3A5F] underline"
                          >
                            {showAlignedPreview ? "Xem ảnh gốc nguyên vẹn" : "Xem ảnh đã cân chỉnh góc"}
                          </button>
                        </div>
                        <div className="flex min-h-64 items-center justify-center rounded-lg border border-slate-200 bg-white p-2">
                          {scanImageUrl ? (
                            <img
                              src={scanImageUrl}
                              alt="Ảnh phiếu tô OMR"
                              className="max-h-96 w-auto rounded object-contain"
                            />
                          ) : (
                            <span className="text-xs text-slate-400">Đang tải ảnh phiếu...</span>
                          )}
                        </div>
                        <p className="font-mono-data text-[10px] text-slate-500 break-all">
                          SHA-256 gốc: {activeScan.source_sha256}
                        </p>
                      </div>

                      <div className="space-y-3">
                        <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-xs">
                          <label className="block space-y-1">
                            <span className="font-semibold text-slate-700">Học sinh trong lớp:</span>
                            <select
                              value={editStudentId}
                              onChange={(e) => setEditStudentId(e.target.value)}
                              className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs"
                            >
                              <option value="">-- Chọn học sinh --</option>
                              {students.map((st) => (
                                <option key={st.id} value={st.id}>
                                  {st.roster_code} — {st.full_name}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label className="block space-y-1">
                            <span className="font-semibold text-slate-700">Mã đề giấy:</span>
                            <select
                              value={editVersionCode}
                              onChange={(e) => setEditVersionCode(e.target.value)}
                              className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs"
                            >
                              <option value="">-- Chọn mã đề --</option>
                              {versions.map((pv) => (
                                <option key={pv.id} value={pv.version_code}>
                                  Mã đề {pv.version_code} ({pv.question_count} câu)
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>

                        <div className="max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 space-y-1.5">
                          <p className="text-xs font-semibold text-slate-700">
                            Đáp án nhận diện / Chỉnh tay:
                          </p>
                          {sortedQuestions.map((qKey) => {
                            const qDiag = activeScan.confidence.questions?.[qKey];
                            const qStatus = qDiag?.status ?? "BLANK";
                            const val = editAnswers[qKey] ?? null;
                            return (
                              <div
                                key={qKey}
                                className={`flex items-center justify-between rounded px-2 py-1 text-xs ${
                                  qStatus === "AMBIGUOUS" || qStatus === "FAINT"
                                    ? "bg-amber-50 border border-amber-200"
                                    : "bg-slate-50"
                                }`}
                              >
                                <span className="font-mono-data font-semibold text-slate-800 w-16">
                                  Câu {qKey}
                                </span>
                                <div className="flex items-center gap-1">
                                  {OMR_ANSWERS.map((lbl) => (
                                    <button
                                      key={lbl}
                                      type="button"
                                      onClick={() =>
                                        setEditAnswers((prev) => ({
                                          ...prev,
                                          [qKey]: prev[qKey] === lbl ? null : lbl,
                                        }))
                                      }
                                      className={`h-6 w-6 rounded-full text-[11px] font-bold ${
                                        val === lbl
                                          ? "bg-[#1E3A5F] text-white"
                                          : "border border-slate-300 bg-white text-slate-700"
                                      }`}
                                    >
                                      {lbl}
                                    </button>
                                  ))}
                                </div>
                                <span className="text-[10px] text-slate-500 w-20 text-right">
                                  {qStatus === "CONFIDENT" ? (
                                    <span className="inline-flex items-center gap-0.5 text-emerald-700">
                                      <CheckCircle2 className="h-3 w-3" /> Rõ
                                    </span>
                                  ) : qStatus === "BLANK" ? (
                                    "Bỏ trống"
                                  ) : (
                                    <span className="font-semibold text-amber-700">Cần xem</span>
                                  )}
                                </span>
                              </div>
                            );
                          })}
                        </div>

                        <label className="block space-y-1 text-xs">
                          <span className="font-semibold text-slate-700">
                            Lý do xác nhận / điều chỉnh (lưu vào dấu vết kiểm toán):
                          </span>
                          <input
                            type="text"
                            value={confirmReason}
                            onChange={(e) => setConfirmReason(e.target.value)}
                            className="w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                          />
                        </label>

                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleConfirmScan()}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#0F766E] px-4 py-2 text-xs font-semibold text-white hover:bg-[#0D655E] disabled:opacity-50"
                        >
                          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                          <span>Xác nhận & Chuyển vào Bảng điểm chung</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-xs text-slate-500">
                    Chọn một phiếu OMR bên trái hoặc tải ảnh phiếu mới lên để rà soát.
                  </div>
                )}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
