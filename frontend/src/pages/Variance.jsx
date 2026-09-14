import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Scale } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function Variance() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "total_stock_prev", label: "Total Stock Kemarin", type: "number", align: "right" },
    { key: "smt_total", label: "Total SMT", type: "number", align: "right" },
    { key: "assy_total", label: "Total Assy", type: "number", align: "right" },
    { key: "actual_total_stock", label: "Actual Total Stock", type: "strong", align: "right" },
    { key: "stok_jam", label: "Stok Jam 01.00", type: "number", align: "right" },
    { key: "stock_sistem", label: "Stock Sistem", type: "strong", align: "right" },
    { key: "variance", label: "Variance", type: "signed", align: "right" },
    { key: "variance_pct", label: "Var %", type: "percent", align: "right" },
    { key: "variance_status", label: "Status", type: "status" },
    { key: "reason", label: "Keterangan" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "total_stock_prev", label: "Total Stock Kemarin", type: "number" },
    { key: "actual_total_stock", label: "Actual Total Stock Hari Ini", type: "number" },
    { key: "smt_total", label: "Total Produksi SMT", type: "number" },
    { key: "assy_total", label: "Total Produksi Assy", type: "number" },
    { key: "smt3", label: "SMT Shift 3 (untuk Stok Jam 01.00)", type: "number" },
    { key: "assy3", label: "Assy Shift 3 (untuk Stok Jam 01.00)", type: "number" },
    { key: "reason", label: "Keterangan Selisih", type: "textarea", full: true },
  ];
  return (
    <CrudPage title="Variance Stock" subtitle="Stock Sistem = Stock Kemarin + SMT − Assy · Variance = Actual − Sistem · Stok Jam 01.00 = Actual − SMT Sh3 + Assy Sh3"
      icon={Scale} endpoint="/variance" dataset="variance" module="variance"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no", "variance_status"]} options={options} refreshOptions={refresh} />
  );
}
