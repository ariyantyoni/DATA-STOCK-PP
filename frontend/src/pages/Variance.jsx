import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Scale } from "lucide-react";

export default function Variance() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "part_number", label: "Part Number", mono: true },
    { key: "system_stock", label: "Stock System", type: "number", align: "right" },
    { key: "physical_stock", label: "Stock Fisik", type: "number", align: "right" },
    { key: "variance", label: "Variance", type: "signed", align: "right" },
    { key: "variance_pct", label: "Variance %", type: "percent", align: "right" },
    { key: "accuracy", label: "Akurasi %", type: "percent", tone: true, align: "right" },
    { key: "variance_status", label: "Status", type: "status" },
    { key: "reason", label: "Alasan" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: new Date().toISOString().slice(0, 10) },
    { key: "part_number", label: "Part Number", type: "text", required: true },
    { key: "type", label: "Type", type: "text" },
    { key: "system_stock", label: "Stock System", type: "number" },
    { key: "physical_stock", label: "Stock Fisik (Opname)", type: "number" },
    { key: "reason", label: "Alasan Selisih", type: "textarea", full: true },
  ];
  return (
    <CrudPage title="Variance Stock" subtitle="Perbandingan stock system vs fisik (opname) — variance & akurasi otomatis"
      icon={Scale} endpoint="/variance" dataset="variance" module="variance"
      columns={columns} formFields={formFields}
      filters={["date", "type", "part_number", "variance_status"]} options={options} refreshOptions={refresh} />
  );
}
