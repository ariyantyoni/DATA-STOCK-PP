import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Gauge } from "lucide-react";

export default function StockStandards() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product" },
    { key: "type", label: "Type" },
    { key: "standard_stock", label: "Standart Stock", type: "strong", align: "right" },
  ];
  const formFields = [
    { key: "lane", label: "Lane", type: "select", options: options.lanes || [] },
    { key: "product", label: "Product", type: "select", options: options.products?.length ? options.products : ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "select", options: options.types || [] },
    { key: "standard_stock", label: "Standart Stock (pcs)", type: "number", required: true },
  ];
  return (
    <CrudPage title="Standar Stock SMT" subtitle="Master nilai standar stock per kombinasi LANE + PRODUCT + TYPE — dipakai untuk INDIKATOR (PASS / MINUS / OVER) di modul Stock SMT"
      icon={Gauge} endpoint="/stock-standards" dataset="stock-standards" module="stock_standards" itemPicker={false} hideAudit
      columns={columns} formFields={formFields}
      filters={["lane", "product", "type"]} options={options} refreshOptions={refresh} />
  );
}
