"use client";
import { useState } from "react";
import { postJson } from "@/lib/api";
import { Field, errMsg } from "./kit";

// ---------------------------------------------------------------- shared types
export interface Col { name: string; kind: "number" | "text" | "date" | "bool"; distinct?: number }
export interface Source { id: string; label: string; rows: number | null; columns: Col[] }
export interface AType { id: string; label: string; blurb: string }
export interface Cond { column: string; op: string; value: string; value2: string }
export type Mode = "and" | "or";
export interface Base { source: string; filters: { column: string; op: string; value: string; value2?: string }[]; mode: Mode }

export const OPS: Record<string, { id: string; label: string }[]> = {
  number: [["eq", "is"], ["ne", "is not"], ["gt", ">"], ["gte", ">="], ["lt", "<"], ["lte", "<="], ["between", "between"], ["is_null", "is empty"], ["not_null", "is not empty"]].map(([id, label]) => ({ id, label })),
  date: [["eq", "is"], ["gt", "after"], ["gte", "on or after"], ["lt", "before"], ["lte", "on or before"], ["between", "between"], ["is_null", "is empty"], ["not_null", "is not empty"]].map(([id, label]) => ({ id, label })),
  text: [["eq", "is"], ["ne", "is not"], ["in", "is one of"], ["contains", "contains"], ["is_null", "is empty"], ["not_null", "is not empty"]].map(([id, label]) => ({ id, label })),
  bool: [["eq", "is"], ["ne", "is not"], ["is_null", "is empty"], ["not_null", "is not empty"]].map(([id, label]) => ({ id, label })),
};
export const NO_VALUE = new Set(["is_null", "not_null"]);


export const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
export const pv = (v: number | null | undefined) => (v == null ? "—" : v < 0.001 ? "<0.001" : v.toFixed(3));

export function Sentences({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((s, i) => <li key={i}>{s}</li>)}</ul>;
}
export function Lesson({ text }: { text?: string }) {
  return text ? <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">{text}</p> : null;
}
export function Warn({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return <div className="space-y-1">{items.map((w, i) => <p key={i} className="rounded border border-line px-3 py-2 text-xs" style={{ background: "var(--warn-bg)" }}>{w}</p>)}</div>;
}
export function ColSelect({ label, value, onChange, cols, kinds, none }: { label: string; value: string; onChange: (v: string) => void; cols: Col[]; kinds?: Col["kind"][]; none?: string }) {
  const list = kinds ? cols.filter((c) => kinds.includes(c.kind)) : cols;
  return (
    <Field label={label}>
      <select className="field" value={value} onChange={(e) => onChange(e.target.value)}>
        {none !== undefined && <option value="">{none}</option>}
        {list.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
      </select>
    </Field>
  );
}
export function useRun<T>() {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (path: string, body: unknown) => {
    setBusy(true); setErr(null);
    try { setData(await postJson<T>(path, body)); } catch (e) { setData(null); setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); }
  };
  return { data, err, busy, run, reset: () => { setData(null); setErr(null); } };
}
/** Category columns with a handful of values (good to group by); ID-like columns are left for last. */
export const groupish = (cols: Col[]) => cols.filter((c) => (c.kind === "text" || c.kind === "bool") && (c.distinct ?? 2) >= 2 && (c.distinct ?? 2) <= 30);
export const first = (cols: Col[], kind: Col["kind"], skip: string[] = []) => cols.find((c) => c.kind === kind && !skip.includes(c.name))?.name ?? "";


export function CondEditor({ label, cols, c, set }: { label: string; cols: Col[]; c: Cond; set: (c: Cond) => void }) {
  const k = cols.find((x) => x.name === c.column)?.kind ?? "text";
  return (
    <div className="grid gap-2 sm:grid-cols-4">
      <div className="self-end text-sm font-medium">{label}</div>
      <Field label="Column"><select className="field" value={c.column} onChange={(e) => { const nk = cols.find((x) => x.name === e.target.value)?.kind ?? "text"; set({ column: e.target.value, op: OPS[nk][0].id, value: "", value2: "" }); }}>{cols.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}</select></Field>
      <Field label="Condition"><select className="field" value={c.op} onChange={(e) => set({ ...c, op: e.target.value })}>{OPS[k].map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</select></Field>
      {!NO_VALUE.has(c.op) && <Field label={c.op === "between" ? "From" : "Value"}><input className="field" type={k === "date" ? "date" : "text"} value={c.value} onChange={(e) => set({ ...c, value: e.target.value })} /></Field>}
      {c.op === "between" && <Field label="To"><input className="field" type={k === "date" ? "date" : "text"} value={c.value2} onChange={(e) => set({ ...c, value2: e.target.value })} /></Field>}
    </div>
  );
}
