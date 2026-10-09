"use client";
import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import type { FsApiMap, FsCodebase, FsEndpoint, FsResponse, FsScaffold, FsStack } from "@/lib/types";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";

const TABS = [{ id: "api", label: "API map & tester" }, { id: "scaffold", label: "Scaffold from a table" }, { id: "code", label: "Codebase" }, { id: "stack", label: "Stack & config" }];

export function FullStackPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return (
    <div className="space-y-4">
      <Tabs tabs={TABS} value={tab} onChange={onTab} label="Full stack tools" />
      {tab === "api" && <ApiTester />}
      {tab === "scaffold" && <Scaffold />}
      {tab === "code" && <Codebase />}
      {tab === "stack" && <StackFacts />}
    </div>
  );
}

const tone = (m: string) => (m === "GET" ? "ok" : m === "DELETE" ? "bad" : "warn");

function ApiTester() {
  const [map, setMap] = useState<FsApiMap | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [group, setGroup] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<FsEndpoint | null>(null);
  const [path, setPath] = useState("/api/pm");
  const [method, setMethod] = useState("GET");
  const [body, setBody] = useState("");
  const [res, setRes] = useState<FsResponse | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<FsApiMap>("/api/fullstack/api-map", ctl.signal).then(setMap).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the API map.")); });
    return () => ctl.abort();
  }, []);
  const shown = useMemo(() => (map?.endpoints ?? []).filter((e) => (!group || e.group === group) && (!q || e.path.includes(q) || e.summary.toLowerCase().includes(q.toLowerCase()))), [map, group, q]);
  const pick = (e: FsEndpoint) => {
    setSel(e); setMethod(e.method); setPath(e.path);
    setBody(e.sample_body ? JSON.stringify(e.sample_body, null, 2) : "");
  };
  const send = async () => {
    setBusy(true); setErr(null); setRes(null);
    try {
      let parsed: unknown = undefined;
      if (body.trim()) { try { parsed = JSON.parse(body); } catch { throw new Error("The body isn't valid JSON."); } }
      setRes(await postJson<FsResponse>("/api/fullstack/request", { method, path, body: parsed }));
    } catch (e) { setErr(errMsg(e, "The request failed.")); } finally { setBusy(false); }
  };
  if (!map) return <>{err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>}</>;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Endpoints" value={String(map.total)} sub={`${map.title} v${map.version}`} />
        {(["GET", "POST", "PUT"] as const).map((m) => <Stat key={m} label={m} value={String(map.by_method[m] ?? 0)} />)}
      </div>
      <Section title="Request tester" note="Calls this app's own API in-process. Writes (POST, PUT, PATCH, DELETE) only run while the Practice workspace is active; Real is read-only here.">
        <div className="grid gap-2 sm:grid-cols-[7rem_1fr_auto] sm:items-end">
          <Field label="Method"><select className="field" value={method} onChange={(e) => setMethod(e.target.value)}>{["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => <option key={m}>{m}</option>)}</select></Field>
          <Field label="Path (include ?query=…)"><input className="field font-mono" value={path} onChange={(e) => setPath(e.target.value)} /></Field>
          <button className="btn btn-primary" disabled={busy || !path.startsWith("/api/")} onClick={send}>{busy ? "Sending…" : "Send"}</button>
        </div>
        {method !== "GET" && method !== "DELETE" && (
          <Field label="JSON body"><textarea className="field mt-2 h-32 font-mono text-xs" value={body} onChange={(e) => setBody(e.target.value)} spellCheck={false} /></Field>
        )}
        {sel && sel.params.length > 0 && <p className="mt-2 text-xs text-muted">Parameters: {sel.params.map((p) => `${p.name} (${p.in}${p.required ? ", required" : ""}, ${p.type})`).join(" · ")}</p>}
        {res && (
          <div className="mt-3 space-y-1" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2 text-sm"><Badge tone={res.status < 300 ? "ok" : res.status < 500 ? "warn" : "bad"}>{res.status}</Badge><span>{res.ms} ms</span><span className="text-muted">{res.reading}</span></div>
            <pre className="max-h-80 overflow-auto rounded-md bg-panel2 p-3 text-xs" tabIndex={0}><code>{prettify(res.body)}{res.truncated ? "\n… (shortened)" : ""}</code></pre>
          </div>
        )}
      </Section>
      <Section title="API map">
        <div className="mb-2 flex flex-wrap gap-2">
          <select aria-label="Filter by group" className="field max-w-full" value={group} onChange={(e) => setGroup(e.target.value)}><option value="">All groups ({map.groups.length})</option>{map.groups.map((g) => <option key={g.group} value={g.group}>{g.group} ({g.endpoints})</option>)}</select>
          <input aria-label="Search endpoints" className="field" placeholder="Search path or summary" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="max-h-96 overflow-auto">
          <Table caption="Endpoints" head={["", "Method", "Path", "Summary"]} rows={shown.map((e) => [<button key="b" className="btn !py-0.5 text-xs" onClick={() => pick(e)}>Use</button>, <Badge key="m" tone={tone(e.method)}>{e.method}</Badge>, <span key="p" className="font-mono text-xs">{e.path}</span>, e.summary])} />
        </div>
      </Section>
    </div>
  );
}
function prettify(s: string): string { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } }

