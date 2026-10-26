import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, { canWrite, fmtNum, fmtPct2, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import ExcelGrid from "@/components/ExcelGrid";
import NeedsImportDialog from "@/components/NeedsImportDialog";
import { ClipboardList, Download, RefreshCw, Search, Loader2, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const ALL = "__all__";
const MESIN = ["ON", "OFF", "DANDORI"];
const localToday = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };

const STATUS_FILL = {
  SHORTAGE: "!bg-red-600 !text-white font-bold",
  "POTENSI SHORTAGE": "!bg-amber-400 !text-slate-900 font-bold",
  "TIDAK SHORTAGE": "!bg-emerald-600 !text-white font-bold",
  "STD BELUM DISET": "!bg-slate-200 !text-slate-700 dark:!bg-slate-700 dark:!text-slate-100",
};
const MESIN_FILL = {
  ON: "!bg-emerald-100 !text-emerald-800 dark:!bg-emerald-500/20 dark:!text-emerald-300 font-bold",
  OFF: "!bg-slate-200 !text-slate-700 dark:!bg-slate-600/40 dark:!text-slate-200 font-bold",
  DANDORI: "!bg-amber-100 !text-amber-800 dark:!bg-amber-500/20 dark:!text-amber-300 font-bold",
};

const signed = (v) => (v === null || v === undefined ? <span className="text-muted-foreground">-</span>
  : <span className={cn(v < 0 ? "text-red-600 font-semibold" : v > 0 ? "text-emerald-700 dark:text-emerald-400" : "")}>{fmtNum(v)}</span>);
const achv = (v) => (v === null || v === undefined ? <span className="text-muted-foreground">-</span>
  : <span className={cn("font-semibold", v > 97 ? "text-emerald-700 dark:text-emerald-400" : v >= 90 ? "text-amber-600" : "text-red-600")}>{fmtPct2(v)}</span>);
const dash = (v) => (v === null || v === undefined || v === "" ? <span className="text-muted-foreground">-</span> : v);
const master = (k, num) => ({ key: k, render: (r) => dash(num ? (r[k] === null || r[k] === undefined ? null : fmtNum(r[k])) : r[k]) });
const canEdit = (r) => r.master_found;

const shiftCols = (s) => [
  { key: `plan_s${s}`, label: `PLAN S${s}`, width: 78, align: "right", edit: "int", canEdit, sum: true },
  { key: `actual_s${s}`, label: `ACTUAL S${s}`, width: 84, align: "right", edit: "int", canEdit, sum: true },
  { key: `achievement_s${s}`, label: `ACHIEVEMENT S${s}`, width: 104, align: "right", render: (r) => achv(r[`achievement_s${s}`]) },
  { key: `balance_s${s}`, label: `BALANCE S${s}`, width: 90, align: "right", render: (r) => signed(r[`balance_s${s}`]), sum: true },
  { key: `status_mesin_s${s}`, label: `STATUS MESIN S${s}`, width: 118, align: "center", edit: "select", options: MESIN, canEdit,
    cellClass: (r) => MESIN_FILL[r[`status_mesin_s${s}`]] },
];

const COLUMNS = [
  { key: "date", label: "TANGGAL", width: 96, align: "center" },
  { key: "lane", label: "LANE", width: 110, render: (r) => (r.master_found ? dash(r.lane) : <span className="text-red-600 font-bold" data-testid="master-missing">MASTER BELUM ADA</span>) },
  { ...master("product"), label: "PRODUCT", width: 90 },
  { key: "type", label: "TYPE", width: 80 },
  { key: "ics_no", label: "ICS NO", width: 104 },
  { ...master("ics_name"), label: "ICS NAME", width: 140 },
  { ...master("proses_mesin"), label: "PROSES MESIN", width: 120 },
  { ...master("group"), label: "GROUP", width: 90, align: "center" },
  { ...master("std_stock_min", true), label: "STD STOCK MIN", width: 90, align: "right" },
  { ...master("std_stock_max", true), label: "STD STOCK MAX", width: 90, align: "right" },
  { ...master("act_stock", true), label: "ACT STOCK\nJAM 01:00", width: 100, align: "right", sum: true, headerClass: "bg-sky-100 dark:bg-sky-500/20" },
  { key: "plan_customer", label: "PLAN CUSTOMER\n(ASSY)", width: 112, align: "right", edit: "int", canEdit, sum: true },
  { key: "actual_customer", label: "ACTUAL CUSTOMER\n(ASSY)", width: 112, align: "right", edit: "int", canEdit, sum: true },
  { key: "balance", label: "BALANCE", width: 92, align: "right", render: (r) => signed(r.balance), sum: true },
  { key: "level_stock", label: "LEVEL STOCK\n(DAY)", width: 92, align: "right", render: (r) => dash(r.level_stock === null || r.level_stock === undefined ? null : new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(r.level_stock)) },
  { key: "status_part", label: "STATUS PART", width: 140, align: "center", cellClass: (r) => STATUS_FILL[r.status_part], render: (r) => dash(r.status_part) },
  ...shiftCols(3), ...shiftCols(1), ...shiftCols(2),
];

const GROUPS = [
  { label: "IDENTITAS ITEM · MASTER ITEM", span: 10 },
  { label: "STOCK VS KEBUTUHAN ASSY", span: 6, className: "bg-sky-100 dark:bg-sky-500/20" },
  { label: "SHIFT 3", span: 5, className: "bg-indigo-100 dark:bg-indigo-500/20" },
  { label: "SHIFT 1", span: 5, className: "bg-emerald-100 dark:bg-emerald-500/20" },
  { label: "SHIFT 2", span: 5, className: "bg-amber-100 dark:bg-amber-500/20" },
];

const FILTERS = [["product", "Product"], ["lane", "Lane"], ["proses_mesin", "Proses Mesin"], ["group", "Group"], ["status_part", "Status Part"]];

function FSelect({ k, label, value, options, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">{label}</label>
      <Select value={value || ALL} onValueChange={(v) => onChange(k, v === ALL ? "" : v)}>
        <SelectTrigger className="h-9 w-40 bg-secondary/60 border-border" data-testid={`needs-filter-${k}`}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Semua</SelectItem>
          {options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function ProductionNeeds() {
  const { user } = useAuth();
  const writable = canWrite(user, "production_needs");
  const [date, setDate] = useState(localToday());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({});
  const [search, setSearch] = useState("");

  const reqId = useRef(0);
  const load = useCallback(async () => {
    if (!date) return;
    const my = ++reqId.current;
    setLoading(true);
    try { const { data } = await api.get("/needs-grid", { params: { date } }); if (my === reqId.current) setRows(data); }
    catch (e) { if (my === reqId.current) toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { if (my === reqId.current) setLoading(false); }
  }, [date]);
  useEffect(() => { load(); }, [load]);

  const onSave = useCallback(async (row, field, value) => {
    const { data } = await api.patch("/needs-grid/cell", { date: row.date, ics_no: row.ics_no, type: row.type, field, value });
    setRows((rs) => rs.map((r) => (r.id === data.id ? data : r)));
  }, []);

  const opts = useMemo(() => Object.fromEntries(FILTERS.map(([k]) => [k, [...new Set(rows.map((r) => r[k]).filter(Boolean))].sort()])), [rows]);
  const view = useMemo(() => {
    const s = search.trim().toLowerCase();
    return rows.filter((r) => FILTERS.every(([k]) => !f[k] || r[k] === f[k])
      && (!s || [r.ics_no, r.type, r.lane, r.ics_name, r.product].some((x) => (x || "").toLowerCase().includes(s))));
  }, [rows, f, search]);
  const counts = useMemo(() => view.reduce((a, r) => { if (r.status_part) a[r.status_part] = (a[r.status_part] || 0) + 1; return a; }, {}), [view]);

  const [importOpen, setImportOpen] = useState(false);
  const exportXlsx = async () => {
    try {
      const res = await api.get("/needs-grid/import/template", { params: { date }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `kebutuhan_assy_${date}.xlsx`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Gagal export Excel"); }
  };

  return (
    <div className="space-y-5 fade-up" data-testid="production-needs-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><ClipboardList className="w-5 h-5 text-primary" /></div>
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Kebutuhan Assy VS. Stock Part Production</h1>
            <p className="text-sm text-muted-foreground mt-0.5 max-w-4xl">BALANCE = (ACT STOCK JAM 01:00 − PLAN CUSTOMER) + ACTUAL S3 + S1 + S2 · ACHIEVEMENT Sx = ACTUAL ÷ PLAN × 100% · LEVEL STOCK = ACT STOCK ÷ STD STOCK MAX · STATUS PART: ≤ 0 SHORTAGE · ≤ MID POTENSI SHORTAGE · &gt; MID TIDAK SHORTAGE (MID = (MIN + MAX) ÷ 2)</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} data-testid="needs-reload-button"><RefreshCw className="w-4 h-4 mr-1.5" /> Muat ulang</Button>
          {writable && <Button size="sm" onClick={() => setImportOpen(true)} data-testid="needs-import-button"><Upload className="w-4 h-4 mr-1.5" /> Import Excel</Button>}
          <Button variant="outline" size="sm" onClick={exportXlsx} data-testid="needs-export-button"><Download className="w-4 h-4 mr-1.5" /> Export Excel</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 p-4 rounded-lg border border-border bg-card/60">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Tanggal Produksi</label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="h-9 w-40 bg-secondary/60" data-testid="needs-date-input" />
        </div>
        {FILTERS.map(([k, l]) => <FSelect key={k} k={k} label={l} value={f[k]} options={opts[k] || []} onChange={(kk, v) => setF((p) => ({ ...p, [kk]: v }))} />)}
        <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
          <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Pencarian</label>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari ICS No., ICS Name, type, lane..." className="h-9 pl-8 bg-secondary/60" data-testid="needs-search-input" />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs font-mono-data" data-testid="needs-status-summary">
        {["SHORTAGE", "POTENSI SHORTAGE", "TIDAK SHORTAGE"].map((s) => (
          <span key={s} className={cn("px-3 py-1 rounded", STATUS_FILL[s])} data-testid={`needs-count-${s.replace(/ /g, "-").toLowerCase()}`}>{s}: {counts[s] || 0}</span>
        ))}
      </div>

      {loading ? (
        <div className="py-20 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : (
        <ExcelGrid testId="needs-grid" columns={COLUMNS} groups={GROUPS} rows={view} rowKey={(r) => r.id} onSave={onSave} editable={writable}
          info={writable ? "Klik cell putih lalu ketik angka · Enter simpan & turun · Tab simpan & ke kanan · Panah pindah cell · Esc batal · ACT STOCK = TOTAL STOCK HARI INI SHIFT 3" : "Mode lihat saja"} />
      )}
      <NeedsImportDialog open={importOpen} onOpenChange={setImportOpen} date={date} onDone={load} />
    </div>
  );
}
