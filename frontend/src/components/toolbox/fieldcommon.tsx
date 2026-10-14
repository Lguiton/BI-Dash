"use client";
import { useState, type ReactNode } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";
import { Rows } from "./common";

type Hit = { id: string; title: string; area: string; minutes: number; why: string };
type Guide = { id: string; title: string; area: string; why: string; steps: string[]; verify: string; minutes: number; caution: string; tool: string };

/** A "how to do / fix" search bar limited to one field, with the agent walk-through. */
export function FieldHowTo({ area, agent, examples }: { area: string; agent: string; examples: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [g, setG] = useState<Guide | null>(null);
  const [all, setAll] = useState<{ id: string; title: string }[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function open(id: string) { setErr(null); setReply(null); try { setG(await getJson<Guide>(`/api/fieldbox/howto/${id}`)); } catch (e) { setErr(errMsg(e, "Could not open that guide.")); } }
  async function browse() { setErr(null); try { setAll((await getJson<{ areas: Record<string, { id: string; title: string }[]> }>("/api/fieldbox/howto")).areas[area] ?? []); } catch (e) { setErr(errMsg(e, "Could not load the guides.")); } }
  async function walk() {
    if (!g) return;
    setErr(null); setBusy(true); setReply(null);
    try {
      const r = await postJson<{ reply: string }>(`/api/agents/${agent}/chat`, { message: `Walk me through this, step by step, using the field_fix guide "${g.id}" (${g.title}). ${ask}`.slice(0, 1200) });
      setReply(r.reply);
    } catch (e) { setErr(errMsg(e, "The agent could not answer. If no AI provider is set up, the written steps above still work.")); } finally { setBusy(false); }
  }
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title={`How to do it or fix it: ${area}`} note="Describe the problem in your own words. Guides are steps to follow; nothing here changes your data.">
        <form className="flex flex-wrap items-end gap-2" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setHits((await getJson<{ results: Hit[] }>(`/api/fieldbox/howto/search?q=${encodeURIComponent(q)}&area=${encodeURIComponent(area)}`)).results); } catch (x) { setErr(errMsg(x, "Search failed.")); } }}>
          <Field label="What is going wrong, or what do you need to do?"><input aria-label={`Search how-to for ${area}`} className="input w-96 max-w-full" value={q} onChange={(e) => setQ(e.target.value)} placeholder={examples} /></Field>
          <button className="btn" type="submit" disabled={!q.trim()}>Find the guide</button>
          <button className="btn" type="button" onClick={browse}>Browse all</button>
        </form>
        {hits && hits.length === 0 && <p className="mt-2 text-xs text-muted">Nothing matched. Try other words, or browse all.</p>}
        {hits && hits.length > 0 && <ul className="mt-3 grid gap-2 text-sm">{hits.map((h) => <li key={h.id}><button className="btn" onClick={() => open(h.id)}>{h.title}</button> <span className="text-xs text-muted">about {h.minutes} min. {h.why}</span></li>)}</ul>}
        {all && <div className="mt-3 flex flex-wrap gap-2">{all.map((x) => <button key={x.id} className="btn" onClick={() => open(x.id)}>{x.title}</button>)}</div>}
      </Section>
      {g && (
        <Section title={g.title} note={`${g.area} · about ${g.minutes} minutes`}>
          <p className="mb-2 text-sm"><b>Why it happens:</b> {g.why}</p>
          {g.caution && <p className="mb-2 rounded border border-amber-500 bg-amber-500/10 p-2 text-sm"><b>Before you start:</b> {g.caution}</p>}
          <ol aria-label="Guide steps" className="list-decimal space-y-1 pl-5 text-sm">{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <p className="mt-3 text-sm"><Badge tone="ok">Check it worked</Badge> {g.verify}</p>
          {g.tool && <p className="mt-1 text-xs text-muted">Dashboard tool: {g.tool}</p>}
          <div className="mt-4 border-t border-line pt-3">
            <Field label="Ask the agent to walk you through it (optional note about your situation)"><input aria-label="Note for the agent" className="input" value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
            <button className="btn mt-2" disabled={busy} onClick={walk}>{busy ? "Asking…" : "Walk me through it"}</button>
            {reply && <pre aria-label="Agent reply" className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-3 text-sm">{reply}</pre>}
          </div>
        </Section>
      )}
    </div>
  );
}

/** Runs one request and holds its busy/error/result state. */
export function useRun<T>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<T>, fallback = "That did not work.") {
    setErr(null); setBusy(true);
    try { setRes(await fn()); } catch (e) { setErr(errMsg(e, fallback)); setRes(null); } finally { setBusy(false); }
  }
  return { res, err, busy, run, setRes, setErr };
}

export function TA({ label, value, onChange, rows = 5, placeholder }: { label: string; value: string; onChange: (v: string) => void; rows?: number; placeholder?: string }) {
  return <label className="grid gap-1 text-xs text-muted">{label}<textarea aria-label={label} className="input font-mono text-sm" rows={rows} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></label>;
}

