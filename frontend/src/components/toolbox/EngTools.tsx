"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Tabs, errMsg } from "@/components/panels/kit";
import { Notes, Pick, Rows, SourcePick, useCols } from "./common";
import { Scripts } from "./Scripts";

type Chg = { kind: string; column: string; to?: string; severity: string; says: string };
type Sc = { status: string; says: string; changes: Chg[]; baseline_at?: string };
type Prev = { says: string; warnings: string[]; examples?: Record<string, string | number>[]; note?: string; explosion?: boolean; rows_to_remove?: number };
type CCol = { name: string; kind: string; nullable: boolean; unique?: boolean; min?: number; max?: number; allowed?: string[] };
type Chk = { status: string; says: string; issues: { column: string; rule: string; says: string; examples: string[] }[]; extra_columns: string[] };
type Est = { total_rows: number; storage_raw_gb: number; storage_db_gb: number; memory_if_loaded_gb: number; load_seconds_range: number[]; full_scan_seconds_range: number[]; tier: string; recommendation: string; notes: string[]; assumptions: string[]; caution: string };

function SchemaCheck() {
  const [src, setSrc] = useState("");
  const [r, setR] = useState<Sc | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const post = async (path: string, extra = {}) => { setErr(null); setMsg(null); try { return await postJson<Record<string, unknown>>(`/api/toolbox/de/${path}`, { source: src, ...extra }); } catch (e) { setErr(errMsg(e, "That did not work.")); return null; } };
  return (
    <Section title="Schema change detector" note="Save the shape of a table while the data is good, then check after each load. It spots missing, renamed, new and retyped columns.">
      {err && <ErrorBanner message={err} />}
      <SourcePick value={src} onChange={(v) => { setSrc(v); setR(null); setMsg(null); }} />
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn" disabled={!src} onClick={async () => { const x = await post("snapshot"); if (x) setMsg(`Saved the current shape (${x.columns} columns).`); }}>Save current shape as baseline</button>
        <button className="btn" disabled={!src} onClick={async () => { const x = await post("schema-check"); if (x) setR(x as unknown as Sc); }}>Check against baseline</button>
        {r && r.changes.length > 0 && <button className="btn" onClick={async () => { const x = await post("schema-check", { accept: true }); if (x) { setR(x as unknown as Sc); setMsg("New shape accepted as the baseline."); } }}>Accept as new baseline</button>}
      </div>
      {msg && <p className="mt-2 text-sm">{msg}</p>}
      {r && (
        <div className="mt-3">
          <p aria-label="Schema verdict" className="text-sm"><Badge tone={r.status === "ok" ? "ok" : r.status === "breaking" ? "bad" : "warn"}>{r.status.replace("_", " ")}</Badge> {r.says}</p>
          <ul className="mt-2 grid gap-1 text-sm">{r.changes.map((c, i) => <li key={i}><Badge tone={c.severity === "high" ? "bad" : c.severity === "medium" ? "warn" : "muted"}>{c.kind.replace("_", " ")}</Badge> {c.says}</li>)}</ul>
        </div>
      )}
    </Section>
  );
}

