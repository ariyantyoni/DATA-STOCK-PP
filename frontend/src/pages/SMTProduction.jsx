import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Cpu } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function SMTProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No", mono: true },
    { key: "tt", label: "T/T", type: "number", align: "right" },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { sum: true, key: "planing_smt", label: "Planing Part", type: "number", align: "right" },
    { sum: true, key: "act_smt_s3", label: "Act Part S3", type: "number", align: "right" },
    { sum: true, key: "act_smt_s1", label: "Act Part S1", type: "number", align: "right" },
    { sum: true, key: "act_smt_s2", label: "Act Part S2", type: "number", align: "right" },
    { sum: true, key: "total_act_smt", label: "Total Act Part", type: "strong", align: "right" },
    { key: "achv", label: "Achv %", type: "percent", tone: true, align: "right" },
    { sum: true, key: "plan_assy", label: "Plan Assy", type: "number", align: "right" },
    { sum: true, key: "act_assy_s3", label: "Act Assy S3", type: "number", align: "right" },
    { sum: true, key: "act_assy_s1", label: "Act Assy S1", type: "number", align: "right" },
    { sum: true, key: "act_assy_s2", label: "Act Assy S2", type: "number", align: "right" },
    { sum: true, key: "total_act_assy", label: "Total Act Assy", type: "strong", align: "right" },
    { sum: true, key: "balance", label: "Balance", type: "signed", align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { sum: true, key: "planing_smt", label: "Planing Part (pcs)", type: "number" },
    { sum: true, key: "act_smt_s3", label: "Act Part Shift 3", type: "number" },
    { sum: true, key: "act_smt_s1", label: "Act Part Shift 1", type: "number" },
    { sum: true, key: "act_smt_s2", label: "Act Part Shift 2", type: "number" },
    { sum: true, key: "plan_assy", label: "Plan Assy (pcs)", type: "number" },
    { sum: true, key: "act_assy_s3", label: "Act Assy Shift 3", type: "number" },
    { sum: true, key: "act_assy_s1", label: "Act Assy Shift 1", type: "number" },
    { sum: true, key: "act_assy_s2", label: "Act Assy Shift 2", type: "number" },
  ];
  return (
    <CrudPage title="Produksi Part & ASSY" subtitle="Total Act Part = S3+S1+S2 · Achv % = Total Act Part / Planing Part · Total Act Assy = S3+S1+S2 · Balance = Total Act Part − Total Act Assy"
      icon={Cpu} endpoint="/smt-production" dataset="smt-production" module="smt_production"
      columns={columns} formFields={formFields}
      filters={["date", "product", "lane", "type", "ics_no", "lamp_status"]} options={options} refreshOptions={refresh} />
  );
}
