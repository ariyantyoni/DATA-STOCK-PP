import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Scale } from "lucide-react";

export default function Variance() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product", na: "BELUM DIMAPPING" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "total_stock_prev", label: "Total Stock Kemarin", type: "number", align: "right", na: "N/A" },
    { key: "smt_total", label: "Total Produksi SMT", type: "number", align: "right", sum: true },
    { key: "assy_total", label: "Total Produksi Assy", type: "number", align: "right", sum: true },
    { key: "stock_sistem", label: "Stock System", type: "strong", align: "right", na: "N/A" },
    { key: "actual_total_stock", label: "Stock Actual", type: "strong", align: "right", sum: true },
    { key: "variance", label: "Variance", type: "signed", align: "right", sum: true, na: "N/A" },
    { key: "variance_pct", label: "Var %", type: "percent", align: "right", na: "-" },
    { key: "variance_status", label: "Status Variance", type: "status" },
  ];
  return (
    <CrudPage title="Variance Stock"
      subtitle="Stock System = Total Stock Kemarin + Total Produksi SMT − Total Produksi Assy · Variance = Stock Actual − Stock System · Total Produksi diambil otomatis dari Produksi SMT & ASSY (Total Act SMT / Total Act Assy)"
      icon={Scale} endpoint="/variance" dataset="variance" module="variance" readOnly hideAudit
      columns={columns} formFields={[]} note="Stock Actual = Total Stock Hari Ini pada modul Stock SMT"
      filters={["date", "product", "lane", "type", "ics_no", "variance_status"]} options={options} refreshOptions={refresh} />
  );
}
