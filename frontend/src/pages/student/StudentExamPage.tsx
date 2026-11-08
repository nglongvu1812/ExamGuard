import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  PauseCircle,
  Send,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import {
  studentExamApi,
  type StudentPaperResponse,
  type SubmitAttemptResponse,
} from "../../api/client";
import { RichContentBlocks } from "../../components/RichContentBlocks";
import { StatusBadge } from "../../components/StatusBadge";

interface PendingWriteItem {
  question_version_id: string;
  selected_option_ids: string[];
  idempotency_key: string;
  client_timestamp: string;
}

interface StudentExamPageProps {
  studentToken: string;
  attemptId: string;
  studentName: string;
  rosterCode: string;
  onSubmitted: () => void;
}

function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function StudentExamPage({
  studentToken,
  attemptId,
  studentName,
  rosterCode,
  onSubmitted,
}: StudentExamPageProps) {
  const pendingKey = `eg_pending_${attemptId}`;

  const [paper, setPaper] = useState<StudentPaperResponse | null>(null);
  const [selectedMap, setSelectedMap] = useState<Record<string, string[]>>({});
  const [pendingQueue, setPendingQueue] = useState<PendingWriteItem[]>(() => {
    try {
      const raw = window.localStorage.getItem(pendingKey);
      return raw ? (JSON.parse(raw) as PendingWriteItem[]) : [];
    } catch {
      return [];
    }
  });
  const [currentIdx, setCurrentIdx] = useState(0);
  const [remainingS, setRemainingS] = useState<number>(0);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [serverRev, setServerRev] = useState<number>(0);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "pending_offline">("idle");
  const [error, setError] = useState<string | null>(null);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittedInfo, setSubmittedInfo] = useState<SubmitAttemptResponse | null>(null);
  const flushingRef = useRef(false);

  const persistPending = useCallback(
    (items: PendingWriteItem[]) => {
      setPendingQueue(items);
      try {
        window.localStorage.setItem(pendingKey, JSON.stringify(items));
      } catch {
        // ignore storage quota errors cleanly
      }
    },
    [pendingKey]
  );

  // Initial load of exam paper (no keys in response!)
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await studentExamApi.getPaper(studentToken);
        if (cancelled) return;
        setPaper(res);
        setRemainingS(res.remaining_s);
        setIsPaused(res.is_paused);
        setServerRev(res.latest_revision);

        const initSelected: Record<string, string[]> = {};
        for (const [qvid, entry] of Object.entries(res.saved_answers)) {
          initSelected[qvid] = entry.selected_option_ids;
        }
        // Overlay any unsynced local pending selections
        for (const p of pendingQueue) {
          initSelected[p.question_version_id] = p.selected_option_ids;
        }
        setSelectedMap(initSelected);
        if (res.latest_revision > 0 && pendingQueue.length === 0) {
          setSaveState("saved");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Không thể tải đề thi.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentToken, attemptId]);

  // Flush pending offline writes sequentially using exact idempotency keys
  const flushPendingQueue = useCallback(async () => {
    if (flushingRef.current || pendingQueue.length === 0) return;
    flushingRef.current = true;
    try {
      setSaveState("saving");
      const remaining = [...pendingQueue];
      while (remaining.length > 0) {
        const item = remaining[0];
        if (!item) break;
        const ack = await studentExamApi.saveAnswer(studentToken, attemptId, item);
        setServerRev(ack.server_revision);
        remaining.shift();
        persistPending([...remaining]);
      }
      setSaveState("saved");
      setError(null);
    } catch (err) {
      setSaveState("pending_offline");
      setError(err instanceof Error ? err.message : "Mất kết nối — bài chọn được giữ tạm để đồng bộ lại.");
    } finally {
      flushingRef.current = false;
    }
  }, [attemptId, pendingQueue, persistPending, studentToken]);

  // Periodic canonical sync with server timer (every 4s) & pending queue flush
  useEffect(() => {
    if (submittedInfo) return;
    const syncTimer = setInterval(async () => {
      if (pendingQueue.length > 0) {
        await flushPendingQueue();
      }
      try {
        const sync = await studentExamApi.syncAttempt(studentToken, attemptId);
        setRemainingS(sync.remaining_s);
        setIsPaused(sync.is_paused);
        setServerRev(sync.latest_revision);
        if (sync.attempt_state === "SUBMITTED" && sync.submitted_at) {
          setSubmittedInfo({
            submission_id: "server-closed",
            attempt_id: attemptId,
            snapshot_hash: sync.snapshot_hash ?? "",
            submitted_at: sync.submitted_at,
            submission_mode: "server",
            already_submitted: true,
          });
          onSubmitted();
        }
      } catch {
        // Keep current countdown and mark connectivity warning cleanly
      }
    }, 4000);
    return () => clearInterval(syncTimer);
  }, [attemptId, flushPendingQueue, onSubmitted, pendingQueue.length, studentToken, submittedInfo]);

  // Smooth local 1s countdown between authoritative server syncs
  useEffect(() => {
    if (isPaused || submittedInfo || !paper) return;
    const t = setInterval(() => {
      setRemainingS((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(t);
  }, [isPaused, paper, submittedInfo]);

  const handleSelectOption = async (questionVersionId: string, optionId: string) => {
    if (isPaused || submittedInfo) return;
    setSelectedMap((prev) => ({ ...prev, [questionVersionId]: [optionId] }));

    const item: PendingWriteItem = {
      question_version_id: questionVersionId,
      selected_option_ids: [optionId],
      idempotency_key:
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      client_timestamp: new Date().toISOString(),
    };

    setSaveState("saving");
    try {
      const ack = await studentExamApi.saveAnswer(studentToken, attemptId, item);
      setServerRev(ack.server_revision);
      setSaveState(pendingQueue.length > 0 ? "pending_offline" : "saved");
      setError(null);
    } catch (err) {
      const nextQueue = [...pendingQueue, item];
      persistPending(nextQueue);
      setSaveState("pending_offline");
      setError(
        err instanceof Error
          ? `${err.message} — Đã lưu tạm cục bộ chờ đồng bộ.`
          : "Mất kết nối LAN — đáp án đang chờ đồng bộ."
      );
    }
  };

  const handleConfirmSubmit = async () => {
    try {
      setSubmitting(true);
      setError(null);
      if (pendingQueue.length > 0) {
        await flushPendingQueue();
      }
      const res = await studentExamApi.submitAttempt(studentToken, attemptId);
      setSubmittedInfo(res);
      setConfirmSubmitOpen(false);
      window.localStorage.removeItem(pendingKey);
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chưa nộp được bài. Vui lòng thử lại.");
    } finally {
      setSubmitting(false);
    }
  };

  const answeredCount = useMemo(() => {
    return Object.values(selectedMap).filter((arr) => arr.length > 0).length;
  }, [selectedMap]);

  if (submittedInfo) {
    return (
      <div className="mx-auto max-w-md px-4 py-8">
        <div className="rounded-xl border border-emerald-200 bg-white p-6 space-y-4 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" aria-hidden="true" />
          <h1 className="text-xl font-bold text-slate-900">Đã nộp bài thành công</h1>
          <p className="text-sm text-slate-600">
            Hệ thống đã niêm phong bài làm của <strong>{studentName}</strong> ({rosterCode}).
          </p>
          <div className="rounded-lg bg-slate-50 p-3 text-left text-xs text-slate-700 space-y-1">
            <p>
              <strong>Thời gian máy chủ ghi nhận:</strong>{" "}
              <span className="font-mono-data">{submittedInfo.submitted_at}</span>
            </p>
            <p className="break-all">
              <strong>Mã băm biên nhận bài làm:</strong>{" "}
              <span className="font-mono-data">{submittedInfo.snapshot_hash}</span>
            </p>
          </div>
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-900">
            Vui lòng giữ điện thoại trên bàn và chờ cả phòng kết thúc. Điểm số và đáp án chỉ công bố sau khi giáo viên rà soát và phê duyệt kết quả.
          </p>
        </div>
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="mx-auto max-w-md px-4 py-8 text-center text-sm text-slate-600">
        {error ? (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
            {error}
          </div>
        ) : (
          "Đang tải gói đề cá nhân từ máy chủ..."
        )}
      </div>
    );
  }

  const currentQ = paper.questions[currentIdx];

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      {/* Sticky server timer & save acknowledgement header */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white px-4 py-2.5 shadow-xs">
        <div className="mx-auto flex max-w-xl items-center justify-between gap-2">
          <div>
            <p className="text-xs font-bold text-slate-800 truncate max-w-[180px]">
              {paper.exam_title}
            </p>
            <p className="font-mono-data text-[11px] text-slate-500">
              {rosterCode} · {answeredCount}/{paper.questions.length} câu
            </p>
          </div>

          <div className="flex items-center gap-2">
            {saveState === "saving" ? (
              <StatusBadge tone="info" label="Đang lưu..." />
            ) : saveState === "pending_offline" || pendingQueue.length > 0 ? (
              <StatusBadge
                tone="warning"
                label={`Chờ đồng bộ (${pendingQueue.length})`}
                icon={<WifiOff className="h-3 w-3" aria-hidden="true" />}
              />
            ) : saveState === "saved" ? (
              <StatusBadge tone="success" label={`Đã lưu #${serverRev}`} />
            ) : (
              <StatusBadge tone="neutral" label="Sẵn sàng" />
            )}

            <div
              aria-label="Thời gian còn lại"
              className={`font-mono-data flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm font-bold ${
                remainingS <= 60 ? "bg-red-100 text-red-800" : "bg-slate-900 text-white"
              }`}
            >
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{formatClock(remainingS)}</span>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-xl px-4 py-4 space-y-4">
        {isPaused ? (
          <div
            role="status"
            className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
          >
            <PauseCircle className="h-5 w-5 shrink-0 text-amber-700" aria-hidden="true" />
            <div>
              <p className="font-semibold">Phòng thi đang tạm dừng</p>
              <p className="text-xs">Đồng hồ máy chủ đã tạm dừng. Chờ giáo viên cho phép tiếp tục.</p>
            </div>
          </div>
        ) : null}

        {error ? (
          <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        {/* Question quick navigator */}
        <div className="flex flex-wrap gap-1.5 rounded-xl border border-slate-200 bg-white p-3">
          {paper.questions.map((q, idx) => {
            const isAnswered = (selectedMap[q.question_version_id]?.length ?? 0) > 0;
            const isCurrent = idx === currentIdx;
            return (
              <button
                key={q.question_version_id}
                type="button"
                onClick={() => setCurrentIdx(idx)}
                className={`font-mono-data h-9 min-w-[36px] rounded-lg px-2 text-xs font-bold transition-colors ${
                  isCurrent
                    ? "bg-[#1E3A5F] text-white"
                    : isAnswered
                    ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {q.position}
              </button>
            );
          })}
        </div>

        {/* Active question card */}
        {currentQ ? (
          <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h2 className="text-sm font-bold text-[#1E3A5F]">Câu {currentQ.position}</h2>
              <span className="text-xs text-slate-400">Chọn 1 phương án đúng</span>
            </div>

            <div className="text-base">
              <RichContentBlocks blocks={currentQ.blocks} />
            </div>

            <div className="space-y-2.5 pt-1">
              {currentQ.options.map((opt) => {
                const isSelected = (selectedMap[currentQ.question_version_id] ?? []).includes(
                  opt.option_id
                );
                return (
                  <button
                    key={opt.option_id}
                    type="button"
                    disabled={isPaused}
                    onClick={() => void handleSelectOption(currentQ.question_version_id, opt.option_id)}
                    className={`flex min-h-[48px] w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors ${
                      isSelected
                        ? "border-[#1E3A5F] bg-blue-50 ring-1 ring-[#1E3A5F]"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    } disabled:opacity-60`}
                  >
                    <span
                      className={`font-mono-data mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                        isSelected ? "bg-[#1E3A5F] text-white" : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {opt.display_label}
                    </span>
                    <div className="min-w-0 flex-1 text-sm">
                      <RichContentBlocks blocks={opt.blocks} />
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        ) : null}

        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            disabled={currentIdx === 0}
            onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
            className="min-h-[44px] flex-1 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 disabled:opacity-40"
          >
            Câu trước
          </button>
          {currentIdx < paper.questions.length - 1 ? (
            <button
              type="button"
              onClick={() => setCurrentIdx((i) => Math.min(paper.questions.length - 1, i + 1))}
              className="min-h-[44px] flex-1 rounded-xl bg-[#0F766E] px-4 text-sm font-semibold text-white"
            >
              Câu tiếp theo
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmSubmitOpen(true)}
              className="min-h-[44px] flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-[#1E3A5F] px-4 text-sm font-semibold text-white"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              <span>Nộp bài ngay</span>
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => setConfirmSubmitOpen(true)}
          className="min-h-[44px] w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#1E3A5F] bg-white px-4 text-sm font-semibold text-[#1E3A5F]"
        >
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          <span>Hoàn thành & Nộp bài ({answeredCount}/{paper.questions.length})</span>
        </button>
      </main>

      {confirmSubmitOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
        >
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Xác nhận nộp bài?</h3>
            <p className="text-sm text-slate-600">
              Bạn đã chọn{" "}
              <strong>
                {answeredCount}/{paper.questions.length}
              </strong>{" "}
              câu hỏi. Sau khi nộp, bạn không thể thay đổi đáp án.
            </p>
            {pendingQueue.length > 0 ? (
              <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">
                Còn {pendingQueue.length} đáp án đang chờ đồng bộ — hệ thống sẽ đồng bộ trước khi khóa bài.
              </p>
            ) : null}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setConfirmSubmitOpen(false)}
                className="min-h-[44px] flex-1 rounded-lg border border-slate-300 text-sm font-semibold text-slate-700"
              >
                Quay lại làm tiếp
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => void handleConfirmSubmit()}
                className="min-h-[44px] flex-1 rounded-lg bg-[#1E3A5F] text-sm font-semibold text-white disabled:opacity-50"
              >
                {submitting ? "Đang nộp..." : "Xác nhận nộp"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
