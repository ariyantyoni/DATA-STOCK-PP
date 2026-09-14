import { useState, useEffect, useCallback } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { UserPlus, Users as UsersIcon, Trash2, Loader2 } from "lucide-react";

const ROLE_BADGE = {
  admin: "bg-primary/10 text-primary border-primary/30",
  management: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  production_planning: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  production_control: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  smt: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  assembly: "bg-orange-500/10 text-orange-400 border-orange-500/30",
};

export default function Users() {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteId, setDeleteId] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r] = await Promise.all([api.get("/users"), api.get("/roles")]);
      setUsers(u.data);
      setRoles(r.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/auth/register", form);
      toast.success("User berhasil dibuat");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "" });
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    try {
      await api.delete(`/users/${deleteId}`);
      toast.success("User dihapus");
      setDeleteId(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><UsersIcon className="w-5 h-5 text-primary" /></div>
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Manajemen User</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Kelola akun & peran pengguna sistem</p>
          </div>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="add-user-button"><UserPlus className="w-4 h-4 mr-1.5" /> Tambah User</Button>
      </div>

      <div className="rounded-lg border border-border bg-card/60 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-secondary/80 border-b border-border">
              {["Nama", "Email", "Role", "Aksi"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-mono-data text-[11px] uppercase tracking-wider text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-16 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></td></tr>
            ) : users.map((u, i) => (
              <tr key={u.id} data-testid={`user-row-${i}`} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                <td className="px-4 py-3 font-medium">{u.name}</td>
                <td className="px-4 py-3 font-mono-data text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block text-xs font-mono-data px-2 py-0.5 rounded-full border ${ROLE_BADGE[u.role] || "bg-slate-500/10 text-slate-400 border-slate-500/30"}`}>{u.role_label}</span>
                </td>
                <td className="px-4 py-3">
                  {u.role !== "admin" && (
                    <button onClick={() => setDeleteId(u.id)} data-testid={`delete-user-${i}`}
                      className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-red-400 hover:border-red-500/40 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader><DialogTitle className="font-heading">Tambah User Baru</DialogTitle></DialogHeader>
          <form onSubmit={create} className="space-y-4 py-2">
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Nama</Label>
              <Input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} required className="bg-secondary/60 border-border" data-testid="user-name" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Email</Label>
              <Input type="email" value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} required className="bg-secondary/60 border-border" data-testid="user-email" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Password</Label>
              <Input type="password" value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} required className="bg-secondary/60 border-border" data-testid="user-password" /></div>
            <div className="space-y-1.5"><Label className="text-xs text-muted-foreground">Role</Label>
              <Select value={form.role} onValueChange={(v) => setForm((p) => ({ ...p, role: v }))}>
                <SelectTrigger className="bg-secondary/60 border-border" data-testid="user-role"><SelectValue placeholder="Pilih role..." /></SelectTrigger>
                <SelectContent>{roles.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}</SelectContent>
              </Select></div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Batal</Button>
              <Button type="submit" disabled={saving} data-testid="user-save">{saving ? "Menyimpan..." : "Simpan"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={(v) => !v && setDeleteId(null)}>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader><AlertDialogTitle>Hapus user ini?</AlertDialogTitle>
            <AlertDialogDescription>Akun akan kehilangan akses ke sistem.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Batal</AlertDialogCancel>
            <AlertDialogAction onClick={del} className="bg-red-500 hover:bg-red-600" data-testid="user-delete-confirm">Hapus</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
