import { memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { Loader2, CheckCircle2, AlertTriangle, RotateCcw } from "lucide-react";
import { fmtNum, formatApiErrorDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

const INT_RE = /^\d*$/;
const BORDER = "border border-slate-300 dark:border-border";

const canEditCell = (editable, col, row) => editable && !!col.edit && (!col.canEdit || col.canEdit(row));

function IntEditor({ value, h }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (el) { el.focus({ preventScroll: true }); el.setSelectionRange(el.value.length, el.value.length); }
  }, []);
  return (
    <input ref={ref} value={value ?? ""} inputMode="numeric" data-testid="grid-cell-input"
      onChange={(e) => h.change(e.target.value)} onKeyDown={h.editKey} onBlur={h.blur}
      className="absolute inset-0 w-full h-full px-1.5 text-right font-mono-data text-[12px] bg-white dark:bg-background text-foreground outline outline-2 -outline-offset-2 outline-emerald-600" />
  );
}

function SelectEditor({ value, options, h, anchor }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    const td = document.querySelector(`[data-cell="${anchor}"]`);
    if (!td) return;
    const r = td.getBoundingClientRect();
    const menuH = (options.length + 1) * 26 + 10;
    const up = r.bottom + menuH > window.innerHeight - 8;
    setPos({ left: r.left, width: r.width, top: up ? r.top - menuH - 2 : r.bottom + 2 });
  }, [anchor, options.length]);
  useEffect(() => { if (pos) ref.current?.focus({ preventScroll: true }); }, [pos]);
  return createPortal(
    <div ref={ref} tabIndex={0} onKeyDown={h.editKey} onBlur={h.blur} data-testid="grid-select-editor"
      style={pos ? { position: "fixed", left: pos.left, top: pos.top, minWidth: pos.width } : { position: "fixed", visibility: "hidden" }}
      className="z-[100] rounded-md border border-border bg-popover shadow-lg py-1 outline-none">
      {[...options, ""].map((o) => (
        <div key={o || "empty"} data-testid={`grid-select-option-${o || "kosong"}`}
          onMouseDown={(e) => e.preventDefault()} onClick={() => h.pick(o)}
          className={cn("px-3 h-[26px] leading-[26px] text-xs font-mono-data cursor-pointer", value === o ? "bg-emerald-600 text-white" : "hover:bg-secondary")}>
          {o || "(kosong)"}
        </div>
      ))}
    </div>,
    document.body
  );
}

function cellContent(col, row, rowPending) {
  const hasP = rowPending && col.key in rowPending;
  const v = hasP ? rowPending[col.key] : row[col.key];
  if (col.render && !hasP) return col.render(row);
  if (v === null || v === undefined || v === "") return <span className="text-muted-foreground">-</span>;
  if (col.edit === "int" || col.num) return fmtNum(v);
  return v;
}

const GridRow = memo(function GridRow({ row, ri, columns, activeC, editing, rowStatus, rowPending, editable, h, renderActions }) {
  return (
    <tr data-testid={`grid-row-${ri}`} className="group">
      <td className={cn(BORDER, "sticky left-0 z-[2] bg-slate-100 dark:bg-secondary text-center text-[10px] text-muted-foreground font-mono-data")}>{ri + 1}</td>
      {columns.map((c, ci) => {
        const st = rowStatus?.[c.key];
        const isEdit = editing && editing.c === ci;
        const can = canEditCell(editable, c, row);
        return (
          <td key={c.key} data-cell={`${ri}-${ci}`} data-testid={`cell-${ri}-${c.key}`} data-save-state={st || ""}
            onMouseDown={() => h.down(ri, ci)} onDoubleClick={() => h.dbl(ri, ci)}
            title={st === "error" ? "Gagal menyimpan — tekan Enter untuk mencoba lagi" : undefined}
            className={cn(BORDER, "relative h-7 px-1.5 whitespace-nowrap font-mono-data text-[12px] tabular-nums",
              c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left",
              can ? "bg-white dark:bg-card cursor-cell" : "bg-slate-50 dark:bg-secondary/30",
              c.cellClass?.(row),
              st === "saved" && "!bg-emerald-50 dark:!bg-emerald-500/15",
              st === "error" && "!bg-red-50 dark:!bg-red-500/15 text-red-700 dark:text-red-400",
              activeC === ci && "outline outline-2 -outline-offset-2 outline-emerald-600 z-[3]")}>
            {isEdit && c.edit === "int" ? <IntEditor value={editing.value} h={h} /> : cellContent(c, row, rowPending)}
            {isEdit && c.edit === "select" && <SelectEditor value={editing.value} options={c.options} h={h} anchor={`${ri}-${ci}`} />}
            {st === "saving" && <Loader2 className="absolute left-0.5 top-0.5 w-3 h-3 animate-spin text-emerald-600" />}
            {st === "error" && <AlertTriangle className="absolute left-0.5 top-0.5 w-3 h-3 text-red-600" />}
          </td>
        );
      })}
      {renderActions && <td className={cn(BORDER, "px-1.5 bg-white dark:bg-card whitespace-nowrap")}>{renderActions(row, ri)}</td>}
    </tr>
  );
});

