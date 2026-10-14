"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, ApiError, apiFetch, getJson, postForm, postJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";

const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
export const ACCEPT = ".csv,.tsv,.txt,.log,.dat,.xlsx,.xlsm,.json,.jsonl,.ndjson,.xml,.pdf,.parquet,.html,.htm";
const label = (s: string) => s.replace(/_/g, " ");

type Field = { name: string; type: "date" | "text" | "number"; options?: string[]; default?: string; required: boolean };

/** One record at a time, with the values you already use offered as suggestions. */
export function QuickAdd({ pid, onDone }: { pid: string; onDone: () => void }) {
  const [fields, setFields] = useState<Field[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<{ fields: Field[] }>(`/api/biz-packs/${pid}/form`).then((r) => {
      if (!live) return;
      setFields(r.fields);
      setVals(Object.fromEntries(r.fields.map((f) => [f.name, f.default ?? ""])));
    }).catch((e) => live && setErr(msg(e)));
    return () => { live = false; };
  }, [pid]);
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setOk("");
    try {
      const r = await postJson<{ rows: number }>(`/api/biz-packs/${pid}/rows`, { values: vals });
      setOk(`Added. This dashboard now has ${r.rows.toLocaleString()} records.`);
      setVals((v) => Object.fromEntries(Object.entries(v).map(([k, x]) => [k, fields.find((f) => f.name === k)?.type === "date" && k === "record_date" ? x : fields.find((f) => f.name === k)?.type === "text" ? x : ""])));
      onDone();
    } catch (x) { setErr(msg(x)); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={save} className="space-y-2">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {fields.map((f) => (
          <label key={f.name} className="flex flex-col gap-1 text-xs">
            <span>{label(f.name)}{f.required ? "" : " (optional)"}</span>
            <input className="field" required={f.required} value={vals[f.name] ?? ""} onChange={(e) => setVals({ ...vals, [f.name]: e.target.value })}
                   type={f.type === "date" ? "date" : "text"} inputMode={f.type === "number" ? "decimal" : undefined} list={f.options?.length ? `qa-${pid}-${f.name}` : undefined} />
            {f.options?.length ? <datalist id={`qa-${pid}-${f.name}`}>{f.options.map((o) => <option key={o} value={o} />)}</datalist> : null}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-3"><button className="btn btn-primary" disabled={busy} type="submit">Add record</button>{ok && <span role="status" className="text-sm" style={{ color: "var(--good)" }}>{ok}</span>}</div>
    </form>
  );
}

type Preview = {
  rows_valid: number; rows_skipped: number; skipped_notes: string[]; current_rows: number; resulting_rows: number; duplicates: number; warnings: string[]; verdict: string;
  new_dates: string[]; sample: Record<string, string>[]; kpis: { label: string; unit: string; before: number | null; after: number | null; change_pct: number | null }[];
};

/** Import any supported file type into the dashboard. "Test first" tries it on a throw-away copy and shows what would change. */
export function FileImport({ pid, onDone }: { pid: string; onDone: (m: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [prev, setPrev] = useState<Preview | null>(null);
  const body = () => { const b = new FormData(); b.append("file", file as File); b.append("replace", String(replace)); return b; };
  async function test() {
    if (!file) return;
    setBusy(true); setErr(null); setPrev(null);
    try { setPrev(await postForm<Preview>(`/api/biz-packs/${pid}/import-file/preview`, body())); } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  }
  async function go() {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const r = await postForm<{ imported: number; skipped_notes: string[] }>(`/api/biz-packs/${pid}/import-file`, body());
      onDone(`Imported ${r.imported} rows from ${file.name}.${r.skipped_notes.length ? " Skipped: " + r.skipped_notes.join("; ") : ""}`);
      setFile(null); setPrev(null);
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  }
  const fmt = (v: number | null) => (v === null ? "-" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }));
  return (
    <div className="space-y-2">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <input type="file" accept={ACCEPT} aria-label="Data file" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPrev(null); }} />
        <label className="flex items-center gap-1"><input type="checkbox" checked={replace} onChange={(e) => { setReplace(e.target.checked); setPrev(null); }} />Replace existing rows</label>
        <button className="btn" disabled={busy || !file} onClick={test}>{busy ? "Working…" : "Test first (sandbox)"}</button>
        <button className="btn btn-primary" disabled={busy || !file} onClick={go}>Import file</button>
      </div>
      {prev && (
        <section className="card space-y-2 p-3 text-sm" aria-label="Sandbox result">
          <p className="font-semibold">Sandbox: nothing has been changed yet. {prev.verdict}</p>
          <p>{prev.rows_valid.toLocaleString()} rows are valid ({prev.rows_skipped} skipped). Rows after import: {prev.current_rows.toLocaleString()} → {prev.resulting_rows.toLocaleString()}. Dates {prev.new_dates[0]} to {prev.new_dates[1]}.</p>
          {prev.warnings.length > 0 && <ul className="list-disc pl-5" style={{ color: "var(--warn, #b45309)" }}>{prev.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          {prev.skipped_notes.length > 0 && <p className="text-xs text-muted">Skipped: {prev.skipped_notes.join("; ")}</p>}
          <table className="w-full text-xs"><thead><tr className="text-left"><th>Number</th><th>Now</th><th>After</th><th>Change</th></tr></thead>
            <tbody>{prev.kpis.map((k) => <tr key={k.label}><td>{k.label}</td><td>{fmt(k.before)}</td><td>{fmt(k.after)}</td><td>{k.change_pct === null ? "-" : `${k.change_pct > 0 ? "+" : ""}${k.change_pct}%`}</td></tr>)}</tbody></table>
          <button className="btn btn-primary" disabled={busy} onClick={go}>Apply this import</button>
        </section>
      )}
      <p className="text-xs text-muted">CSV, TSV, TXT, Excel (.xlsx), JSON, XML, PDF with a table, Parquet or an HTML table. Column names are matched ignoring capitals and spaces. Use Test first to see the warnings and the before/after numbers without changing anything.</p>
    </div>
  );
}

/** A client report as a web page (print it) or a PDF. */
export function ReportBox({ pid, days }: { pid: string; days: number }) {
  const [client, setClient] = useState("");
  const [by, setBy] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const q = (fmt: string) => `/api/biz-packs/${pid}/report?fmt=${fmt}&days=${days}&client=${encodeURIComponent(client)}&prepared_by=${encodeURIComponent(by)}`;
  async function open() {
    setErr(null);
    try {
      const res = await apiFetch(`${API_BASE}${q("html")}`);
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Couldn't make the report.");
      window.open(URL.createObjectURL(await res.blob()), "_blank", "noopener");
    } catch (e) { setErr(msg(e)); }
  }
  return (
    <section className="card space-y-2 p-4" aria-label="Client report">
      <h3 className="text-sm font-semibold">Client report</h3>
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col gap-1">Client name<input className="field" maxLength={80} value={client} onChange={(e) => setClient(e.target.value)} /></label>
        <label className="flex flex-col gap-1">Prepared by<input className="field" maxLength={80} value={by} onChange={(e) => setBy(e.target.value)} /></label>
        <button className="btn" onClick={open}>Open report</button>
        <button className="btn" onClick={() => downloadFile(q("pdf"), `${pid}-report.pdf`).catch((e) => setErr(msg(e)))}>Download PDF</button>
      </div>
      <p className="text-xs text-muted">Uses the {days === 0 ? "all-data" : `${days}-day`} window above. Plain-English summary, key numbers, trend, breakdowns and next actions. Practice data is stamped SAMPLE.</p>
    </section>
  );
}

/** Build a dashboard from any file, no code. */
export function CustomBuilder({ onDone }: { onDone: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [dateCol, setDateCol] = useState("");
  const [lower, setLower] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const body = new FormData();
      body.append("file", file); body.append("name", name || file.name.replace(/\.[^.]+$/, "")); body.append("date_column", dateCol); body.append("lower_is_better", lower);
      const r = await postForm<{ id: string }>("/api/biz-packs/custom-file", body);
      setFile(null); setName(""); onDone(r.id);
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-2">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <input type="file" accept={ACCEPT} aria-label="File for the new dashboard" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <label className="flex flex-col gap-1">Dashboard name<input className="field" maxLength={50} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Shop sales" /></label>
        <label className="flex flex-col gap-1">Date column (optional)<input className="field" value={dateCol} onChange={(e) => setDateCol(e.target.value)} placeholder="found automatically" /></label>
        <label className="flex flex-col gap-1">Lower is better (optional)<input className="field" value={lower} onChange={(e) => setLower(e.target.value)} placeholder="e.g. cost, returns" /></label>
        <button className="btn btn-primary" disabled={busy || !file} onClick={go}>{busy ? "Building…" : "Build dashboard"}</button>
      </div>
      <p className="text-xs text-muted">It finds the date, the numbers and the categories, makes KPIs and charts, and adds an assistant. Needs a date column and at least one number column.</p>
    </div>
  );
}

type Explained = {
  kpi: string; value: number | null; summary: string; formula: string; in_words: string; goodword: string; records: number;
  best_day: { day: string; v: number } | null; worst_day: { day: string; v: number } | null; movers: { dim: string; name: string; now: number; before: number; change: number }[];
};

/** "Explain this number": meaning, formula, how it moved and what moved it, from your own data. */
export function ExplainButton({ pid, kpi, days }: { pid: string; kpi: string; days: number }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState<Explained | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true); setErr(null);
    try { setD(await getJson<Explained>(`/api/biz-packs/${pid}/explain?kpi=${encodeURIComponent(kpi)}&days=${days}`)); } catch (e) { setErr(msg(e)); }
  }
  return (
    <div className="mt-2">
      <button className="text-xs underline" aria-expanded={open} onClick={toggle}>{open ? "Hide explanation" : "Explain this number"}</button>
      {open && (
        <div className="mt-2 space-y-1 rounded-lg p-2 text-xs" style={{ background: "var(--panel2, rgba(127,127,127,.1))" }} role="region" aria-label={`Explanation of ${kpi}`}>
          {err && <ErrorBanner message={err} />}
          {!d && !err && <p>Working it out…</p>}
          {d && (<>
            <p>{d.summary}</p>
            <p><strong>What it measures:</strong> {d.in_words} ({d.goodword}).</p>
            <p><strong>Exact calculation:</strong> <code className="break-all">{d.formula}</code> over {d.records.toLocaleString()} records.</p>
            {d.movers.length > 0 && <ul className="list-disc pl-4">{d.movers.slice(0, 4).map((m) => <li key={m.dim + m.name}>{m.name} ({m.dim.replace(/_/g, " ")}): {m.before.toLocaleString()} to {m.now.toLocaleString()}</li>)}</ul>}
            {d.best_day && d.worst_day && <p>Best day {d.best_day.day} ({d.best_day.v.toLocaleString(undefined, { maximumFractionDigits: 2 })}), weakest day {d.worst_day.day} ({d.worst_day.v.toLocaleString(undefined, { maximumFractionDigits: 2 })}).</p>}
          </>)}
        </div>
      )}
    </div>
  );
}
