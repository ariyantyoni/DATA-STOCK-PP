import { useState, useEffect, useCallback } from "react";
import api, { fmtNum } from "@/lib/api";
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

const pct2 = (v) => (v === null || v === undefined ? "-" : new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v));
const pctTone = (v) => (v === null || v === undefined ? "text-muted-foreground" : v >= 100 ? "text-emerald-400" : "text-amber-400");

function MetricCard({ title, cols, testId, note }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-border bg-card/70 p-5 hover:border-primary/30 transition-colors">
      <p className="text-sm font-mono-data uppercase tracking-wider text-muted-foreground mb-4 font-bold">{title}</p>
      <div className="flex items-start justify-between gap-2">
        {cols.map((c) => (
          <div key={c.label} className="flex-1 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1 leading-tight">{c.label}</p>
            <p className={cn("font-heading text-3xl sm:text-4xl font-bold tracking-tight tabular-nums", c.accent || "text-foreground")}>{c.value}</p>
            {c.unit && <p className="text-[11px] font-mono-data text-muted-foreground mt-1">{c.unit}</p>}
          </div>
        ))}
      </div>
      {note && <p className="text-[11px] font-mono-data text-muted-foreground mt-4 border-t border-border/60 pt-2" data-testid={`${testId}-note`}>{note}</p>}
    </div>
  );
}

