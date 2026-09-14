import { cn } from "@/lib/utils";

const MAP = {
  // stock
  AMAN: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  REORDER: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  CRITICAL: "bg-red-500/10 text-red-400 border-red-500/30",
  // needs
  CUKUP: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  PAS: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  SHORTAGE: "bg-red-500/10 text-red-400 border-red-500/30",
  // variance
  OK: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  SURPLUS: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  // lamp
  SELESAI: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  PROSES: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  "BELUM MULAI": "bg-slate-500/10 text-slate-400 border-slate-500/30",
};

const DOT = {
  AMAN: "bg-emerald-400", CUKUP: "bg-emerald-400", OK: "bg-emerald-400", SELESAI: "bg-emerald-400",
  REORDER: "bg-amber-400 pulse-dot", PAS: "bg-sky-400", PROSES: "bg-amber-400 pulse-dot", SURPLUS: "bg-sky-400",
  CRITICAL: "bg-red-400 pulse-dot", SHORTAGE: "bg-red-400 pulse-dot", "BELUM MULAI": "bg-slate-400",
};

export function StatusBadge({ status, testId }) {
  if (!status) return <span className="text-muted-foreground">-</span>;
  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs font-mono-data font-medium tracking-wide",
        MAP[status] || "bg-slate-500/10 text-slate-400 border-slate-500/30"
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", DOT[status] || "bg-slate-400")} />
      {status}
    </span>
  );
}
