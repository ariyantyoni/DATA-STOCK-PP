import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { UploadCloud, FileSpreadsheet, Loader2, Download } from "lucide-react";
import { cn } from "@/lib/utils";

const MODES = [
  { v: "add", label: "Tambah Data", desc: "Hanya baris baru; data yang sudah ada dilewati" },
  { v: "update", label: "Update Data", desc: "Perbarui data existing (Tanggal + ICS NO + TYPE) dan tambah yang baru" },
];
const ACTION_CLS = {
  baru: "bg-emerald-500/10 text-emerald-700", diperbarui: "bg-sky-500/10 text-sky-700",
  dilewati: "bg-slate-500/10 text-slate-600", gagal: "bg-red-500/10 text-red-700",
};
const COUNT_LABEL = [["total", "Total baris"], ["baru", "Baru"], ["diperbarui", "Diperbarui"], ["dilewati", "Dilewati"], ["gagal", "Gagal"]];

function Counts({ counts, testId }) {
  return (
    <div className="flex flex-wrap gap-2 text-xs font-mono-data" data-testid={testId}>
      {COUNT_LABEL.map(([k, l]) => (
        <span key={k} data-testid={`${testId}-${k}`} className={cn("px-2 py-1 rounded-md border border-border", ACTION_CLS[k])}>{l}: {counts[k] ?? 0}</span>
      ))}
    </div>
  );
}

