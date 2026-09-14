import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import SMTProduction from "@/pages/SMTProduction";
import LampProduction from "@/pages/LampProduction";
import SMTStock from "@/pages/SMTStock";
import ProductionNeeds from "@/pages/ProductionNeeds";
import Variance from "@/pages/Variance";
import Users from "@/pages/Users";
import { Loader2 } from "lucide-react";
import { canRead } from "@/lib/api";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading || user === null)
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Guard({ module, children }) {
  const { user } = useAuth();
  if (!canRead(user, module))
    return (
      <div className="py-24 text-center text-muted-foreground" data-testid="no-access">
        Anda tidak memiliki akses ke modul ini.
      </div>
    );
  return children;
}

function App() {
  return (
    <div className="App min-h-screen">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <Protected>
                  <Layout />
                </Protected>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="smt-production" element={<Guard module="smt_production"><SMTProduction /></Guard>} />
              <Route path="lamp-production" element={<Guard module="lamp_production"><LampProduction /></Guard>} />
              <Route path="smt-stock" element={<Guard module="smt_stock"><SMTStock /></Guard>} />
              <Route path="production-needs" element={<Guard module="production_needs"><ProductionNeeds /></Guard>} />
              <Route path="variance" element={<Guard module="variance"><Variance /></Guard>} />
              <Route path="users" element={<Guard module="users"><Users /></Guard>} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
