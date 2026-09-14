import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function RecordDialog({ open, onOpenChange, title, fields, initial, onSubmit, submitting }) {
  const [form, setForm] = useState({});

  useEffect(() => {
    if (open) {
      const base = {};
      fields.forEach((f) => (base[f.key] = initial?.[f.key] ?? f.default ?? ""));
      setForm(base);
    }
  }, [open, initial]); // eslint-disable-line

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

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
