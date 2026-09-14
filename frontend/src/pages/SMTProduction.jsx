import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Cpu } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function SMTProduction() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { key: "tt", label: "T/T", type: "number", align: "right" },
    { key: "led_rank", label: "LED Rank" },
    { key: "smt1", label: "Shift 1", type: "number", align: "right" },
    { key: "smt2", label: "Shift 2", type: "number", align: "right" },
    { key: "smt3", label: "Shift 3", type: "number", align: "right" },
    { key: "total", label: "Total SMT", type: "strong", align: "right" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "led_rank", label: "LED Rank", type: "text" },
    { key: "smt1", label: "Hasil SMT Shift 1", type: "number" },
    { key: "smt2", label: "Hasil SMT Shift 2", type: "number" },
    { key: "smt3", label: "Hasil SMT Shift 3", type: "number" },
  ];
  return (
    <CrudPage title="Produksi SMT" subtitle="Hasil produksi SMT hari ini per shift — CAP/H & Total otomatis"
      icon={Cpu} endpoint="/smt-production" dataset="smt-production" module="smt_production"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no"]} options={options} refreshOptions={refresh} />
  );
}