function PreviewTable({ preview }) {
  const cols = preview.input_columns;
  return (
    <div className="border border-border rounded-lg overflow-auto max-h-[40vh]">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-secondary">
          <tr>{["Baris", "Aksi", "TANGGAL", "ICS NO", "TYPE", ...cols, "Keterangan"].map((c) => <th key={c} className="px-2 py-1.5 text-left font-mono-data whitespace-nowrap">{c.toUpperCase()}</th>)}</tr>
        </thead>
        <tbody>
          {preview.rows.map((r) => (
            <tr key={r.row} className="border-t border-border/60" data-testid={`needs-import-row-${r.row}`}>
              <td className="px-2 py-1 font-mono-data">{r.row}</td>
              <td className="px-2 py-1"><span className={cn("px-1.5 py-0.5 rounded font-bold uppercase text-[10px]", ACTION_CLS[r.action])}>{r.action}</span></td>
              <td className="px-2 py-1 font-mono-data whitespace-nowrap">{r.date || "-"}</td>
              <td className="px-2 py-1 font-mono-data">{r.ics_no || "-"}</td>
              <td className="px-2 py-1 whitespace-nowrap">{r.type || "-"}</td>
              {cols.map((c) => <td key={c} className="px-2 py-1 font-mono-data text-right">{r.values[c] ?? "-"}</td>)}
              <td className="px-2 py-1 text-red-600 whitespace-nowrap">{[...r.errors, r.note].filter(Boolean).join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function NeedsImportDialog({ open, onOpenChange, date, onDone }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("update");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef();
  const reset = () => { setFile(null); setPreview(null); setResult(null); };

  const runPreview = async (f, m) => {
    if (!f) return;
    setFile(f); setBusy(true); setResult(null);
    try {
      const fd = new FormData(); fd.append("file", f); fd.append("mode", m);
      const { data } = await api.post("/needs-grid/import/preview", fd);
      setPreview(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail)); reset();
    } finally { setBusy(false); }
  };

  const changeMode = (m) => { setMode(m); if (file) runPreview(file, m); };

  const confirm = async () => {
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("file", file); fd.append("mode", mode);
      const { data } = await api.post("/needs-grid/import/confirm", fd);
      setResult(data); setPreview(null);
      toast.success(`Import selesai: ${data.counts.baru} baru, ${data.counts.diperbarui} diperbarui`);
      onDone?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  const downloadTemplate = async () => {
    try {
      const res = await api.get("/needs-grid/import/template", { params: { date }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `kebutuhan_assy_${date}.xlsx`; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Gagal mengunduh template"); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) reset(); }}>
      <DialogContent className="max-w-4xl bg-card border-border max-h-[90vh] overflow-y-auto" data-testid="needs-import-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2"><FileSpreadsheet className="w-5 h-5 text-primary" /> Import Excel · Kebutuhan Assy</DialogTitle>
          <DialogDescription>Kolom wajib: TANGGAL, ICS NO, TYPE. Kolom yang diimpor: PLAN/ACTUAL CUSTOMER (ASSY), PLAN/ACTUAL S3/S1/S2, STATUS MESIN. Kolom master & hasil hitung diabaikan. Cell kosong tidak menimpa data yang sudah ada.</DialogDescription>
        </DialogHeader>
        <button type="button" onClick={downloadTemplate} data-testid="needs-import-template" className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline w-fit">
          <Download className="w-3.5 h-3.5" /> Unduh template (isi tanggal {date})
        </button>
        <div className="grid sm:grid-cols-2 gap-2" data-testid="needs-import-mode">
          {MODES.map((m) => (
            <button key={m.v} type="button" onClick={() => changeMode(m.v)} data-testid={`needs-import-mode-${m.v}`}
              className={cn("text-left rounded-lg border p-3 transition-colors", mode === m.v ? "border-primary bg-primary/10" : "border-border hover:border-primary/40")}>
              <p className="text-sm font-semibold">{m.label}</p>
              <p className="text-xs text-muted-foreground">{m.desc}</p>
            </button>
          ))}
        </div>

        {!preview && !result && (
          <div onClick={() => inputRef.current?.click()} onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); runPreview(e.dataTransfer.files[0], mode); }} data-testid="needs-import-dropzone"
            className="border-2 border-dashed border-border rounded-lg py-10 flex flex-col items-center gap-2 cursor-pointer hover:border-primary/50 transition-colors">
            {busy ? <Loader2 className="w-8 h-8 text-primary animate-spin" /> : <UploadCloud className="w-10 h-10 text-muted-foreground" />}
            <p className="text-sm font-medium">Tarik & lepas file Excel di sini, atau klik untuk memilih</p>
            <p className="text-xs text-muted-foreground">.xlsx, .xls, .csv</p>
            <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv" hidden data-testid="needs-import-file-input"
              onChange={(e) => { runPreview(e.target.files[0], mode); e.target.value = ""; }} />
          </div>
        )}

        {preview && (
          <div className="space-y-3">
            <p className="text-xs font-mono-data text-muted-foreground">{file?.name} · kolom input: {preview.input_columns.join(", ").toUpperCase()}</p>
            <Counts counts={preview.counts} testId="needs-import-preview-counts" />
            {preview.unknown_columns.length > 0 && <p className="text-xs text-amber-600" data-testid="needs-import-unknown">Kolom tidak dikenal (diabaikan): {preview.unknown_columns.join(", ")}</p>}
            <PreviewTable preview={preview} />
          </div>
        )}

        {result && (
          <div className="space-y-3" data-testid="needs-import-result">
            <p className="text-sm font-semibold">Ringkasan hasil import</p>
            <Counts counts={result.counts} testId="needs-import-result-counts" />
            {result.failed.length > 0 && (
              <ul className="text-xs text-red-600 max-h-40 overflow-auto list-disc pl-5">
                {result.failed.map((r) => <li key={r.row}>Baris {r.row}: {r.errors.join("; ")}</li>)}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          {(preview || result) && <Button variant="ghost" onClick={reset} data-testid="needs-import-reset">Pilih file lain</Button>}
          {result ? (
            <Button onClick={() => { onOpenChange(false); reset(); }} data-testid="needs-import-close">Selesai</Button>
          ) : (
            <Button disabled={!preview || busy || (preview.counts.baru + preview.counts.diperbarui === 0)} onClick={confirm} data-testid="needs-import-confirm">
              {busy ? "Mengimpor..." : "Konfirmasi & Simpan"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
