import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Cpu, Lightbulb, Boxes, ClipboardList, Scale,
  Users as UsersIcon, LogOut, Factory, Menu, X, Package, ScrollText, Sun, Moon, DatabaseBackup, Gauge,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { canRead } from "@/lib/api";
import { useTheme } from "@/context/ThemeContext";
import NotificationBell from "@/components/NotificationBell";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/smt-stock", label: "Stock Part Production", icon: Boxes, module: "smt_stock" },
  { to: "/production-needs", label: "Kebutuhan Assy VS. Stock Part Production", icon: ClipboardList, module: "production_needs" },
  { to: "/items", label: "Master Item", icon: Package, module: "items" },
  { to: "/audit", label: "Audit Trail", icon: ScrollText, module: "audit" },
  { to: "/backup", label: "Backup & Restore", icon: DatabaseBackup, module: "backup" },
  { to: "/users", label: "Manajemen User", icon: UsersIcon, module: "users" },
];

const ROLE_BADGE = {
  admin: "bg-primary/10 text-primary border-primary/30",
  management: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  production_planning: "bg-blue-500/10 text-blue-600 border-blue-500/30",
  production_control: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  smt: "bg-cyan-500/10 text-cyan-600 border-cyan-500/30",
  assembly: "bg-orange-500/10 text-orange-600 border-orange-500/30",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const nav = NAV.filter((n) => !n.module || canRead(user, n.module));

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const SidebarInner = (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-5 h-16 border-b border-border">
        <div className="w-9 h-9 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
          <Factory className="w-5 h-5 text-primary" />
        </div>
        <div className="leading-tight">
          <p className="font-heading font-bold text-sm text-foreground">PART PRODUCTION F1</p>
          <p className="text-[10px] font-mono-data uppercase tracking-widest text-muted-foreground">Stock & Production</p>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setOpen(false)}
            data-testid={`nav-${item.to === "/" ? "dashboard" : item.to.slice(1)}`}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary border border-primary/25"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent"
              )
            }
          >
            <item.icon className="w-4 h-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-border text-[10px] font-mono-data text-muted-foreground uppercase tracking-widest">
        v1.0 · Manufacturing MES
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border bg-slate-50 fixed inset-y-0 left-0 z-40">
        {SidebarInner}
      </aside>

      {/* Mobile sidebar */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="w-64 bg-card border-r border-border">{SidebarInner}</div>
          <div className="flex-1 bg-black/30" onClick={() => setOpen(false)} />
        </div>
      )}

      <div className="flex-1 lg:ml-64 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-16 flex items-center justify-between px-4 sm:px-6 border-b border-border bg-background/85 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden text-muted-foreground"
              onClick={() => setOpen(!open)}
              data-testid="mobile-menu-toggle"
            >
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <p className="text-xs font-mono-data uppercase tracking-widest text-muted-foreground hidden sm:block">
              PART PRODUCTION F1
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-foreground leading-tight" data-testid="header-user-name">{user?.name}</p>
              <span
                className={cn("inline-block text-[10px] font-mono-data px-2 py-0.5 rounded-full border mt-0.5", ROLE_BADGE[user?.role] || "bg-slate-500/10 text-slate-600 border-slate-500/30")}
                data-testid="header-user-role"
              >
                {user?.role_label}
              </span>
            </div>
            <button onClick={toggle} data-testid="theme-toggle" title={theme === "dark" ? "Mode terang" : "Mode gelap"}
              className="w-9 h-9 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors">
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <NotificationBell />
            <button
              onClick={handleLogout}
              data-testid="logout-button"
              className="w-9 h-9 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-red-600 hover:border-red-500/40 transition-colors"
              title="Keluar"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