export function TI({ label, value, onChange, w = "w-48", placeholder, type }: { label: string; value: string; onChange: (v: string) => void; w?: string; placeholder?: string; type?: string }) {
  return <label className="grid gap-1 text-xs text-muted">{label}<input aria-label={label} type={type} className={`input ${w} max-w-full`} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></label>;
}

const SKIP = new Set(["caution", "says", "arithmetic", "tips", "explain", "run_first", "verify", "findings", "notes"]);
function isFlat(o: unknown): o is Record<string, string | number | boolean | null> {
  return !!o && typeof o === "object" && !Array.isArray(o) && Object.values(o as object).every((v) => v == null || ["string", "number", "boolean"].includes(typeof v));
}
const label = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const cell = (v: unknown): string | number | null => (v == null ? null : typeof v === "boolean" ? (v ? "yes" : "no") : typeof v === "number" || typeof v === "string" ? v : JSON.stringify(v));

/** Shows any tool result in plain terms: headline, findings, tables, lists, then everything else. */
export function Out({ data, hide = [] }: { data: Record<string, unknown> | null; hide?: string[] }) {
  if (!data) return null;
  const blocks: ReactNode[] = [];
  const list = (k: string, items: unknown) => Array.isArray(items) && items.length ? <div key={k}><h4 className="mt-2 text-xs font-medium text-muted">{label(k)}</h4><ul className="list-disc pl-5 text-sm">{items.map((x, i) => <li key={i}>{typeof x === "string" ? x : isFlat(x) ? Object.values(x).map(String).join(" · ") : JSON.stringify(x)}</li>)}</ul></div> : null;
  const scalars = Object.entries(data).filter(([k, v]) => !SKIP.has(k) && !hide.includes(k) && v != null && ["string", "number", "boolean"].includes(typeof v) && !(typeof v === "string" && (v.length > 90 || v.includes("\n"))));
  Object.entries(data).forEach(([k, v]) => {
    if (SKIP.has(k) || hide.includes(k) || v == null) return;
    if (typeof v === "string" && (v.length > 90 || v.includes("\n"))) blocks.push(<div key={k}><h4 className="mt-2 text-xs font-medium text-muted">{label(k)}</h4><pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-3 text-xs">{v}</pre></div>);
    else if (Array.isArray(v) && v.length && v.every(isFlat) && !v.every((x) => typeof x === "string")) {
      const cols = Object.keys(v[0] as object);
      blocks.push(<div key={k} className="mt-2"><Rows caption={label(k)} columns={cols.map(label)} rows={(v as Record<string, unknown>[]).map((r) => cols.map((c) => cell(r[c])))} /></div>);
    } else if (Array.isArray(v) && v.every((x) => typeof x === "string")) blocks.push(list(k, v));
    else if (Array.isArray(v) && v.length) blocks.push(<div key={k}><h4 className="mt-2 text-xs font-medium text-muted">{label(k)}</h4><pre className="max-h-60 overflow-auto rounded bg-panel2 p-2 text-xs">{JSON.stringify(v, null, 1)}</pre></div>);
    else if (v && typeof v === "object" && !Array.isArray(v)) blocks.push(<div key={k}><h4 className="mt-2 text-xs font-medium text-muted">{label(k)}</h4><pre className="overflow-auto rounded bg-panel2 p-2 text-xs">{JSON.stringify(v, null, 1)}</pre></div>);
  });
  const files = Array.isArray((data as { files?: unknown }).files) ? ((data as { files: { path: string; language: string; code: string }[] }).files) : null;
  return (
    <div className="mt-3 text-sm" aria-label="Result">
      {typeof data.says === "string" && <p className="mb-2 font-medium">{data.says}</p>}
      {scalars.length > 0 && <p className="mb-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">{scalars.map(([k, v]) => <span key={k}>{label(k)}: <b className="text-fg">{typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v)}</b></span>)}</p>}
      {Array.isArray(data.findings) && data.findings.length > 0 && <ul className="mb-2 grid gap-1">{(data.findings as Record<string, unknown>[]).map((f, i) => <li key={i} className="rounded border border-amber-500 bg-amber-500/10 p-2">{f.severity ? <Badge tone={f.severity === "high" ? "bad" : "warn"}>{String(f.severity)}</Badge> : null} {String(f.says ?? f.message ?? JSON.stringify(f))}</li>)}</ul>}
      {files?.map((f) => <div key={f.path}><h4 className="mt-2 text-xs font-medium text-muted">{f.path}</h4><pre className="max-h-80 overflow-auto rounded bg-panel2 p-3 text-xs">{f.code}</pre></div>)}
      {blocks}
      {["arithmetic", "tips", "explain", "run_first", "notes"].map((k) => list(k, data[k]))}
      {typeof data.verify === "string" && <p className="mt-2"><Badge tone="ok">Check it worked</Badge> {data.verify}</p>}
      {typeof data.caution === "string" && <p className="mt-2 rounded border border-line bg-panel2 p-2 text-xs text-muted">{data.caution}</p>}
    </div>
  );
}

export const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
export const cols = (l: string) => l.split(/\s*[,|]\s*/);
export const num = (s: string | undefined) => (s === undefined || s === "" ? undefined : Number(s));
