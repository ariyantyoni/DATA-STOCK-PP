import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Package } from "lucide-react";

export default function MasterItems() {
  const { options, refresh } = useMetaOptions();
  const columns = [
    { key: "lane", label: "Lane", mono: true },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "tt", label: "T/T (detik)", type: "number", align: "right" },
    { key: "cap_h", label: "CAP/H", type: "number", align: "right" },
    { key: "led_rank", label: "LED Rank" },
    { key: "tray", label: "Tray" },
  ];
  const formFields = [
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "tt", label: "T/T (detik) — CAP/H = 3600 / T/T", type: "number" },
    { key: "led_rank", label: "LED Rank", type: "text" },
    { key: "tray", label: "Tray", type: "text" },
  ];
  return (
    <CrudPage title="Master Item" subtitle="Daftar Lane / Type / ICS No. / T-T — dipakai untuk memilih item di semua form input"
      icon={Package} endpoint="/items" dataset="items" module="items" itemPicker={false}
      columns={columns} formFields={formFields}
      filters={["lane", "type", "ics_no"]} options={options} refreshOptions={refresh} />
  );
}
