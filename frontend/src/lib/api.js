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

export const MODULE_ROUTES = {
  smt_production: "/smt-production",
  lamp_production: "/lamp-production",
  smt_stock: "/smt-stock",
  production_needs: "/production-needs",
  variance: "/variance",
  users: "/users",
};

export function permOf(user, module) {
  return user?.effective_permissions?.[module] || "none";
}
export function canRead(user, module) {
  return permOf(user, module) !== "none";
}
export function canWrite(user, module) {
  return permOf(user, module) === "write";
}

export const fmtNum = (v) =>
  v === null || v === undefined || v === "" || isNaN(Number(v))
    ? "-"
    : new Intl.NumberFormat("id-ID").format(Number(v));

export const fmtPct = (v) =>
  v === null || v === undefined || isNaN(Number(v)) ? "-" : `${Number(v).toFixed(1)}%`;

export default api;
