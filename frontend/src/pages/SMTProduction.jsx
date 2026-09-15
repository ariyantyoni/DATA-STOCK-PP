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
    { key: "planing", label: "Planing", type: "number", align: "right" },
    { key: "act_s3", label: "Act S3", type: "number", align: "right" },
    { key: "act_s1", label: "Act S1", type: "number", align: "right" },
    { key: "act_s2", label: "Act S2", type: "number", align: "right" },
    { key: "total_smt", label: "Total SMT", type: "strong", align: "right" },
    { key: "achv", label: "Achv %", type: "percent", tone: true, align: "right" },
    { key: "plan_assy_s3", label: "Plan Assy S3", type: "number", align: "right" },
    { key: "plan_assy_s1", label: "Plan Assy S1", type: "number", align: "right" },
    { key: "plan_assy_s2", label: "Plan Assy S2", type: "number", align: "right" },
    { key: "total_plan", label: "Total Plan", type: "strong", align: "right" },
    { key: "balance", label: "Balance", type: "signed", align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "planing", label: "Planing SMT (pcs)", type: "number" },
    { key: "act_s3", label: "Actual SMT Shift 3", type: "number" },
    { key: "act_s1", label: "Actual SMT Shift 1", type: "number" },
    { key: "act_s2", label: "Actual SMT Shift 2", type: "number" },
    { key: "plan_assy_s3", label: "Plan Assy Shift 3", type: "number" },
    { key: "plan_assy_s1", label: "Plan Assy Shift 1", type: "number" },
    { key: "plan_assy_s2", label: "Plan Assy Shift 2", type: "number" },
  ];
  return (
    <CrudPage title="Produksi SMT & ASSY" subtitle="Total SMT = Act S3+S1+S2 · Achv % = Total SMT / Planing · Total Plan = Plan Assy S3+S1+S2 · Balance = Total SMT − Total Plan"
      icon={Cpu} endpoint="/smt-production" dataset="smt-production" module="smt_production"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no", "lamp_status"]} options={options} refreshOptions={refresh} />
  );
}
