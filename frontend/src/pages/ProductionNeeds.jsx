import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { ClipboardList } from "lucide-react";

export default function ProductionNeeds() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product", na: "BELUM DIMAPPING" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "planing_smt", label: "Planing SMT", type: "number", align: "right", sum: true },
    { key: "plan_assy", label: "Plan Assy", type: "number", align: "right", sum: true },
    { key: "stock_ok_today", label: "Stock OK Hari Ini", type: "strong", align: "right", sum: true },
    { key: "blc", label: "BLC", type: "signed", align: "right" },
    { key: "tt_assy", label: "T/T Assy (dtk/unit)", type: "number", align: "right", na: "N/A" },
    { key: "material_per_unit", label: "Material / Unit", type: "number", align: "right" },
    { key: "status", label: "Status", type: "status" },
    { key: "waktu_shortage", label: "Waktu Shortage", type: "hours", align: "right", na: "N/A" },
    { key: "kondisi_produksi", label: "Kondisi Produksi", type: "status" },
  ];
  return (
    <CrudPage title="Kebutuhan Assy VS. Stock SMT"
      subtitle="Otomatis dari Produksi SMT & ASSY (planning) + Stock SMT (Total Stock Hari Ini) + Master Item (T/T Assy) · Waktu Shortage (jam) = Stock ÷ Material/Unit × T/T Assy ÷ 3600"
      icon={ClipboardList} endpoint="/production-needs" dataset="production-needs" module="production_needs" readOnly hideAudit
      columns={columns} formFields={[]} note="Kondisi Produksi ON = ada Planing SMT pada tanggal, lane, product & ICS terkait"
      filters={["date", "product", "lane", "type", "ics_no", "needs_status"]} options={options} refreshOptions={refresh} />
  );
}
