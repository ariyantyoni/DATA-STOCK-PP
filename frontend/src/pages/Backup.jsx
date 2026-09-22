import { useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DatabaseBackup, Download, Upload, Loader2, FileArchive, AlertTriangle } from "lucide-react";
import { fmtTs } from "@/components/NotificationBell";

export default function Backup() {
  const [exporting, setExporting] = useState(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState(null);

  const doExport = async () => {
    setExporting(true);
    try {
      const res = await api.get("/backup/export", { responseType: "blob" });
      const name = /filename="([^"]+)"/.exec(res.headers["content-disposition"] || "")?.[1] || "backup_cds.zip";
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
      toast.success("Backup berhasil diunduh");
    } catch (e) {
      toast.error("Gagal membuat backup");
    } finally { setExporting(false); }
  };

  const pick = async (f) => {
    if (!f) return;
    setFile(f); setPreview(null); setResult(null); setLoading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const { data } = await api.post("/backup/preview", fd);
      setPreview(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail)); setFile(null);
    } finally { setLoading(false); }
  };

  const doRestore = async () => {
    setLoading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const { data } = await api.post("/backup/restore", fd);
      setResult(data.result); setPreview(null); setFile(null);
      toast.success("Restore selesai. Data telah diganti dengan isi backup.");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); setConfirm(false); }
  };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex items-start gap-3">
        <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><DatabaseBackup className="w-5 h-5 text-primary" /></div>
        <div>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Backup & Restore</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Export seluruh data modul ke satu file .zip dan pulihkan kembali kapan saja</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card/60 p-6 space-y-4">
          <div className="flex items-center gap-2"><Download className="w-4 h-4 text-primary" /><h3 className="font-heading font-semibold">Backup (Export)</h3></div>
          <p className="text-sm text-muted-foreground">File .zip berisi: Produksi SMT & ASSY, Stock SMT, Kebutuhan vs Stock, Variance, Master Item, Manajemen User, Audit Trail, dan Notifikasi (format JSON per modul). Dapat dibuka dengan WinRAR / 7-Zip.</p>
          <Button onClick={doExport} disabled={exporting} data-testid="backup-export-button">
            {exporting ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FileArchive className="w-4 h-4 mr-1.5" />} Unduh Backup (.zip)
          </Button>
        </div>

        <div className="rounded-lg border border-border bg-card/60 p-6 space-y-4">
          <div className="flex items-center gap-2"><Upload className="w-4 h-4 text-primary" /><h3 className="font-heading font-semibold">Restore (Import)</h3></div>
          <p className="text-sm text-muted-foreground">Unggah file .zip hasil backup. Data modul saat ini akan <span className="text-amber-600 font-medium">dihapus dan diganti</span> dengan isi backup (user & audit trail tidak ditimpa). Proses tercatat di Audit Trail.</p>
          <label className="flex items-center justify-center gap-2 border-2 border-dashed border-border rounded-lg p-6 cursor-pointer hover:border-primary/50 transition-colors text-sm text-muted-foreground">
            <input type="file" accept=".zip" className="hidden" data-testid="restore-file-input" onChange={(e) => pick(e.target.files?.[0])} />
            <FileArchive className="w-5 h-5" /> {file ? file.name : "Pilih file backup .zip"}
          </label>
          {loading && <Loader2 className="w-5 h-5 animate-spin text-primary mx-auto" />}
          {preview && (
            <div className="space-y-3" data-testid="restore-preview">
              <p className="text-xs font-mono-data text-muted-foreground">Dibuat {fmtTs(preview.meta.exported_at)} oleh {preview.meta.exported_by}</p>
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] font-mono-data uppercase text-muted-foreground border-b border-border"><th className="py-1.5">Modul</th><th className="text-right">Di backup</th><th className="text-right">Saat ini</th></tr></thead>
                <tbody>{preview.modules.map((m) => (
                  <tr key={m.key} className="border-b border-border/60"><td className="py-1.5">{m.label}</td><td className="text-right font-mono-data text-emerald-600">{m.in_backup}</td><td className="text-right font-mono-data text-muted-foreground">{m.current}</td></tr>
                ))}</tbody>
              </table>
              <Button variant="destructive" onClick={() => setConfirm(true)} data-testid="restore-button" className="w-full"><AlertTriangle className="w-4 h-4 mr-1.5" /> Restore & Ganti Data</Button>
            </div>
          )}
          {result && (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm space-y-1" data-testid="restore-result">
              <p className="font-medium text-emerald-600">Restore selesai</p>
              {Object.entries(result).map(([k, v]) => <p key={k} className="text-xs font-mono-data text-muted-foreground">{k}: {v.removed} dihapus → {v.restored} dipulihkan</p>)}
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-red-600">Ganti seluruh data dengan backup?</AlertDialogTitle>
            <AlertDialogDescription>Semua data modul saat ini akan dihapus dan diganti dengan isi file {file?.name}. Tindakan ini tidak dapat dibatalkan — pastikan Anda sudah mengunduh backup terbaru.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="restore-cancel">Batal</AlertDialogCancel>
            <AlertDialogAction onClick={doRestore} className="bg-red-500 hover:bg-red-600" data-testid="restore-confirm">Ya, Restore</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
