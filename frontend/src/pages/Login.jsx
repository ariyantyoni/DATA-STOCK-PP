import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, formatApiErrorDetail } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Factory, Loader2, Cpu } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left: brand / image */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden border-r border-border">
        <img src="https://images.unsplash.com/photo-1581091212991-8891c7d4bd9b?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400"
          alt="SMT Manufacturing" className="absolute inset-0 w-full h-full object-cover opacity-30" />
        <div className="absolute inset-0 bg-background/70" />
        <div className="relative z-10 flex flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
              <Factory className="w-6 h-6 text-primary" />
            </div>
            <div>
              <p className="font-heading font-bold text-lg">Control Data</p>
              <p className="text-xs font-mono-data uppercase tracking-widest text-muted-foreground">Stock & Production</p>
            </div>
          </div>
          <div>
            <h1 className="font-heading text-4xl font-bold tracking-tight leading-tight">
              Monitoring Produksi & Stock<br /><span className="text-primary">SMT & LAMP ASSY</span>
            </h1>
            <p className="text-muted-foreground mt-4 max-w-md">
              Platform terpusat untuk memantau hasil produksi harian, stok komponen SMT, kebutuhan produksi, dan variance — menggantikan laporan Excel manual dengan perhitungan otomatis.
            </p>
            <div className="flex items-center gap-2 mt-6 text-xs font-mono-data text-muted-foreground uppercase tracking-widest">
              <Cpu className="w-4 h-4 text-primary" /> Automotive Manufacturing MES
            </div>
          </div>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm fade-up">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center">
              <Factory className="w-5 h-5 text-primary" />
            </div>
            <p className="font-heading font-bold text-lg">Control Data</p>
          </div>
          <h2 className="font-heading text-2xl font-bold">Masuk ke Sistem</h2>
          <p className="text-sm text-muted-foreground mt-1 mb-6">Gunakan akun yang telah diberikan admin.</p>

          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                placeholder="nama@perusahaan.co.id" className="bg-secondary/60 border-border h-11" data-testid="login-email" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                placeholder="••••••••" className="bg-secondary/60 border-border h-11" data-testid="login-password" />
            </div>
            {error && <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2" data-testid="login-error">{error}</p>}
            <Button type="submit" disabled={loading} className="w-full h-11" data-testid="login-submit">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Masuk"}
            </Button>
          </form>

          <div className="mt-6 text-xs text-muted-foreground bg-secondary/40 border border-border rounded-md p-3 font-mono-data">
            <p className="text-foreground mb-1">Akun demo:</p>
            <p>manager@cds.co.id / password123 (Management)</p>
            <p>ppic@cds.co.id / password123 (PPIC)</p>
            <p>smt@cds.co.id / password123 (SMT)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
