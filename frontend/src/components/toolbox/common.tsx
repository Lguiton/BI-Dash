"use client";
import { useEffect, useState, type ReactNode } from "react";
import { API_BASE, apiFetch, getJson } from "@/lib/api";
import { Table, errMsg } from "@/components/panels/kit";

export type Source = { id: string; label: string };
export type Col = { name: string; type: string };

export function useSources(): Source[] {
  const [s, setS] = useState<Source[]>([]);
  useEffect(() => {
    let live = true;
    Promise.all([
      getJson<{ packs: { id: string; title: string; rows: number | null }[] }>("/api/biz-packs").catch(() => ({ packs: [] })),
      getJson<{ tables: { table_name: string; label: string }[] }>("/api/data/tables").catch(() => ({ tables: [] })),
    ]).then(([p, t]) => {
      if (live) setS([...p.packs.filter((x) => x.rows).map((x) => ({ id: x.id, label: `${x.title} (dashboard)` })), ...t.tables.map((x) => ({ id: x.table_name, label: `${x.label || x.table_name} (table)` }))]);
    });
    return () => { live = false; };
  }, []);
  return s;
}

export function useCols(source: string): Col[] {
  const [c, setC] = useState<{ source: string; cols: Col[] }>({ source: "", cols: [] });
  useEffect(() => {
    if (!source) return;
    let live = true;
    getJson<{ columns: Col[] }>(`/api/toolbox/analyst/columns?source=${encodeURIComponent(source)}`).then((r) => { if (live) setC({ source, cols: r.columns }); }).catch(() => { if (live) setC({ source, cols: [] }); });
    return () => { live = false; };
  }, [source]);
  return c.source === source ? c.cols : [];
}

export const isNum = (t: string) => /INT|DOUBLE|DECIMAL|FLOAT|REAL|HUGEINT/i.test(t);
export const isDate = (t: string) => /DATE|TIMESTAMP/i.test(t);

export function Pick({ label, value, onChange, options, blank = "Choose…" }: { label: string; value: string; onChange: (v: string) => void; options: { id: string; label: string }[]; blank?: string }) {
  return (
    <label className="grid gap-1 text-xs text-muted">{label}
      <select aria-label={label} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{blank}</option>
        {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function SourcePick({ value, onChange, label = "Data" }: { value: string; onChange: (v: string) => void; label?: string }) {
  const s = useSources();
  return <Pick label={label} value={value} onChange={onChange} options={s} />;
}

export function Notes({ items, tone = "warn" }: { items?: string[]; tone?: "warn" | "info" }) {
  if (!items?.length) return null;
  return <ul className={`mt-2 grid gap-1 rounded border p-2 text-sm ${tone === "warn" ? "border-amber-500 bg-amber-500/10" : "border-line bg-panel2"}`}>{items.map((n, i) => <li key={i}>{n}</li>)}</ul>;
}

export function Rows({ columns, rows, caption }: { columns: string[]; rows: (string | number | null)[][]; caption?: string }) {
  return <Table caption={caption} head={columns} rows={rows.map((r) => r.map((x): ReactNode => (x == null ? "—" : typeof x === "number" ? x.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(x))))} />;
}

export function HtmlFrame({ html, name }: { html: string; name: string }) {
  function save() {
    const u = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const a = document.createElement("a");
    a.href = u; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(u), 2000);
  }
  return (
    <div className="mt-2">
      <button className="btn mb-2" onClick={save}>Download HTML</button>
      <iframe title="Preview" sandbox="" srcDoc={html} className="h-[28rem] w-full rounded border border-line bg-white" />
    </div>
  );
}

export async function fetchText(path: string, body: unknown): Promise<string> {
  const r = await apiFetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const t = await r.text();
  if (!r.ok) {
    let m = t;
    try { m = (JSON.parse(t) as { detail?: string }).detail || t; } catch { /* keep text */ }
    throw new Error(m || "Request failed.");
  }
  return t;
}

export { errMsg };
