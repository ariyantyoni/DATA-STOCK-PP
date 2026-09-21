import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import Layout from "@/components/Layout";
import AuditTrail from "@/pages/AuditTrail";
import Notifications from "@/pages/Notifications";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import SMTProduction from "@/pages/SMTProduction";
import SMTStock from "@/pages/SMTStock";
import ProductionNeeds from "@/pages/ProductionNeeds";
import Variance from "@/pages/Variance";
import Users from "@/pages/Users";
import MasterItems from "@/pages/MasterItems";
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
      <ThemeProvider>
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
              <Route path="smt-stock" element={<Guard module="smt_stock"><SMTStock /></Guard>} />
              <Route path="production-needs" element={<Guard module="production_needs"><ProductionNeeds /></Guard>} />
              <Route path="variance" element={<Guard module="variance"><Variance /></Guard>} />
              <Route path="items" element={<Guard module="items"><MasterItems /></Guard>} />
              <Route path="audit" element={<Guard module="audit"><AuditTrail /></Guard>} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="users" element={<Guard module="users"><Users /></Guard>} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
      </ThemeProvider>
    </div>
  );
}

export default App;
