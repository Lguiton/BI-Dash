"use client";
import { Play, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, deleteJson, getJson, patchJson, postJson } from "@/lib/api";
import { num } from "@/lib/format";
import type { DataSource, InboxFiles, SourceKind, SourcePreview, SourceRun } from "@/lib/types";

const KIND_LABEL: Record<SourceKind, string> = { file: "File in a folder", url: "Web link (CSV / JSON)", sql: "Database query" };
const EVERY = [[0, "Only when I click"], [15, "Every 15 minutes"], [60, "Every hour"], [360, "Every 6 hours"], [1440, "Every day"]] as const;

export default function SourcesPage() {
  const [list, setList] = useState<DataSource[] | null>(null);
  const [files, setFiles] = useState<InboxFiles | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ id: number; ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [runs, setRuns] = useState<SourceRun[]>([]);

  const load = useCallback((signal?: AbortSignal) => {
    Promise.all([getJson<{ sources: DataSource[] }>("/api/sources", signal), getJson<InboxFiles>("/api/sources/files", signal)])
      .then(([a, b]) => { setList(a.sources); setFiles(b); setError(null); })
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : "Could not load sources."); });
  }, []);
  useEffect(() => { const ctl = new AbortController(); load(ctl.signal); return () => ctl.abort(); }, [load]);

  async function run(s: DataSource) {
    setBusy(s.id); setMsg(null);
    try { const r = await postJson<{ message: string }>(`/api/sources/${s.id}/run`, {}); setMsg({ id: s.id, ok: true, text: r.message }); }
    catch (e) { setMsg({ id: s.id, ok: false, text: e instanceof ApiError ? e.message : "Failed." }); }
    finally { setBusy(null); load(); if (open === s.id) showRuns(s.id); }
  }
  async function showRuns(id: number) {
    if (open === id) { setOpen(null); return; }
    const r = await getJson<{ runs: SourceRun[] }>(`/api/sources/${id}/runs`).catch(() => ({ runs: [] }));
    setRuns(r.runs); setOpen(id);
  }
  const patch = (id: number, body: object) => patchJson(`/api/sources/${id}`, body).then(() => load()).catch((e) => setError(e instanceof ApiError ? e.message : "Failed."));
  const remove = (id: number) => deleteJson(`/api/sources/${id}`).then(() => load()).catch((e) => setError(e instanceof ApiError ? e.message : "Failed."));

  return (
    <PageShell title="Sources" subtitle="Save where your data comes from, and refresh it on a schedule instead of re-uploading.">
      {error && <ErrorBanner message={error} onRetry={() => load()} />}
      <NewSource files={files} onSaved={() => load()} />
      <section aria-label="Saved sources" className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Saved in this workspace</h2>
        {list && list.length === 0 && <p className="card p-5 text-sm text-muted">No sources yet.</p>}
        {list?.map((s) => (
          <div key={s.id} className="card space-y-2 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{s.name} <span className="text-xs font-normal text-muted">· {KIND_LABEL[s.kind]} → {s.config.load === "operations" ? "operations dashboards" : s.target}</span></div>
                <div className="text-xs text-muted">
                  {s.last_run_at ? <>Last run {s.last_run_at} UTC · <span style={{ color: s.last_status === "ok" ? "var(--good)" : "var(--bad)" }}>{s.last_message}</span></> : "Never run"}
                </div>
              </div>
              <select aria-label={`Schedule for ${s.name}`} className="field" value={s.interval_minutes} onChange={(e) => patch(s.id, { interval_minutes: Number(e.target.value) })}>
                {EVERY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                {!EVERY.some(([v]) => v === s.interval_minutes) && <option value={s.interval_minutes}>Every {s.interval_minutes} min</option>}
              </select>
              <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={s.enabled} onChange={(e) => patch(s.id, { enabled: e.target.checked })} /> On</label>
              <button className="btn btn-primary" disabled={busy === s.id} onClick={() => run(s)}><Play className="h-4 w-4" aria-hidden /> {busy === s.id ? "Running…" : "Refresh now"}</button>
              <button className="btn" onClick={() => showRuns(s.id)}>{open === s.id ? "Hide history" : "History"}</button>
              <button className="btn" aria-label={`Delete ${s.name}`} onClick={() => remove(s.id)}><Trash2 className="h-4 w-4" aria-hidden /></button>
            </div>
            {msg?.id === s.id && <div role={msg.ok ? "status" : "alert"} className="rounded-lg p-2 text-sm" style={{ background: msg.ok ? "var(--good-bg)" : "var(--bad-bg)", color: msg.ok ? "var(--good)" : "var(--bad)" }}>{msg.text}</div>}
            {open === s.id && (
              <table className="w-full text-sm"><thead><tr><th className="th">When (UTC)</th><th className="th">Result</th><th className="th">Rows</th></tr></thead>
                <tbody>{runs.map((r, i) => <tr key={i} className="border-t border-line"><td className="td">{r.at}</td><td className="td" style={{ color: r.ok ? "var(--good)" : "var(--bad)" }}>{r.message}</td><td className="td">{num(r.rows)}</td></tr>)}
                  {runs.length === 0 && <tr><td className="td text-muted" colSpan={3}>No runs yet.</td></tr>}</tbody></table>
            )}
          </div>
        ))}
        <p className="text-xs text-muted">Scheduled refreshes run while the app is running, for the workspace that is open. Each refresh is staged and swapped in as one step, and one that would shrink a table below half its size is refused.</p>
      </section>
    </PageShell>
  );
}