function Dedupe() {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [keys, setKeys] = useState<string[]>([]);
  const [keep, setKeep] = useState("first");
  const [oc, setOc] = useState("");
  const [name, setName] = useState("");
  const [p, setP] = useState<Prev | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const body = { source: src, keys, keep, order_col: oc || null, new_table: name };
  return (
    <Section title="Dedupe" note="Preview what repeats, then make a NEW table without the repeats. The original is never changed.">
      {err && <ErrorBanner message={err} />}
      <SourcePick value={src} onChange={(v) => { setSrc(v); setKeys([]); setP(null); setMsg(null); }} />
      <p className="mt-2 text-xs text-muted">Columns that identify one real record:</p>
      <div className="flex flex-wrap gap-3 text-sm">{cols.map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={keys.includes(c.name)} onChange={(e) => { setKeys(e.target.checked ? [...keys, c.name] : keys.filter((x) => x !== c.name)); setP(null); }} />{c.name}</label>)}</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <Pick label="Keep which copy" value={keep} onChange={setKeep} options={[{ id: "first", label: "First in the file" }, { id: "last", label: "Last in the file" }, { id: "newest", label: "Newest (by a column)" }, { id: "oldest", label: "Oldest (by a column)" }]} blank="" />
        {(keep === "newest" || keep === "oldest") && <Pick label="Date or number column" value={oc} onChange={setOc} options={cols.map((c) => ({ id: c.name, label: c.name }))} />}
        <Field label="Name for the new table"><input aria-label="Dedupe new table" className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      </div>
      <div className="mt-3 flex gap-2">
        <button className="btn" disabled={!src || !keys.length} onClick={async () => { setErr(null); setMsg(null); try { setP(await postJson<Prev>("/api/toolbox/de/dedupe/preview", body)); } catch (e) { setErr(errMsg(e, "Could not preview.")); } }}>Preview</button>
        <button className="btn" disabled={!p || !name.trim() || !p.rows_to_remove} onClick={async () => { setErr(null); try { const r = await postJson<{ message: string }>("/api/toolbox/de/dedupe/apply", body); setMsg(r.message); setP(null); } catch (e) { setErr(errMsg(e, "Could not create.")); } }}>Create the new table</button>
      </div>
      {p && <div className="mt-3"><p aria-label="Dedupe preview" className="text-sm">{p.says}</p><Notes items={p.warnings} />{p.examples && p.examples.length > 0 && <Rows columns={Object.keys(p.examples[0])} rows={p.examples.map((e) => Object.values(e) as (string | number | null)[])} caption="Examples of repeats" />}<p className="mt-1 text-xs text-muted">{p.note}</p></div>}
      {msg && <p aria-label="Dedupe result" className="mt-2 text-sm">{msg}</p>}
    </Section>
  );
}

function Merge() {
  const [l, setL] = useState("");
  const [r, setR] = useState("");
  const lc = useCols(l), rc = useCols(r);
  const [f, setF] = useState({ lk: "", rk: "", how: "left", name: "", multiply: false });
  const [p, setP] = useState<Prev | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const body = { left: l, right: r, left_key: f.lk, right_key: f.rk, how: f.how, new_table: f.name, allow_multiply: f.multiply };
  return (
    <Section title="Merge" note="Preview the join first: matches, unmatched rows and any row multiplication. The result is a new table.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-2">
        <SourcePick label="Left table" value={l} onChange={(v) => { setL(v); setF({ ...f, lk: "" }); setP(null); }} />
        <SourcePick label="Right table" value={r} onChange={(v) => { setR(v); setF({ ...f, rk: "" }); setP(null); }} />
        <Pick label="Left key" value={f.lk} onChange={(v) => { setF({ ...f, lk: v }); setP(null); }} options={lc.map((c) => ({ id: c.name, label: c.name }))} />
        <Pick label="Right key" value={f.rk} onChange={(v) => { setF({ ...f, rk: v }); setP(null); }} options={rc.map((c) => ({ id: c.name, label: c.name }))} />
        <Pick label="Keep" value={f.how} onChange={(v) => { setF({ ...f, how: v }); setP(null); }} options={[{ id: "left", label: "Every left row" }, { id: "inner", label: "Only matches" }, { id: "full", label: "Everything" }]} blank="" />
        <Field label="Name for the new table"><input aria-label="Merge new table" className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
      </div>
      <div className="mt-3 flex gap-2">
        <button className="btn" disabled={!l || !r || !f.lk || !f.rk} onClick={async () => { setErr(null); setMsg(null); try { setP(await postJson<Prev>("/api/toolbox/de/merge/preview", body)); } catch (e) { setErr(errMsg(e, "Could not preview.")); } }}>Preview</button>
        <button className="btn" disabled={!p || !f.name.trim()} onClick={async () => { setErr(null); try { const x = await postJson<{ message: string }>("/api/toolbox/de/merge/apply", body); setMsg(x.message); setP(null); } catch (e) { setErr(errMsg(e, "Could not merge.")); } }}>Create the merged table</button>
      </div>
      {p?.explosion && <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={f.multiply} onChange={(e) => setF({ ...f, multiply: e.target.checked })} /> I understand rows will repeat and want this anyway</label>}
      {p && <div className="mt-3"><p aria-label="Merge preview" className="text-sm">{p.says}</p><Notes items={p.warnings} /></div>}
      {msg && <p aria-label="Merge result" className="mt-2 text-sm">{msg}</p>}
    </Section>
  );
}

