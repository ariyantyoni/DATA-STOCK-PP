import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Package } from "lucide-react";

export default function MasterItems() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "tt", label: "T/T (detik)", type: "number", align: "right" },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { key: "tt_assy", label: "T/T Assy (dtk/unit)", type: "number", align: "right", na: "N/A" },
    { key: "proses_mesin", label: "Proses Mesin" },
    { key: "material_per_unit", label: "Material / Unit Assy", type: "number", align: "right" },
  ];
  const formFields = [
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "tt_assy", label: "T/T Assy (detik/unit) — untuk Waktu Shortage", type: "number" },
    { key: "material_per_unit", label: "Kebutuhan Material Part per Unit Assy (default 1)", type: "number" },
    { key: "proses_mesin", label: "Proses Mesin", type: "text" },
  ];
  return (
    <CrudPage title="Master Item" subtitle="Daftar Lane / Type / ICS No. / T-T — dipakai untuk memilih item di semua form input"
      icon={Package} endpoint="/items" dataset="items" module="items" itemPicker={false}
      columns={columns} formFields={formFields}
      filters={["product", "lane", "type", "ics_no"]} options={options} refreshOptions={refresh} />
  );
}
