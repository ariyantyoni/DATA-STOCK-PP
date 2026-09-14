import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { ClipboardList } from "lucide-react";

export default function ProductionNeeds() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "part_number", label: "Part Number", mono: true },
    { key: "model", label: "Sumber / MPS" },
    { key: "required_qty", label: "Kebutuhan", type: "number", align: "right" },
    { key: "stock_actual", label: "Stock Aktual", type: "number", align: "right" },
    { key: "balance", label: "Balance", type: "signed", align: "right" },
    { key: "shortage_qty", label: "Shortage", type: "number", align: "right" },
    { key: "fulfillment", label: "Terpenuhi %", type: "percent", tone: true, align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: new Date().toISOString().slice(0, 10) },
    { key: "part_number", label: "Part Number", type: "text", required: true },
    { key: "model", label: "Sumber / MPS", type: "text", default: "MPS Mingguan" },
    { key: "type", label: "Type", type: "text" },
    { key: "required_qty", label: "Kebutuhan (Qty)", type: "number" },
  ];
  return (
    <CrudPage title="Kebutuhan vs Stock" subtitle="Perbandingan kebutuhan produksi dengan stok aktual — shortage dihitung otomatis"
      icon={ClipboardList} endpoint="/production-needs" dataset="production-needs" module="production_needs"
      columns={columns} formFields={formFields}
      filters={["date", "type", "part_number", "needs_status"]} options={options} refreshOptions={refresh} />
  );
}
