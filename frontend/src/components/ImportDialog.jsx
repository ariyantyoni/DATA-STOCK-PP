import { useState, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { UploadCloud, FileSpreadsheet, Loader2 } from "lucide-react";

export default function ImportDialog({ open, onOpenChange, dataset, title, onDone }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const inputRef = useRef();

  const reset = () => { setFile(null); setPreview(null); };

  const handleFile = async (f) => {
    if (!f) return;
    setFile(f);
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const { data } = await api.post(`/import/${dataset}/preview`, fd);
      setPreview(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
      reset();
    } finally {
      setLoading(false);
    }
  };

  const confirm = async () => {
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/import/${dataset}/confirm`, fd);
      toast.success(`${data.inserted} baris berhasil diimpor`);
      reset();
      onOpenChange(false);
      onDone?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) reset(); }}>
      <DialogContent className="max-w-3xl bg-card border-border max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-primary" /> Import {title}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">Unggah file Excel/CSV, pratinjau data, lalu konfirmasi untuk menyimpan.</DialogDescription>
        </DialogHeader>

        {!preview && (
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); }}
            className="border-2 border-dashed border-border rounded-lg py-12 flex flex-col items-center justify-center gap-3 cursor-pointer hover:border-primary/50 transition-colors"
            data-testid="import-dropzone"
          >
            {loading ? <Loader2 className="w-8 h-8 text-primary animate-spin" /> : <UploadCloud className="w-10 h-10 text-muted-foreground" />}
            <p className="text-sm text-foreground font-medium">Tarik & lepas file Excel/CSV di sini</p>
            <p className="text-xs text-muted-foreground">atau klik untuk memilih (.xlsx, .xls, .csv)</p>
            <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" hidden
              onChange={(e) => handleFile(e.target.files[0])} data-testid="import-file-input" />
          </div>
        )}

        {preview && (
          <div className="space-y-3">
            <p className="text-xs font-mono-data text-muted-foreground">
              {file?.name} · {preview.total} baris terdeteksi · menampilkan {preview.rows.length}
            </p>
            <div className="border border-border rounded-lg overflow-auto max-h-[45vh]">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-secondary">
                  <tr>{preview.columns.map((c) => <th key={c} className="px-3 py-2 text-left font-mono-data text-muted-foreground whitespace-nowrap">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.rows.map((r, i) => (
                    <tr key={i} className="border-t border-border/60">
                      {preview.columns.map((c) => <td key={c} className="px-3 py-1.5 font-mono-data whitespace-nowrap">{String(r[c] ?? "")}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <DialogFooter>
          {preview && <Button variant="ghost" onClick={reset} data-testid="import-back">Pilih file lain</Button>}
          <Button disabled={!preview || importing} onClick={confirm} data-testid="import-confirm">
            {importing ? "Mengimpor..." : "Konfirmasi & Simpan"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
