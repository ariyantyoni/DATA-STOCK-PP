import { useState, useEffect, useCallback } from "react";
import api, { canWrite, fmtNum, fmtPct, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import FilterBar from "@/components/FilterBar";
import RecordDialog from "@/components/RecordDialog";
import ImportDialog from "@/components/ImportDialog";
import { StatusBadge } from "@/components/StatusBadge";
import { Plus, Upload, Pencil, Trash2, Loader2, Download, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export default function CrudPage({
  title, subtitle, icon: Icon, endpoint, dataset, module,
  columns, formFields, filters, options, refreshOptions, itemPicker = true,
}) {
  const { user } = useAuth();
  const writable = canWrite(user, module);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteId, setDeleteId] = useState(null);
  const [dup, setDup] = useState(null);

  const AUDIT_COLS = [
    { key: "created_by_name", label: "Diinput oleh" },
    { key: "created_at", label: "Waktu Input", type: "datetime" },
  ];
  const allColumns = [...columns, ...AUDIT_COLS];

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      Object.entries(values).forEach(([k, v]) => { if (v) params[k] = v; });
      const { data } = await api.get(endpoint, { params });
      setRows(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [endpoint, values]);

  useEffect(() => {
    const t = setTimeout(fetchData, 250);
    return () => clearTimeout(t);
  }, [fetchData]);

  const onSubmit = async (payload, force = false) => {
    setSaving(true);
    try {
      if (editing) await api.put(`${endpoint}/${editing.id}`, payload);
      else await api.post(endpoint, force ? { ...payload, force: true } : payload);
      toast.success(editing ? "Data diperbarui" : force ? "Data yang ada berhasil diperbarui" : "Data ditambahkan");
      setDialogOpen(false);
      setEditing(null);
      setDup(null);
      fetchData();
      refreshOptions?.();
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (e.response?.status === 409 && detail?.code === "DUPLICATE") {
        setDup({ message: detail.message, payload });
        toast.warning("Data duplikat terdeteksi", { description: detail.message });
        return;
      }
      toast.error(formatApiErrorDetail(detail));
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    try {
      await api.delete(`${endpoint}/${deleteId}`);
      toast.success("Data dihapus");
      setDeleteId(null);
      fetchData();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const exportCsv = () => {
    const cols = columns.map((c) => c.key);
    const header = columns.map((c) => c.label).join(",");
    const body = rows.map((r) => cols.map((k) => `"${r[k] ?? ""}"`).join(",")).join("\n");
    const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${dataset}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const renderCell = (col, row) => {
    const v = row[col.key];
    if (col.type === "status") return <StatusBadge status={v} testId={`row-status-${row.id}`} />;
    if (col.type === "number") return <span className="font-mono-data">{fmtNum(v)}</span>;
    if (col.type === "percent")
      return <span className={cn("font-mono-data", col.tone && (Number(v) >= 100 ? "text-emerald-600" : Number(v) >= 85 ? "text-amber-600" : "text-red-600"))}>{fmtPct(v)}</span>;
    if (col.type === "signed")
      return <span className={cn("font-mono-data", Number(v) < 0 ? "text-red-600" : Number(v) > 0 ? "text-emerald-600" : "text-muted-foreground")}>{Number(v) > 0 ? "+" : ""}{fmtNum(v)}</span>;
    if (col.type === "strong") return <span className="font-mono-data font-semibold text-foreground">{fmtNum(v)}</span>;
    if (col.type === "datetime") return <span className="font-mono-data text-xs text-muted-foreground">{v ? new Date(v).toLocaleString("id-ID", { dateStyle: "short", timeStyle: "short" }) : "-"}</span>;
    if (col.mono) return <span className="font-mono-data text-foreground">{v ?? "-"}</span>;
    return <span>{v ?? "-"}</span>;
  };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {Icon && <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><Icon className="w-5 h-5 text-primary" /></div>}
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportCsv} data-testid="export-csv-button" className="border-border">
            <Download className="w-4 h-4 mr-1.5" /> Export
          </Button>
          {writable && (
            <>
              <Button variant="outline" size="sm" onClick={() => setImportOpen(true)} data-testid="import-open-button" className="border-border">
                <Upload className="w-4 h-4 mr-1.5" /> Import
              </Button>
              <Button size="sm" onClick={() => { setEditing(null); setDialogOpen(true); }} data-testid="add-record-button">
                <Plus className="w-4 h-4 mr-1.5" /> Tambah
              </Button>
            </>
          )}
        </div>
      </div>

      <FilterBar filters={filters} values={values} setValues={setValues} options={options} />

      <div className="rounded-lg border border-border bg-card/60 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-secondary/80 border-b border-border">
                {allColumns.map((c) => (
                  <th key={c.key} className={cn("px-4 py-3 text-left font-mono-data text-[11px] uppercase tracking-wider text-muted-foreground whitespace-nowrap border-r border-border last:border-r-0", c.align === "right" && "text-right")}>{c.label}</th>
                ))}
                {writable && <th className="px-4 py-3 text-right font-mono-data text-[11px] uppercase tracking-wider text-muted-foreground border-l border-border">Aksi</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={allColumns.length + 1} className="px-4 py-16 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={allColumns.length + 1} className="px-4 py-16 text-center text-muted-foreground text-sm">Tidak ada data. {writable && "Tambah data atau import dari Excel."}</td></tr>
              ) : (
                rows.map((row, i) => (
                  <tr key={row.id} data-testid={`data-row-${i}`} className="border-b border-border/70 hover:bg-secondary/60 transition-colors">
                    {allColumns.map((c) => (
                      <td key={c.key} className={cn("px-4 py-2.5 whitespace-nowrap border-r border-border/70 last:border-r-0", c.align === "right" && "text-right")}>{renderCell(c, row)}</td>
                    ))}
                    {writable && (
                      <td className="px-4 py-2.5 text-right whitespace-nowrap border-l border-border/70">
                        <div className="inline-flex gap-1">
                          <button onClick={() => { setEditing(row); setDialogOpen(true); }} data-testid={`edit-${i}`}
                            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                          <button onClick={() => setDeleteId(row.id)} data-testid={`delete-${i}`}
                            className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-red-600 hover:border-red-500/40 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {!loading && rows.length > 0 && (
          <div className="px-4 py-2.5 border-t border-border text-xs font-mono-data text-muted-foreground">{rows.length} baris</div>
        )}
      </div>

      <RecordDialog open={dialogOpen} onOpenChange={setDialogOpen}
        title={editing ? `Edit ${title}` : `Tambah ${title}`} fields={formFields}
        initial={editing} onSubmit={onSubmit} submitting={saving} itemPicker={itemPicker} />

      <ImportDialog open={importOpen} onOpenChange={setImportOpen} dataset={dataset} title={title} onDone={() => { fetchData(); refreshOptions?.(); }} />

      <AlertDialog open={!!dup} onOpenChange={(v) => !v && setDup(null)}>
        <AlertDialogContent className="bg-card border-amber-500/50">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-amber-600 flex items-center gap-2"><AlertTriangle className="w-5 h-5" /> Data duplikat terdeteksi</AlertDialogTitle>
            <AlertDialogDescription data-testid="duplicate-message">{dup?.message}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="duplicate-cancel">Batal</AlertDialogCancel>
            <AlertDialogAction onClick={() => onSubmit(dup.payload, true)} data-testid="duplicate-update" className="bg-amber-500 hover:bg-amber-600 text-white">Update Data</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!deleteId} onOpenChange={(v) => !v && setDeleteId(null)}>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader>
            <AlertDialogTitle>Hapus data ini?</AlertDialogTitle>
            <AlertDialogDescription>Tindakan ini tidak dapat dibatalkan.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-cancel">Batal</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="delete-confirm" className="bg-red-500 hover:bg-red-600">Hapus</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
