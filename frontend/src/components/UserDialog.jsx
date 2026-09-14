import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const LEVEL_STYLE = {
  none: "bg-slate-500/15 text-slate-300 border-slate-500/40",
  read: "bg-sky-500/15 text-sky-300 border-sky-500/40",
  write: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
};

export default function UserDialog({ open, onOpenChange, editing, roles, modules, levels, onSubmit, saving }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "", permissions: {} });
  const isMainAdmin = editing?.is_main_admin;

  useEffect(() => {
    if (open) setForm({
      name: editing?.name || "", email: editing?.email || "", password: "",
      role: editing?.role || "", permissions: { ...(editing?.permissions || {}) },
    });
  }, [open, editing]);

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const roleDefaults = roles.find((r) => r.value === form.role)?.defaults || {};
  const effective = (m) => form.permissions[m] || roleDefaults[m] || "none";
  const setPerm = (m, lvl) => setForm((p) => {
    const perms = { ...p.permissions };
    if (lvl === roleDefaults[m]) delete perms[m]; else perms[m] = lvl;
    return { ...p, permissions: perms };
  });

  const submit = (e) => {
    e.preventDefault();
    const payload = { name: form.name, role: form.role, permissions: form.permissions };
    if (!editing) payload.email = form.email;
    if (form.password) payload.password = form.password;
    onSubmit(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-card border-border max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading">{editing ? "Edit User" : "Tambah User Baru"}</DialogTitle>
          <DialogDescription className="text-muted-foreground">Atur akun, role, dan hak akses per modul. Hak akses default mengikuti role; ubah untuk override.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Nama</Label>
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} required className="bg-secondary/60 border-border" data-testid="user-name" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Email</Label>
              <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required disabled={!!editing} className="bg-secondary/60 border-border" data-testid="user-email" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">{editing ? "Password baru (kosongkan jika tidak diubah)" : "Password"}</Label>
              <Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required={!editing} minLength={6} className="bg-secondary/60 border-border" data-testid="user-password" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Role</Label>
              <Select value={form.role} onValueChange={(v) => set("role", v)} disabled={isMainAdmin}>
                <SelectTrigger className="bg-secondary/60 border-border" data-testid="user-role"><SelectValue placeholder="Pilih role..." /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.value} value={r.value} data-testid={`role-option-${r.value}`}>{r.label}</SelectItem>)}</SelectContent>
              </Select></div>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground uppercase tracking-wider font-mono-data">Hak Akses Modul</Label>
            <div className="rounded-lg border border-border divide-y divide-border/60" data-testid="permissions-grid">
              {modules.map((m) => (
                <div key={m.key} className="flex items-center justify-between gap-3 px-3 py-2">
                  <div>
                    <p className="text-sm">{m.label}</p>
                    {form.permissions[m.key] && <p className="text-[10px] text-amber-400 font-mono-data">override (default: {levels.find((l) => l.value === roleDefaults[m.key])?.label || "Tidak ada"})</p>}
                  </div>
                  <div className="inline-flex rounded-md border border-border overflow-hidden">
                    {levels.map((l) => (
                      <button type="button" key={l.value} disabled={isMainAdmin || !form.role}
                        onClick={() => setPerm(m.key, l.value)} data-testid={`perm-${m.key}-${l.value}`}
                        className={cn("px-3 py-1 text-xs font-mono-data border-r last:border-r-0 border-border transition-colors",
                          effective(m.key) === l.value ? LEVEL_STYLE[l.value] : "text-muted-foreground hover:bg-secondary",
                          (isMainAdmin || !form.role) && "opacity-60 cursor-not-allowed")}>
                        {l.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {!form.role && <p className="text-xs text-muted-foreground">Pilih role terlebih dahulu untuk mengatur hak akses.</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} data-testid="user-cancel">Batal</Button>
            <Button type="submit" disabled={saving || !form.role} data-testid="user-save">{saving ? "Menyimpan..." : "Simpan"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
