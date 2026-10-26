import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Package, AlertTriangle } from "lucide-react";
import { fmtNum } from "@/lib/api";

const stdCell = (k) => (row) => {
  const v = row[k];
  if (v === null || v === undefined) return <span className="text-muted-foreground font-mono-data">BELUM DISET</span>;
  return (
    <span className={`font-mono-data inline-flex items-center gap-1 ${row.std_warning ? "text-amber-600 font-semibold" : ""}`}
      title={row.std_warning ? "Peringatan: STD STOCK MIN lebih besar dari STD STOCK MAX" : undefined} data-testid={row.std_warning ? `std-warning-${row.id}` : undefined}>
      {row.std_warning && <AlertTriangle className="w-3 h-3" />}{fmtNum(v)}
    </span>
  );
};

const GROUPS = ["GROUP 1", "GROUP 2", "GROUP 3", "GROUP 4", "GROUP 5", "GROUP 6"];

export default function MasterItems() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "ics_name", label: "ICS Name", na: "-" },
    { key: "group", label: "Group", na: "-" },
    { key: "std_stock_min", label: "Std Stock Min", type: "number", align: "right", na: "BELUM DISET", render: stdCell("std_stock_min") },
    { key: "std_stock_max", label: "Std Stock Max", type: "number", align: "right", na: "BELUM DISET", render: stdCell("std_stock_max") },
    { key: "tt", label: "T/T (detik)", type: "number", align: "right" },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { key: "tt_assy", label: "T/T Assy (dtk/unit)", type: "number", align: "right", na: "N/A" },
    { key: "proses_mesin", label: "Proses Mesin" },
    { key: "material_per_unit", label: "Material / Unit Assy", type: "number", align: "right" },
  ];
  const formFields = [
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: options.products?.length ? options.products : ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "ics_name", label: "ICS Name", type: "text" },
    { key: "group", label: "Group", type: "select", options: GROUPS },
    { key: "std_stock_min", label: "Std Stock Min (kosongkan jika belum diset)", type: "number" },
    { key: "std_stock_max", label: "Std Stock Max (idealnya ≥ Min; jika < Min diberi tanda peringatan)", type: "number" },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "tt_assy", label: "T/T Assy (detik/unit) — untuk Waktu Shortage", type: "number" },
    { key: "material_per_unit", label: "Kebutuhan Material Part per Unit Assy (default 1)", type: "number" },
    { key: "proses_mesin", label: "Proses Mesin", type: "text" },
  ];
  return (
    <CrudPage title="Master Item" subtitle="Single source of truth: identitas item, ICS Name, Group, Standard Stock Min/Max — dipakai di seluruh modul. Gunakan Export/Import Excel untuk update massal."
      icon={Package} endpoint="/items" dataset="items" module="items" itemPicker={false}
      columns={columns} formFields={formFields}
      filters={["product", "lane", "type", "ics_no", "proses_mesin"]} options={options} refreshOptions={refresh} />
  );
}
