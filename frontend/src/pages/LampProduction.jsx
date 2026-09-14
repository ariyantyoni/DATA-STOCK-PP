import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Lightbulb } from "lucide-react";

export default function LampProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Line" },
    { key: "type", label: "Type Lampu" },
    { key: "part_number", label: "Part Number", mono: true },
    { key: "target", label: "Target", type: "number", align: "right" },
    { key: "actual", label: "Actual", type: "number", align: "right" },
    { key: "balance", label: "Balance", type: "signed", align: "right" },
    { key: "achievement", label: "Achv %", type: "percent", tone: true, align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: new Date().toISOString().slice(0, 10) },
    { key: "lane", label: "Line", type: "text", required: true },
    { key: "type", label: "Type Lampu (Head/Tail/DRL)", type: "text" },
    { key: "part_number", label: "Part Number", type: "text" },
    { key: "target", label: "Target (pcs)", type: "number" },
    { key: "actual", label: "Actual (pcs)", type: "number" },
  ];
  return (
    <CrudPage title="Produksi LAMP ASSY" subtitle="Monitoring perakitan lampu otomotif (Head Lamp, Tail Lamp, DRL)"
      icon={Lightbulb} endpoint="/lamp-production" dataset="lamp-production" module="lamp_production"
      columns={columns} formFields={formFields}
      filters={["date", "lamp_line", "type", "part_number"]} options={options} refreshOptions={refresh} />
  );
}
