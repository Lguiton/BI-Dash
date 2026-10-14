"use client";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";

type Table = { title: string; columns: string[]; rows: (string | number | null)[][] };
type Chart = { title: string; x: number[]; y: number[] };
type Result = {
  agent: "nlp" | "dl"; task: string; intent: { what: string }; plan: { who: string; did: string }[]; findings: string[]; tables: Table[]; charts: Chart[]; caveats: string[]; next: string[];
  used: Record<string, unknown>; rows: number; seconds: number;
};
type Example = { agent: string; text: string; needs: string };
type Pack = { id: string; title: string; industry: string; rows: number | null };

const AGENT = { nlp: "Language agent", dl: "Deep-learning agent" } as const;

function Line({ c }: { c: Chart }) {
  const w = 600, h = 140, ys = c.y, lo = Math.min(...ys), hi = Math.max(...ys), sp = hi - lo || 1;
  const pts = ys.map((v, i) => `${(i / Math.max(1, ys.length - 1)) * w},${h - ((v - lo) / sp) * (h - 10) - 5}`).join(" ");
  return (
    <figure className="space-y-1">
      <figcaption className="text-xs text-muted">{c.title}</figcaption>
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={c.title} className="w-full max-w-2xl rounded-md border border-line bg-panel2"><polyline fill="none" stroke="currentColor" strokeWidth="2" points={pts} /></svg>
    </figure>
  );
}

export default function NlpDlPage() {
  const [prompt, setPrompt] = useState("");
  const [data, setData] = useState("");
  const [source, setSource] = useState("");
  const [packs, setPacks] = useState<Pack[]>([]);
  const [textCol, setTextCol] = useState("");
  const [labelCol, setLabelCol] = useState("");
  const [target, setTarget] = useState("");
  const [query, setQuery] = useState("");
  const [examples, setExamples] = useState<Example[]>([]);
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const auto = useRef(false);

  const run = async (p = prompt) => {
    setBusy(true); setErr(null); setRes(null);
    try { setRes(await postJson<Result>("/api/nlp-dl/run", { prompt: p, data, source, text_col: textCol, label_col: labelCol, target, query })); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "That didn't work."); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    getJson<{ examples: Example[] }>("/api/nlp-dl/examples").then((r) => setExamples(r.examples)).catch(() => {});
    getJson<{ packs: Pack[] }>("/api/biz-packs").then((r) => setPacks(r.packs.filter((p) => p.rows))).catch(() => {});
    const ask = new URLSearchParams(window.location.search).get("ask");
    if (ask && !auto.current) { auto.current = true; setPrompt(ask); void run(ask); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PageShell title="NLP & Deep Learning" subtitle="Tell the agents what you need. They plan the job, run real models on your data and compare against a do-nothing baseline.">
      <section className="card space-y-3 p-4" aria-label="Ask the agents">
        <form onSubmit={(e) => { e.preventDefault(); void run(); }} className="flex gap-2">
          <input className="field w-full" aria-label="What do you need" placeholder="e.g. sort these tickets by category · find unusual rows · forecast sales with a neural network" value={prompt} onChange={(e) => setPrompt(e.target.value)} maxLength={600} />
          <button className="btn btn-primary shrink-0" disabled={busy || !prompt.trim()}>{busy ? "Working…" : "Start"}</button>
        </form>
        <div className="flex flex-wrap gap-1.5" aria-label="Examples">
          {examples.map((x) => <button key={x.text} type="button" className="btn !px-2 !py-1 text-xs" title={`${AGENT[x.agent as "nlp" | "dl"]} · needs: ${x.needs}`} onClick={() => setPrompt(x.text)}>{x.text}</button>)}
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">Your data: paste a CSV with a header row, or one text per line
            <textarea className="field min-h-36 font-mono" aria-label="Data" value={data} onChange={(e) => setData(e.target.value)} spellCheck={false} placeholder={"text,category\nprinter shows paper jam,technical\ncharged twice on my card,billing"} /></label>
          <div className="space-y-2 text-sm">
            <label className="flex flex-col gap-1">…or use a table from one of your dashboards
              <select className="field" aria-label="Dashboard table" value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="">None (use the pasted data)</option>
                {packs.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.rows} rows)</option>)}
              </select></label>
            <div className="grid grid-cols-3 gap-2">
              <label className="flex flex-col gap-1">Text column<input className="field" value={textCol} onChange={(e) => setTextCol(e.target.value)} placeholder="auto" /></label>
              <label className="flex flex-col gap-1">Category column<input className="field" value={labelCol} onChange={(e) => setLabelCol(e.target.value)} placeholder="auto" /></label>
              <label className="flex flex-col gap-1">Predict / forecast<input className="field" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="auto" /></label>
            </div>
            <label className="flex flex-col gap-1">A sample text to classify or look up (optional)<input className="field" value={query} onChange={(e) => setQuery(e.target.value)} maxLength={1000} /></label>
            <p className="text-xs text-muted">Nothing is saved or sent anywhere. Language and neural-network jobs run on this computer.</p>
          </div>
        </div>
      </section>

      {err && <ErrorBanner message={err} />}
      {busy && <p role="status" className="text-sm text-muted">The agents are working…</p>}

      {res && (
        <section className="space-y-4" aria-label="Result">
          <div className="card space-y-2 p-4">
            <h2 className="text-sm font-semibold">{AGENT[res.agent]} · {res.intent.what}</h2>
            <ol className="space-y-1 text-sm">
              {res.plan.map((s, i) => <li key={i}><span className="mr-2 rounded-full bg-panel2 px-2 py-0.5 text-xs font-medium">{s.who}</span>{s.did}</li>)}
            </ol>
            <p className="text-xs text-muted">{res.rows ? `${res.rows.toLocaleString()} rows · ` : ""}{res.seconds}s</p>
          </div>
          <div className="card space-y-1 p-4" aria-label="Findings">
            <h2 className="text-sm font-semibold">What it found</h2>
            {res.findings.map((f, i) => <p key={i} className="text-sm">{f}</p>)}
          </div>
          {res.charts.map((c) => <div key={c.title} className="card p-4"><Line c={c} /></div>)}
          {res.tables.map((t) => (
            <div key={t.title} className="card overflow-auto p-4">
              <h3 className="mb-2 text-sm font-semibold">{t.title}</h3>
              <table className="w-full text-left text-sm"><thead><tr>{t.columns.map((c) => <th key={c} className="border-b border-line px-2 py-1 font-medium">{c}</th>)}</tr></thead>
                <tbody>{t.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="border-b border-line px-2 py-1 align-top">{v ?? ""}</td>)}</tr>)}</tbody></table>
            </div>
          ))}
          {(res.caveats.length > 0 || res.next.length > 0) && (
            <div className="card space-y-1 p-4 text-sm">
              {res.caveats.map((c, i) => <p key={i} className="text-muted">Be careful: {c}</p>)}
              {res.next.map((c, i) => <p key={i}>Next: {c}</p>)}
            </div>
          )}
        </section>
      )}
    </PageShell>
  );
}
