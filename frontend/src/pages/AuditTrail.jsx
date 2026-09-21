import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { fmtTs } from "@/components/NotificationBell";
import { ScrollText, Loader2, X, Eye } from "lucide-react";
import { cn } from "@/lib/utils";

const ALL = "__all__";
const ACTION_STYLE = {
  CREATE: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  UPDATE: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  DELETE: "bg-red-500/10 text-red-600 border-red-500/30",
};

function FSel({ label, value, onChange, options, testId }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">{label}</label>
      <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
        <SelectTrigger className="h-9 w-44 bg-secondary/60 border-border" data-testid={testId}><SelectValue placeholder="Semua" /></SelectTrigger>
        <SelectContent><SelectItem value={ALL}>Semua</SelectItem>{options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  );
}

function Changes({ row }) {
  if (row.action === "UPDATE" && row.before && row.after) {
    const keys = Object.keys(row.after).filter((k) => JSON.stringify(row.before[k]) !== JSON.stringify(row.after[k]));
    if (!keys.length) return <p className="text-sm text-muted-foreground">Tidak ada perubahan nilai.</p>;
    return (
      <table className="w-full text-sm"><thead><tr className="text-left text-[11px] font-mono-data uppercase text-muted-foreground"><th className="py-1">Field</th><th>Sebelum</th><th>Sesudah</th></tr></thead>
        <tbody>{keys.map((k) => <tr key={k} className="border-t border-border/60"><td className="py-1.5 font-mono-data">{k}</td><td className="text-red-600 font-mono-data">{String(row.before[k] ?? "-")}</td><td className="text-emerald-600 font-mono-data">{String(row.after[k] ?? "-")}</td></tr>)}</tbody></table>
    );
  }
  const d = row.after || row.before || {};
  return <pre className="text-xs font-mono-data bg-secondary/60 rounded-md p-3 overflow-auto max-h-72">{JSON.stringify(d, null, 2)}</pre>;
}

export default function AuditTrail() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({});
  const [users, setUsers] = useState([]);
  const [modules, setModules] = useState([]);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api.get("/meta/modules").then((r) => setModules(r.data.modules)).catch(() => {});
    api.get("/users").then((r) => setUsers(r.data)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {}; Object.entries(f).forEach(([k, v]) => { if (v) params[k] = v; });
      const { data } = await api.get("/audit", { params }); setRows(data);
    } finally { setLoading(false); }
  }, [f]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const modLabel = (m) => modules.find((x) => x.key === m)?.label || m;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex items-start gap-3">
        <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><ScrollText className="w-5 h-5 text-primary" /></div>
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Audit Trail</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Log semua aktivitas input, edit, dan hapus data — hanya dapat dilihat, tidak dapat dihapus</p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 p-4 rounded-lg border border-border bg-card/60">
        <div className="flex flex-col gap-1"><label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Dari</label>
          <Input type="date" value={f.date_from || ""} onChange={(e) => set("date_from", e.target.value)} className="h-9 w-40 bg-secondary/60 border-border" data-testid="audit-date-from" /></div>
        <div className="flex flex-col gap-1"><label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Sampai</label>
          <Input type="date" value={f.date_to || ""} onChange={(e) => set("date_to", e.target.value)} className="h-9 w-40 bg-secondary/60 border-border" data-testid="audit-date-to" /></div>
        <FSel label="User" value={f.user_id} onChange={(v) => set("user_id", v)} options={users.map((u) => ({ value: u.id, label: u.name }))} testId="audit-filter-user" />
        <FSel label="Aksi" value={f.action} onChange={(v) => set("action", v)} options={["CREATE", "UPDATE", "DELETE"].map((a) => ({ value: a, label: a }))} testId="audit-filter-action" />
        <FSel label="Modul" value={f.module} onChange={(v) => set("module", v)} options={modules.filter((m) => !["users", "audit"].includes(m.key)).map((m) => ({ value: m.key, label: m.label }))} testId="audit-filter-module" />
        <div className="flex flex-col gap-1 flex-1 min-w-[160px]"><label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Cari</label>
          <Input value={f.search || ""} onChange={(e) => set("search", e.target.value)} placeholder="ICS No., type, nama user..." className="h-9 bg-secondary/60 border-border" data-testid="audit-search" /></div>
        {Object.values(f).some(Boolean) && <Button variant="ghost" size="sm" onClick={() => setF({})} className="h-9" data-testid="audit-reset"><X className="w-4 h-4 mr-1" /> Reset</Button>}
      </div>

      <div className="rounded-lg border border-border bg-card/60 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-secondary/80 border-b border-border">
            {["Waktu", "User", "Role", "Aksi", "Modul", "ICS No / Type", "Tanggal Data", "IP / Device", "Detail"].map((h) => <th key={h} className="px-3 py-3 text-left font-mono-data text-[11px] uppercase tracking-wider text-muted-foreground whitespace-nowrap border-r border-border last:border-r-0">{h}</th>)}
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={9} className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></td></tr>
              : rows.length === 0 ? <tr><td colSpan={9} className="py-16 text-center text-sm text-muted-foreground">Belum ada log aktivitas.</td></tr>
              : rows.map((r, i) => (
                <tr key={r.id} data-testid={`audit-row-${i}`} className="border-b border-border/70 hover:bg-secondary/60">
                  <td className="px-3 py-2 font-mono-data whitespace-nowrap border-r border-border/70">{fmtTs(r.ts)}</td>
                  <td className="px-3 py-2 whitespace-nowrap border-r border-border/70">{r.user_name}<span className="text-xs text-muted-foreground font-mono-data"> @{r.username}</span></td>
                  <td className="px-3 py-2 text-xs text-muted-foreground border-r border-border/70">{r.role}</td>
                  <td className="px-3 py-2 border-r border-border/70"><span className={cn("text-[11px] font-mono-data px-2 py-0.5 rounded-full border", ACTION_STYLE[r.action])} data-testid={`audit-action-${i}`}>{r.action}</span></td>
                  <td className="px-3 py-2 whitespace-nowrap border-r border-border/70">{modLabel(r.module)}</td>
                  <td className="px-3 py-2 border-r border-border/70"><span className="font-mono-data">{r.ics_no || "-"}</span><span className="text-xs text-muted-foreground"> {r.type}</span>{r.note && <p className="text-[10px] text-amber-600">{r.note}</p>}</td>
                  <td className="px-3 py-2 font-mono-data border-r border-border/70">{r.date || "-"}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground max-w-[200px] truncate border-r border-border/70" title={r.user_agent}>{r.ip}<br /><span className="text-[10px]">{r.user_agent?.split(") ")[0]?.slice(0, 40)}</span></td>
                  <td className="px-3 py-2"><button onClick={() => setDetail(r)} data-testid={`audit-detail-${i}`} className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-primary"><Eye className="w-3.5 h-3.5" /></button></td>
                </tr>
              ))}
          </tbody>
        </table>
        {!loading && rows.length > 0 && <div className="px-4 py-2.5 border-t border-border text-xs font-mono-data text-muted-foreground">{rows.length} log</div>}
      </div>

      <Dialog open={!!detail} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="max-w-2xl bg-card border-border max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">Detail {detail?.action} · {detail && modLabel(detail.module)}</DialogTitle>
            <DialogDescription>{detail?.user_name} ({detail?.role}) · {detail && fmtTs(detail.ts)} · {detail?.ip}</DialogDescription>
          </DialogHeader>
          {detail && <Changes row={detail} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
