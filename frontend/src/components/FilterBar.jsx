import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Search, X } from "lucide-react";

const ALL = "__all__";

function FSelect({ label, value, onChange, options, testId, allLabel = "Semua" }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">{label}</label>
      <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
        <SelectTrigger className="h-9 w-full sm:w-40 bg-secondary/60 border-border" data-testid={testId}>
          <SelectValue placeholder="Semua" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{allLabel}</SelectItem>
          {options.map((o) => (
            <SelectItem key={o} value={o}>{o}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function FilterBar({ filters, values, setValues, options }) {
  const set = (k, v) => setValues((p) => ({ ...p, [k]: v }));
  const reset = () => setValues({});
  const hasActive = Object.values(values).some((v) => v);

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 rounded-lg border border-border bg-card/60">
      {filters.includes("date") && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Dari Tanggal</label>
            <Input type="date" value={values.date_from || ""} onChange={(e) => set("date_from", e.target.value)}
              className="h-9 w-40 bg-secondary/60 border-border" data-testid="filter-date-from" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Sampai Tanggal</label>
            <Input type="date" value={values.date_to || ""} onChange={(e) => set("date_to", e.target.value)}
              className="h-9 w-40 bg-secondary/60 border-border" data-testid="filter-date-to" />
          </div>
        </>
      )}
      {filters.includes("product") && <FSelect label="Product" value={values.product} onChange={(v) => set("product", v)} options={options.products || []} testId="filter-product" allLabel="ALL PRODUCT" />}
      {filters.includes("lane") && <FSelect label="Lane / Line" value={values.lane} onChange={(v) => set("lane", v)} options={options.lanes || []} testId="filter-lane" />}
      {filters.includes("lamp_line") && <FSelect label="Line" value={values.lane} onChange={(v) => set("lane", v)} options={options.lamp_lines || []} testId="filter-lamp-line" />}
      {filters.includes("shift") && <FSelect label="Shift" value={values.shift} onChange={(v) => set("shift", v)} options={options.shifts || []} testId="filter-shift" allLabel="ALL" />}
      {filters.includes("proses_mesin") && <FSelect label="Proses Mesin" value={values.proses_mesin} onChange={(v) => set("proses_mesin", v)} options={options.proses_mesin || []} testId="filter-proses-mesin" allLabel="ALL PROSES" />}
      {filters.includes("type") && <FSelect label="Type / Model" value={values.type} onChange={(v) => set("type", v)} options={options.types || []} testId="filter-type" />}
      {filters.includes("ics_no") && <FSelect label="ICS No." value={values.ics_no} onChange={(v) => set("ics_no", v)} options={options.ics_nos || []} testId="filter-ics-no" />}
      {filters.includes("indikator") && <FSelect label="Indikator" value={values.status} onChange={(v) => set("status", v)} options={options.indikator || []} testId="filter-status" />}
      {filters.includes("status_part") && <FSelect label="Status Part" value={values.status} onChange={(v) => set("status", v)} options={options.status_part || []} testId="filter-status" />}
      {filters.includes("stock_status") && <FSelect label="Status Stock" value={values.status} onChange={(v) => set("status", v)} options={options.stock_status || []} testId="filter-status" />}
      {filters.includes("lamp_status") && <FSelect label="Status" value={values.status} onChange={(v) => set("status", v)} options={options.lamp_status || []} testId="filter-status" />}
      {filters.includes("needs_status") && <FSelect label="Status" value={values.status} onChange={(v) => set("status", v)} options={options.needs_status || []} testId="filter-status" />}
      {filters.includes("variance_status") && <FSelect label="Status" value={values.status} onChange={(v) => set("status", v)} options={options.variance_status || []} testId="filter-status" />}

      <div className="flex flex-col gap-1 flex-1 min-w-[180px]">
        <label className="text-[10px] font-mono-data uppercase tracking-wider text-muted-foreground">Pencarian</label>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input value={values.search || ""} onChange={(e) => set("search", e.target.value)} placeholder="Cari ICS No., type, lane..."
            className="h-9 pl-8 bg-secondary/60 border-border" data-testid="filter-search" />
        </div>
      </div>
      {hasActive && (
        <Button variant="ghost" size="sm" onClick={reset} className="h-9 text-muted-foreground" data-testid="filter-reset">
          <X className="w-4 h-4 mr-1" /> Reset
        </Button>
      )}
    </div>
  );
}
