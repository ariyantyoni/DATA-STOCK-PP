import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Cpu } from "lucide-react";

export default function SMTProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane" },
    { key: "shift", label: "Shift" },
    { key: "part_number", label: "Part Number", mono: true },
    { key: "type", label: "Type" },
    { key: "target", label: "Target", type: "number", align: "right" },
    { key: "actual", label: "Actual", type: "number", align: "right" },
    { key: "defect", label: "Defect", type: "number", align: "right" },
    { key: "good", label: "Good", type: "number", align: "right" },
    { key: "achievement", label: "Achv %", type: "percent", tone: true, align: "right" },
    { key: "yield_rate", label: "Yield %", type: "percent", tone: true, align: "right" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: new Date().toISOString().slice(0, 10) },
    { key: "shift", label: "Shift", type: "select", options: ["Shift 1", "Shift 2", "Shift 3"] },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "part_number", label: "Part Number", type: "text", required: true },
    { key: "type", label: "Type / Model", type: "text" },
    { key: "target", label: "Target (pcs)", type: "number" },
    { key: "actual", label: "Actual (pcs)", type: "number" },
    { key: "defect", label: "Defect (pcs)", type: "number" },
  ];
  return (
    <CrudPage title="Produksi SMT" subtitle="Monitoring hasil produksi SMT harian per lane & shift"
      icon={Cpu} endpoint="/smt-production" dataset="smt-production" module="smt_production"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "shift", "type", "part_number"]} options={options} refreshOptions={refresh} />
  );
}
