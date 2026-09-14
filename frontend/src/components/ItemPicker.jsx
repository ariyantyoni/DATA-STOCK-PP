import { useState, useEffect } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import { ChevronsUpDown, PackageSearch } from "lucide-react";

export default function ItemPicker({ onPick, current }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (open && items.length === 0) api.get("/items").then((r) => setItems(r.data)).catch(() => {});
  }, [open, items.length]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" role="combobox" data-testid="item-picker-trigger"
          className="w-full justify-between bg-secondary/60 border-border font-normal h-10">
          <span className="flex items-center gap-2 truncate">
            <PackageSearch className="w-4 h-4 text-primary shrink-0" />
            {current ? <span className="truncate"><span className="font-mono-data">{current.ics_no}</span> · {current.type}</span> : "Pilih item dari Master Item..."}
          </span>
          <ChevronsUpDown className="w-4 h-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0 bg-card border-border" align="start">
        <Command>
          <CommandInput placeholder="Cari ICS No., type, lane..." data-testid="item-picker-search" />
          <CommandList className="max-h-64">
            <CommandEmpty>Item tidak ditemukan.</CommandEmpty>
            <CommandGroup>
              {items.map((it) => (
                <CommandItem key={it.id} value={`${it.ics_no} ${it.type} ${it.lane}`} data-testid={`item-option-${it.ics_no}`}
                  onSelect={() => { onPick(it); setOpen(false); }} className="flex justify-between gap-3">
                  <span className="truncate">{it.type}</span>
                  <span className="font-mono-data text-xs text-muted-foreground shrink-0">{it.lane} · {it.ics_no}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
