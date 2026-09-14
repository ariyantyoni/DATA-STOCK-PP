import { useState, useEffect, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import api from "@/lib/api";
import { History } from "lucide-react";

const PREV_KEYS = ["stock_ok_prev", "total_stock_prev"];

export default function RecordDialog({ open, onOpenChange, title, fields, initial, onSubmit, submitting }) {
  const [form, setForm] = useState({});
  const [prev, setPrev] = useState(null);
  const touched = useRef(new Set());
  const hasPrev = fields.some((f) => PREV_KEYS.includes(f.key));

  useEffect(() => {
    if (open) {
      const base = {};
      fields.forEach((f) => (base[f.key] = initial?.[f.key] ?? f.default ?? ""));
      setForm(base);
      setPrev(null);
      touched.current = new Set();
    }
  }, [open, initial]); // eslint-disable-line

  useEffect(() => {
    if (!open || !hasPrev || !form.date || !form.ics_no || initial) return;
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get("/prev-values", { params: { date: form.date, ics_no: form.ics_no } });
        setPrev(data);
        if (data.found) {
          setForm((p) => {
            const n = { ...p };
            PREV_KEYS.forEach((k) => { if (k in n && !touched.current.has(k)) n[k] = data[k]; });
            return n;
          });
        }
      } catch {}
    }, 400);
    return () => clearTimeout(t);
  }, [open, hasPrev, form.date, form.ics_no, initial]);

  const set = (k, v) => { touched.current.add(k); setForm((p) => ({ ...p, [k]: v })); };

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = { ...form };
    fields.forEach((f) => {
      if (f.type === "number") payload[f.key] = payload[f.key] === "" ? 0 : Number(payload[f.key]);
    });
    onSubmit(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-card border-border max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading">{title}</DialogTitle>
          <DialogDescription className="text-muted-foreground">Lengkapi data berikut. Nilai perhitungan otomatis akan dihitung oleh sistem.</DialogDescription>
        </DialogHeader>
        {hasPrev && !initial && prev && (
          <p data-testid="prev-values-hint" className={`text-xs font-mono-data flex items-center gap-1.5 ${prev.found ? "text-emerald-400" : "text-amber-400"}`}>
            <History className="w-3.5 h-3.5" />
            {prev.found ? `Nilai kemarin diambil dari Stock SMT ${prev.source_date} (OK ${prev.stock_ok_prev}, Total ${prev.total_stock_prev})` : "Tidak ada data Stock SMT sebelum tanggal ini — isi nilai kemarin manual"}
          </p>
        )}
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4 py-2">
          {fields.map((f) => (
            <div key={f.key} className={f.full ? "col-span-2 space-y-1.5" : "space-y-1.5"}>
              <Label className="text-xs text-muted-foreground">{f.label}</Label>
              {f.type === "select" ? (
                <Select value={form[f.key] || ""} onValueChange={(v) => set(f.key, v)}>
                  <SelectTrigger className="bg-secondary/60 border-border" data-testid={`field-${f.key}`}>
                    <SelectValue placeholder="Pilih..." />
                  </SelectTrigger>
                  <SelectContent>
                    {f.options.map((o) => (
                      <SelectItem key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : f.type === "textarea" ? (
                <Textarea value={form[f.key] || ""} onChange={(e) => set(f.key, e.target.value)}
                  className="bg-secondary/60 border-border" data-testid={`field-${f.key}`} />
              ) : (
                <Input type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  step="any" value={form[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)}
                  required={f.required} className="bg-secondary/60 border-border font-mono-data"
                  data-testid={`field-${f.key}`} />
              )}
            </div>
          ))}
          <DialogFooter className="col-span-2 mt-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} data-testid="record-cancel">Batal</Button>
            <Button type="submit" disabled={submitting} data-testid="record-save">{submitting ? "Menyimpan..." : "Simpan"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
