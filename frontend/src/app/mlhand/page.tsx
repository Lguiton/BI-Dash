"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";

type Preset = { id: string; method: string; title: string; data: string; query: string; params?: Record<string, unknown>; note: string };
type Step = { title: string; detail: string; math: string };
type Result = { method: string; steps: Step[]; answer: Record<string, number | string | Record<string, number>>; metrics?: Record<string, number | null>; check: { library: string; values: Record<string, number | string | null>; agrees: boolean | null; note?: string } };
type PackInfo = { id: string; title: string; industry: string; dept: string; columns: string[]; rows: number | null };

type Meth = { id: string; label: string; hint: string; group: string; q?: string; qreq?: boolean };
const METHODS: Meth[] = [
  { id: "linear", group: "Classic ML", label: "Simple regression", hint: "Two columns: x, then y. Optional new x to predict.", q: "New x to predict (optional)" },
  { id: "multiple", group: "Classic ML", label: "Multiple regression", hint: "Input columns, then the target last. Needs at least (inputs + 1) rows.", q: "New row to predict (optional): values in the same order as the inputs" },
  { id: "knn", group: "Classic ML", label: "KNN", hint: "Features, then the label last.", q: "New row to classify (required)", qreq: true },
  { id: "tree", group: "Classic ML", label: "Decision tree", hint: "Features (numbers or words), then the class last.", q: "New row to classify (optional)" },
  { id: "forest", group: "Classic ML", label: "Random forest", hint: "Features, then the class last.", q: "New row to classify (required)", qreq: true },
  { id: "metrics", group: "Classic ML", label: "Error metrics", hint: "Two columns: actual, then predicted." },
  { id: "tfidf", group: "NLP", label: "TF-IDF search", hint: "One document per line (2 to 12 lines).", q: "Search phrase (required)", qreq: true },
  { id: "bayes", group: "NLP", label: "Naive Bayes text", hint: "Header 'label,text' then one labelled message per line.", q: "Message to classify (required)", qreq: true },
  { id: "ngram", group: "NLP", label: "Next-word model", hint: "One sentence per line.", q: "Phrase to continue (optional)" },
  { id: "edit", group: "NLP", label: "Edit distance", hint: "First word in the data box.", q: "Second word (required)", qreq: true },
  { id: "perceptron", group: "Deep learning", label: "Perceptron", hint: "Rows of x1,x2,class where class is 0 or 1." },
  { id: "gd", group: "Deep learning", label: "Gradient descent", hint: "Two columns: x, then y. Learns the line by small steps." },
  { id: "nn", group: "Deep learning", label: "Tiny neural network", hint: "One row: x1,x2,target (target between 0 and 1). Shows forward pass, backpropagation and an update." },
];
const GROUPS = ["Classic ML", "NLP", "Deep learning"];
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
const fmt = (v: unknown) => (typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")) : String(v));

export default function MlHandPage() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [method, setMethod] = useState("linear");
  const [data, setData] = useState("distance_km,fare\n2,100\n4,150\n6,200\n8,250\n10,300");
  const [query, setQuery] = useState("15");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [quiz, setQuiz] = useState(false);
  const [mine, setMine] = useState<Record<string, string>>({});
  const [packs, setPacks] = useState<PackInfo[]>([]);
  const [pid, setPid] = useState("");
  const [cols, setCols] = useState("");
  useEffect(() => {
    getJson<{ presets: Preset[] }>("/api/ml-hand/presets").then((r) => setPresets(r.presets)).catch((e) => setErr(msg(e)));
    getJson<{ packs: PackInfo[] }>("/api/biz-packs").then((r) => setPacks(r.packs.filter((p) => p.rows))).catch(() => {});
  }, []);
  const mdef = METHODS.find((m) => m.id === method)!;
  function pickMethod(m: string) { setMethod(m); setRes(null); setErr(null); setParams({}); const p = presets.find((x) => x.method === m); if (p) load(p); }
  function load(p: Preset) { setMethod(p.method); setData(p.data); setQuery(p.query); setParams(p.params ?? {}); setRes(null); setErr(null); setMine({}); }
  async function run() {
    setBusy(true); setErr(null); setMine({});
    try { setRes(await postJson<Result>("/api/ml-hand/run", { method, data, query, params })); } catch (e) { setRes(null); setErr(msg(e)); } finally { setBusy(false); }
  }
  async function fromPack() {
    setErr(null);
    try { const r = await getJson<{ data: string }>(`/api/ml-hand/from-pack?pid=${encodeURIComponent(pid)}&columns=${encodeURIComponent(cols)}&rows=8`); setData(r.data); setRes(null); } catch (e) { setErr(msg(e)); }
  }
  const keys = res ? Object.entries(res.answer).filter(([, v]) => typeof v === "number" || typeof v === "string").slice(0, 6) : [];
  const verdict = (k: string, truth: number | string | Record<string, number>) => {
    const t = mine[k]; if (t === undefined || t === "") return "";
    const ok = typeof truth === "number" ? Math.abs(Number(t) - truth) <= Math.max(0.01, Math.abs(truth) * 0.005) : t.trim().toLowerCase() === String(truth).toLowerCase();
    return ok ? "✓ correct" : "✗ not yet";
  };
  return (
    <PageShell title="ML by hand" subtitle="Work small machine-learning, language (NLP) and deep-learning problems step by step with every number shown, then check them against the real library. A sandbox: nothing here is saved or changes your data.">
      {err && <ErrorBanner message={err} />}
      {GROUPS.map((g) => (
        <div key={g} className="flex flex-wrap items-center gap-2" role="tablist" aria-label={g}>
          <span className="w-28 text-xs font-semibold uppercase text-muted">{g}</span>
          {METHODS.filter((m) => m.group === g).map((m) => <button key={m.id} role="tab" aria-selected={method === m.id} className={`btn ${method === m.id ? "btn-primary" : ""}`} onClick={() => pickMethod(m.id)}>{m.label}</button>)}
        </div>))}
      <section className="card space-y-3 p-4" aria-label="Sandbox input">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1 text-xs">Start from an example
            <select className="field" aria-label="Example" value="" onChange={(e) => { const p = presets.find((x) => x.id === e.target.value); if (p) load(p); }}>
              <option value="">Choose…</option>{presets.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select></label>
          <span className="text-xs text-muted">{mdef.hint}</span>
        </div>
        <label className="flex flex-col gap-1 text-xs">Your data (comma separated, first row is the header; max 60 rows)
          <textarea className="field min-h-32 font-mono" aria-label="Data" value={data} onChange={(e) => { setData(e.target.value); setRes(null); }} spellCheck={false} /></label>
        {mdef.q && (
          <label className="flex flex-col gap-1 text-xs">{mdef.q}
            <input className="field max-w-lg" aria-label="New row" value={query} onChange={(e) => setQuery(e.target.value)} /></label>)}
        <div className="flex flex-wrap gap-3 text-xs">
          {method === "knn" && (<>
            <label className="flex flex-col gap-1">k (neighbours)<input className="field w-20" type="number" min={1} value={Number(params.k ?? 3)} onChange={(e) => setParams({ ...params, k: Number(e.target.value) })} /></label>
            <label className="flex flex-col gap-1">Task<select className="field" value={String(params.task ?? "classification")} onChange={(e) => setParams({ ...params, task: e.target.value })}><option value="classification">Classification</option><option value="regression">Regression</option></select></label>
            <label className="flex items-center gap-1 pt-5"><input type="checkbox" checked={!!params.scale} onChange={(e) => setParams({ ...params, scale: e.target.checked })} />Scale features 0..1</label></>)}
          {(method === "tree" || method === "forest") && (
            <label className="flex flex-col gap-1">Impurity<select className="field" value={String(params.criterion ?? "gini")} onChange={(e) => setParams({ ...params, criterion: e.target.value })}><option value="gini">Gini</option><option value="entropy">Entropy</option></select></label>)}
          {method === "tree" && <label className="flex flex-col gap-1">Depth<select className="field" value={Number(params.depth ?? 2)} onChange={(e) => setParams({ ...params, depth: Number(e.target.value) })}>{[1, 2, 3].map((d) => <option key={d}>{d}</option>)}</select></label>}
          {method === "forest" && (<>
            <label className="flex flex-col gap-1">Trees<input className="field w-20" type="number" min={1} max={9} value={Number(params.trees ?? 5)} onChange={(e) => setParams({ ...params, trees: Number(e.target.value) })} /></label>
            <label className="flex flex-col gap-1">Seed<input className="field w-20" type="number" value={Number(params.seed ?? 1)} onChange={(e) => setParams({ ...params, seed: Number(e.target.value) })} /></label></>)}
          {(method === "tfidf" || method === "bayes") && <label className="flex items-center gap-1 pt-5"><input type="checkbox" checked={!!params.stop} onChange={(e) => setParams({ ...params, stop: e.target.checked })} />Ignore filler words (the, and, is…)</label>}
          {(method === "gd" || method === "perceptron" || method === "nn") && (
            <label className="flex flex-col gap-1">Learning rate<input className="field w-24" type="number" step="any" min={0} value={Number(params.lr ?? (method === "gd" ? 0.02 : method === "nn" ? 0.5 : 1))} onChange={(e) => setParams({ ...params, lr: Number(e.target.value) })} /></label>)}
          {(method === "gd" || method === "nn") && (
            <label className="flex flex-col gap-1">Steps<input className="field w-24" type="number" min={1} value={Number(params.steps ?? (method === "gd" ? 500 : 1))} onChange={(e) => setParams({ ...params, steps: Number(e.target.value) })} /></label>)}
          {method === "perceptron" && <label className="flex flex-col gap-1">Passes<input className="field w-24" type="number" min={1} max={30} value={Number(params.epochs ?? 10)} onChange={(e) => setParams({ ...params, epochs: Number(e.target.value) })} /></label>}
          {method === "nn" && (
            <label className="flex flex-col gap-1">Starting weights (hidden 1: w1,w2; hidden 2: w1,w2; biases; output weights; output bias)
              <input className="field w-[28rem] max-w-full" aria-label="Weights" value={`${(params.wh as number[] ?? [0.15, 0.2, 0.25, 0.3]).join(",")} | ${(params.bh as number[] ?? [0.35, 0.35]).join(",")} | ${(params.wo as number[] ?? [0.4, 0.45]).join(",")} | ${params.bo ?? 0.6}`}
                onChange={(e) => { const parts = e.target.value.split("|").map((x) => x.split(",").map((n) => Number(n.trim()))); if (parts.length === 4 && parts.every((a) => a.every((n) => Number.isFinite(n)))) setParams({ ...params, wh: parts[0], bh: parts[1], wo: parts[2], bo: parts[3][0] }); }} /></label>)}
          {method === "metrics" && <label className="flex flex-col gap-1">Kind<select className="field" value={String(params.kind ?? "regression")} onChange={(e) => setParams({ ...params, kind: e.target.value })}><option value="regression">Regression</option><option value="classification">Classification</option></select></label>}
        </div>
        {packs.length > 0 && (
          <details className="text-xs"><summary className="cursor-pointer">Try it on a few rows of your own dashboard data (copied, read-only)</summary>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <select className="field" aria-label="Dashboard" value={pid} onChange={(e) => { setPid(e.target.value); setCols(""); }}><option value="">Choose a dashboard…</option>{packs.map((p) => <option key={p.id} value={p.id}>{p.industry}: {p.dept}</option>)}</select>
              <input className="field min-w-64" aria-label="Columns" placeholder={pid ? `columns, e.g. ${packs.find((p) => p.id === pid)?.columns.slice(-3, -1).join(",")}` : "choose a dashboard first"} value={cols} onChange={(e) => setCols(e.target.value)} />
              <button className="btn" disabled={!pid || !cols} onClick={fromPack}>Copy 8 rows here</button></div></details>)}
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? "Working…" : "Work it out"}</button>
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={quiz} onChange={(e) => setQuiz(e.target.checked)} />Try it myself first</label>
          <Link href="/tracks/ml" className="text-xs underline">Ask the ML agent to do this for you</Link>
        </div>
      </section>
      {res && (
        <section className="space-y-3" aria-label="Worked solution">
          {quiz && (
            <div className="card space-y-2 p-4 text-sm" aria-label="Your answers">
              <h2 className="font-semibold">Your answers</h2>
              <div className="flex flex-wrap gap-3">{keys.map(([k, v]) => (
                <label key={k} className="flex flex-col gap-1 text-xs">{k.replace(/_/g, " ")}
                  <input className="field w-32" aria-label={`Your ${k}`} value={mine[k] ?? ""} onChange={(e) => setMine({ ...mine, [k]: e.target.value })} />
                  <span style={{ color: verdict(k, v).startsWith("✓") ? "var(--good)" : "var(--bad)" }}>{verdict(k, v)}</span></label>))}</div>
            </div>)}
          {res.steps.map((s, i) => (
            <details key={i} className="card p-4" open={!quiz && i < 12}>
              <summary className="cursor-pointer font-semibold">{i + 1}. {s.title}</summary>
              {s.detail && <p className="mt-2 text-sm">{s.detail}</p>}
              {s.math && <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg p-2 text-xs" style={{ background: "var(--panel2, rgba(127,127,127,.1))" }}>{s.math}</pre>}
            </details>))}
          <div className="card space-y-1 p-4 text-sm" aria-label="Answer">
            <h2 className="font-semibold">Answer</h2>
            <p>{Object.entries(res.answer).filter(([, v]) => typeof v !== "object").map(([k, v]) => `${k.replace(/_/g, " ")} = ${fmt(v)}`).join("   ·   ")}</p>
            <p style={{ color: res.check.agrees === false ? "var(--bad)" : "var(--good)" }}>
              {res.check.agrees === true ? `✓ Matches ${res.check.library}.` : res.check.agrees === false ? `✗ Differs from ${res.check.library}: ${Object.entries(res.check.values).map(([k, v]) => `${k} ${fmt(v)}`).join(", ")}.` : `Not compared with ${res.check.library}.`}
              {res.check.note ? ` ${res.check.note}` : ""}</p>
          </div>
        </section>)}
    </PageShell>
  );
}
