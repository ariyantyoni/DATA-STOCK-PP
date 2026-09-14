import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Boxes } from "lucide-react";

export default function SMTStock() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "part_number", label: "Part Number", mono: true },
    { key: "description", label: "Deskripsi" },
    { key: "unit", label: "Unit" },
    { key: "actual_stock", label: "Stock Aktual", type: "number", align: "right" },
    { key: "safety_stock", label: "Safety Stock", type: "number", align: "right" },
    { key: "reorder_level", label: "Reorder Level", type: "number", align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "part_number", label: "Part Number", type: "text", required: true },
    { key: "description", label: "Deskripsi", type: "text", full: true },
    { key: "type", label: "Type", type: "text" },
    { key: "unit", label: "Unit (Reel/Tray/Pcs)", type: "text", default: "Reel" },
    { key: "actual_stock", label: "Stock Aktual", type: "number" },
    { key: "safety_stock", label: "Safety Stock", type: "number" },
    { key: "reorder_level", label: "Reorder Level", type: "number" },
  ];
  return (
    <CrudPage title="Stock SMT" subtitle="Monitoring stok komponen SMT dengan status AMAN / REORDER / CRITICAL otomatis"
      icon={Boxes} endpoint="/smt-stock" dataset="smt-stock" module="smt_stock"
      columns={columns} formFields={formFields}
      filters={["type", "part_number", "stock_status"]} options={options} refreshOptions={refresh} />
  );
}
