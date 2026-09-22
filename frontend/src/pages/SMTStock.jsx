import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Boxes } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function SMTStock() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "stock_ok_prev", label: "Stock OK Kemarin (H-1)", type: "number", align: "right" },
    { key: "coating", label: "Coating", type: "number", align: "right" },
    { key: "belum_cutting", label: "Belum Cutting", type: "number", align: "right" },
    { key: "belum_ict", label: "Belum ICT", type: "number", align: "right" },
    { key: "belum_fct", label: "Belum FCT", type: "number", align: "right" },
    { key: "ok", label: "OK", type: "strong", align: "right" },
    { key: "total", label: "Total Stock", type: "strong", align: "right" },
    { key: "tray", label: "Tray" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "stock_ok_prev", label: "Stock OK SMT Kemarin (otomatis dari H-1, bisa diubah)", type: "number" },
    { key: "coating", label: "Coating", type: "number" },
    { key: "belum_cutting", label: "Belum Cutting", type: "number" },
    { key: "belum_ict", label: "Belum ICT", type: "number" },
    { key: "belum_fct", label: "Belum FCT", type: "number" },
    { key: "ok", label: "OK", type: "number" },
    { key: "tray", label: "Tray", type: "text" },
  ];
  return (
    <CrudPage title="Stock SMT" subtitle="Actual stock SMT per proses — Total = Coating + Belum Cutting + Belum ICT + Belum FCT + OK · Stock OK Kemarin tertaut otomatis ke data tanggal H-1"
      icon={Boxes} endpoint="/smt-stock" dataset="smt-stock" module="smt_stock"
      columns={columns} formFields={formFields}
      filters={["date", "lane", "type", "ics_no", "stock_status"]} options={options} refreshOptions={refresh} />
  );
}
