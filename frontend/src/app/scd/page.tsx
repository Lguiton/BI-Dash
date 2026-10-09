"use client";

import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { ScdCompare, ScdState } from "@/lib/types";

const money = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

export default function ScdPage() {
  const [state, setState] = useState<ScdState | null>(null);
  const [cmp, setCmp] = useState<ScdCompare | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [entity, setEntity] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [bounds, setBounds] = useState<{ min: string; max: string } | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([
      getJson<ScdState>("/api/scd/state", ctl.signal),
      getJson<ScdCompare>("/api/scd/compare", ctl.signal),
      getJson<{ min_date: string | null; max_date: string | null }>("/api/analytics/meta", ctl.signal),
    ]).then(([s, c, m]) => {
      setState(s); setCmp(c); setError(null);
      if (m.min_date && m.max_date) {
        setBounds({ min: m.min_date, max: m.max_date });
        // default the effective date to the middle of the data, so the demo has history on both sides
        const mid = new Date((Date.parse(m.min_date) + Date.parse(m.max_date)) / 2);
        setDate((d) => d || mid.toISOString().slice(0, 10));
      }
    }).catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the SCD lab."); });
    return () => ctl.abort();
  }, [version]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  const entityId = entity || state?.type1[0]?.entity_id || "";
  const currentCat = state?.type1.find((r) => r.entity_id === entityId)?.category ?? "";
  const categories = [...new Set((state?.type1 ?? []).map((r) => r.category).filter(Boolean))] as string[];
  const effective = date;

  async function apply() {
    setBusy(true); setError(null); setNotice(null);
    try {
      await postJson("/api/scd/change", { entity_id: entityId, new_category: category.trim(), effective_date: effective });
      setNotice(`${entityId} moved to "${category.trim()}" from ${effective}. Compare the two tables below.`);
      setCategory(""); refresh();
    } catch (e) { setError(e instanceof ApiError ? e.message : "Change failed."); } finally { setBusy(false); }
  }
  async function reset() {
    if (!window.confirm("Reset both sandbox tables back to the current dim_entities?")) return;
    setBusy(true); setError(null); setNotice(null);
    try { await postJson("/api/scd/reset", {}); setNotice("Sandbox reset."); refresh(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Reset failed."); } finally { setBusy(false); }
  }

  const changed = (cmp?.changes_made ?? 0) > 0;
  const showDate = (d: string) => (state && d === state.beginning ? "(beginning)" : state && d === state.forever ? "(current)" : d);

  return (
    <PageShell title="SCD lab" subtitle="Slowly changing dimensions: what happens to history when an entity's category changes?">
      <section className="card space-y-2 p-5 text-sm" aria-label="Concept">
        <p>A dimension value changes over time (a zone is re-classified from Logistics to Fleet). Two common ways to store it:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li><b>Type 1, overwrite:</b> replace the old value. Simple, but <b>history is rewritten</b>: last year&apos;s revenue now appears under the new category.</li>
          <li><b>Type 2, add a row:</b> close the old version (<span className="font-mono">valid_to</span>) and add a new one (<span className="font-mono">valid_from</span>, <span className="font-mono">is_current</span>). Facts join on the version that was valid <i>on their date</i>, so history stays true.</li>
        </ul>
        <p className="text-muted">This works on sandbox copies (<span className="font-mono">scd_type1</span>, <span className="font-mono">scd_type2</span>). Your real <span className="font-mono">dim_entities</span> is never changed. Both tables are queryable in SQL Lab.</p>
      </section>

      {error && <ErrorBanner message={error} />}
      {notice && <div role="status" className="rounded-lg px-4 py-3 text-sm" style={{ background: "var(--good-bg)", color: "var(--good)" }}>{notice}</div>}

      {state && state.type1.length === 0 && <p className="text-sm text-muted">No entities yet. Load some data on the dashboard first.</p>}

      {state && state.type1.length > 0 && (
        <section className="card p-5" aria-label="Make a change">
          <h2 className="text-lg font-semibold">1. Change a category</h2>
          <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); void apply(); }}>
            <label className="text-sm">Entity
              <select className="field mt-1 block" value={entityId} onChange={(e) => setEntity(e.target.value)}>
                {state.type1.map((r) => <option key={r.entity_id} value={r.entity_id}>{r.name ?? r.entity_id} ({r.category})</option>)}
              </select>
            </label>
            <label className="text-sm">New category
              <input className="field mt-1 block" list="cats" value={category} onChange={(e) => setCategory(e.target.value)} placeholder={`not "${currentCat}"`} maxLength={40} required />
              <datalist id="cats">{categories.filter((c) => c !== currentCat).map((c) => <option key={c} value={c} />)}</datalist>
            </label>
            <label className="text-sm">Effective from
              <input className="field mt-1 block" type="date" value={effective} min={bounds?.min} max={bounds?.max} onChange={(e) => setDate(e.target.value)} required />
            </label>
            <button className="btn btn-primary" disabled={busy || !category.trim() || !effective}>Apply to both</button>
            <button type="button" className="btn" onClick={reset} disabled={busy}><RotateCcw className="h-4 w-4" aria-hidden /> Reset</button>
          </form>
          <p className="mt-2 text-xs text-muted">Tip: pick a date in the middle of the data range so the entity has facts both before and after the change.</p>
        </section>
      )}

      {state && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="card overflow-x-auto" aria-label="Type 1 table">
            <h2 className="p-4 pb-2 text-lg font-semibold">scd_type1 <span className="text-xs font-normal text-muted">one row per entity</span></h2>
            <table className="w-full text-sm">
              <thead><tr><th className="th">entity_id</th><th className="th">name</th><th className="th">category</th></tr></thead>
              <tbody>{state.type1.map((r) => <tr key={r.entity_id} className="border-t border-line"><td className="td font-mono text-xs">{r.entity_id}</td><td className="td">{r.name}</td><td className="td">{r.category}</td></tr>)}</tbody>
            </table>
          </section>
          <section className="card overflow-x-auto" aria-label="Type 2 table">
            <h2 className="p-4 pb-2 text-lg font-semibold">scd_type2 <span className="text-xs font-normal text-muted">one row per version</span></h2>
            <table className="w-full text-sm">
              <thead><tr><th className="th">entity_id</th><th className="th">category</th><th className="th">valid_from</th><th className="th">valid_to</th><th className="th">current</th></tr></thead>
              <tbody>{state.type2.map((r) => (
                <tr key={r.surrogate_key} className="border-t border-line" style={r.is_current ? undefined : { color: "var(--muted)" }}>
                  <td className="td font-mono text-xs">{r.entity_id}</td><td className="td">{r.category}</td>
                  <td className="td">{showDate(r.valid_from)}</td><td className="td">{showDate(r.valid_to)}</td><td className="td">{r.is_current ? "yes" : "no"}</td>
                </tr>))}</tbody>
            </table>
          </section>
        </div>
      )}

      {cmp && (
        <section className="card overflow-x-auto" aria-label="Revenue comparison">
          <h2 className="p-4 pb-1 text-lg font-semibold">2. Same facts, revenue by category</h2>
          <p className="px-4 pb-3 text-sm text-muted">
            {changed ? "Type 1 moved all of the changed entity's history to the new category. Type 2 split it at the effective date." : "Nothing has changed yet, so both methods agree. Make a change above."}
          </p>
          <table className="w-full min-w-[560px] text-sm">
            <thead><tr><th className="th">Category</th><th className="th th-r">Type 1 revenue</th><th className="th th-r">Type 2 revenue</th><th className="th th-r">Difference</th></tr></thead>
            <tbody>
              {cmp.rows.map((r) => (
                <tr key={r.category} className="border-t border-line">
                  <td className="td">{r.category}</td>
                  <td className="td text-right tabular-nums">{money(r.type1_revenue)}</td>
                  <td className="td text-right tabular-nums">{money(r.type2_revenue)}</td>
                  <td className="td text-right font-semibold tabular-nums" style={r.difference !== 0 ? { color: "var(--bad)" } : { color: "var(--muted)" }}>
                    {r.difference > 0 ? "+" : r.difference < 0 ? "−" : ""}{money(Math.abs(r.difference))}
                  </td>
                </tr>
              ))}
              <tr className="border-t border-line font-semibold">
                <td className="td">Total</td><td className="td text-right tabular-nums">{money(cmp.total_type1)}</td>
                <td className="td text-right tabular-nums">{money(cmp.total_type2)}</td><td className="td text-right text-muted">same total</td>
              </tr>
            </tbody>
          </table>
          <details className="border-t border-line p-4 text-sm">
            <summary className="cursor-pointer font-medium">Show the two SQL queries</summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-panel2 p-3 font-mono text-xs leading-relaxed" tabIndex={0}>{`-- Type 1: join on the key only
SELECT d.category, SUM(f.revenue)
FROM fact_operations f JOIN scd_type1 d ON f.entity_id = d.entity_id
GROUP BY 1;

-- Type 2: join on the key AND the version valid on the fact's date
SELECT d.category, SUM(f.revenue)
FROM fact_operations f
JOIN scd_type2 d ON f.entity_id = d.entity_id
 AND f.record_date BETWEEN d.valid_from AND d.valid_to
GROUP BY 1;`}</pre>
          </details>
        </section>
      )}
    </PageShell>
  );
}