function AchvCard({ title, d, tone, testId }) {
  return (
    <MetricCard testId={testId} title={title} cols={[
      { label: "Total Plan", value: fmtNum(d.total_plan), unit: "Type" },
      { label: "Act", value: fmtNum(d.act), unit: "Type", accent: "text-cyan-400" },
      { label: "Average", value: pct2(d.average), unit: "%", accent: tone },
    ]} />
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

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {};
      if (range.date_from) params.date_from = range.date_from;
      if (range.date_to) params.date_to = range.date_to;
      if (range.product) params.product = range.product;
      const { data } = await api.get("/dashboard/summary", { params });
      setData(data);
    } catch {
      if (!silent) setData(null);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [range]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => load(true), 30000);
    const onVis = () => { if (document.visibilityState === "visible") load(true); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("focus", onVis);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", onVis); window.removeEventListener("focus", onVis); };
  }, [load]);

  const pctMax = Math.max(130, Math.ceil(Math.max(0, ...((data?.smt_trend || []).map((t) => t.pct || 0))) / 10) * 10);

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
          <p className="text-sm text-muted-foreground mt-0.5">Semua kartu & grafik bersumber dari Kebutuhan Assy VS. Stock Part Production, Stock Part Production, dan Master Item</p>
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
          { label: "Total Actual", value: fmtNum(r.part_production.act_prod), unit: "Pcs", accent: "text-cyan-400" },
          { label: "Pencapaian", value: pct2(r.part_production.pct), unit: "%", accent: pctTone(r.part_production.pct) },
        ]} note="Σ PLAN & ACTUAL S3+S1+S2 · Kebutuhan Assy VS. Stock Part" />
        <MetricCard testId="resume-assy" title="PRODUKSI LAMP ASSY" cols={[
          { label: "Total Plan", value: fmtNum(r.lamp_assy.total_plan), unit: "Pcs" },
          { label: "Total Actual", value: fmtNum(r.lamp_assy.act_prod), unit: "Pcs", accent: "text-cyan-400" },
          { label: "Pencapaian", value: pct2(r.lamp_assy.pct), unit: "%", accent: pctTone(r.lamp_assy.pct) },
        ]} note="Σ PLAN CUSTOMER (ASSY) & Σ ACTUAL CUSTOMER (ASSY)" />
        <MetricCard testId="resume-shortage" title="ITEM SHORTAGE" cols={[
          { label: "Total Part", value: fmtNum(r.shortage.total_part), unit: "Type" },
          { label: "Tidak Shortage", value: fmtNum(r.shortage.tidak_shortage), unit: "Type", accent: "text-emerald-400" },
          { label: "Potensi Shortage", value: fmtNum(r.shortage.potensi_shortage), unit: "Type", accent: "text-amber-400" },
          { label: "Shortage", value: fmtNum(r.shortage.shortage), unit: "Type", accent: "text-red-500" },
        ]} note={`Total Part = TYPE unik Master Item · status per TYPE dari data tanggal terakhir${r.shortage.latest_date ? ` (s/d ${r.shortage.latest_date})` : ""} · ${fmtNum(r.shortage.with_status)} TYPE berstatus, ${fmtNum(r.shortage.no_status)} belum ada data${r.shortage.std_belum_diset ? `, ${fmtNum(r.shortage.std_belum_diset)} STD belum diset` : ""}`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <AchvCard testId="resume-achv-high" title="PENCAPAIAN PART PRODUCTION (>97%)" d={r.achievement.gt97} tone="text-emerald-400" />
        <AchvCard testId="resume-achv-9697" title="PENCAPAIAN PART PRODUCTION (>96–97%)" d={r.achievement.b96_97} tone="text-lime-400" />
        <AchvCard testId="resume-achv-mid" title="PENCAPAIAN PART PRODUCTION (90–96%)" d={r.achievement.mid} tone="text-amber-400" />
        <AchvCard testId="resume-achv-low" title="PENCAPAIAN PART PRODUCTION (<90%)" d={r.achievement.lt90} tone="text-red-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel icon={TrendingUp} title="MONITORING PENCAPAIAN PRODUKSI" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data.smt_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
              <XAxis dataKey="date" tick={axis} tickFormatter={(d) => d?.slice(5)} />
              <YAxis yAxisId="left" tick={axis} label={{ value: "Pcs", angle: -90, position: "insideLeft", fill: "var(--axis)", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={axis} domain={[0, pctMax]} ticks={pctMax === 130 ? [0, 25, 50, 75, 100, 130] : undefined} tickFormatter={(v) => `${v}%`} />
              <Tooltip content={<TooltipBox />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine yAxisId="right" y={100} stroke="#ef4444" strokeDasharray="6 4" strokeWidth={1.5}
                label={{ value: "TARGET 100%", position: "insideTopRight", fill: "#ef4444", fontSize: 11, fontWeight: 700 }} />
              <Bar yAxisId="left" dataKey="plan" name="PLAN (PLAN CUSTOMER)" fill="#84cc16" radius={[2, 2, 0, 0]} />
              <Bar yAxisId="left" dataKey="actual" name="ACTUAL (S3+S1+S2)" fill="#f97316" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="pct" name="%" connectNulls stroke="#38bdf8" strokeWidth={2.5} dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>

        <Panel icon={Boxes} title="Komposisi Stock Part (per Group)">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left py-2 font-semibold uppercase text-xs tracking-wide">Group</th>
                  <th className="text-right py-2 font-semibold uppercase text-xs tracking-wide">Total Type</th>
                  <th className="text-right py-2 font-semibold uppercase text-xs tracking-wide">Total Stock</th>
                  <th className="text-right py-2 font-semibold uppercase text-xs tracking-wide">Shortage Type</th>
                </tr>
              </thead>
              <tbody>
                {(data.group_composition || []).map((g) => (
                  <tr key={g.group} className="border-b border-border/40" data-testid={`group-row-${g.group.replace(/ /g, "-")}`}>
                    <td className="py-2.5 font-semibold text-foreground">{g.group}</td>
                    <td className="py-2.5 text-right font-mono-data tabular-nums">{fmtNum(g.total_type)}</td>
                    <td className="py-2.5 text-right font-mono-data tabular-nums">{fmtNum(g.total_stock)} <span className="text-[10px] text-muted-foreground">pcs</span></td>
                    <td className={cn("py-2.5 text-right font-mono-data tabular-nums font-bold", g.shortage_type > 0 ? "text-red-500" : "text-emerald-500")}>{fmtNum(g.shortage_type)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] font-mono-data text-muted-foreground mt-3">Sumber: Stock Part Production (data terbaru per item pada periode) · GROUP dari Master Item</p>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <Panel icon={AlertTriangle} title="Top Shortage (BLC)" tone="text-red-600">
          {data.top_shortage.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center" data-testid="top-shortage-empty">Tidak ada item SHORTAGE (BALANCE ≤ 0) pada periode ini</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
              {data.top_shortage.map((n) => (
                <div key={n.id} className="flex items-center justify-between border-b border-border/50 py-2" data-testid={`top-shortage-${n.ics_no}-${(n.type || "").replace(/\s+/g, "-")}`}>
                  <div>
                    <p className="text-sm text-foreground font-medium">{n.type}{n.ics_name ? <span className="text-muted-foreground font-normal"> · {n.ics_name}</span> : null}</p>
                    <p className="text-[11px] font-mono-data text-muted-foreground">{n.date} · {n.product || "-"} · {n.ics_no} · Plan {fmtNum(n.plan_customer)} · Stock {n.act_stock === null ? "-" : fmtNum(n.act_stock)} · {n.status_part || "-"}</p>
                  </div>
                  <span className={cn("font-mono-data text-sm font-bold", n.balance < 0 ? "text-red-600" : n.balance === 0 ? "text-amber-500" : "text-emerald-600")}>{fmtNum(n.balance)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