export function SaveIndicator({ state, errorCount, onRetry }) {
  if (!state) return <span className="text-muted-foreground">Siap input</span>;
  if (state === "saving") return <span data-testid="save-indicator" className="inline-flex items-center gap-1 text-amber-600"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Menyimpan...</span>;
  if (state === "error" || errorCount > 0)
    return (
      <span data-testid="save-indicator" className="inline-flex items-center gap-2 text-red-600">
        <AlertTriangle className="w-3.5 h-3.5" /> Gagal menyimpan ({errorCount})
        <button onClick={onRetry} data-testid="save-retry-button" className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-red-400 hover:bg-red-50 dark:hover:bg-red-500/10">
          <RotateCcw className="w-3 h-3" /> Coba lagi
        </button>
      </span>
    );
  return <span data-testid="save-indicator" className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="w-3.5 h-3.5" /> Tersimpan</span>;
}

export default function ExcelGrid({ columns, rows, rowKey, onSave, editable = false, groups, renderActions, actionsLabel = "Aksi", info, testId = "excel-grid" }) {
  const [active, setActive] = useState(null);
  const [editing, setEditing] = useState(null);
  const [status, setStatus] = useState({});
  const [pending, setPending] = useState({});
  const [saveState, setSaveState] = useState(null);
  const wrapRef = useRef(null);
  const S = useRef({});
  S.current = { ...S.current, rows, columns, active, pending, status, onSave, rowKey, editable };
  const seq = useRef({});
  const chains = useRef({});

  const patch = (setter, rk, key, val) => setter((p) => {
    const r = { ...(p[rk] || {}) };
    if (val === undefined) delete r[key]; else r[key] = val;
    return { ...p, [rk]: r };
  });

  const save = (row, col, value) => {
    const rk = S.current.rowKey(row);
    const id = `${rk}\u0000${col.key}`;
    const my = (seq.current[id] || 0) + 1;
    seq.current[id] = my;
    patch(setPending, rk, col.key, value);
    patch(setStatus, rk, col.key, "saving");
    setSaveState("saving");
    const run = async () => {
      try {
        await S.current.onSave(row, col.key, value);
        if (seq.current[id] !== my) return;
        patch(setPending, rk, col.key, undefined);
        patch(setStatus, rk, col.key, "saved");
        setSaveState("saved");
        setTimeout(() => setStatus((p) => (p[rk]?.[col.key] === "saved" ? { ...p, [rk]: { ...p[rk], [col.key]: undefined } } : p)), 1500);
      } catch (e) {
        if (seq.current[id] !== my) return;
        patch(setStatus, rk, col.key, "error");
        setSaveState("error");
        toast.error("Gagal menyimpan", { id: "grid-save-error", description: formatApiErrorDetail(e.response?.data?.detail) || e.message });
      }
    };
    chains.current[id] = (chains.current[id] || Promise.resolve()).then(run);
  };

  const editableIdx = (r, c, dir) => {
    const { rows: rs, columns: cs, editable: ed } = S.current;
    let rr = r, cc = c + dir;
    for (let guard = 0; guard < rs.length * cs.length + 1; guard++) {
      if (cc >= cs.length) { rr += 1; cc = 0; }
      if (cc < 0) { rr -= 1; cc = cs.length - 1; }
      if (rr < 0 || rr >= rs.length) return null;
      if (canEditCell(ed, cs[cc], rs[rr])) return { r: rr, c: cc };
      cc += dir;
    }
    return null;
  };

  const moveTo = (r, c) => {
    const { rows: rs, columns: cs } = S.current;
    if (!rs.length) return;
    setActive({ r: Math.max(0, Math.min(rs.length - 1, r)), c: Math.max(0, Math.min(cs.length - 1, c)) });
  };

  const currentValue = (row, col) => {
    const rp = S.current.pending[S.current.rowKey(row)];
    return rp && col.key in rp ? rp[col.key] : row[col.key] ?? null;
  };

  const startEdit = (r, c, initial) => {
    const row = S.current.rows[r], col = S.current.columns[c];
    if (!row || !col || !canEditCell(S.current.editable, col, row)) return;
    const cur = currentValue(row, col);
    const value = initial !== undefined ? initial : col.edit === "int" ? (cur === null ? "" : String(cur)) : cur || col.options[0];
    const ed = { r, c, value };
    S.current.editing = ed;
    setEditing(ed);
    setActive({ r, c });
  };

  const commit = (move, forced) => {
    const ed = S.current.editing;
    if (!ed) return;
    S.current.editing = null;
    setEditing(null);
    const row = S.current.rows[ed.r], col = S.current.columns[ed.c];
    if (row && col) {
      let v = forced !== undefined ? forced : ed.value;
      v = col.edit === "int" ? (String(v ?? "").trim() === "" ? null : parseInt(String(v).trim(), 10)) : v || null;
      const errored = S.current.status[S.current.rowKey(row)]?.[col.key] === "error";
      if (v !== currentValue(row, col) || errored) save(row, col, v);
    }
    if (move?.dr) moveTo(ed.r + move.dr, ed.c);
    if (move?.tab) { const n = editableIdx(ed.r, ed.c, move.tab); if (n) setActive(n); }
    wrapRef.current?.focus({ preventScroll: true });
  };

  const cancel = () => {
    S.current.editing = null;
    setEditing(null);
    wrapRef.current?.focus({ preventScroll: true });
  };

  const h = useRef(null);
  h.current = h.current || {};
  Object.assign(h.current, {
    change: (val) => {
      if (!INT_RE.test(val)) { toast.warning("Hanya angka bulat (0-9) yang diizinkan", { id: "grid-int-only" }); return; }
      const ed = { ...S.current.editing, value: val };
      S.current.editing = ed;
      setEditing(ed);
    },
    pick: (val) => commit(null, val),
    blur: () => {
      const ed = S.current.editing;
      if (ed && S.current.columns[ed.c]?.edit === "select") { S.current.editing = null; setEditing(null); }
      else commit(null);
    },
    editKey: (e) => {
      e.stopPropagation();
      const ed = S.current.editing;
      const col = ed && S.current.columns[ed.c];
      if (e.key === "Enter") { e.preventDefault(); commit({ dr: e.shiftKey ? -1 : 1 }); }
      else if (e.key === "Tab") { e.preventDefault(); commit({ tab: e.shiftKey ? -1 : 1 }); }
      else if (e.key === "Escape") { e.preventDefault(); cancel(); }
      else if (col?.edit === "select" && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
        e.preventDefault();
        const opts = [...col.options, ""];
        const i = Math.max(0, opts.indexOf(ed.value ?? ""));
        const next = { ...ed, value: opts[(i + (e.key === "ArrowDown" ? 1 : opts.length - 1)) % opts.length] };
        S.current.editing = next;
        setEditing(next);
      }
    },
    down: (ri, ci) => {
      const ed = S.current.editing;
      if (ed && ed.r === ri && ed.c === ci) return;
      setActive({ r: ri, c: ci });
      const col = S.current.columns[ci];
      if (col?.edit === "select") setTimeout(() => startEdit(ri, ci), 0);
    },
    dbl: (ri, ci) => startEdit(ri, ci),
  });

  const onKeyDown = (e) => {
    const a = S.current.active;
    const nav = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Tab", "F2"];
    if (!a) { if (nav.includes(e.key)) { e.preventDefault(); moveTo(0, 0); } return; }
    const row = S.current.rows[a.r], col = S.current.columns[a.c];
    const can = row && col && canEditCell(S.current.editable, col, row);
    switch (e.key) {
      case "ArrowUp": e.preventDefault(); moveTo(a.r - 1, a.c); break;
      case "ArrowDown": e.preventDefault(); moveTo(a.r + 1, a.c); break;
      case "ArrowLeft": e.preventDefault(); moveTo(a.r, a.c - 1); break;
      case "ArrowRight": e.preventDefault(); moveTo(a.r, a.c + 1); break;
      case "Enter": e.preventDefault(); if (can) startEdit(a.r, a.c); else moveTo(a.r + (e.shiftKey ? -1 : 1), a.c); break;
      case "F2": e.preventDefault(); startEdit(a.r, a.c); break;
      case "Tab": { e.preventDefault(); const n = editableIdx(a.r, a.c, e.shiftKey ? -1 : 1); if (n) setActive(n); break; }
      case "Delete":
      case "Backspace":
        if (can && currentValue(row, col) !== null) { e.preventDefault(); save(row, col, null); }
        break;
      default:
        if (can && col.edit === "int" && /^\d$/.test(e.key) && !e.ctrlKey && !e.metaKey) { e.preventDefault(); startEdit(a.r, a.c, e.key); }
        else if (can && col.edit === "int" && e.key.length === 1 && !e.ctrlKey && !e.metaKey) toast.warning("Hanya angka bulat (0-9) yang diizinkan", { id: "grid-int-only" });
    }
  };

  const onScroll = () => {
    const ed = S.current.editing;
    if (ed && S.current.columns[ed.c]?.edit === "select") { S.current.editing = null; setEditing(null); }
  };

  useEffect(() => {
    if (!active) return;
    wrapRef.current?.querySelector(`[data-cell="${active.r}-${active.c}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);

  useEffect(() => { setActive((a) => (a && a.r >= rows.length ? null : a)); }, [rows.length]);

  const errorList = [];
  Object.entries(status).forEach(([rk, cols]) => Object.entries(cols).forEach(([k, v]) => { if (v === "error") errorList.push([rk, k]); }));
  const retryAll = () => {
    errorList.forEach(([rk, k]) => {
      const row = rows.find((r) => rowKey(r) === rk);
      const col = columns.find((c) => c.key === k);
      if (row && col) save(row, col, pending[rk]?.[k] ?? null);
    });
  };
  const sumCols = columns.some((c) => c.sum);

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden" data-testid={testId}>
      <div ref={wrapRef} tabIndex={0} onKeyDown={onKeyDown} onScroll={onScroll} data-testid={`${testId}-scroll`}
        className="overflow-auto max-h-[68vh] outline-none focus-visible:ring-2 focus-visible:ring-emerald-600/40">
        <table className="border-collapse text-[12px]" style={{ tableLayout: "fixed", width: 44 + columns.reduce((a, c) => a + (c.width || 100), 0) + (renderActions ? 90 : 0) }}>
          <colgroup>
            <col style={{ width: 44 }} />
            {columns.map((c) => <col key={c.key} style={{ width: c.width || 100 }} />)}
            {renderActions && <col style={{ width: 90 }} />}
          </colgroup>
          <thead className="sticky top-0 z-[5]">
            {groups && (
              <tr>
                <th className={cn(BORDER, "sticky left-0 z-[6] h-7 bg-slate-200 dark:bg-secondary")} />
                {groups.map((g, i) => (
                  <th key={i} colSpan={g.span} className={cn(BORDER, "h-7 px-2 text-[11px] font-bold tracking-wider text-center", g.className || "bg-slate-200 dark:bg-secondary")}>{g.label}</th>
                ))}
                {renderActions && <th className={cn(BORDER, "bg-slate-200 dark:bg-secondary")} />}
              </tr>
            )}
            <tr>
              <th className={cn(BORDER, "sticky left-0 z-[6] bg-slate-200 dark:bg-secondary text-[10px] text-muted-foreground")}>#</th>
              {columns.map((c) => (
                <th key={c.key} data-testid={`grid-header-${c.key}`}
                  className={cn(BORDER, "h-11 px-1.5 text-[11px] font-bold leading-tight whitespace-pre-line text-center align-middle text-slate-800 dark:text-foreground",
                    c.headerClass || "bg-slate-100 dark:bg-secondary")}>
                  {c.label}
                </th>
              ))}
              {renderActions && <th className={cn(BORDER, "bg-slate-100 dark:bg-secondary text-[11px] font-bold")}>{actionsLabel}</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <GridRow key={rowKey(row)} row={row} ri={ri} columns={columns} editable={editable} h={h.current} renderActions={renderActions}
                activeC={active && active.r === ri ? active.c : -1}
                editing={editing && editing.r === ri ? editing : null}
                rowStatus={status[rowKey(row)]} rowPending={pending[rowKey(row)]} />
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={columns.length + 2} className="py-14 text-center text-sm text-muted-foreground">Tidak ada data.</td></tr>
            )}
          </tbody>
          {sumCols && rows.length > 0 && (
            <tfoot className="sticky bottom-0 z-[4]">
              <tr data-testid="grid-totals">
                <td className={cn(BORDER, "sticky left-0 bg-slate-200 dark:bg-secondary")} />
                {columns.map((c, i) => (
                  <td key={c.key} className={cn(BORDER, "h-7 px-1.5 bg-slate-200 dark:bg-secondary font-mono-data font-bold text-[12px]", c.align === "right" && "text-right")}>
                    {i === 0 ? "TOTAL" : c.sum ? fmtNum(rows.reduce((a, r) => a + (Number(r[c.key]) || 0), 0)) : ""}
                  </td>
                ))}
                {renderActions && <td className={cn(BORDER, "bg-slate-200 dark:bg-secondary")} />}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-t border-border text-xs font-mono-data">
        <span className="text-muted-foreground" data-testid={`${testId}-info`}>{rows.length} baris{info ? ` · ${info}` : ""}</span>
        {editable && <SaveIndicator state={saveState} errorCount={errorList.length} onRetry={retryAll} />}
      </div>
    </div>
  );
}
