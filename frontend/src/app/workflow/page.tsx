"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { NotebookButton } from "@/components/NotebookButton";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, postJson } from "@/lib/api";

interface Col { name: string; type: string; kind: string }
interface Src { table: string; label: string; kind: string; columns: Col[] }
interface Measure { agg: string; column: string }
type Step = Record<string, unknown> & { kind: string };
interface RunRes { sql: string; pandas: string; notes: string[]; columns: Col[]; names: string[]; rows: (string | number | null)[][]; row_counts: number[]; total_rows: number; truncated: boolean }
interface Saved { id: number; name: string; steps: Step[]; updated_at: string }

const OPS = ["=", "!=", ">", ">=", "<", "<=", "contains", "is_null", "not_null"];
const AGGS = ["sum", "avg", "min", "max", "count", "median", "distinct"];

export default function WorkflowPage() {
  const [sources, setSources] = useState<Src[]>([]);
  const [table, setTable] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [res, setRes] = useState<RunRes | null>(null);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [wid, setWid] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [tableName, setTableName] = useState("");
  const [tab, setTab] = useState("rows");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ver, setVer] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([getJson<{ sources: Src[] }>("/api/workflows/sources", ctl.signal), getJson<{ workflows: Saved[] }>("/api/workflows", ctl.signal)])
      .then(([s, w]) => { setSources(s.sources); setSaved(w.workflows); setTable((t) => t || (s.sources.find((x) => x.table === "v_operations_flat") ?? s.sources[0])?.table || ""); })
      .catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load tables.")); });
    return () => ctl.abort();
  }, [ver]);

  const full = useMemo<Step[]>(() => (table ? [{ kind: "source", table }, ...steps] : []), [table, steps]);

  // The columns available at the end of the chain, from the last preview (or the source's own columns before the first run).
  const cols: Col[] = useMemo(() => res?.columns ?? sources.find((s) => s.table === table)?.columns ?? [], [res, sources, table]);
  const sourceCols: Col[] = sources.find((s) => s.table === table)?.columns ?? [];

  const run = useCallback(async (list: Step[]) => {
    setBusy(true); setErr(null); setMsg(null);
    try { setRes(await postJson<RunRes>("/api/workflows/run", { steps: list, limit: 100 })); } catch (e) { setErr(errMsg(e, "That workflow didn't run.")); setRes(null); } finally { setBusy(false); }
  }, []);

  const add = (kind: string) => {
    const first = (cols[0]?.name) ?? "";
    const num = cols.find((c) => c.kind === "number")?.name ?? first;
    const base: Record<string, Step> = {
      filter: { kind, column: num, op: ">", value: "0" },
      select: { kind, columns: cols.slice(0, 3).map((c) => c.name) },
      derive: { kind, name: "new_column", a: num, op: "/", b_column: num, b_value: "" },
      aggregate: { kind, group_by: [], measures: [{ agg: "sum", column: num }] },
      sort: { kind, column: first, desc: true },
      limit: { kind, n: 100 },
    };
    setSteps([...steps, base[kind]]); setRes(null);
  };
  const upd = (i: number, patch: Record<string, unknown>) => { setSteps(steps.map((s, n) => (n === i ? { ...s, ...patch } : s))); setRes(null); };
  const del = (i: number) => { setSteps(steps.filter((_, n) => n !== i)); setRes(null); };
  const move = (i: number, d: number) => { const n = [...steps]; const j = i + d; if (j < 0 || j >= n.length) return; [n[i], n[j]] = [n[j], n[i]]; setSteps(n); setRes(null); };

  const clean = (s: Step): Step => {
    if (s.kind === "derive") { const o = { ...s }; if (o.b_column) delete o.b_value; else delete o.b_column; return o; }
    return s;
  };
  const payload = full.map(clean);

  const save = async () => {
    setErr(null); setMsg(null);
    try { const r = await postJson<{ id: number }>("/api/workflows", { name: name || "My workflow", steps: payload, id: wid ?? undefined }); setWid(r.id); setMsg("Saved."); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  };
  const saveTable = async () => {
    setErr(null); setMsg(null);
    try { const r = await postJson<{ table: string; rows: number }>("/api/workflows/save-table", { name: tableName, steps: payload }); setMsg(`Saved ${r.rows.toLocaleString()} rows as table ${r.table}. Find it in My data and the Dataset hub.`); } catch (e) { setErr(errMsg(e, "Couldn't save the table.")); }
  };
  const load = (w: Saved) => { setTable(String(w.steps[0]?.table ?? "")); setSteps(w.steps.slice(1)); setWid(w.id); setName(w.name); setRes(null); };

  const colSel = (value: string, on: (v: string) => void, only?: string, label = "Column") => (
    <select className="field" aria-label={label} value={value} onChange={(e) => on(e.target.value)}>{(only ? cols.filter((c) => c.kind === only) : cols).map((c) => <option key={c.name}>{c.name}</option>)}</select>
  );

  return (
    <PageShell title="Workflow builder" subtitle="Chain simple steps over a table. The app writes the SQL and the pandas for you and shows the rows that survive each step.">
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="rounded-lg p-2 text-sm" style={{ background: "var(--good-bg)", color: "var(--good)" }}>{msg}</p>}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="min-w-0 space-y-4">
          <Section title="1. Start from a table">
            <select className="field w-full" aria-label="Source table" value={table} onChange={(e) => { setTable(e.target.value); setSteps([]); setRes(null); }}>
              {sources.map((s) => <option key={s.table} value={s.table}>{s.label} ({s.kind})</option>)}
            </select>
            <p className="mt-1 text-xs text-muted">{sourceCols.length} columns: {sourceCols.map((c) => c.name).join(", ")}</p>
          </Section>
          <Section title="2. Add steps">
            <div className="flex flex-wrap gap-2">
              {["filter", "select", "derive", "aggregate", "sort", "limit"].map((k) => <button key={k} className="btn" disabled={!table || steps.length >= 12} onClick={() => add(k)}>+ {k}</button>)}
            </div>
            <ol className="mt-3 space-y-3">
              {steps.map((s, i) => (
                <li key={i} className="rounded border border-line p-3 text-sm">
                  <div className="mb-2 flex items-center gap-2"><Badge>{i + 1}</Badge><b>{s.kind}</b>
                    <span className="ml-auto flex gap-1"><button className="btn" aria-label="Move up" onClick={() => move(i, -1)}>↑</button><button className="btn" aria-label="Move down" onClick={() => move(i, 1)}>↓</button><button className="btn" aria-label={`Remove step ${i + 1}`} onClick={() => del(i)}>Remove</button></span></div>
                  <div className="flex flex-wrap items-end gap-2">
                    {s.kind === "filter" && (<>
                      {colSel(String(s.column), (v) => upd(i, { column: v }))}
                      <select className="field" aria-label="Comparison" value={String(s.op)} onChange={(e) => upd(i, { op: e.target.value })}>{OPS.map((o) => <option key={o}>{o}</option>)}</select>
                      {!["is_null", "not_null"].includes(String(s.op)) && <input className="field w-32" aria-label="Value" value={String(s.value ?? "")} onChange={(e) => upd(i, { value: e.target.value })} />}
                    </>)}
                    {s.kind === "select" && (
                      <div className="flex max-h-40 flex-wrap gap-x-3 gap-y-1 overflow-y-auto">{cols.map((c) => {
                        const on = (s.columns as string[]).includes(c.name);
                        return <label key={c.name} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={on} onChange={() => upd(i, { columns: on ? (s.columns as string[]).filter((x) => x !== c.name) : [...(s.columns as string[]), c.name] })} />{c.name}</label>;
                      })}</div>
                    )}
                    {s.kind === "derive" && (<>
                      <Field label="New column"><input className="field w-32" value={String(s.name)} onChange={(e) => upd(i, { name: e.target.value })} /></Field>
                      {colSel(String(s.a), (v) => upd(i, { a: v }), "number", "First column")}
                      <select className="field" aria-label="Operator" value={String(s.op)} onChange={(e) => upd(i, { op: e.target.value })}>{["+", "-", "*", "/"].map((o) => <option key={o}>{o}</option>)}</select>
                      <select className="field" aria-label="Second column or number" value={s.b_column ? String(s.b_column) : "#"} onChange={(e) => upd(i, e.target.value === "#" ? { b_column: "", b_value: "1" } : { b_column: e.target.value })}>
                        <option value="#">a number…</option>{cols.filter((c) => c.kind === "number").map((c) => <option key={c.name}>{c.name}</option>)}
                      </select>
                      {!s.b_column && <input className="field w-24" aria-label="Number" value={String(s.b_value ?? "")} onChange={(e) => upd(i, { b_value: e.target.value })} />}
                    </>)}
                    {s.kind === "aggregate" && (
                      <div className="w-full space-y-2">
                        <div className="flex max-h-28 flex-wrap gap-x-3 gap-y-1 overflow-y-auto"><span className="text-xs text-muted">Group by:</span>{cols.map((c) => {
                          const on = (s.group_by as string[]).includes(c.name);
                          return <label key={c.name} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={on} onChange={() => upd(i, { group_by: on ? (s.group_by as string[]).filter((x) => x !== c.name) : [...(s.group_by as string[]), c.name] })} />{c.name}</label>;
                        })}</div>
                        {(s.measures as Measure[]).map((m, n) => (
                          <div key={n} className="flex flex-wrap items-center gap-2">
                            <select className="field" aria-label="Calculation" value={m.agg} onChange={(e) => upd(i, { measures: (s.measures as Measure[]).map((x, k) => (k === n ? { ...x, agg: e.target.value } : x)) })}>{AGGS.map((a) => <option key={a}>{a}</option>)}</select>
                            <span className="text-xs text-muted">of</span>
                            <select className="field" aria-label="Measure column" value={m.column} onChange={(e) => upd(i, { measures: (s.measures as Measure[]).map((x, k) => (k === n ? { ...x, column: e.target.value } : x)) })}><option value="*">all rows</option>{cols.map((c) => <option key={c.name}>{c.name}</option>)}</select>
                            <button className="btn" onClick={() => upd(i, { measures: (s.measures as Measure[]).filter((_, k) => k !== n) })}>×</button>
                          </div>
                        ))}
                        <button className="btn" onClick={() => upd(i, { measures: [...(s.measures as Measure[]), { agg: "count", column: "*" }] })}>+ measure</button>
                      </div>
                    )}
                    {s.kind === "sort" && (<>
                      {colSel(String(s.column), (v) => upd(i, { column: v }))}
                      <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={Boolean(s.desc)} onChange={(e) => upd(i, { desc: e.target.checked })} /> largest first</label>
                    </>)}
                    {s.kind === "limit" && <Field label="Keep rows"><input className="field w-28" type="number" min={1} value={Number(s.n)} onChange={(e) => upd(i, { n: Number(e.target.value) })} /></Field>}
                  </div>
                </li>
              ))}
              {steps.length === 0 && <li className="text-sm text-muted">No steps yet. The workflow is just the whole table.</li>}
            </ol>
            <button className="btn btn-primary mt-3" disabled={busy || !table} onClick={() => run(payload)}>{busy ? "Running…" : "Run"}</button>
            <span className="ml-2 mt-3 inline-block"><NotebookButton kind="workflow" body={() => ({ steps: payload, title: "Workflow" })} disabled={!table} /></span>
          </Section>
          <Section title="3. Save" note="Saving a table writes a NEW table in My data. Built-in tables are never changed.">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Workflow name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} /></Field>
              <button className="btn" disabled={!table} onClick={save}>{wid ? "Update workflow" : "Save workflow"}</button>
            </div>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <Field label="Save the result as a table"><input className="field" value={tableName} placeholder="top_customers" onChange={(e) => setTableName(e.target.value)} /></Field>
              <button className="btn" disabled={!table || !tableName.trim()} onClick={saveTable}>Save as table</button>
            </div>
          </Section>
          {saved.length > 0 && (
            <Section title="Saved workflows">
              <ul className="space-y-1 text-sm">{saved.map((w) => (
                <li key={w.id} className="flex items-center gap-2"><span className="min-w-0 flex-1 truncate">{w.name} <span className="text-xs text-muted">({w.steps.length - 1} steps)</span></span>
                  <button className="btn" onClick={() => load(w)}>Open</button>
                  <button className="btn" aria-label={`Delete ${w.name}`} onClick={async () => { try { await deleteJson(`/api/workflows/${w.id}`); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, "Couldn't delete.")); } }}>Delete</button></li>
              ))}</ul>
            </Section>
          )}
        </div>
        <div className="min-w-0 space-y-4">
          {!res && <p className="text-sm text-muted">Press Run to see the rows, the row count after every step, and the code.</p>}
          {res && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="Rows out" value={res.total_rows.toLocaleString()} sub={res.truncated ? "showing the first 100" : undefined} />
                <Stat label="Columns" value={String(res.names.length)} />
                <Stat label="Steps" value={String(res.notes.length)} />
              </div>
              <Section title="What happens, step by step">
                <ol className="space-y-1 text-sm">{res.notes.map((n, i) => <li key={i} className="flex gap-2"><Badge>{i === 0 ? "start" : `step ${i}`}</Badge><span className="min-w-0 flex-1">{n}</span><span className="text-xs text-muted tabular-nums">{res.row_counts[i].toLocaleString()} rows</span></li>)}</ol>
              </Section>
              <Tabs tabs={[{ id: "rows", label: "Result" }, { id: "sql", label: "SQL" }, { id: "pandas", label: "pandas" }]} value={tab} onChange={setTab} label="Workflow output" />
              {tab === "rows" && <Section title="Result"><Table head={res.names} rows={res.rows.map((r) => r.map((v) => (v === null ? "—" : String(v))))} caption="Workflow result" /></Section>}
              {tab === "sql" && <Section title="SQL (read-only)"><pre className="overflow-x-auto rounded bg-panel2 p-3 text-xs">{res.sql}</pre></Section>}
              {tab === "pandas" && <Section title="The same thing in pandas" note="Division by zero gives NULL in SQL and inf in pandas; everything else matches."><pre className="overflow-x-auto rounded bg-panel2 p-3 text-xs">{res.pandas}</pre></Section>}
            </>
          )}
        </div>
      </div>
    </PageShell>
  );
}