function NewSource({ files, onSaved }: { files: InboxFiles | null; onSaved: () => void }) {
  const [kind, setKind] = useState<SourceKind>("file");
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [url, setUrl] = useState("");
  const [authEnv, setAuthEnv] = useState("");
  const [driver, setDriver] = useState<"postgres" | "sqlite">("postgres");
  const [dsnEnv, setDsnEnv] = useState("");
  const [query, setQuery] = useState("");
  const [load, setLoad] = useState<"table" | "operations">("table");
  const [target, setTarget] = useState("");
  const [mode, setMode] = useState<"replace" | "append">("replace");
  const [every, setEvery] = useState(0);
  const [pv, setPv] = useState<SourcePreview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const config = () => kind === "file" ? { path } : kind === "url" ? { url, auth_env: authEnv || null } : driver === "postgres" ? { driver, dsn_env: dsnEnv, query } : { driver, path, query };
  const fail = (e: unknown) => setErr(e instanceof ApiError ? e.message : "Failed.");

  async function test() {
    setBusy(true); setErr(null); setPv(null);
    try { setPv(await postJson<SourcePreview>("/api/sources/test", { kind, config: config() })); } catch (e) { fail(e); } finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setErr(null);
    try {
      await postJson("/api/sources", { name, kind, config: config(), target, load, mode, interval_minutes: every });
      setName(""); setTarget(""); setPv(null); onSaved();
    } catch (e) { fail(e); } finally { setBusy(false); }
  }
  const ready = name.trim() && (load === "operations" || target.trim());

  return (
    <section className="card space-y-4 p-5" aria-label="Add a source">
      <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide"><Plus className="h-4 w-4 text-accent" aria-hidden /> Add a source</div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-muted">Type
          <select className="field" value={kind} onChange={(e) => { setKind(e.target.value as SourceKind); setPv(null); }}>{(Object.keys(KIND_LABEL) as SourceKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Name
          <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Weekly sales export" maxLength={80} /></label>
        {kind === "file" && (
          <label className="flex flex-col gap-1 text-xs text-muted sm:col-span-2">File (from the inbox folder)
            <input className="field" list="inbox-files" value={path} onChange={(e) => setPath(e.target.value)} placeholder="sales.csv" />
            <datalist id="inbox-files">{files?.files.map((f) => <option key={f.path} value={f.path} />)}</datalist></label>
        )}
        {kind === "url" && (<>
          <label className="flex flex-col gap-1 text-xs text-muted sm:col-span-2">Link<input className="field" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…/export.csv" /></label>
          <label className="flex flex-col gap-1 text-xs text-muted">Token variable (optional)<input className="field" value={authEnv} onChange={(e) => setAuthEnv(e.target.value.toUpperCase())} placeholder="MY_API_TOKEN" /></label>
        </>)}
        {kind === "sql" && (<>
          <label className="flex flex-col gap-1 text-xs text-muted">Database
            <select className="field" value={driver} onChange={(e) => setDriver(e.target.value as "postgres" | "sqlite")}><option value="postgres">Postgres</option><option value="sqlite">SQLite file</option></select></label>
          {driver === "postgres"
            ? <label className="flex flex-col gap-1 text-xs text-muted">Connection variable<input className="field" value={dsnEnv} onChange={(e) => setDsnEnv(e.target.value.toUpperCase())} placeholder="PG_URL" /></label>
            : <label className="flex flex-col gap-1 text-xs text-muted">SQLite file (inbox)<input className="field" value={path} onChange={(e) => setPath(e.target.value)} placeholder="shop.sqlite" /></label>}
          <label className="flex flex-col gap-1 text-xs text-muted sm:col-span-2 lg:col-span-4">Query (one SELECT; read-only)
            <textarea className="field font-mono" rows={3} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="SELECT order_date, amount FROM orders" /></label>
        </>)}
      </div>
      {kind !== "file" && <p className="text-xs text-muted">Passwords and tokens are never typed here. Put them in <code>backend/.env</code> (for example <code>PG_URL=postgresql://user:pw@host/db</code>) and enter only the variable name.</p>}
      {kind === "file" && <p className="text-xs text-muted">Folders the app may read: {files?.folders.join(", ") ?? "…"}. Drop files in the first one; add more with <code>BI_SOURCE_DIRS</code>.</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-muted">Load into
          <select className="field" value={load} onChange={(e) => setLoad(e.target.value as "table" | "operations")}><option value="table">My data (its own table)</option><option value="operations">Operations dashboards (strict columns)</option></select></label>
        {load === "table" && <label className="flex flex-col gap-1 text-xs text-muted">Table name<input className="field" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="weekly_sales" /></label>}
        <label className="flex flex-col gap-1 text-xs text-muted">Each refresh
          <select className="field" value={mode} onChange={(e) => setMode(e.target.value as "replace" | "append")}><option value="replace">Replaces the data</option><option value="append">Adds rows</option></select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Schedule
          <select className="field" value={every} onChange={(e) => setEvery(Number(e.target.value))}>{EVERY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn" disabled={busy} onClick={test}>Test (nothing is saved)</button>
        <button className="btn btn-primary" disabled={busy || !ready} onClick={save}>Save source</button>
      </div>
      {pv && (
        <div role="status" className="space-y-2 rounded-lg border border-line p-3 text-sm">
          <div>Found {num(pv.rows)} rows from {pv.from}: {pv.columns.map((c) => `${c.name} (${c.type})`).join(", ")}</div>
          <div className="overflow-x-auto"><table className="w-full text-xs"><tbody>{pv.preview.slice(0, 4).map((r, i) => <tr key={i} className="border-t border-line">{pv.columns.map((c) => <td key={c.name} className="td">{r[c.name] ?? "—"}</td>)}</tr>)}</tbody></table></div>
        </div>
      )}
      {err && <div role="alert" className="rounded-lg p-3 text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>{err}</div>}
    </section>
  );
}
