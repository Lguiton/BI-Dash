"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg, num } from "./kit";
import { CondEditor, Lesson, type Col, type Cond, type Source } from "./analysisKit";

interface Issue { kind: string; column?: string; detail: string; value?: number }
interface Insp { table: string; rows: number; duplicate_rows: number; health: number; clean: boolean; issues: Issue[]; columns: { name: string; kind: string; missing: number }[]; lesson: string }
interface Res { table: string; rows_before: number; rows_after: number; health_before: number; health_after: number; message: string; log: { step: number; text: string; rows_removed: number; rows_after: number }[]; verification: Insp }
interface Tbl { table_name: string; label: string; rows_count: number }

const FIX: Record<string, { id: string; label: string }[]> = {
  missing_num: [{ id: "keep", label: "Leave as is" }, { id: "drop", label: "Remove those rows" }, { id: "median", label: "Fill with the median" }, { id: "mean", label: "Fill with the average" }],
  missing_text: [{ id: "keep", label: "Leave as is" }, { id: "drop", label: "Remove those rows" }, { id: "mode", label: "Fill with the most common value" }],
  outliers: [{ id: "keep", label: "Keep (look first)" }, { id: "remove", label: "Remove outliers" }],
  case: [{ id: "keep", label: "Leave as is" }, { id: "lower", label: "Make all lower case" }, { id: "upper", label: "Make all upper case" }],
  spaces: [{ id: "keep", label: "Leave as is" }, { id: "trim", label: "Trim spaces" }],
  number_as_text: [{ id: "keep", label: "Leave as is" }, { id: "number", label: "Convert to number" }],
  placeholder: [{ id: "keep", label: "Leave as is" }, { id: "setmissing", label: "Treat as missing" }],
  many_levels: [{ id: "keep", label: "Leave as is" }, { id: "group", label: "Group rare values into Other" }],
  date_as_text: [{ id: "keep", label: "Leave as is" }, { id: "date", label: "Convert to date" }],
};
const defaultFix = (i: Issue) => (i.kind === "placeholder" ? "setmissing" : i.kind === "spaces" ? "trim" : i.kind === "number_as_text" ? "number" : i.kind === "date_as_text" ? "date" : "keep");

