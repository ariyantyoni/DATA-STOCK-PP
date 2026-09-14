import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Lightbulb } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function LampProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "plan_assy", label: "Plan Assy", type: "number", align: "right" },
    { key: "assy1", label: "Shift 1", type: "number", align: "right" },
    { key: "assy2", label: "Shift 2", type: "number", align: "right" },
    { key: "assy3", label: "Shift 3", type: "number", align: "right" },
    { key: "total", label: "Total Assy", type: "strong", align: "right" },
    { key: "achievement", label: "Achv %", type: "percent", tone: true, align: "right" },
    { key: "stock_ok_prev", label: "Stock OK SMT", type: "number", align: "right" },
    { key: "blc", label: "BLC", type: "signed", align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "plan_assy", label: "Plan Assy Hari Ini", type: "number" },
    { key: "stock_ok_prev", label: "Stock OK SMT Kemarin", type: "number" },
    { key: "assy1", label: "Actual Assy Shift 1", type: "number" },
    { key: "assy2", label: "Actual Assy Shift 2", type: "number" },
    { key: "assy3", label: "Actual Assy Shift 3", type: "number" },
  ];
  return (
    <CrudPage title="Produksi LAMP ASSY" subtitle="Plan vs actual produksi Assy per shift — BLC = Stock OK SMT − Plan Assy"
      icon={Lightbulb} endpoint="/lamp-production" dataset="lamp-production" module="lamp_production"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no", "lamp_status"]} options={options} refreshOptions={refresh} />
  );
}
