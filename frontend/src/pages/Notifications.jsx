import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fmtTs } from "@/components/NotificationBell";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Notifications() {
  const [data, setData] = useState(null);
  const load = useCallback(async () => { const { data } = await api.get("/notifications"); setData(data); }, []);
  useEffect(() => { load(); }, [load]);
  const markAll = async () => { await api.post("/notifications/read", {}); load(); };

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/25 flex items-center justify-center"><Bell className="w-5 h-5 text-primary" /></div>
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">Riwayat Notifikasi</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Pemberitahuan input data yang dikirim ke akun Anda</p>
          </div>
        </div>
        {data?.unread > 0 && <Button variant="outline" size="sm" onClick={markAll} data-testid="notif-page-mark-all"><CheckCheck className="w-4 h-4 mr-1.5" /> Tandai semua dibaca</Button>}
      </div>
      <div className="rounded-lg border border-border bg-card/60 divide-y divide-border/60">
        {!data ? <div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></div>
          : data.items.length === 0 ? <p className="text-sm text-muted-foreground text-center py-16">Belum ada notifikasi. Admin dapat mengaktifkan notifikasi untuk akun Anda di Manajemen User.</p>
          : data.items.map((n, i) => (
            <div key={n.id} data-testid={`notif-row-${i}`} className={cn("px-4 py-3 flex items-start gap-3", !n.read && "bg-primary/5")}>
              <span className={cn("mt-2 w-2 h-2 rounded-full shrink-0", n.read ? "bg-border" : "bg-primary")} />
              <div className="flex-1">
                <p className="text-sm font-medium">{n.title}</p>
                <p className="text-sm text-muted-foreground mt-0.5">{n.message}</p>
              </div>
              <span className="text-xs font-mono-data text-muted-foreground whitespace-nowrap">{fmtTs(n.ts)}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
