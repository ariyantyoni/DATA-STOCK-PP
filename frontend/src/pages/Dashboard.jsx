import { useState, useEffect, useCallback } from "react";
import api, { fmtNum, fmtPct } from "@/lib/api";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, PieChart, Pie, Cell, Legend,
} from "recharts";
import { Input } from "@/components/ui/input";
import {
  Cpu, Lightbulb, AlertTriangle, Scale, TrendingUp, Loader2, Boxes, Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STOCK_COLORS = ["#10b981", "#f59e0b", "#38bdf8", "#a78bfa", "#f97316"];

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

function Panel({ icon: Icon, title, tone = "text-primary", children, className }) {
  return (
    <div className={cn("rounded-lg border border-border bg-card/60 p-5", className)}>
      <div className="flex items-center gap-2 mb-4">
        <Icon className={cn("w-4 h-4", tone)} />
        <h3 className="font-heading font-semibold">{title}</h3>
      </div>
      {children}
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
  const axis = { fill: "var(--axis)", fontSize: 11 };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Dashboard Kontrol Produksi</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Ringkasan produksi SMT & ASSY, stock SMT, kebutuhan (BLC), dan variance</p>
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
        <KpiCard testId="kpi-smt" icon={Cpu} label="Total Produksi SMT" value={fmtNum(k.smt_total)}
          sub={`Planing ${fmtNum(k.smt_plan)} · Achv ${fmtPct(k.smt_achievement)}`}
          accent={k.smt_achievement >= 100 ? "text-emerald-600" : "text-cyan-600"} />
        <KpiCard testId="kpi-assy" icon={Lightbulb} label="Total Act Assy" value={fmtNum(k.assy_total)}
          sub={`Plan ${fmtNum(k.plan_assy)} · Achv ${fmtPct(k.assy_achievement)} · Balance ${k.balance > 0 ? "+" : ""}${fmtNum(k.balance)}`}
          accent={k.balance >= 0 ? "text-emerald-600" : "text-red-600"} />
        <KpiCard testId="kpi-shortage" icon={AlertTriangle} label="Item Shortage (BLC < 0)" value={fmtNum(k.shortage_count)}
          sub={`dari ${fmtNum(k.needs_items)} item kebutuhan`} accent={k.shortage_count > 0 ? "text-red-600" : "text-emerald-600"} />
        <KpiCard testId="kpi-variance" icon={Scale} label="Item Variance" value={fmtNum(k.variance_count)}
          sub={`Total selisih ${k.variance_sum > 0 ? "+" : ""}${fmtNum(k.variance_sum)} pcs`} accent={k.variance_count > 0 ? "text-amber-600" : "text-emerald-600"} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard testId="kpi-stock-ok" icon={Boxes} label="Stock OK SMT" value={fmtNum(k.stock_ok)} sub={k.stock_date ? `per ${k.stock_date}` : ""} accent="text-emerald-600" />
        <KpiCard testId="kpi-stock-total" icon={Layers} label="Total Stock SMT" value={fmtNum(k.stock_total)} sub={`${fmtNum(k.stock_items)} item`} accent="text-primary" />
        <KpiCard testId="kpi-stock-wip" icon={Layers} label="Stock WIP (belum OK)" value={fmtNum(k.stock_total - k.stock_ok)} accent="text-amber-600" />
        <KpiCard testId="kpi-plan" icon={Lightbulb} label="Item Produksi" value={fmtNum(k.smt_items)} sub="baris SMT & ASSY" accent="text-orange-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel icon={TrendingUp} title="Trend Produksi SMT & ASSY (Plan vs Actual)" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data.smt_trend}>
              <defs>
                <linearGradient id="gActual" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="date" tick={axis} tickFormatter={(d) => d?.slice(5)} />
              <YAxis tick={axis} />
              <Tooltip content={<TooltipBox />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="actual" name="Total Act SMT" stroke="#0ea5e9" fill="url(#gActual)" strokeWidth={2} />
              <Area type="monotone" dataKey="plan" name="Planing SMT" stroke="#0ea5e9" fill="none" strokeWidth={2} strokeDasharray="4 4" />
              <Area type="monotone" dataKey="actual_assy" name="Total Act Assy" stroke="#f97316" fill="none" strokeWidth={2} />
              <Area type="monotone" dataKey="plan_assy" name="Plan Assy" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="4 4" />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>

        <Panel icon={Boxes} title="Komposisi Stock SMT">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.stock_breakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3}>
                {data.stock_breakdown.map((s, i) => <Cell key={s.name} fill={STOCK_COLORS[i]} />)}
              </Pie>
              <Tooltip content={<TooltipBox />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {data.stock_breakdown.map((s, i) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <span className="inline-flex items-center gap-2"><span className="w-2 h-2 rounded-full" style={{ background: STOCK_COLORS[i] }} />{s.name}</span>
                <span className="font-mono-data">{fmtNum(s.value)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel icon={Cpu} title="Hasil SMT per Lane (per Shift)" tone="text-cyan-600" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.smt_by_lane}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="lane" tick={axis} />
              <YAxis tick={axis} />
              <Tooltip content={<TooltipBox />} cursor={{ fill: "var(--grid)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="act_smt_s3" name="Shift 3" stackId="a" fill="#0369a1" />
              <Bar dataKey="act_smt_s1" name="Shift 1" stackId="a" fill="#38bdf8" />
              <Bar dataKey="act_smt_s2" name="Shift 2" stackId="a" fill="#0ea5e9" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <div className="space-y-4">
          <Panel icon={AlertTriangle} title="Top Shortage (BLC)" tone="text-red-600">
            {data.top_shortage.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">Tidak ada item shortage</p>
            ) : (
              <div className="space-y-2">
                {data.top_shortage.map((n) => (
                  <div key={n.id} className="flex items-center justify-between border-b border-border/50 pb-1.5">
                    <div>
                      <p className="text-sm text-foreground">{n.type}</p>
                      <p className="text-[11px] font-mono-data text-muted-foreground">{n.ics_no} · Plan {fmtNum(n.plan_assy)} · Stock {fmtNum(n.stock_ok_prev)}</p>
                    </div>
                    <span className="font-mono-data text-sm text-red-600">{fmtNum(n.blc)}</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
          <Panel icon={Scale} title="Top Variance" tone="text-amber-600">
            {data.top_variance.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">Tidak ada variance</p>
            ) : (
              <div className="space-y-2">
                {data.top_variance.map((v) => (
                  <div key={v.id} className="flex items-center justify-between border-b border-border/50 pb-1.5">
                    <div>
                      <p className="text-sm text-foreground">{v.type}</p>
                      <p className="text-[11px] font-mono-data text-muted-foreground">{v.ics_no} · Sistem {fmtNum(v.stock_sistem)} · Actual {fmtNum(v.actual_total_stock)}</p>
                    </div>
                    <span className={cn("font-mono-data text-sm", v.variance < 0 ? "text-red-600" : "text-emerald-600")}>{v.variance > 0 ? "+" : ""}{fmtNum(v.variance)}</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