export function CleanTab() {
  const [tables, setTables] = useState<Tbl[] | null>(null);
  const [table, setTable] = useState("");
  const [insp, setInsp] = useState<Insp | null>(null);
  const [fix, setFix] = useState<Record<string, string>>({});
  const [dedupe, setDedupe] = useState(true);
  const [newName, setNewName] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<{ tables: Tbl[] }>("/api/data/tables").then((d) => setTables(d.tables)).catch((e) => setErr(errMsg(e, "Couldn't list your tables."))); }, []);
  const [feats, setFeats] = useState<Record<string, unknown>[]>([]);
  const [fd, setFd] = useState<{ how: string; name: string; a: string; b: string; part: string; bins: string; op2: string; value: string; entity: string; days: string; cutoff: string }>({ how: "ratio", name: "", a: "", b: "", part: "month", bins: "4", op2: "gt", value: "", entity: "", days: "30", cutoff: "" });
  const key = (i: Issue) => `${i.kind}:${i.column ?? ""}`;
  const kindOf = (i: Issue) => (i.kind === "missing" ? (insp?.columns.find((c) => c.name === i.column)?.kind === "number" ? "missing_num" : "missing_text") : i.kind);
  const look = async () => {
    setBusy(true); setErr(null); setRes(null);
    try {
      const d = await getJson<Insp>(`/api/stats/clean/inspect?table=${encodeURIComponent(table)}`);
      setInsp(d); setNewName(`${table}_clean`); setDedupe(d.duplicate_rows > 0);
      setFix(Object.fromEntries(d.issues.filter((i) => i.kind !== "duplicates").map((i) => [key(i), defaultFix(i)])));
    } catch (e) { setInsp(null); setErr(errMsg(e, "Couldn't inspect that table.")); } finally { setBusy(false); }
  };
  const steps = () => {
    const s: Record<string, unknown>[] = [];
    if (dedupe) s.push({ op: "dedupe" });
    for (const i of insp?.issues ?? []) {
      const f = fix[key(i)];
      const c = i.column;
      if (!f || f === "keep" || !c) continue;
      if (f === "trim") s.push({ op: "trim", column: c });
      else if (f === "lower" || f === "upper") s.push({ op: f, column: c });
      else if (f === "drop") s.push({ op: "drop_missing", columns: [c] });
      else if (f === "median" || f === "mean" || f === "mode") s.push({ op: "fill_missing", column: c, method: f });
      else if (f === "setmissing") s.push({ op: "set_missing", column: c, value: i.value });
      else if (f === "group") s.push({ op: "group_rare", column: c, min_share: 0.02 });
      else if (f === "remove") s.push({ op: "remove_outliers", column: c });
      else if (f === "number" || f === "date") s.push({ op: "convert", column: c, to: f });
    }
    return [...s, ...feats];
  };
  const [tx, setTx] = useState({ op: "strip_chars", column: "", keep: "digits", delimiter: "space", a: "first_name", b: "last_name", find: "", rep: "" });
  const addText = () => {
    const f: Record<string, unknown> = { op: tx.op, column: tx.column };
    let label = "";
    if (tx.op === "strip_chars") { f.keep = tx.keep; label = `keep ${tx.keep.replace(/_/g, " ")} in ${tx.column}`; }
    if (tx.op === "split_text") { f.delimiter = tx.delimiter; f.names = [tx.a.trim(), tx.b.trim()]; label = `split ${tx.column} into ${tx.a} and ${tx.b}`; }
    if (tx.op === "replace_text") { f.find = tx.find; f.with = tx.rep; label = `replace "${tx.find}" in ${tx.column}`; }
    setFeats([...feats, { ...f, name: label, how: "text step" }]);
  };
  const addFeat = () => {
    const f: Record<string, unknown> = { op: "add_feature", how: fd.how, name: fd.name.trim(), a: fd.a };
    if (["ratio", "difference", "product"].includes(fd.how)) f.b = fd.b;
    if (fd.how === "date_part") f.part = fd.part;
    if (fd.how === "bucket") f.bins = Number(fd.bins);
    if (fd.how === "before_after") f.cutoff = fd.cutoff;
    if (fd.how === "repeat_within") { f.entity = fd.entity; f.days = Number(fd.days); }
    if (fd.how === "flag") { f.op2 = fd.op2; f.value = fd.value; }
    setFeats([...feats, f]); setFd({ ...fd, name: "" });
  };
  const go = async () => {
    setBusy(true); setErr(null);
    try { setRes(await postJson<Res>("/api/stats/clean", { table, new_table: newName, steps: steps(), note: "Cleaning from the Analysis Lab" })); } catch (e) { setErr(errMsg(e, "Couldn't clean that.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Cleaning is the part of wrangling that fixes missing, duplicate, wrong-type, inconsistent and extreme values. The workflow is <b>inspect, clean, verify</b>. Your original table is never changed: a cleaned copy is made, and each step is saved in your Wrangling log with the reason.</p>
      <Section title="1. Inspect">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Table to inspect">
            <select className="field" value={table} onChange={(e) => { setTable(e.target.value); setInsp(null); setRes(null); setFeats([]); }}>
              <option value="">Choose…</option>
              {(tables ?? []).map((t) => <option key={t.table_name} value={t.table_name}>{t.label} ({t.rows_count.toLocaleString()} rows)</option>)}
            </select>
          </Field>
          <button className="btn btn-primary" disabled={busy || !table} onClick={look}>{busy && !insp ? "Looking…" : "Inspect"}</button>
        </div>
        {tables && tables.length === 0 && <p className="mt-2 text-sm text-muted">No imported tables yet. Load a file in My data first.</p>}
      </Section>
      {err && <ErrorBanner message={err} />}
      {insp && (
        <>
          <Lesson text={insp.lesson} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Rows" value={insp.rows.toLocaleString()} />
            <Stat label="Health score" value={`${insp.health}`} sub="100 means nothing to fix" />
            <Stat label="Issues found" value={String(insp.issues.length)} />
          </div>
          {insp.clean ? <p className="text-sm">Nothing to fix here. Check for outliers and relevance yourself.</p> : (
            <Section title="2. Choose what to fix">
              {insp.duplicate_rows > 0 && <label className="mb-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} />Remove {insp.duplicate_rows.toLocaleString()} exact duplicate row(s)</label>}
              <Table head={["Column", "Problem", "What to do"]} rows={insp.issues.filter((i) => i.kind !== "duplicates").map((i) => [
                i.column ?? "", <span key="d">{i.detail}</span>,
                <select key="s" className="field" aria-label={`Fix for ${i.column}: ${i.kind}`} value={fix[key(i)] ?? "keep"} onChange={(e) => setFix({ ...fix, [key(i)]: e.target.value })}>
                  {(FIX[kindOf(i)] ?? [{ id: "keep", label: "Leave as is" }]).map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
                </select>])} />
              <p className="mt-2 text-xs text-muted">A value like 999 or -1 may be a code for &ldquo;missing&rdquo;: decide what it means, treat it as missing, then remove or fill. A column with very many different values is easier to use once the rare ones are grouped. Missing values can be removed, sourced elsewhere, or imputed (filled with a statistic). Pick what suits your use case. Outliers can be real, so look before removing. Irrelevant columns can be dropped in SQL Lab.</p>
              <div className="mt-4 rounded border border-line p-3">
                <h4 className="text-sm font-semibold">Add a column (feature engineering)</h4>
                <p className="mb-2 text-xs text-muted">A feature is something you know about the business that helps a model: a ratio, the month of a date, a size group, a yes/no flag. Add the ones that fit your question.</p>
                {(() => {
                  const nums = insp.columns.filter((c) => c.kind === "number"), dates = insp.columns.filter((c) => c.kind === "date");
                  const pool = fd.how === "date_part" || fd.how === "repeat_within" || fd.how === "before_after" ? dates : nums;
                  return (
                    <div className="grid gap-2 sm:grid-cols-4">
                      <Field label="Kind"><select className="field" value={fd.how} onChange={(e) => setFd({ ...fd, how: e.target.value, a: "", b: "" })}>
                        <option value="ratio">Ratio (A / B)</option><option value="difference">Difference (A - B)</option><option value="product">Product (A x B)</option>
                        <option value="date_part">Part of a date</option><option value="bucket">Size groups</option><option value="flag">Yes/no flag</option><option value="log">Log (tames long tails)</option><option value="before_after">Before / after a launch date</option><option value="repeat_within">Outcome: same entity returns within N days</option></select></Field>
                      <Field label={["ratio", "difference", "product"].includes(fd.how) ? "Column A" : fd.how === "repeat_within" || fd.how === "before_after" ? "Date column" : "Column"}><select className="field" value={fd.a} onChange={(e) => setFd({ ...fd, a: e.target.value })}><option value="">Choose…</option>{pool.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select></Field>
                      {["ratio", "difference", "product"].includes(fd.how) && <Field label="Column B"><select className="field" value={fd.b} onChange={(e) => setFd({ ...fd, b: e.target.value })}><option value="">Choose…</option>{nums.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select></Field>}
                      {fd.how === "date_part" && <Field label="Part"><select className="field" value={fd.part} onChange={(e) => setFd({ ...fd, part: e.target.value })}>{["year", "quarter", "month", "week", "dayofweek"].map((x) => <option key={x}>{x}</option>)}</select></Field>}
                      {fd.how === "before_after" && <Field label="Launch date"><input className="field" type="date" value={fd.cutoff} onChange={(e) => setFd({ ...fd, cutoff: e.target.value })} /></Field>}
                      {fd.how === "repeat_within" && <><Field label="Entity (who returns)"><select className="field" value={fd.entity} onChange={(e) => setFd({ ...fd, entity: e.target.value })}><option value="">Choose…</option>{insp.columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select></Field>
                        <Field label="Days"><input className="field" type="number" min={1} max={3650} value={fd.days} onChange={(e) => setFd({ ...fd, days: e.target.value })} /></Field></>}
                      {fd.how === "bucket" && <Field label="Groups"><input className="field" type="number" min={2} max={10} value={fd.bins} onChange={(e) => setFd({ ...fd, bins: e.target.value })} /></Field>}
                      {fd.how === "flag" && <><Field label="Is"><select className="field" value={fd.op2} onChange={(e) => setFd({ ...fd, op2: e.target.value })}><option value="gt">above</option><option value="gte">at least</option><option value="lt">below</option><option value="lte">at most</option><option value="eq">equal to</option></select></Field>
                        <Field label="Number"><input className="field" value={fd.value} onChange={(e) => setFd({ ...fd, value: e.target.value })} /></Field></>}
                      <Field label="New column name"><input className="field" maxLength={60} value={fd.name} onChange={(e) => setFd({ ...fd, name: e.target.value })} /></Field>
                      <div className="self-end"><button className="btn" disabled={!fd.name.trim() || !fd.a || (fd.how === "repeat_within" && !fd.entity) || (fd.how === "before_after" && !fd.cutoff) || (["ratio", "difference", "product"].includes(fd.how) && !fd.b) || (fd.how === "flag" && !fd.value)} onClick={addFeat}>Add column</button></div>
                    </div>
                  );
                })()}
                {feats.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm">{feats.map((f, k) => <li key={k}>{String(f.name)}{f.how === "text step" ? "" : ` (${String(f.how)})`} <button className="underline text-xs" onClick={() => setFeats(feats.filter((_, j) => j !== k))}>remove</button></li>)}</ul>}
              </div>
              <div className="mt-4 rounded border border-line p-3">
                <h4 className="text-sm font-semibold">Fix text values (special characters, phone numbers, names, typos)</h4>
                <p className="mb-2 text-xs text-muted">Strip a column down to digits or letters, split a full name in two, or replace one piece of text with another. Added to the same cleaned copy; the original is not touched.</p>
                <div className="grid gap-2 sm:grid-cols-4">
                  <Field label="Fix"><select className="field" value={tx.op} onChange={(e) => setTx({ ...tx, op: e.target.value })}><option value="strip_chars">Remove unwanted characters</option><option value="split_text">Split into two columns</option><option value="replace_text">Find and replace text</option></select></Field>
                  <Field label="Text column"><select className="field" value={tx.column} onChange={(e) => setTx({ ...tx, column: e.target.value })}><option value="">Choose…</option>{insp.columns.filter((c) => c.kind === "text").map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select></Field>
                  {tx.op === "strip_chars" && <Field label="Keep only"><select className="field" value={tx.keep} onChange={(e) => setTx({ ...tx, keep: e.target.value })}><option value="digits">Digits (phone numbers)</option><option value="letters_digits">Letters and digits</option><option value="letters_digits_spaces">Letters, digits, spaces</option></select></Field>}
                  {tx.op === "split_text" && <><Field label="Split at"><select className="field" value={tx.delimiter} onChange={(e) => setTx({ ...tx, delimiter: e.target.value })}>{["space", "comma", "semicolon", "pipe", "dash", "slash", "underscore", "at"].map((x) => <option key={x}>{x}</option>)}</select></Field>
                    <Field label="First part column"><input className="field" maxLength={60} value={tx.a} onChange={(e) => setTx({ ...tx, a: e.target.value })} /></Field>
                    <Field label="Rest column"><input className="field" maxLength={60} value={tx.b} onChange={(e) => setTx({ ...tx, b: e.target.value })} /></Field></>}
                  {tx.op === "replace_text" && <><Field label="Find"><input className="field" maxLength={200} value={tx.find} onChange={(e) => setTx({ ...tx, find: e.target.value })} /></Field>
                    <Field label="Replace with"><input className="field" maxLength={200} value={tx.rep} onChange={(e) => setTx({ ...tx, rep: e.target.value })} /></Field></>}
                  <div className="self-end"><button className="btn" disabled={!tx.column || (tx.op === "replace_text" && !tx.find) || (tx.op === "split_text" && (!tx.a.trim() || !tx.b.trim()))} onClick={addText}>Add fix</button></div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-end gap-3">
                <Field label="Name of the cleaned copy"><input className="field" maxLength={80} value={newName} onChange={(e) => setNewName(e.target.value)} /></Field>
                <button className="btn btn-primary" disabled={busy || !newName.trim() || steps().length === 0} onClick={go}>{busy ? "Cleaning…" : `Clean (${steps().length} step${steps().length === 1 ? "" : "s"})`}</button>
              </div>
            </Section>
          )}
        </>
      )}
      {res && (
        <Section title="3. Verify">
          <p className="text-sm" role="status">{res.message}</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <Stat label="Rows" value={`${num(res.rows_before, 0)} to ${num(res.rows_after, 0)}`} />
            <Stat label="Health before" value={String(res.health_before)} />
            <Stat label="Health after" value={String(res.health_after)} />
          </div>
          <Table head={["Step", "What changed", "Rows removed", "Rows left"]} rows={res.log.map((l) => [String(l.step), l.text, String(l.rows_removed), String(l.rows_after)])} />
          {res.verification.issues.length > 0 ? (
            <div className="mt-2 text-sm"><Badge tone="warn">Still to look at</Badge><ul className="mt-1 list-disc pl-5">{res.verification.issues.map((i, k) => <li key={k}>{i.column ? `${i.column}: ` : ""}{i.detail}</li>)}</ul></div>
          ) : <p className="mt-2 text-sm"><Badge tone="ok">Re-inspected: no issues left</Badge></p>}
        </Section>
      )}
    </div>
  );
}

interface RollRes { table: string; records_used: number; entities: number; columns: number; created: string[]; cohort: string[]; message: string }

export function RollupTab() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [table, setTable] = useState("");
  const [ent, setEnt] = useState("");
  const [useCohort, setUseCohort] = useState(false);
  const [cond, setCond] = useState<Cond>({ column: "", op: "eq", value: "", value2: "" });
  const [name, setName] = useState("");
  const [res, setRes] = useState<RollRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<{ sources: Source[] }>("/api/stats/sources").then((d) => setSources(d.sources)).catch((e) => setErr(errMsg(e, "Couldn't load your data."))); }, []);
  const src = sources?.find((x) => x.id === table);
  const cols: Col[] = src?.columns ?? [];
  const pick = (id: string) => {
    setTable(id); setRes(null); setErr(null); setName(`${id}_per_entity`);
    const c = sources?.find((x) => x.id === id)?.columns ?? [];
    setEnt(c.find((x) => x.kind === "text")?.name ?? c[0]?.name ?? "");
    setCond({ column: c[0]?.name ?? "", op: "eq", value: "", value2: "" });
  };
  const go = async () => {
    setBusy(true); setErr(null); setRes(null);
    try {
      const cohort = useCohort ? [{ column: cond.column, op: cond.op, value: cond.value, value2: cond.value2 || undefined }] : [];
      setRes(await postJson<RollRes>("/api/stats/rollup", { table, entity_col: ent, new_table: name, cohort }));
    } catch (e) { setErr(errMsg(e, "Couldn't roll that table up.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <Section title="One row per entity (data requirements for modeling)">
        <p className="text-sm">Decision trees, clusters and regressions usually need <b>one record per customer, patient, product or account</b>, with a column for each thing you know about them. Your raw data often has thousands of transaction rows per entity. This tool rolls them up: counts, sums, averages, minimums, maximums and first/last dates. Do it before modeling, and write the inclusion rules (the cohort) down: who is in, and who is left out so they don&apos;t skew the result.</p>
        <p className="mt-2 text-xs text-muted">Creates a new table; the original is never changed, and the steps are saved in your Wrangling log. Pick only entity IDs that repeat (customer, not order number).</p>
      </Section>
      {err && <ErrorBanner message={err} />}
      <Section title="Roll up">
        {sources && sources.length <= 1 && <p className="mb-2 text-xs text-muted">Load a file in My data and it will appear here.</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Table"><select className="field" value={table} onChange={(e) => pick(e.target.value)}><option value="">Choose…</option>{(sources ?? []).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></Field>
          <Field label="One row per…"><select className="field" value={ent} onChange={(e) => setEnt(e.target.value)} disabled={!src}>{cols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}</select></Field>
          <Field label="Name of the new table"><input className="field" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        </div>
        {src && (
          <div className="mt-3">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useCohort} onChange={(e) => setUseCohort(e.target.checked)} /> Only include records that match a cohort rule</label>
            {useCohort && <div className="mt-2"><CondEditor label="Keep records where" cols={cols} c={cond} set={setCond} /></div>}
          </div>
        )}
        <button className="btn btn-primary mt-3" disabled={busy || !src || !ent || !name.trim()} onClick={go}>{busy ? "Rolling up…" : "Create one row per entity"}</button>
      </Section>
      {res && (
        <Section title="Result">
          <p className="text-sm" role="status">{res.message}</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <Stat label="Records used" value={num(res.records_used, 0)} />
            <Stat label="Rows now (entities)" value={num(res.entities, 0)} />
            <Stat label="Columns" value={num(res.columns, 0)} />
          </div>
          {res.cohort.length > 0 && <p className="mt-2 text-sm">Cohort: {res.cohort.join("; ")}</p>}
          <ul className="mt-2 list-disc pl-5 text-sm">{res.created.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="mt-2 text-xs text-muted">Next: pick this table in the Analysis Lab for a decision tree, clusters or regression.</p>
        </Section>
      )}
    </div>
  );
}
