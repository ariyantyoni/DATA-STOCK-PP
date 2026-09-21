import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Bell, CheckCheck } from "lucide-react";
import { cn } from "@/lib/utils";

export const fmtTs = (iso) => (iso ? new Date(iso).toLocaleString("id-ID", { dateStyle: "short", timeStyle: "short" }) : "-");

export default function NotificationBell() {
  const [data, setData] = useState({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/notifications"); setData(data); } catch {}
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const markAll = async () => { await api.post("/notifications/read", {}); load(); };
  const markOne = async (id) => { await api.post("/notifications/read", { ids: [id] }); load(); };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button data-testid="notif-bell" title="Notifikasi"
          className="relative w-9 h-9 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors">
          <Bell className="w-4 h-4" />
          {data.unread > 0 && (
            <span data-testid="notif-badge" className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-mono-data flex items-center justify-center">
              {data.unread > 99 ? "99+" : data.unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0 bg-card border-border">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
          <p className="text-sm font-semibold font-heading">Notifikasi</p>
          {data.unread > 0 && (
            <button onClick={markAll} data-testid="notif-mark-all" className="text-xs text-primary inline-flex items-center gap-1 hover:underline"><CheckCheck className="w-3.5 h-3.5" /> Tandai semua dibaca</button>
          )}
        </div>
        <div className="max-h-80 overflow-y-auto divide-y divide-border/60">
          {data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">Belum ada notifikasi</p>
          ) : data.items.slice(0, 10).map((n) => (
            <button key={n.id} onClick={() => !n.read && markOne(n.id)} data-testid="notif-item"
              className={cn("w-full text-left px-4 py-2.5 hover:bg-secondary/60 transition-colors", !n.read && "bg-primary/5")}>
              <div className="flex items-start gap-2">
                {!n.read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />}
                <div className={cn(n.read && "pl-3.5")}>
                  <p className="text-sm font-medium">{n.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{n.message}</p>
                  <p className="text-[10px] font-mono-data text-muted-foreground mt-1">{fmtTs(n.ts)}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
        <Link to="/notifications" onClick={() => setOpen(false)} data-testid="notif-history-link"
          className="block text-center text-xs text-primary py-2.5 border-t border-border hover:underline">Lihat semua riwayat</Link>
      </PopoverContent>
    </Popover>
  );
}
