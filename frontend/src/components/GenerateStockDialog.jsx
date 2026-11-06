import { useEffect, useState } from "react";
import api, { fmtNum, formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { CalendarPlus, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const fmtTs = (v) => (v ? new Date(v).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" }) : "-");

function Logs({ logs }) {
  if (!logs.length) return <p className="text-xs text-muted-foreground">Belum ada riwayat generate.</p>;
  return (
    <div className="border border-border rounded-md max-h-56 overflow-auto">
      <table className="w-full text-xs font-mono-data">
        <thead className="bg-secondary sticky top-0">
          <tr>{["Tanggal", "Sumber", "Status", "Baru", "Sudah ada", "Waktu (WIB)"].map((h) => <th key={h} className="px-2 py-1 text-left">{h}</th>)}</tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id} className="border-t border-border/60" data-testid={`generate-log-${l.id}`}>
              <td className="px-2 py-1">{l.date}</td>
              <td className="px-2 py-1">{l.source}</td>
              <td className={cn("px-2 py-1 font-bold", l.status === "SUCCESS" ? "text-emerald-600" : l.status === "FAILED" ? "text-red-600" : "text-amber-600")}
                title={l.error || undefined}>{l.status}</td>
              <td className="px-2 py-1 text-right">{fmtNum(l.inserted ?? 0)}</td>
              <td className="px-2 py-1 text-right">{fmtNum(l.existing ?? 0)}</td>
              <td className="px-2 py-1">{fmtTs(l.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function GenerateStockDialog({ open, onOpenChange, today, onDone }) {
  const [date, setDate] = useState(today);
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState([]);

  const loadLogs = () => api.get("/smt-stock/generate-logs").then(({ data }) => setLogs(data)).catch(() => {});
  useEffect(() => { if (open) { setDate(today); loadLogs(); } }, [open, today]);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/smt-stock/generate", { date });
      toast.success(`Generate ${data.date}: ${fmtNum(data.inserted)} baris baru, ${fmtNum(data.existing)} sudah ada (tidak diduplikasi)`);
      loadLogs();
      onDone?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
      loadLogs();
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl grid-cols-[minmax(0,1fr)] bg-card border-border" data-testid="generate-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><CalendarPlus className="w-5 h-5 text-primary" /> Generate Data Harian</DialogTitle>
          <DialogDescription>
            Membuat baris SHIFT 3, SHIFT 1, SHIFT 2 untuk semua item Master Item pada tanggal terpilih dengan input stok kosong.
            Otomatis berjalan setiap hari pukul 00:01 WIB. Aman dijalankan ulang: data yang sudah ada tidak ditimpa dan tidak diduplikasi.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Tanggal operasional</label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="h-9 w-44" data-testid="generate-date-input" />
          </div>
          <Button onClick={run} disabled={busy || !date} data-testid="generate-run-button">
            {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <CalendarPlus className="w-4 h-4 mr-1.5" />} Generate Sekarang
          </Button>
        </div>
        <div className="space-y-1.5">
          <p className="text-xs font-semibold">Riwayat generate</p>
          <Logs logs={logs} />
        </div>
        <DialogFooter><Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="generate-close-button">Tutup</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
