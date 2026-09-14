import { useState, useEffect, useCallback } from "react";
import api, { fmtNum, fmtPct } from "@/lib/api";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, PieChart, Pie, Cell, Legend,
} from "recharts";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Cpu, Lightbulb, AlertTriangle, Scale, Target, TrendingUp, Loader2, Boxes, Gauge,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STOCK_COLORS = { AMAN: "#10b981", REORDER: "#f59e0b", CRITICAL: "#ef4444" };

function TooltipBox({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border border-border rounded-md px-3 py-2 text-xs font-mono-data shadow-xl">
      <p className="text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {fmtNum(p.value)}</p>
      ))}
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, accent, testId }) {
  return (
    <div data-testid={testId} className="rounded-lg border border-border bg-card/60 p-5 hover:border-primary/30 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-mono-data uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="font-heading text-3xl font-bold mt-2 tracking-tight">{value}</p>
          {sub && <p className={cn("text-xs mt-1 font-mono-data", accent)}>{sub}</p>}
        </div>
        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center border", accent ? `${accent} border-current/30 bg-current/10` : "text-primary border-primary/25 bg-primary/10")}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState({ date_from: "", date_to: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (range.date_from) params.date_from = range.date_from;
      if (range.date_to) params.date_to = range.date_to;
      const { data } = await api.get("/dashboard/summary", { params });
      setData(data);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => { load(); }, [load]);

  if (loading || !data)
    return <div className="flex items-center justify-center py-32"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;

  const k = data.kpi;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Dashboard Kontrol Produksi</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Ringkasan produksi SMT, LAMP ASSY, stok, dan variance</p>
        </div>
        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Dari</label>
            <Input type="date" value={range.date_from} onChange={(e) => setRange((p) => ({ ...p, date_from: e.target.value }))} className="h-9 w-36 bg-secondary/60 border-border" data-testid="dash-date-from" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Sampai</label>
            <Input type="date" value={range.date_to} onChange={(e) => setRange((p) => ({ ...p, date_to: e.target.value }))} className="h-9 w-36 bg-secondary/60 border-border" data-testid="dash-date-to" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard testId="kpi-smt" icon={Cpu} label="Output SMT (Actual)" value={fmtNum(k.smt_actual)}
          sub={`Target ${fmtNum(k.smt_target)} · Achv ${fmtPct(k.smt_achievement)}`}
          accent={k.smt_achievement >= 100 ? "text-emerald-400" : "text-amber-400"} />
        <KpiCard testId="kpi-lamp" icon={Lightbulb} label="Output LAMP ASSY" value={fmtNum(k.lamp_actual)}
          sub={`Target ${fmtNum(k.lamp_target)} · Achv ${fmtPct(k.lamp_achievement)}`}
          accent="text-orange-400" />
        <KpiCard testId="kpi-shortage" icon={AlertTriangle} label="Item Shortage" value={fmtNum(k.shortage_count)}
          sub="Part kurang dari kebutuhan" accent={k.shortage_count > 0 ? "text-red-400" : "text-emerald-400"} />
        <KpiCard testId="kpi-variance" icon={Scale} label="Item Variance" value={fmtNum(k.variance_count)}
          sub={`Akurasi stok ${fmtPct(k.stock_accuracy)}`} accent={k.variance_count > 0 ? "text-amber-400" : "text-emerald-400"} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard testId="kpi-yield" icon={Gauge} label="SMT Yield" value={fmtPct(k.smt_yield)} accent="text-cyan-400" />
        <KpiCard testId="kpi-defect" icon={AlertTriangle} label="Total Defect" value={fmtNum(k.smt_defect)} accent="text-red-400" />
        <KpiCard testId="kpi-stock-total" icon={Boxes} label="Total Item Stock" value={fmtNum(k.stock_total)} accent="text-primary" />
        <KpiCard testId="kpi-achv" icon={Target} label="SMT Achievement" value={fmtPct(k.smt_achievement)}
          accent={k.smt_achievement >= 100 ? "text-emerald-400" : "text-amber-400"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg border border-border bg-card/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-primary" />
            <h3 className="font-heading font-semibold">Trend Produksi SMT (Target vs Actual)</h3>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data.smt_trend}>
              <defs>
                <linearGradient id="gActual" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
              <Tooltip content={<TooltipBox />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="actual" name="Actual" stroke="#38bdf8" fill="url(#gActual)" strokeWidth={2} />
              <Area type="monotone" dataKey="target" name="Target" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="4 4" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-border bg-card/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Boxes className="w-4 h-4 text-primary" />
            <h3 className="font-heading font-semibold">Status Stock SMT</h3>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.stock_status} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3}>
                {data.stock_status.map((s) => <Cell key={s.name} fill={STOCK_COLORS[s.name]} />)}
              </Pie>
              <Tooltip content={<TooltipBox />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {data.stock_status.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <StatusBadge status={s.name} />
                <span className="font-mono-data">{fmtNum(s.value)} item</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg border border-border bg-card/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-4 h-4 text-orange-400" />
            <h3 className="font-heading font-semibold">Trend Produksi LAMP ASSY</h3>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.lamp_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
              <Tooltip content={<TooltipBox />} cursor={{ fill: "#1e293b40" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="target" name="Target" fill="#334155" radius={[3, 3, 0, 0]} />
              <Bar dataKey="actual" name="Actual" fill="#f97316" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-border bg-card/60 p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <h3 className="font-heading font-semibold">Top Item Shortage</h3>
          </div>
          {data.top_shortage.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Tidak ada item shortage 🎯</p>
          ) : (
            <div className="space-y-3">
              {data.top_shortage.map((n) => (
                <div key={n.id} className="flex items-center justify-between border-b border-border/50 pb-2">
                  <div>
                    <p className="font-mono-data text-sm text-foreground">{n.part_number}</p>
                    <p className="text-xs text-muted-foreground">Butuh {fmtNum(n.required_qty)} · Stock {fmtNum(n.stock_actual)}</p>
                  </div>
                  <span className="font-mono-data text-sm text-red-400">-{fmtNum(n.shortage_qty)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
