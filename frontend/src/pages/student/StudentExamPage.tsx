import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Lock,
  PauseCircle,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Wifi,
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
  examId?: string;
  initialAttemptState?: string;
  initialIncidentReason?: string | null;
  studentName: string;
  rosterCode: string;
  onTokenRefreshed?: (newToken: string) => void;
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
  examId,
  initialAttemptState = "ACTIVE",
  initialIncidentReason = null,
  studentName,
  rosterCode,
  onTokenRefreshed,
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
  const [attemptState, setAttemptState] = useState<string>(initialAttemptState);
  const [incidentReason, setIncidentReason] = useState<string | null>(initialIncidentReason);
  const [serverRev, setServerRev] = useState<number>(0);
  const [serverTimeUtc, setServerTimeUtc] = useState<string>("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "pending_offline">("idle");
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [hiddenReturnNotice, setHiddenReturnNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittedInfo, setSubmittedInfo] = useState<SubmitAttemptResponse | null>(null);

  const flushingRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffAttemptRef = useRef(0);

  const persistPending = useCallback(
    (items: PendingWriteItem[]) => {
      setPendingQueue(items);
      try {
        window.localStorage.setItem(pendingKey, JSON.stringify(items));
      } catch {
        // ignore storage quota cleanly
      }
    },
    [pendingKey]
  );

  // Sync canonical state (timer, lock status, answers)
  const syncNow = useCallback(async () => {
    try {
      const sync = await studentExamApi.syncAttempt(studentToken, attemptId);
      setRemainingS(sync.remaining_s);
      setIsPaused(sync.is_paused);
      setServerRev(sync.latest_revision);
      setServerTimeUtc(sync.server_time_utc);
      setAttemptState(sync.attempt_state);
      setIncidentReason(sync.incident_reason ?? null);
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
      setError(null);
    } catch (err) {
      setWsStatus("disconnected");
      setError(err instanceof Error ? err.message : "Mất kết nối LAN tạm thời.");
    }
  }, [attemptId, onSubmitted, studentToken]);

  // Initial load of exam paper if not locked/ended
  useEffect(() => {
    if (
      attemptState === "LOCKED_PENDING_REVIEW" ||
      attemptState === "ENDED_WITH_REVIEW" ||
      submittedInfo
    ) {
      void syncNow();
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const res = await studentExamApi.getPaper(studentToken);
        if (cancelled) return;
        setPaper(res);
        setRemainingS(res.remaining_s);
        setIsPaused(res.is_paused);
        setAttemptState(res.attempt_state);
        setServerRev(res.latest_revision);
        setServerTimeUtc(res.server_time_utc);

        const initSelected: Record<string, string[]> = {};
        for (const [qvid, entry] of Object.entries(res.saved_answers)) {
          initSelected[qvid] = entry.selected_option_ids;
        }
        for (const p of pendingQueue) {
          initSelected[p.question_version_id] = p.selected_option_ids;
        }
        setSelectedMap(initSelected);
        if (res.latest_revision > 0 && pendingQueue.length === 0) {
          setSaveState("saved");
        }
        setError(null);
      } catch (err) {
        if (!cancelled) {
          await syncNow();
          if (err instanceof Error) {
            setError(err.message);
          }
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentToken, attemptId, attemptState]);

  // Flush pending offline writes sequentially using exact idempotency keys
  const flushPendingQueue = useCallback(async () => {
    if (
      flushingRef.current ||
      pendingQueue.length === 0 ||
      attemptState === "LOCKED_PENDING_REVIEW" ||
      attemptState === "ENDED_WITH_REVIEW"
    ) {
      return;
    }
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
      setError(
        err instanceof Error
          ? err.message
          : "Mất kết nối LAN — đáp án chưa đồng bộ đang được giữ an toàn trên máy."
      );
    } finally {
      flushingRef.current = false;
    }
  }, [attemptId, attemptState, pendingQueue, persistPending, studentToken]);

  // Authenticated WebSocket + exponential backoff & jitter + server heartbeat
  const resolvedExamId = paper?.exam_id ?? examId;
  const heartbeatS = Math.max(2, paper?.heartbeat_s ?? 3);

  useEffect(() => {
    if (!resolvedExamId || submittedInfo || typeof WebSocket === "undefined") {
      return;
    }
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let hbTimer: ReturnType<typeof setInterval> | null = null;

    const connectWs = () => {
      if (stopped) return;
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      if (!host) {
        setWsStatus("disconnected");
        return;
      }
      setWsStatus("connecting");
      let ws: WebSocket;
      try {
        ws = new WebSocket(
          `${proto}//${host}/ws/v1/room/${encodeURIComponent(resolvedExamId)}?token=${encodeURIComponent(studentToken)}`
        );
      } catch {
        setWsStatus("disconnected");
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        backoffAttemptRef.current = 0;
        setWsStatus("connected");
        if (hbTimer) clearInterval(hbTimer);
        hbTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "heartbeat" }));
          }
        }, heartbeatS * 1000);
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
          if (msg.type === "welcome" || msg.type === "heartbeat_ack" || msg.type === "attempt_update") {
            if (typeof msg.remaining_s === "number") setRemainingS(msg.remaining_s);
            if (typeof msg.is_paused === "boolean") setIsPaused(msg.is_paused);
            if (typeof msg.server_time_utc === "string") setServerTimeUtc(msg.server_time_utc);
            if (typeof msg.attempt_state === "string") setAttemptState(msg.attempt_state);
            if (typeof msg.incident_reason === "string") {
              setIncidentReason(msg.incident_reason);
            } else if (msg.attempt_state === "ACTIVE") {
              setIncidentReason(null);
            }
          } else if (msg.type === "exam_state") {
            if (typeof msg.remaining_s === "number") setRemainingS(msg.remaining_s);
            if (typeof msg.is_paused === "boolean") setIsPaused(msg.is_paused);
            if (msg.exam_status === "CLOSED") {
              void syncNow();
            }
          } else if (msg.type === "session_revoked") {
            setError(
              typeof msg.reason === "string"
                ? msg.reason
                : "Phiên thiết bị đã được giáo viên đặt lại."
            );
            setWsStatus("disconnected");
          }
        } catch {
          // ignore malformed frames cleanly
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (hbTimer) {
          clearInterval(hbTimer);
          hbTimer = null;
        }
        if (stopped) return;
        setWsStatus("disconnected");
        const step = Math.min(4, backoffAttemptRef.current);
        backoffAttemptRef.current += 1;
        const delay = Math.min(10000, 1000 * 2 ** step) + Math.floor(Math.random() * 350);
        reconnectTimer = setTimeout(connectWs, delay);
      };

      ws.onerror = () => {
        setWsStatus("disconnected");
      };
    };

    connectWs();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (hbTimer) clearInterval(hbTimer);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [heartbeatS, resolvedExamId, studentToken, submittedInfo, syncNow]);

  // Capture non-punitive browser telemetry signals: visibilitychange, pagehide, network offline
  const emitClientSignal = useCallback(
    (eventType: "APP_HIDDEN" | "PAGE_UNLOADED" | "NETWORK_LOST" | "CLIENT_RELOAD", details: Record<string, unknown>) => {
      if (submittedInfo) return;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && eventType !== "PAGE_UNLOADED") {
        ws.send(JSON.stringify({ type: "client_event", event_type: eventType, details }));
        return;
      }
      void studentExamApi.sendClientEvent(studentToken, attemptId, eventType, details).catch(() => {
        // telemetry is best-effort and must never throw to crash student flow
      });
    },
    [attemptId, studentToken, submittedInfo]
  );

  useEffect(() => {
    if (submittedInfo) return;
    let hiddenAt: string | null = null;
    const onVisibility = () => {
      if (document.hidden) {
        hiddenAt = new Date().toLocaleTimeString("vi-VN", { hour12: false });
        emitClientSignal("APP_HIDDEN", { visibility_state: "hidden" });
      } else if (hiddenAt) {
        setHiddenReturnNotice(
          `Hệ thống đã ghi nhận tín hiệu rời màn hình làm bài lúc ${hiddenAt}. Tín hiệu này chỉ gửi giáo viên tham khảo và không tự động kết luận gian lận.`
        );
        hiddenAt = null;
      }
    };
    const onPageHide = () => {
      emitClientSignal("PAGE_UNLOADED", { persisted: false });
    };
    const onOffline = () => {
      setWsStatus("disconnected");
      emitClientSignal("NETWORK_LOST", { online: false });
    };
    const onOnline = () => {
      void flushPendingQueue();
      void syncNow();
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, [emitClientSignal, flushPendingQueue, submittedInfo, syncNow]);

  // Periodic canonical sync & token refresh fallback (every 4s)
  useEffect(() => {
    if (submittedInfo) return;
    const syncTimer = setInterval(async () => {
      if (pendingQueue.length > 0 && attemptState === "ACTIVE") {
        await flushPendingQueue();
      }
      await syncNow();
      if (wsStatus !== "connected") {
        void studentExamApi.sendHeartbeat(studentToken, attemptId).catch(() => {});
      }
    }, 4000);
    return () => clearInterval(syncTimer);
  }, [attemptId, attemptState, flushPendingQueue, pendingQueue.length, studentToken, submittedInfo, syncNow, wsStatus]);

  // Periodic silent token refresh every 30 minutes for long exams
  useEffect(() => {
    if (!onTokenRefreshed || submittedInfo) return;
    const refTimer = setInterval(async () => {
      try {
        const res = await studentExamApi.refreshToken(studentToken, attemptId);
        onTokenRefreshed(res.attempt_token);
      } catch {
        // keep current valid token until retry
      }
    }, 1_800_000);
    return () => clearInterval(refTimer);
  }, [attemptId, onTokenRefreshed, studentToken, submittedInfo]);

  // Smooth local 1s countdown between authoritative server syncs
  useEffect(() => {
    if (isPaused || submittedInfo || !paper || attemptState !== "ACTIVE") return;
    const t = setInterval(() => {
      setRemainingS((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(t);
  }, [attemptState, isPaused, paper, submittedInfo]);

  const handleSelectOption = async (questionVersionId: string, optionId: string) => {
    if (isPaused || submittedInfo || attemptState !== "ACTIVE") return;
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

  // S6: Submitted Waiting Screen (no early score/key!)
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

  // S5: Locked Pending Review / Terminated Screen
  if (attemptState === "LOCKED_PENDING_REVIEW" || attemptState === "ENDED_WITH_REVIEW") {
    const isEnded = attemptState === "ENDED_WITH_REVIEW";
    return (
      <div className="mx-auto max-w-md px-4 py-8">
        <div className="rounded-xl border border-amber-300 bg-white p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
              {isEnded ? (
                <ShieldAlert className="h-6 w-6" aria-hidden="true" />
              ) : (
                <Lock className="h-6 w-6" aria-hidden="true" />
              )}
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">
                {isEnded
                  ? "Phiên làm bài đã kết thúc sau xác minh"
                  : "Bài thi đang tạm khóa chờ giáo viên xác minh"}
              </h1>
              <p className="font-mono-data text-xs text-slate-500">
                {rosterCode} · {studentName}
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3.5 text-sm text-amber-950 space-y-1.5">
            <p className="font-semibold">Lý do kỹ thuật / quy trình:</p>
            <p className="text-xs leading-relaxed">
              {incidentReason ||
                (isEnded
                  ? "Giáo viên đã đóng phiên làm bài này và niêm phong các đáp án đã lưu."
                  : "Kết nối mạng mất quá ngưỡng quy định hoặc giáo viên cần kiểm tra kỹ thuật thiết bị.")}
            </p>
          </div>

          <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700 space-y-1">
            <p>
              <strong>Trạng thái lưu đáp án:</strong>{" "}
              {serverRev > 0
                ? `Máy chủ đã lưu an toàn đến lần sửa #${serverRev}.`
                : "Các đáp án đã có dấu 'Đã lưu' đều được bảo toàn trên máy chủ."}
            </p>
            {pendingQueue.length > 0 ? (
              <p className="text-amber-800 font-medium">
                Có {pendingQueue.length} lựa chọn chưa đồng bộ đang được giữ tạm trên máy và sẽ tiếp tục gửi nếu giáo viên mở lại.
              </p>
            ) : null}
            {serverTimeUtc ? (
              <p>
                <strong>Giờ máy chủ:</strong>{" "}
                <span className="font-mono-data">{serverTimeUtc}</span>
              </p>
            ) : null}
          </div>

          {!isEnded ? (
            <>
              <p className="text-xs leading-relaxed text-slate-600">
                Vui lòng <strong>không tắt trình duyệt</strong> và giơ tay báo giáo viên tại phòng thi để kiểm tra, mở lại hoặc gia hạn thời gian nếu do sự cố Wi-Fi.
              </p>
              <button
                type="button"
                onClick={() => void syncNow()}
                className="min-h-[44px] w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#1E3A5F] px-4 text-sm font-semibold text-white"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                <span>Kiểm tra trạng thái mở lại</span>
              </button>
            </>
          ) : null}
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
      {/* Sticky server timer, WS status & save acknowledgement header */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white px-4 py-2.5 shadow-xs">
        <div className="mx-auto flex max-w-xl items-center justify-between gap-2">
          <div>
            <p className="text-xs font-bold text-slate-800 truncate max-w-[160px]">
              {paper.exam_title}
            </p>
            <p className="font-mono-data text-[11px] text-slate-500">
              {rosterCode} · {answeredCount}/{paper.questions.length} câu
            </p>
          </div>

          <div className="flex items-center gap-1.5">
            {wsStatus === "connected" ? (
              <StatusBadge
                tone="success"
                label="LAN"
                icon={<Wifi className="h-3 w-3" aria-hidden="true" />}
              />
            ) : (
              <StatusBadge
                tone="warning"
                label="Kết nối lại"
                icon={<WifiOff className="h-3 w-3" aria-hidden="true" />}
              />
            )}

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
        {/* S5 Technical Offline / Pending Warning Banner */}
        {(wsStatus === "disconnected" || pendingQueue.length > 0) ? (
          <div
            role="status"
            className="rounded-xl border border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-950 space-y-2"
          >
            <div className="flex items-start gap-2">
              <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
              <p className="leading-relaxed">
                <strong>Mất kết nối hoặc tín hiệu yếu.</strong> Những đáp án có dấu{" "}
                <strong>Đã lưu</strong> đã được ghi nhận trên máy chủ; câu chưa đồng bộ đang được giữ tạm trên máy và cần chờ đồng bộ lại hoặc giáo viên xác nhận.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void flushPendingQueue();
                void syncNow();
              }}
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg border border-amber-400 bg-white px-3 text-xs font-semibold text-amber-900"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Thử kết nối & đồng bộ lại</span>
            </button>
          </div>
        ) : null}

        {hiddenReturnNotice ? (
          <div
            role="status"
            className="flex items-start justify-between gap-2 rounded-xl border border-slate-300 bg-white p-3 text-xs text-slate-700"
          >
            <p className="leading-relaxed">{hiddenReturnNotice}</p>
            <button
              type="button"
              onClick={() => setHiddenReturnNotice(null)}
              className="shrink-0 text-xs font-semibold text-[#1E3A5F]"
            >
              Đóng
            </button>
          </div>
        ) : null}

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
          <div
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800"
          >
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
