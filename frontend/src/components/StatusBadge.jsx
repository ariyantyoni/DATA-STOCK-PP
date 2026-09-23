import { cn } from "@/lib/utils";

const MAP = {
  // stock
  AMAN: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  REORDER: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  CRITICAL: "bg-red-500/10 text-red-600 border-red-500/30",
  // needs
  CUKUP: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  PAS: "bg-sky-500/10 text-sky-600 border-sky-500/30",
  SHORTAGE: "bg-red-500/10 text-red-600 border-red-500/30",
  // variance
  OK: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  SURPLUS: "bg-sky-500/10 text-sky-600 border-sky-500/30",
  PASS: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  MINUS: "bg-red-500/10 text-red-600 border-red-500/30",
  OVER: "bg-orange-500/10 text-orange-600 border-orange-500/30",
  "BELUM DISET": "bg-slate-500/10 text-slate-600 border-slate-500/30",
  "BELUM DICEK": "bg-slate-500/10 text-slate-600 border-slate-500/30",
  "BELUM DIMAPPING": "bg-slate-500/10 text-slate-600 border-slate-500/30",
  ON: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  OFF: "bg-slate-500/10 text-slate-600 border-slate-500/30",
  "VARIANCE +": "bg-orange-500/10 text-orange-600 border-orange-500/30",
  "VARIANCE -": "bg-red-500/10 text-red-600 border-red-500/30",
  WIP: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  KOSONG: "bg-slate-500/10 text-slate-600 border-slate-500/30",
  // lamp
  SELESAI: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  PROSES: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  "BELUM MULAI": "bg-slate-500/10 text-slate-600 border-slate-500/30",
};

const DOT = {
  AMAN: "bg-emerald-500", CUKUP: "bg-emerald-500", OK: "bg-emerald-500", SELESAI: "bg-emerald-500",
  REORDER: "bg-amber-500 pulse-dot", PAS: "bg-sky-500", PROSES: "bg-amber-500 pulse-dot", SURPLUS: "bg-sky-500",
  WIP: "bg-amber-500", KOSONG: "bg-slate-500", PASS: "bg-emerald-500", MINUS: "bg-red-500", OVER: "bg-orange-500", ON: "bg-emerald-500", OFF: "bg-slate-500", "VARIANCE +": "bg-orange-500", "VARIANCE -": "bg-red-500",
  CRITICAL: "bg-red-500 pulse-dot", SHORTAGE: "bg-red-500 pulse-dot", "BELUM MULAI": "bg-slate-500",
};

export function StatusBadge({ status, testId }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-mono-data font-medium tracking-wide",
        MAP[status] || "bg-slate-500/10 text-slate-600 border-slate-500/30"
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", DOT[status] || "bg-slate-500")} />
      {status}
    </span>
  );
}
