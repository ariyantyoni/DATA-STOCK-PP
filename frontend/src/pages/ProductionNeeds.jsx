import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { ClipboardList } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function ProductionNeeds() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "plan_assy", label: "Plan Assy Hari Ini", type: "number", align: "right" },
    { key: "stock_ok_prev", label: "Stock OK SMT Kemarin", type: "number", align: "right" },
    { key: "blc", label: "BLC", type: "signed", align: "right" },
    { key: "fulfillment", label: "Pemenuhan %", type: "percent", tone: true, align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "plan_assy", label: "Plan Assy Hari Ini", type: "number" },
    { key: "stock_ok_prev", label: "Stock OK SMT Kemarin", type: "number" },
  ];
  return (
    <CrudPage title="Kebutuhan vs Stock" subtitle="Plan Assy vs Stock OK SMT — BLC = Stock OK SMT − Plan Assy (negatif = shortage)"
      icon={ClipboardList} endpoint="/production-needs" dataset="production-needs" module="production_needs"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no", "needs_status"]} options={options} refreshOptions={refresh} />
  );
}
