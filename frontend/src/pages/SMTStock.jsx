import { useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import GenerateStockDialog from "@/components/GenerateStockDialog";
import { CalendarPlus } from "lucide-react";
import CrudPage from "@/components/CrudPage";
import { useMetaOptions } from "@/hooks/useMetaOptions";
import { Boxes } from "lucide-react";

const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });
const SHIFTS = ["SHIFT 3", "SHIFT 1", "SHIFT 2"];

const COLUMNS = [
    { key: "date", label: "Tanggal", mono: true },
    { key: "shift", label: "Shift", mono: true },
    { key: "lane", label: "Lane", mono: true },
    { key: "product", label: "Product", na: "BELUM DIMAPPING" },
    { key: "type", label: "Type" },
    { key: "ics_no", label: "ICS No.", mono: true },
    { key: "ics_name", label: "ICS Name", na: "-" },
    { key: "group", label: "Group", na: "-" },
    { key: "proses_mesin", label: "Proses Mesin", na: "-" },
    { key: "group1", inline: true, label: "Group 1", type: "number", align: "right", sum: true },
    { key: "group2", inline: true, label: "Group 2", type: "number", align: "right", sum: true },
    { key: "group3", inline: true, label: "Group 3", type: "number", align: "right", sum: true },
    { key: "group4", inline: true, label: "Group 4", type: "number", align: "right", sum: true },
    { key: "group5", inline: true, label: "Group 5", type: "number", align: "right", sum: true },
    { key: "group6", inline: true, label: "Group 6", type: "number", align: "right", sum: true },
    { key: "part_ragu", inline: true, label: "Part Ragu-ragu", type: "number", align: "right", sum: true },
    { key: "total", label: "Total Stock Hari Ini", type: "strong", align: "right", sum: true },
    { key: "std_stock_min", label: "Std Min", type: "number", align: "right", na: "-" },
    { key: "std_stock_max", label: "Std Max", type: "number", align: "right", na: "-" },
    { key: "status_part", label: "Status Part", type: "status", width: 160 },
  ];

const todayWib = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });

export default function SMTStock() {
  const { options, refresh } = useMetaOptions();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [genOpen, setGenOpen] = useState(false);
  const [reload, setReload] = useState(0);
  const initialValues = useMemo(() => { const t = todayWib(); return { date_from: t, date_to: t }; }, []);
  const columns = COLUMNS;
  const formFields = [
    { key: "date", label: "Tanggal", type: "date", required: true, default: today() },
    { key: "shift", label: "Shift", type: "select", options: SHIFTS, required: true },
    { key: "lane", label: "Lane", type: "text", required: true },
    { key: "product", label: "Product", type: "select", options: options.products?.length ? options.products : ["REGULER", "SPO"] },
    { key: "type", label: "Type", type: "text", required: true },
    { key: "ics_no", label: "ICS No.", type: "text", required: true },
    { key: "group1", inline: true, label: "Group 1", type: "number" },
    { key: "group2", inline: true, label: "Group 2", type: "number" },
    { key: "group3", inline: true, label: "Group 3", type: "number" },
    { key: "group4", inline: true, label: "Group 4", type: "number" },
    { key: "group5", inline: true, label: "Group 5", type: "number" },
    { key: "group6", inline: true, label: "Group 6", type: "number" },
    { key: "part_ragu", inline: true, label: "Part Ragu-ragu", type: "number" },
  ];
  return (
    <>
    <CrudPage title="Stock Part Production" subtitle="Total Stock Hari Ini = GROUP 1 + … + GROUP 6 + PART RAGU-RAGU · STATUS PART mengikuti Kebutuhan Assy VS. Stock Part (tanggal + ICS NO + TYPE) · ICS Name / Group / Std Stock otomatis dari Master Item"
      icon={Boxes} endpoint="/smt-stock" inlineEdit dataset="smt-stock" module="smt_stock"
      columns={columns} formFields={formFields} note="Pilih item dari Master Item untuk mengisi Lane/Product/Type/ICS otomatis"
      filters={["date", "group", "shift", "proses_mesin", "product", "lane", "type", "ics_no", "status_part"]} options={options} refreshOptions={refresh}
      initialValues={initialValues} bulkDelete freezeUntil="proses_mesin" reloadSignal={reload}
      headerExtra={isAdmin && (
        <Button variant="outline" size="sm" onClick={() => setGenOpen(true)} data-testid="generate-open-button" className="border-border">
          <CalendarPlus className="w-4 h-4 mr-1.5" /> Generate Harian
        </Button>
      )} />
    <GenerateStockDialog open={genOpen} onOpenChange={setGenOpen} today={initialValues.date_from} onDone={() => setReload((x) => x + 1)} />
    </>
  );
}
