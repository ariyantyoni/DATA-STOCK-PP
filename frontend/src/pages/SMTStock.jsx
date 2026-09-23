import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Boxes } from "lucide-react";

const today = () => new Date().toISOString().slice(0, 10);

export default function SMTStock() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product", na: "BELUM DIMAPPING" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "stock_ok_prev", label: "Stock OK Kemarin (H-1)", type: "number", align: "right", sum: true },
    { key: "coating", label: "Coating", type: "number", align: "right", sum: true },
    { key: "belum_cutting", label: "Belum Cutting", type: "number", align: "right", sum: true },
    { key: "belum_ict", label: "Belum ICT", type: "number", align: "right", sum: true },
    { key: "belum_fct", label: "Belum FCT", type: "number", align: "right", sum: true },
    { key: "ok", label: "OK", type: "strong", align: "right", sum: true },
    { key: "total", label: "Total Stock Hari Ini", type: "strong", align: "right", sum: true },
    { key: "standard_stock", label: "Standart Stock", type: "number", align: "right", na: "BELUM DISET" },
    { key: "indikator", label: "Indikator", type: "status" },
    { key: "tray", label: "Tray" },
    { key: "status", label: "Status", type: "status" },
  ];
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: options.products?.length ? options.products : ["REGULER", "SPO"] },
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
    <CrudPage title="Stock SMT" subtitle="Total Stock Hari Ini = Coating + Belum Cutting + Belum ICT + Belum FCT + OK · Indikator = Total vs Standart Stock (PRODUCT + LANE) · Stock OK Kemarin tertaut ke H-1"
      icon={Boxes} endpoint="/smt-stock" dataset="smt-stock" module="smt_stock"
      columns={columns} formFields={formFields} note="Product diambil dari Master Item bila record belum memilikinya"
      filters={["date", "product", "lane", "type", "ics_no", "indikator"]} options={options} refreshOptions={refresh} />
  );
}
