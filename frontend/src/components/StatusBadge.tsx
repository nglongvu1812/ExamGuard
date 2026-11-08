import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, WifiOff } from "lucide-react";

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

interface StatusBadgeProps {
  tone: BadgeTone;
  label: string;
  detail?: string;
  icon?: ReactNode;
}

const TONE_STYLES: Record<BadgeTone, string> = {
  success: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger: "bg-red-50 text-red-800 border-red-200",
  info: "bg-sky-50 text-sky-800 border-sky-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
};

export function StatusBadge({ tone, label, detail, icon }: StatusBadgeProps) {
  const defaultIcon =
    tone === "success" ? (
      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    ) : tone === "warning" ? (
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    ) : tone === "danger" ? (
      <WifiOff className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    ) : (
      <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    );

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${TONE_STYLES[tone]}`}
    >
      {icon ?? defaultIcon}
      <span>{label}</span>
      {detail ? <span className="text-[11px] opacity-80">· {detail}</span> : null}
    </span>
  );
}
