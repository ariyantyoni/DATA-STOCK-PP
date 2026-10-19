import { useState, useEffect, useCallback } from "react";
import api, { fmtNum, fmtPct } from "@/lib/api";
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, PieChart, Pie, Cell, Legend, ComposedChart, Line, ReferenceLine,
} from "recharts";
import { Input } from "@/components/ui/input";
import {
  Cpu, Lightbulb, AlertTriangle, Scale, TrendingUp, Loader2, Boxes, Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";

const STOCK_COLORS = ["#10b981", "#f59e0b", "#38bdf8", "#a78bfa", "#f97316", "#06b6d4", "#ef4444"];

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

function MetricCard({ title, cols, testId }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-border bg-card/70 p-5 hover:border-primary/30 transition-colors">
      <p className="text-xs font-mono-data uppercase tracking-wider text-muted-foreground mb-4 font-semibold">{title}</p>
      <div className="flex items-start justify-between gap-2">
        {cols.map((c) => (
          <div key={c.label} className="flex-1 text-center">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1 leading-tight">{c.label}</p>
            <p className={cn("font-heading text-3xl sm:text-4xl font-bold tracking-tight tabular-nums", c.accent || "text-foreground")}>{c.value}</p>
            {c.unit && <p className="text-[10px] font-mono-data text-muted-foreground mt-0.5">{c.unit}</p>}
          </div>
        ))}
      </div>
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
  const [range, setRange] = useState({ date_from: "", date_to: "", product: "" });
  const [products, setProducts] = useState([]);
  useEffect(() => { api.get("/meta/options").then((r) => setProducts(r.data.products || [])).catch(() => {}); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (range.date_from) params.date_from = range.date_from;
      if (range.date_to) params.date_to = range.date_to;
      if (range.product) params.product = range.product;
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
  const r = data.resume;
  const axis = { fill: "var(--axis)", fontSize: 11 };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Dashboard Kontrol Produksi</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Ringkasan produksi Part & ASSY, stock Part, kebutuhan (BLC), dan variance</p>
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Product</label>
            <select value={range.product} onChange={(e) => setRange((p) => ({ ...p, product: e.target.value }))} data-testid="dash-product"
              className="h-9 w-40 rounded-md border border-border bg-secondary/60 px-2 text-sm">
              <option value="">ALL PRODUCT</option>
              {products.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <MetricCard testId="resume-part" title="PRODUKSI PART PRODUCTION" cols={[
          { label: "Total Plan", value: fmtNum(r.part_production.total_plan), unit: "Pcs" },
          { label: "Act Prod", value: fmtNum(r.part_production.act_prod), unit: "Pcs", accent: "text-cyan-400" },
          { label: "Pencapaian", value: fmtNum(r.part_production.pct), unit: "%", accent: r.part_production.pct >= 100 ? "text-emerald-400" : "text-amber-400" },
        ]} />
        <MetricCard testId="resume-assy" title="PRODUKSI LAMP ASSY" cols={[
          { label: "Total Plan", value: fmtNum(r.lamp_assy.total_plan), unit: "Pcs" },
          { label: "Act Prod", value: fmtNum(r.lamp_assy.act_prod), unit: "Pcs", accent: "text-cyan-400" },
          { label: "Pencapaian", value: fmtNum(r.lamp_assy.pct), unit: "%", accent: r.lamp_assy.pct >= 100 ? "text-emerald-400" : "text-amber-400" },
        ]} />
        <MetricCard testId="resume-shortage" title="ITEM SHORTAGE" cols={[
          { label: "Total Part", value: fmtNum(r.shortage.total_part), unit: "Type" },
          { label: "Tidak Shortage", value: fmtNum(r.shortage.tidak_shortage), unit: "Type", accent: "text-emerald-400" },
          { label: "Potensi Shortage", value: fmtNum(r.shortage.potensi_shortage), unit: "Type", accent: "text-amber-400" },
          { label: "Shortage", value: fmtNum(r.shortage.shortage), unit: "Type", accent: "text-red-500" },
        ]} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <MetricCard testId="resume-achv-high" title="PENCAPAIAN PART PRODUCTION (>97%)" cols={[
          { label: "Total Plan", value: fmtNum(r.achievement.gt97.total_plan), unit: "Type" },
          { label: "Act", value: fmtNum(r.achievement.gt97.act), unit: "Type", accent: "text-cyan-400" },
          { label: "Average", value: fmtNum(r.achievement.gt97.average), unit: "%", accent: "text-emerald-400" },
        ]} />
        <MetricCard testId="resume-achv-mid" title="PENCAPAIAN PART PRODUCTION (90-96%)" cols={[
          { label: "Total Plan", value: fmtNum(r.achievement.mid.total_plan), unit: "Type" },
          { label: "Act", value: fmtNum(r.achievement.mid.act), unit: "Type", accent: "text-cyan-400" },
          { label: "Average", value: fmtNum(r.achievement.mid.average), unit: "%", accent: "text-amber-400" },
        ]} />
        <MetricCard testId="resume-achv-low" title="PENCAPAIAN PART PRODUCTION (<90%)" cols={[
          { label: "Total Plan", value: fmtNum(r.achievement.lt90.total_plan), unit: "Type" },
          { label: "Act", value: fmtNum(r.achievement.lt90.act), unit: "Type", accent: "text-cyan-400" },
          { label: "Average", value: fmtNum(r.achievement.lt90.average), unit: "%", accent: "text-red-500" },
        ]} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel icon={TrendingUp} title="MONITORING PENCAPAIAN PART PRODUCTION" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data.smt_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="date" tick={axis} tickFormatter={(d) => d?.slice(5)} />
              <YAxis yAxisId="left" tick={axis} label={{ value: "Pcs", angle: -90, position: "insideLeft", fill: "var(--axis)", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={axis} domain={[0, 120]} tickFormatter={(v) => `${v}%`} />
              <Tooltip content={<TooltipBox />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine yAxisId="right" y={100} stroke="#ef4444" strokeDasharray="5 4" />
              <Bar yAxisId="left" dataKey="plan" name="PLAN" fill="#84cc16" radius={[2, 2, 0, 0]} />
              <Bar yAxisId="left" dataKey="actual" name="ACTUAL" fill="#f97316" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="pct" name="%" stroke="#38bdf8" strokeWidth={2.5} dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>

        <Panel icon={Boxes} title="Komposisi Stock Part">
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
        <Panel icon={Cpu} title="Hasil Part per Lane (Injection / EVA / Assy)" tone="text-cyan-600" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.smt_by_lane}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="lane" tick={axis} />
              <YAxis tick={axis} />
              <Tooltip content={<TooltipBox />} cursor={{ fill: "var(--grid)" }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="injection" name="Injection" stackId="a" fill="#0369a1" />
              <Bar dataKey="eva" name="EVA" stackId="a" fill="#38bdf8" />
              <Bar dataKey="assy" name="Assy" stackId="a" fill="#f97316" radius={[3, 3, 0, 0]} />
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
