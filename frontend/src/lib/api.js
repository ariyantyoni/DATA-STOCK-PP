import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("cds_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Terjadi kesalahan. Silakan coba lagi.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

// Role-based write permissions (mirror of backend)
export const WRITE_ROLES = {
  smt_production: ["admin", "management", "production_control", "smt"],
  lamp_production: ["admin", "management", "production_control", "assembly"],
  smt_stock: ["admin", "management", "production_planning", "smt"],
  production_needs: ["admin", "management", "production_planning"],
  variance: ["admin", "management", "production_planning", "production_control"],
  users: ["admin"],
};

export function canWrite(role, module) {
  return (WRITE_ROLES[module] || []).includes(role);
}

export const fmtNum = (v) =>
  v === null || v === undefined || v === "" || isNaN(Number(v))
    ? "-"
    : new Intl.NumberFormat("id-ID").format(Number(v));

export const fmtPct = (v) =>
  v === null || v === undefined || isNaN(Number(v)) ? "-" : `${Number(v).toFixed(1)}%`;

export default api;