function Made() {
  const [items, setItems] = useState<{ table: string; label: string; source: string; rows: number }[]>([]);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ items: typeof items }>("/api/toolbox/de/made").then((r) => { if (live) setItems(r.items); }).catch(() => {});
    return () => { live = false; };
  }, [tick]);
  return (
    <Section title="Tables made here (Undo)" note="Undo only drops the new table. The originals were never touched.">
      {err && <ErrorBanner message={err} />}
      <ul className="grid gap-1 text-sm">
        {items.map((t) => <li key={t.table} className="flex items-center gap-2"><b>{t.table}</b> <span className="text-xs text-muted">{t.source} · {t.rows.toLocaleString()} rows</span><button className="btn" onClick={async () => { try { await postJson("/api/toolbox/de/undo", { table: t.table }); setTick((x) => x + 1); } catch (e) { setErr(errMsg(e, "Could not undo.")); } }}>Undo</button></li>)}
        {items.length === 0 && <li className="text-xs text-muted">Nothing made yet.</li>}
      </ul>
      <button className="btn mt-2" onClick={() => setTick((x) => x + 1)}>Refresh</button>
    </Section>
  );
}

function Contract() {
  const [src, setSrc] = useState("");
  const [cols, setCols] = useState<CCol[] | null>(null);
  const [owner, setOwner] = useState("");
  const [res, setRes] = useState<Chk | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fail = (e: unknown, d: string) => setErr(errMsg(e, d));
  async function load(s: string) {
    setErr(null); setRes(null); setMsg(null); setCols(null);
    try {
      const have = await getJson<{ contract: { columns: CCol[]; owner: string } | null }>(`/api/toolbox/de/contract?source=${encodeURIComponent(s)}`);
      if (have.contract) { setCols(have.contract.columns); setOwner(have.contract.owner); setMsg("Saved contract loaded."); return; }
      const pr = await getJson<{ columns: CCol[]; note: string }>(`/api/toolbox/de/contract/propose?source=${encodeURIComponent(s)}`);
      setCols(pr.columns); setMsg(pr.note);
    } catch (e) { fail(e, "Could not load."); }
  }
  const upd = (i: number, patch: Partial<CCol>) => setCols((c) => (c ? c.map((x, j) => (j === i ? { ...x, ...patch } : x)) : c));
  return (
    <Section title="Data contract" note="Rules a table must follow: types, blanks, repeats, ranges, allowed values. Checked on demand and about every 15 minutes while the app runs.">
      {err && <ErrorBanner message={err} />}
      <SourcePick value={src} onChange={(v) => { setSrc(v); if (v) void load(v); }} />
      {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
      {cols && (
        <div className="mt-3 overflow-auto">
          <table className="w-full text-xs"><caption className="sr-only">Contract rules</caption>
            <thead><tr className="text-left"><th>Column</th><th>Type</th><th>May be blank</th><th>Unique</th><th>Min</th><th>Max</th><th>Allowed values</th></tr></thead>
            <tbody>{cols.map((c, i) => (
              <tr key={c.name}><td>{c.name}</td><td>{c.kind}</td>
                <td><input type="checkbox" aria-label={`${c.name} may be blank`} checked={c.nullable} onChange={(e) => upd(i, { nullable: e.target.checked })} /></td>
                <td><input type="checkbox" aria-label={`${c.name} unique`} checked={!!c.unique} onChange={(e) => upd(i, { unique: e.target.checked })} /></td>
                <td>{c.kind === "number" && <input aria-label={`${c.name} min`} className="input w-20" value={c.min ?? ""} onChange={(e) => upd(i, { min: e.target.value === "" ? undefined : +e.target.value })} />}</td>
                <td>{c.kind === "number" && <input aria-label={`${c.name} max`} className="input w-20" value={c.max ?? ""} onChange={(e) => upd(i, { max: e.target.value === "" ? undefined : +e.target.value })} />}</td>
                <td>{c.kind === "text" && <input aria-label={`${c.name} allowed`} className="input w-48" value={(c.allowed ?? []).join(", ")} onChange={(e) => upd(i, { allowed: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} />}</td></tr>
            ))}</tbody></table>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <Field label="Owner"><input aria-label="Contract owner" className="input" value={owner} onChange={(e) => setOwner(e.target.value)} /></Field>
            <button className="btn" onClick={async () => { setErr(null); try { await postJson("/api/toolbox/de/contract", { source: src, columns: cols, owner }); setMsg("Contract saved."); } catch (e) { fail(e, "Could not save."); } }}>Save contract</button>
            <button className="btn" onClick={async () => { setErr(null); try { setRes(await postJson<Chk>("/api/toolbox/de/contract/check", { source: src })); } catch (e) { fail(e, "Save the contract first."); } }}>Check data now</button>
            <a className="btn" href={`${API_BASE}/api/toolbox/de/contract/markdown?source=${encodeURIComponent(src)}`}>Download as Markdown</a>
            <button className="btn" onClick={async () => { try { await deleteJson(`/api/toolbox/de/contract?source=${encodeURIComponent(src)}`); setMsg("Contract deleted."); } catch (e) { fail(e, "Could not delete."); } }}>Delete contract</button>
          </div>
        </div>
      )}
      {res && (
        <div className="mt-3">
          <p aria-label="Contract verdict" className="text-sm"><Badge tone={res.status === "pass" ? "ok" : "bad"}>{res.status}</Badge> {res.says}</p>
          <ul className="mt-1 grid gap-1 text-sm">{res.issues.map((i, k) => <li key={k}><b>{i.column}</b> ({i.rule}): {i.says} {i.examples.length > 0 && <span className="text-xs text-muted">e.g. {i.examples.join(", ")}</span>}</li>)}</ul>
          {res.extra_columns.length > 0 && <p className="mt-1 text-xs text-muted">Columns not in the contract: {res.extra_columns.join(", ")}</p>}
        </div>
      )}
    </Section>
  );
}

function Estimator() {
  const [f, setF] = useState({ rows_per_day: "5000", columns: "20", retention_months: "12", loads_per_day: "1", ram_gb: "16" });
  const [r, setR] = useState<Est | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const k = Object.keys(f) as (keyof typeof f)[];
  const lab: Record<string, string> = { rows_per_day: "New rows per day", columns: "Columns", retention_months: "Months kept", loads_per_day: "Loads per day", ram_gb: "Computer RAM (GB)" };
  return (
    <Section title="Volume estimator" note="How much space, memory and time a data volume needs, and what to run it on. Every figure is a rough range.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-5">{k.map((x) => <Field key={x} label={lab[x]}><input aria-label={lab[x]} className="input" inputMode="decimal" value={f[x]} onChange={(e) => setF({ ...f, [x]: e.target.value })} /></Field>)}</div>
      <button className="btn mt-3" onClick={async () => { setErr(null); try { setR(await postJson<Est>("/api/toolbox/de/estimate", Object.fromEntries(k.map((x) => [x, +f[x]])))); } catch (e) { setErr(errMsg(e, "Check the numbers.")); } }}>Estimate</button>
      {r && (
        <div className="mt-3 grid gap-2">
          <p aria-label="Estimate verdict" className="text-sm"><Badge tone={r.tier === "laptop" ? "ok" : "warn"}>{r.tier}</Badge> {r.recommendation}</p>
          <Rows columns={["Measure", "Estimate"]} rows={[["Total rows kept", r.total_rows], ["Raw size (GB)", r.storage_raw_gb], ["Database size (GB)", r.storage_db_gb], ["Memory if fully loaded (GB)", r.memory_if_loaded_gb], ["One load (seconds)", `${r.load_seconds_range[0]} to ${r.load_seconds_range[1]}`], ["Full scan (seconds)", `${r.full_scan_seconds_range[0]} to ${r.full_scan_seconds_range[1]}`]]} />
          <Notes items={r.notes} />
          <details className="text-xs"><summary>Assumptions</summary><ul className="mt-1 list-disc pl-5">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></details>
          <p className="text-xs text-muted">{r.caution}</p>
        </div>
      )}
    </Section>
  );
}

export function EngTools() {
  const [tab, setTab] = useState("schema");
  return (
    <div className="grid gap-3">
      <Tabs label="Data engineering tools" value={tab} onChange={setTab} tabs={[{ id: "schema", label: "Schema changes" }, { id: "dedupe", label: "Dedupe" }, { id: "merge", label: "Merge" }, { id: "made", label: "Undo" }, { id: "contract", label: "Data contract" }, { id: "est", label: "Volume estimator" }, { id: "scripts", label: "Scripts to paste" }]} />
      {tab === "schema" && <SchemaCheck />}
      {tab === "dedupe" && <Dedupe />}
      {tab === "merge" && <Merge />}
      {tab === "made" && <Made />}
      {tab === "contract" && <Contract />}
      {tab === "est" && <Estimator />}
      {tab === "scripts" && <Scripts />}
    </div>
  );
}
