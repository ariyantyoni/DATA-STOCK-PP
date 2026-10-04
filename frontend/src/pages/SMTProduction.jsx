import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Cpu } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);
const SHIFTS = ["SHIFT 3", "SHIFT 1", "SHIFT 2"];

export default function SMTProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "shift", label: "Shift", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No", mono: true },
    { key: "proses_mesin", label: "Proses Mesin", na: "-" },
    { key: "tt", label: "T/T", type: "number", align: "right" },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { sum: true, key: "plan_injection", label: "Plan Injection", type: "number", align: "right" },
    { sum: true, key: "act_injection", label: "Act Injection", type: "number", align: "right" },
    { sum: true, key: "plan_eva", label: "Plan EVA", type: "number", align: "right" },
    { sum: true, key: "act_eva", label: "Act EVA", type: "number", align: "right" },
    { sum: true, key: "plan_assy", label: "Plan Assy", type: "number", align: "right" },
    { sum: true, key: "act_assy", label: "Act Assy", type: "number", align: "right" },
    { key: "achv", label: "Achv %", type: "percent", tone: true, align: "right" },
    { sum: true, key: "total_act", label: "Total Act", type: "strong", align: "right" },
    { sum: true, key: "balance", label: "Balance", type: "signed", align: "right" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "shift", label: "Shift", type: "select", options: SHIFTS, required: true },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: options.products?.length ? options.products : ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "plan_injection", label: "Plan Injection (pcs)", type: "number" },
    { key: "act_injection", label: "Act Injection (pcs)", type: "number" },
    { key: "plan_eva", label: "Plan EVA (pcs)", type: "number" },
    { key: "act_eva", label: "Act EVA (pcs)", type: "number" },
    { key: "plan_assy", label: "Plan Assy (pcs)", type: "number" },
    { key: "act_assy", label: "Act Assy (pcs)", type: "number" },
  ];
  return (
    <CrudPage title="Produksi Part & ASSY" subtitle="ACHV % = (ACT INJECTION + ACT EVA + ACT ASSY) ÷ (PLAN INJECTION + PLAN EVA + PLAN ASSY) × 100 · Balance = (Act Injection+Act EVA) − Act Assy · Proses Mesin otomatis dari Master Item"
      icon={Cpu} endpoint="/smt-production" dataset="smt-production" module="smt_production"
      columns={columns} formFields={formFields} note="Pilih item dari Master Item untuk mengisi Lane/Product/Type/ICS otomatis"
      filters={["date", "shift", "proses_mesin", "product", "lane", "type", "ics_no", "lamp_status"]} options={options} refreshOptions={refresh} />
  );
}
