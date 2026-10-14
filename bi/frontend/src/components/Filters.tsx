"use client";
import { FilterX } from "lucide-react";
import { addDays } from "@/lib/format";
import { EMPTY_FILTERS, type FilterState, type Meta } from "@/lib/types";

interface Props {
  meta: Meta | null;
  filters: FilterState;
  onChange: (f: FilterState) => void;
}

export function Filters({ meta, filters, onChange }: Props) {
  const set = (patch: Partial<FilterState>) => onChange({ ...filters, ...patch });
  const max = meta?.max_date ?? "";
  const min = meta?.min_date ?? "";

  const presets: { label: string; from: string; to: string }[] = max
    ? [
        { label: "All time", from: "", to: "" },
        { label: "Last 7 days", from: addDays(max, -6), to: max },
        { label: "Last 30 days", from: addDays(max, -29), to: max },
      ]
    : [{ label: "All time", from: "", to: "" }];

  const active = (p: { from: string; to: string }) => filters.date_from === p.from && filters.date_to === p.to;
  const dirty = (Object.keys(filters) as (keyof FilterState)[]).some((k) => filters[k] !== "");

  return (
    <section aria-label="Filters" className="card p-4">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div role="group" aria-label="Date presets" className="flex gap-1">
          {presets.map((p) => (
            <button key={p.label} className={`btn ${active(p) ? "btn-primary" : ""}`} aria-pressed={active(p)}
                    onClick={() => set({ date_from: p.from, date_to: p.to })}>
              {p.label}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-xs text-muted">
          From
          <input type="date" className="field" value={filters.date_from} min={min} max={filters.date_to || max}
                 onChange={(e) => set({ date_from: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          To
          <input type="date" className="field" value={filters.date_to} min={filters.date_from || min} max={max}
                 onChange={(e) => set({ date_to: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          Entity
          <select className="field" value={filters.entity_id} onChange={(e) => set({ entity_id: e.target.value })}>
            <option value="">All entities</option>
            {meta?.entities.map((e) => <option key={e.entity_id} value={e.entity_id}>{e.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          Category
          <select className="field" value={filters.category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">All categories</option>
            {meta?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">
          Status
          <select className="field" value={filters.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="">All statuses</option>
            {meta?.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <button className="btn" disabled={!dirty} onClick={() => onChange(EMPTY_FILTERS)}>
          <FilterX className="h-4 w-4" aria-hidden /> Reset
        </button>
      </div>
    </section>
  );
}
