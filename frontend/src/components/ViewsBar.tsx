"use client";
import { ArrowDown, ArrowUp, LayoutGrid, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteJson, getJson, postJson } from "@/lib/api";
import type { FilterState } from "@/lib/types";

export interface SavedView { id: string; name: string; filters: Partial<FilterState>; hidden: string[]; order: string[] }
export interface Layout { hidden: string[]; order: string[] }

/** Saved dashboard views: filters plus which sections show and in what order. */
export function ViewsBar({ filters, setFilters, sections, layout, setLayout }: {
  filters: FilterState; setFilters: (f: FilterState) => void;
  sections: { id: string; label: string }[]; layout: Layout; setLayout: (l: Layout) => void;
}) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => { getJson<{ views: SavedView[] }>("/api/views").then((r) => setViews(r.views)).catch(() => { /* optional */ }); }, []);
  useEffect(() => { load(); }, [load]);

  const order = [...sections.map((s) => s.id)].sort((a, b) => {
    const ia = layout.order.indexOf(a), ib = layout.order.indexOf(b);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });
  const move = (id: string, d: -1 | 1) => {
    const i = order.indexOf(id), j = i + d;
    if (j < 0 || j >= order.length) return;
    const next = [...order]; [next[i], next[j]] = [next[j], next[i]];
    setLayout({ ...layout, order: next });
  };
  const toggle = (id: string) => setLayout({ ...layout, hidden: layout.hidden.includes(id) ? layout.hidden.filter((x) => x !== id) : [...layout.hidden, id] });
  const apply = (id: string) => {
    setActive(id);
    const v = views.find((x) => x.id === id);
    if (!v) { setLayout({ hidden: [], order: [] }); return; }
    setFilters({ date_from: "", date_to: "", entity_id: "", category: "", status: "", ...v.filters } as FilterState);
    setLayout({ hidden: v.hidden, order: v.order });
  };
  async function save() {
    setMsg(null);
    try {
      const f: Record<string, string> = {};
      for (const [k, v] of Object.entries(filters)) if (typeof v === "string" && v) f[k] = v;
      const v = await postJson<SavedView>("/api/views", { name: name.trim(), filters: f, hidden: layout.hidden, order });
      setName(""); load(); setActive(v.id); setMsg("Saved.");
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Couldn't save the view."); }
  }
  async function remove() {
    if (!active) return;
    try { await deleteJson(`/api/views/${active}`); setActive(""); load(); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Couldn't delete."); }
  }
  return (
    <section className="card p-3" aria-label="Saved views">
      <div className="flex flex-wrap items-end gap-2 text-sm">
        <label className="flex flex-col gap-1 text-xs text-muted">View
          <select className="field" value={active} onChange={(e) => apply(e.target.value)}>
            <option value="">Default layout</option>
            {views.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </label>
        <button className="btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}><LayoutGrid className="h-4 w-4" aria-hidden /> Customize sections</button>
        <label className="flex flex-col gap-1 text-xs text-muted">Save current as
          <input className="field" value={name} maxLength={40} placeholder="e.g. Weekly review" onChange={(e) => setName(e.target.value)} />
        </label>
        <button className="btn" onClick={save} disabled={!name.trim()}><Save className="h-4 w-4" aria-hidden /> Save view</button>
        {active && <button className="btn" onClick={remove} aria-label="Delete this view"><Trash2 className="h-4 w-4" aria-hidden /> Delete</button>}
        {msg && <span role="status" className="text-xs text-muted">{msg}</span>}
      </div>
      {open && (
        <ul className="mt-3 grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
          {order.map((id, i) => (
            <li key={id} className="flex items-center gap-2 rounded-md border border-line px-2 py-1 text-sm">
              <label className="flex min-w-0 flex-1 items-center gap-2"><input type="checkbox" checked={!layout.hidden.includes(id)} onChange={() => toggle(id)} /><span className="truncate">{sections.find((s) => s.id === id)?.label}</span></label>
              <button className="btn !px-1.5 !py-0.5" disabled={i === 0} onClick={() => move(id, -1)} aria-label="Move up"><ArrowUp className="h-3.5 w-3.5" aria-hidden /></button>
              <button className="btn !px-1.5 !py-0.5" disabled={i === order.length - 1} onClick={() => move(id, 1)} aria-label="Move down"><ArrowDown className="h-3.5 w-3.5" aria-hidden /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
