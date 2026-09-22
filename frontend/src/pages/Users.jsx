import { useState, useEffect, useCallback } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import UserDialog from "@/components/UserDialog";
import { UserPlus, Users as UsersIcon, Trash2, Pencil, Loader2, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const ROLE_BADGE = {
  admin: "bg-primary/10 text-primary border-primary/30",
  management: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  production_planning: "bg-blue-500/10 text-blue-600 border-blue-500/30",
  production_control: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  smt: "bg-cyan-500/10 text-cyan-600 border-cyan-500/30",
  assembly: "bg-orange-500/10 text-orange-600 border-orange-500/30",
};
const LEVEL_DOT = { none: "bg-slate-600", read: "bg-sky-500", write: "bg-emerald-500" };
const SHORT = { smt_production: "SMT", smt_stock: "STOCK", production_needs: "KEBUTUHAN", variance: "VARIANCE", items: "ITEM", audit: "AUDIT", backup: "BACKUP", users: "USER" };

export default function Users() {
  const { user: me, setUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [meta, setMeta] = useState({ modules: [], levels: [] });
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteId, setDeleteId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r, m] = await Promise.all([api.get("/users"), api.get("/roles"), api.get("/meta/modules")]);
      setUsers(u.data); setRoles(r.data); setMeta(m.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (payload) => {
    setSaving(true);
    try {
      if (editing) {
        const { data } = await api.put(`/users/${editing.id}`, payload);
        if (data.id === me.id) setUser(data);
        toast.success("User diperbarui");
      } else {
        await api.post("/users", payload);
        toast.success("User berhasil dibuat");
      }
      setOpen(false); setEditing(null); load();
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
      setDeleteId(null); load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><UsersIcon className="w-5 h-5 text-primary" /></div>
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Manajemen User</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Tambah, edit, hapus akun & atur hak akses per modul</p>
          </div>
        </div>
        <Button onClick={() => { setEditing(null); setOpen(true); }} data-testid="add-user-button"><UserPlus className="w-4 h-4 mr-1.5" /> Tambah User</Button>
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground font-mono-data">
        {meta.levels.map((l) => <span key={l.value} className="inline-flex items-center gap-1.5"><span className={cn("w-2 h-2 rounded-full", LEVEL_DOT[l.value])} />{l.label}</span>)}
      </div>

      <div className="rounded-lg border border-border bg-card/60 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-secondary/80 border-b border-border">
              {["Nama", "Username", "Email", "Role", "Hak Akses Modul", "Aksi"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-mono-data text-[11px] uppercase tracking-wider text-muted-foreground whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-16 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></td></tr>
            ) : users.map((u, i) => {
              const isMain = !!u.is_main_admin;
              return (
                <tr key={u.id} data-testid={`user-row-${i}`} className="border-b border-border/50 hover:bg-secondary/40 transition-colors">
                  <td className="px-4 py-3 font-medium whitespace-nowrap">{u.name}{isMain && <ShieldCheck className="inline w-3.5 h-3.5 ml-1.5 text-primary" />}</td>
                  <td className="px-4 py-3 font-mono-data text-foreground" data-testid={`user-username-${i}`}>{u.username}</td>
                  <td className="px-4 py-3 font-mono-data text-muted-foreground">{u.email || "-"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block text-xs font-mono-data px-2 py-0.5 rounded-full border whitespace-nowrap ${ROLE_BADGE[u.role] || "bg-slate-500/10 text-slate-600 border-slate-500/30"}`}>{u.role_label}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5" data-testid={`user-perms-${i}`}>
                      {meta.modules.map((m) => {
                        const lvl = u.effective_permissions?.[m.key] || "none";
                        return (
                          <span key={m.key} title={`${m.label}: ${lvl}`}
                            className={cn("inline-flex items-center gap-1 text-[10px] font-mono-data px-1.5 py-0.5 rounded border border-border/70",
                              u.permissions?.[m.key] && "border-amber-500/50")}>
                            <span className={cn("w-1.5 h-1.5 rounded-full", LEVEL_DOT[lvl])} />{SHORT[m.key]}
                          </span>
                        );
                      })}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="inline-flex gap-1">
                      <button onClick={() => { setEditing({ ...u, is_main_admin: isMain }); setOpen(true); }} data-testid={`edit-user-${i}`}
                        className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                      {!isMain && u.id !== me.id && (
                        <button onClick={() => setDeleteId(u.id)} data-testid={`delete-user-${i}`}
                          className="w-8 h-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-red-600 hover:border-red-500/40 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <UserDialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setEditing(null); }} editing={editing}
        roles={roles} modules={meta.modules} levels={meta.levels} onSubmit={save} saving={saving} />

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