function Scaffold() {
  const [tables, setTables] = useState<string[] | null>(null);
  const [table, setTable] = useState("");
  const [ui, setUi] = useState(true);
  const [out, setOut] = useState<FsScaffold | null>(null);
  const [file, setFile] = useState(0);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ tables: string[] }>("/api/fullstack/scaffold/tables", ctl.signal).then((r) => { setTables(r.tables); setTable(r.tables[0] ?? ""); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't list tables.")); });
    return () => ctl.abort();
  }, []);
  const gen = async () => {
    setErr(null);
    try { setOut(await getJson<FsScaffold>(`/api/fullstack/scaffold?table=${encodeURIComponent(table)}&ui=${ui}`)); setFile(0); setCopied(false); } catch (e) { setErr(errMsg(e, "Couldn't generate.")); }
  };
  const f = out?.files[file];
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Generate starter code from a table" note="Produces the SQL, Pydantic models, a FastAPI CRUD router, a TypeScript type, a React panel and a pytest skeleton. It only shows text: nothing is written to your project until you paste it.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Table"><select className="field" value={table} onChange={(e) => setTable(e.target.value)}>{(tables ?? []).map((t) => <option key={t}>{t}</option>)}</select></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ui} onChange={(e) => setUi(e.target.checked)} /> include React panel</label>
          <button className="btn btn-primary" disabled={!table} onClick={gen}>Generate</button>
        </div>
      </Section>
      {out && f && (
        <Section title={`${out.table}: ${out.columns} columns, key ${out.primary_key ?? "none"}, route ${out.route}`} note={out.caveat}>
          <div role="tablist" aria-label="Generated files" className="mb-2 flex flex-wrap gap-1">
            {out.files.map((x, i) => <button key={x.name} role="tab" aria-selected={i === file} className={`btn !py-0.5 text-xs ${i === file ? "btn-primary" : ""}`} onClick={() => { setFile(i); setCopied(false); }}>{x.name}</button>)}
          </div>
          <button className="btn mb-2 text-xs" onClick={() => { void navigator.clipboard?.writeText(f.content).then(() => setCopied(true)); }}>{copied ? "Copied" : "Copy file"}</button>
          <pre className="max-h-[28rem] overflow-auto rounded-md bg-panel2 p-3 text-xs" tabIndex={0}><code>{f.content}</code></pre>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">{out.next_steps.map((s) => <li key={s}>{s}</li>)}</ol>
        </Section>
      )}
    </div>
  );
}

function Codebase() {
  const [d, setD] = useState<FsCodebase | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<FsCodebase>("/api/fullstack/codebase", ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't read the codebase.")); });
    return () => ctl.abort();
  }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Reading the project…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Source files" value={d.files.toLocaleString()} /><Stat label="Tests" value={d.tests.toLocaleString()} sub="test functions" />
        <Stat label="Route functions" value={String(d.route_functions)} /><Stat label="Test code ÷ Python code" value={d.test_to_python_ratio == null ? "—" : String(d.test_to_python_ratio)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="By language"><Table head={["Language", "Files", "Lines"]} rows={d.languages.map((l) => [l.language, l.files, l.lines.toLocaleString()])} /></Section>
        <Section title="Largest source files" note={d.reading}><Table head={["File", "Lines"]} rows={d.largest.map((l) => [<span key="f" className="font-mono text-xs">{l.file}</span>, l.lines])} /></Section>
      </div>
    </div>
  );
}

function StackFacts() {
  const [d, setD] = useState<FsStack | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<FsStack>("/api/fullstack/stack", ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load.")); });
    return () => ctl.abort();
  }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Python" value={d.python} sub={d.platform} /><Stat label="Packages" value={String(Object.values(d.packages).filter(Boolean).length)} sub="installed of those checked" /><Stat label="Tools on PATH" value={Object.entries(d.tools_on_path).filter(([, v]) => v).map(([k]) => k).join(", ") || "none"} /></div>
      <Section title="Configuration facts" note={d.reading}><Table head={["Area", "Value", "Note"]} rows={d.facts.map((f) => [f.area, f.value, f.note])} /></Section>
      <Section title="Package versions"><Table head={["Package", "Version"]} rows={Object.entries(d.packages).map(([k, v]) => [k, v ?? <Badge key={k} tone="warn">not installed</Badge>])} /></Section>
    </div>
  );
}
