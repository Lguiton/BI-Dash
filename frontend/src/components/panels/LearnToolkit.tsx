"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson, putJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
export type FieldSpec = { k: string; label: string; type?: "number" | "text" | "area" | "select"; def?: string; options?: string[]; rows?: number; modes?: string[] };
export type ToolSpec = { id: string; label: string; note: string; endpoint: string; fields: FieldSpec[]; build: (v: R) => unknown; sample?: (s: R) => R };

const num = (v: any) => Number(v);
const json = (t: string, what: string) => { try { return JSON.parse(t); } catch { throw new Error(`${what} isn't valid JSON.`); } };

const ML_TOOLS: ToolSpec[] = [
  { id: "bv", label: "Bias and variance", endpoint: "/api/learn/ml/bias-variance", note: "Fit polynomials of rising degree to noisy data. Training error always falls; watch the validation error.",
    fields: [{ k: "n", label: "Points", type: "number", def: "40" }, { k: "noise", label: "Noise", type: "number", def: "0.3" }, { k: "degrees", label: "Degrees (comma separated)", def: "1,2,3,5,8,12" }, { k: "seed", label: "Seed", type: "number", def: "7" }],
    build: (v) => ({ n: num(v.n), noise: num(v.noise), degrees: String(v.degrees).split(",").map((x) => Number(x.trim())).filter((x) => !Number.isNaN(x)), seed: num(v.seed) }) },
  { id: "gd", label: "Gradient descent", endpoint: "/api/learn/ml/gradient-descent", note: "Step downhill by learning rate times slope. Try 0.0001, 0.3 and 40.",
    fields: [{ k: "task", label: "Task", type: "select", options: ["linear", "logistic"], def: "linear" }, { k: "lr", label: "Learning rate", type: "number", def: "0.3" }, { k: "steps", label: "Steps", type: "number", def: "100" }, { k: "seed", label: "Seed", type: "number", def: "3" }],
    build: (v) => ({ task: v.task, lr: num(v.lr), steps: num(v.steps), seed: num(v.seed) }) },
  { id: "scratch", label: "Algorithms from scratch", endpoint: "/api/learn/ml/scratch", note: "kNN, logistic regression, a decision tree and naive Bayes written by hand, against a dumb baseline.",
    fields: [{ k: "n", label: "Rows", type: "number", def: "300" }, { k: "noise", label: "Noise", type: "number", def: "0.25" }, { k: "k", label: "k for kNN", type: "number", def: "7" }, { k: "depth", label: "Tree depth", type: "number", def: "4" }, { k: "seed", label: "Seed", type: "number", def: "11" }],
    build: (v) => ({ n: num(v.n), noise: num(v.noise), k: num(v.k), depth: num(v.depth), seed: num(v.seed) }) },
  { id: "scores", label: "Scores and thresholds", endpoint: "/api/learn/ml/scores", note: "Paste 'score,label' lines (label 1 or 0). Get ROC-AUC, PR-AUC, calibration and the cheapest cut-off for YOUR costs.",
    fields: [{ k: "text", label: "score,label lines", type: "area", rows: 8 }, { k: "fp", label: "Cost of a false alarm", type: "number", def: "1" }, { k: "fn", label: "Cost of a miss", type: "number", def: "5" }],
    build: (v) => ({ text: v.text, fp_cost: num(v.fp), fn_cost: num(v.fn) }), sample: (s) => ({ text: s.scores }) },
  { id: "leak", label: "Leakage scan", endpoint: "/api/learn/ml/leak", note: "Paste a CSV and name the target. Finds columns that give the answer away, IDs and duplicates.",
    fields: [{ k: "csv", label: "CSV with a header row", type: "area", rows: 8 }, { k: "target", label: "Target column", def: "churned" }],
    build: (v) => ({ csv: v.csv, target: v.target }), sample: (s) => ({ csv: s.leak, target: "churned" }) },
];

const AI_TOOLS: ToolSpec[] = [
  { id: "ret", label: "Retrieval metrics", endpoint: "/api/learn/ai/retrieval", note: "JSON list of cases: what was retrieved, what was relevant. An empty 'relevant' means the corpus cannot answer it.",
    fields: [{ k: "cases", label: "Cases (JSON)", type: "area", rows: 8 }, { k: "k", label: "k", type: "number", def: "3" }],
    build: (v) => ({ cases: json(v.cases, "Cases"), k: num(v.k) }), sample: (s) => ({ cases: JSON.stringify(s.retrieval, null, 1) }) },
  { id: "hyb", label: "Hybrid search", endpoint: "/api/learn/ai/hybrid", note: "Keyword (BM25) plus a character n-gram vector, merged by rank fusion, then MMR. The vector is a stand-in, not a learned embedding.",
    fields: [{ k: "docs", label: "Documents (JSON list of {id,text})", type: "area", rows: 7 }, { k: "query", label: "Query", def: "how long do refunds take" }, { k: "k", label: "k", type: "number", def: "2" }],
    build: (v) => ({ docs: json(v.docs, "Documents"), query: v.query, k: num(v.k) }), sample: (s) => ({ docs: JSON.stringify(s.docs, null, 1) }) },
  { id: "schema", label: "Structured output", endpoint: "/api/learn/ai/schema", note: "Check a model reply against a schema and get the repair prompt to send back.",
    fields: [{ k: "output", label: "Model reply", type: "area", rows: 5 }, { k: "schema", label: "Schema (JSON)", type: "area", rows: 6 }],
    build: (v) => ({ output: v.output, schema: json(v.schema, "Schema") }), sample: (s) => ({ output: s.output, schema: JSON.stringify(s.schema, null, 1) }) },
  { id: "trace", label: "Agent trace", endpoint: "/api/learn/ai/trace", note: "Paste an agent's steps as JSON. Finds loops, repeated failures, budget overruns and unapproved side effects.",
    fields: [{ k: "steps", label: "Steps (JSON)", type: "area", rows: 8 }, { k: "max", label: "Step budget", type: "number", def: "12" }, { k: "pin", label: "Input price per million tokens", type: "number", def: "0" }, { k: "pout", label: "Output price per million tokens", type: "number", def: "0" }],
    build: (v) => ({ steps: json(v.steps, "Steps"), max_steps: num(v.max), price_in_per_million: num(v.pin), price_out_per_million: num(v.pout) }), sample: (s) => ({ steps: JSON.stringify(s.trace, null, 1), max: "4" }) },
  { id: "stats", label: "Eval statistics", endpoint: "/api/learn/ai/eval-stats", note: "How sure are you? Intervals, test-set size, A/B significance, judge agreement and pass@k.",
    fields: [{ k: "mode", label: "Question", type: "select", options: ["interval", "sample_size", "compare", "kappa", "pass_at_k"], def: "interval" },
      { k: "n", label: "Test cases", type: "number", def: "100", modes: ["interval"] }, { k: "passes", label: "Passes", type: "number", def: "80", modes: ["interval"] }, { k: "confidence", label: "Confidence % (90, 95, 99)", type: "number", def: "95", modes: ["interval", "sample_size"] },
      { k: "expected_rate", label: "Expected pass rate (0 to 1)", type: "number", def: "0.8", modes: ["sample_size"] }, { k: "margin", label: "Margin (0 to 1)", type: "number", def: "0.05", modes: ["sample_size"] },
      { k: "n1", label: "Cases for A", type: "number", def: "100", modes: ["compare"] }, { k: "passes1", label: "Passes for A", type: "number", def: "70", modes: ["compare"] }, { k: "n2", label: "Cases for B", type: "number", def: "100", modes: ["compare"] }, { k: "passes2", label: "Passes for B", type: "number", def: "78", modes: ["compare"] },
      { k: "both_yes", label: "Judge yes, human yes", type: "number", def: "40", modes: ["kappa"] }, { k: "judge_yes_human_no", label: "Judge yes, human no", type: "number", def: "10", modes: ["kappa"] }, { k: "judge_no_human_yes", label: "Judge no, human yes", type: "number", def: "10", modes: ["kappa"] }, { k: "both_no", label: "Judge no, human no", type: "number", def: "40", modes: ["kappa"] },
      { k: "samples", label: "Samples per task", type: "number", def: "10", modes: ["pass_at_k"] }, { k: "correct", label: "Correct samples", type: "number", def: "4", modes: ["pass_at_k"] }, { k: "k", label: "k tries", type: "number", def: "3", modes: ["pass_at_k"] }],
    build: (v) => ({ mode: v.mode, args: Object.fromEntries(Object.entries(v).filter(([k]) => k !== "mode" && k !== "__fields").map(([k, x]) => [k, Number(x)]).filter(([k]) => (v.__fields as FieldSpec[]).some((f) => f.k === k && (!f.modes || f.modes.includes(v.mode))))) }) },
  { id: "rel", label: "Reliability", endpoint: "/api/learn/ai/reliability", note: "Retry back-off, error budgets, chained availability, and how retries multiply load.",
    fields: [{ k: "mode", label: "Question", type: "select", options: ["backoff", "error_budget", "chain", "amplification"], def: "backoff" },
      { k: "base_s", label: "First delay (s)", type: "number", def: "1", modes: ["backoff"] }, { k: "factor", label: "Multiplier", type: "number", def: "2", modes: ["backoff"] }, { k: "cap_s", label: "Longest delay (s)", type: "number", def: "30", modes: ["backoff"] }, { k: "retries", label: "Retries", type: "number", def: "5", modes: ["backoff"] }, { k: "timeout_s", label: "Per-call timeout (s)", type: "number", def: "30", modes: ["backoff"] },
      { k: "slo_pct", label: "Availability target %", type: "number", def: "99.5", modes: ["error_budget"] }, { k: "window_days", label: "Window (days)", type: "number", def: "30", modes: ["error_budget"] }, { k: "downtime_min", label: "Downtime used (min)", type: "number", def: "0", modes: ["error_budget"] },
      { k: "availabilities", label: "Availabilities % (comma separated)", def: "99.9, 99.5, 99.0", modes: ["chain"] }, { k: "fallback_pct", label: "Backup provider availability % (optional)", def: "99.0", modes: ["chain"] },
      { k: "retries_per_layer", label: "Retries per layer", type: "number", def: "2", modes: ["amplification"] }, { k: "layers", label: "Layers that retry", type: "number", def: "3", modes: ["amplification"] }, { k: "requests_per_s", label: "Requests per second", type: "number", def: "10", modes: ["amplification"] }],
    build: (v) => {
      const out: R = {};
      for (const f of v.__fields as FieldSpec[]) {
        if (f.k === "mode" || (f.modes && !f.modes.includes(v.mode))) continue;
        if (f.k === "availabilities") out[f.k] = String(v[f.k]).split(",").map((x) => Number(x.trim()));
        else if (f.k === "fallback_pct") { if (String(v[f.k]).trim() !== "") out[f.k] = Number(v[f.k]); }
        else out[f.k] = Number(v[f.k]);
      }
      return { mode: v.mode, args: out };
    } },
  { id: "ft", label: "Fine-tune data", endpoint: "/api/learn/ai/finetune-data", note: "Paste training data as JSONL (one JSON object per line). Checks format, duplicates and overlap with a test set.",
    fields: [{ k: "train", label: "Training JSONL", type: "area", rows: 8 }, { k: "test", label: "Test JSONL (optional)", type: "area", rows: 3 }],
    build: (v) => ({ train: v.train, test: v.test }), sample: (s) => ({ train: s.finetune, test: String(s.finetune).split("\n")[1] }) },
  { id: "lora", label: "LoRA size", endpoint: "/api/learn/ai/lora", note: "Memory and compute for a full fine-tune versus LoRA. Back-of-envelope: no GPU is used.",
    fields: [{ k: "p", label: "Model size (billions of parameters)", type: "number", def: "7" }, { k: "layers", label: "Layers", type: "number", def: "32" }, { k: "hidden", label: "Hidden size", type: "number", def: "4096" }, { k: "rank", label: "LoRA rank", type: "number", def: "16" }, { k: "targets", label: "Adapted matrices per layer", type: "number", def: "4" },
      { k: "wb", label: "Bytes per weight (2 = 16-bit, 0.5 = 4-bit)", type: "number", def: "2" }, { k: "tok", label: "Training tokens (millions)", type: "number", def: "10" }, { k: "ep", label: "Epochs", type: "number", def: "3" }, { k: "tf", label: "GPU TFLOPS", type: "number", def: "100" }, { k: "mfu", label: "Utilisation %", type: "number", def: "30" }],
    build: (v) => ({ params_b: num(v.p), layers: num(v.layers), hidden: num(v.hidden), rank: num(v.rank), targets: num(v.targets), weight_bytes: num(v.wb), tokens_m: num(v.tok), epochs: num(v.ep), gpu_tflops: num(v.tf), mfu_pct: num(v.mfu) }) },
  { id: "guard", label: "PII and injection scan", endpoint: "/api/learn/ai/guard", note: "Redact personal data and secrets before text reaches a model, and spot instruction-like text in retrieved content.",
    fields: [{ k: "text", label: "Text to scan", type: "area", rows: 6 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.guard }) },
];

const PRE = ["config", "template", "ldif"];
const SKIP = new Set(["lesson", "limit", "reading", "verdict", "note", "repair_prompt", "redacted", "gpu_hours_note", ...PRE]);
const cell = (v: any): string => (v == null ? "-" : typeof v === "object" ? (Array.isArray(v) ? v.map(cell).join(", ") : Object.entries(v).map(([k, x]) => `${k}: ${cell(x)}`).join("; ")) : typeof v === "boolean" ? (v ? "yes" : "no") : typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : String(Math.round(v * 10000) / 10000)) : String(v));
const label = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export function Result({ r }: { r: R }) {
  const scalars = Object.entries(r).filter(([k, v]) => !SKIP.has(k) && (v == null || typeof v !== "object"));
  const lists = Object.entries(r).filter(([k, v]) => !SKIP.has(k) && Array.isArray(v) && v.length > 0);
  const objs = Object.entries(r).filter(([k, v]) => !SKIP.has(k) && v && typeof v === "object" && !Array.isArray(v));
  return (
    <div className="mt-3 space-y-3">
      {r.verdict && <p className="text-sm font-semibold">{r.verdict}</p>}
      {r.reading && <p className="text-sm">{r.reading}</p>}
      {r.note && <p className="text-sm text-muted">{r.note}</p>}
      {scalars.length > 0 && <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{scalars.slice(0, 12).map(([k, v]) => <Stat key={k} label={label(k)} value={cell(v)} />)}</div>}
      {objs.map(([k, v]) => <Table key={k} caption={label(k)} head={["Item", "Value"]} rows={Object.entries(v as R).map(([a, b]) => [label(a), cell(b)])} />)}
      {lists.map(([k, v]) => typeof (v as any[])[0] === "object" && (v as any[])[0] !== null && !Array.isArray((v as any[])[0])
        ? <Table key={k} caption={label(k)} head={Object.keys((v as R[])[0]).map(label)} rows={(v as R[]).map((row) => Object.keys((v as R[])[0]).map((c) => cell(row[c])))} />
        : <div key={k}><h4 className="text-sm font-semibold">{label(k)}</h4><ul className="list-disc pl-5 text-sm">{(v as any[]).map((x, i) => <li key={i}>{cell(x)}</li>)}</ul></div>)}
      {PRE.filter((k) => typeof r[k] === "string" && r[k]).map((k) => <div key={k}><h4 className="text-sm font-semibold">{label(k)}</h4><pre className="overflow-x-auto whitespace-pre-wrap rounded border border-line bg-panel2 p-3 font-mono text-xs">{r[k]}</pre></div>)}
      {r.repair_prompt && <div><h4 className="text-sm font-semibold">Repair prompt to send back</h4><pre className="overflow-x-auto rounded border border-line bg-panel2 p-3 text-xs">{r.repair_prompt}</pre></div>}
      {r.redacted && <div><h4 className="text-sm font-semibold">Redacted text</h4><pre className="overflow-x-auto whitespace-pre-wrap rounded border border-line bg-panel2 p-3 text-xs">{r.redacted}</pre></div>}
      {r.gpu_hours_note && <p className="text-xs text-muted">{r.gpu_hours_note}</p>}
      {r.lesson && <Lesson text={r.lesson} />}
      {r.limit && <p className="text-xs text-muted">{r.limit}</p>}
    </div>
  );
}

export function ToolView({ spec, samples }: { spec: ToolSpec; samples: R | null }) {
  const init = () => Object.fromEntries(spec.fields.map((f) => [f.k, f.def ?? ""]));
  const [v, setV] = useState<R>(init);
  const [res, setRes] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  const shown = spec.fields.filter((f) => !f.modes || f.modes.includes(v.mode));
  const go = () => {
    setErr(null);
    try { postJson<R>(spec.endpoint, spec.build({ ...v, __fields: spec.fields })).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That didn't work.")); }); }
    catch (e) { setRes(null); setErr(e instanceof Error ? e.message : "Check your input."); }
  };
  return (
    <Section title={spec.label} note={spec.note}>
      <div className="grid gap-2 sm:grid-cols-2">
        {shown.map((f) => (
          <div key={f.k} className={f.type === "area" ? "sm:col-span-2" : ""}>
            <Field label={f.label}>
              {f.type === "area" ? <textarea className="field font-mono" rows={f.rows ?? 5} value={v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} aria-label={f.label} />
                : f.type === "select" ? <select className="field" value={v[f.k]} onChange={(e) => { setV({ ...v, [f.k]: e.target.value }); setRes(null); }} aria-label={f.label}>{f.options!.map((o) => <option key={o}>{o}</option>)}</select>
                : <input className="field" type={f.type === "number" ? "number" : "text"} step="any" value={v[f.k]} onChange={(e) => setV({ ...v, [f.k]: e.target.value })} aria-label={f.label} />}
            </Field>
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-2"><button className="btn btn-primary" onClick={go}>Run</button>{spec.sample && samples && <button className="btn" onClick={() => setV({ ...v, ...spec.sample!(samples) })}>Load sample</button>}</div>
      {err && <ErrorBanner message={err} />}
      {res && <Result r={res} />}
    </Section>
  );
}

const Links = ({ items }: { items: { label: string; url: string }[] }) => (
  <>{items.map((l, i) => <span key={l.url}>{i > 0 && " · "}<a href={l.url} target="_blank" rel="noopener noreferrer" className="text-accent underline">{l.label}</a></span>)}</>
);

const STATUS: Record<string, { tone: "ok" | "warn" | "bad" | "muted"; text: string }> = {
  built: { tone: "ok", text: "Built here" }, partial: { tone: "warn", text: "Partly here" }, guide: { tone: "muted", text: "Study outside" }, cannot: { tone: "bad", text: "Can't run here" },
};

function PathView({ track }: { track: "ml" | "ai" }) {
  const [d, setD] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  const load = () => getJson<R>(`/api/learn/path/${track}`).then(setD).catch((e) => setErr(errMsg(e, "Could not load the path.")));
  useEffect(() => { load(); }, [track]); // eslint-disable-line react-hooks/exhaustive-deps
  const tick = (id: string, done: boolean) => { setErr(null); putJson<R>(`/api/learn/path/${track}/module/${id}`, { done }).then(load).catch((e) => setErr(errMsg(e, "Could not save."))); };
  const gate = (id: string, passed: boolean) => { setErr(null); putJson<R>(`/api/learn/path/${track}/gate/${id}`, { passed }).then(load).catch((e) => setErr(errMsg(e, "Could not save."))); };
  if (!d) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading...</p>;
  return (
    <div className="space-y-4">
      <Lesson text={d.intro} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5"><Stat label="Modules proved" value={`${d.done} of ${d.total}`} /><Stat label="Progress" value={`${d.pct}%`} /><Stat label="Gates passed" value={String(d.gates_passed)} />
        <Stat label="Built here" value={String(d.coverage.built)} /><Stat label="Can't run here" value={String(d.coverage.cannot)} /></div>
      {err && <ErrorBanner message={err} />}
      {(d.levels as R[]).map((lv) => (
        <Section key={lv.id} title={`${lv.id}. ${lv.title}  (${lv.weeks} weeks)`} note={`Gate project: ${lv.gate}`}>
          <ul className="space-y-2">
            {(lv.modules as R[]).map((m) => (
              <li key={m.id} className="rounded border border-line p-2 text-sm">
                <label className="flex items-start gap-2"><input type="checkbox" checked={m.done} onChange={(e) => tick(m.id, e.target.checked)} className="mt-1" aria-label={`Proved ${m.title}`} />
                  <span><strong>{m.id} {m.title}</strong> <Badge tone={STATUS[m.status].tone}>{STATUS[m.status].text}</Badge><br /><span className="text-muted">{m.topics}</span></span></label>
                <p className="ml-6 mt-1"><span className="font-medium">Where:</span> {m.where}</p>
                <p className="ml-6"><span className="font-medium">Prove it:</span> {m.practice}</p>
                {(m.links as R[]).length > 0 && <p className="ml-6"><span className="font-medium">Get it:</span> <Links items={m.links} /></p>}
              </li>
            ))}
          </ul>
          <div className="mt-2 flex items-center gap-2"><span className="text-xs text-muted">{lv.done} of {lv.total} modules proved</span>
            <button className="btn" onClick={() => gate(lv.id, !lv.gate_passed)}>{lv.gate_passed ? "Gate passed. Undo" : "Mark gate project passed"}</button></div>
        </Section>
      ))}
      {(d.capstones as string[]).length > 0 && <Section title="Master capstone options"><ul className="list-disc pl-5 text-sm">{(d.capstones as string[]).map((c) => <li key={c}>{c}</li>)}</ul>
        <p className="mt-1 text-xs text-muted">Ship with: live demo, shareable repo, eval report with baselines, threat model, cost model, decision record and a 10-minute walkthrough. Score 3 or more on: {(d.rubric as string[]).join(", ")}.</p></Section>}
      <Section title="Can't run here: where to get it" note={d.link_note}>
        <div className="space-y-3">{(d.not_here as R[]).map((g) => (
          <div key={g.group}><h4 className="text-sm font-semibold">{g.group}</h4>
            <ul className="mt-1 space-y-2 text-sm">{(g.items as R[]).map((it) => <li key={it.name}><strong>{it.name}</strong>: {it.what} <span className="text-muted">{it.why}</span><br /><Links items={it.links} /></li>)}</ul></div>
        ))}</div>
      </Section>
      <Section title="Resources (from general knowledge; confirm current editions)"><Table head={["Level", "Resource", "Type"]} rows={(d.resources as R[]).map((r) => [r.level, r.url ? <a key="u" href={r.url} target="_blank" rel="noopener noreferrer" className="text-accent underline">{r.name}</a> : r.name, r.type])} /></Section>
      <Section title="Slips and limits"><ul className="list-disc space-y-1 pl-5 text-sm">{(d.slips as string[]).map((x) => <li key={x}>{x}</li>)}</ul><p className="mt-2 text-xs text-muted">{d.limit}</p></Section>
    </div>
  );
}

export function LearnToolkit({ track }: { track: "ml" | "ai" }) {
  const tools = track === "ml" ? ML_TOOLS : AI_TOOLS;
  const [tab, setTab] = useState("path");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>(`/api/learn/${track}/reference`).then((r) => setSamples(r.samples)).catch(() => undefined); }, [track]);
  const spec = tools.find((t) => t.id === tab);
  return (
    <section className="card space-y-4 p-4" aria-label={track === "ml" ? "Machine learning learning path" : "AI engineering learning path"}>
      <h2 className="text-base font-semibold">{track === "ml" ? "Machine learning: beginner to advanced" : "AI engineering: beginner to master"}</h2>
      <Lesson text={track === "ml" ? "A level-by-level path with a gate project at the end of each, plus offline tools that show why the usual rules exist. Everything runs free on your machine." : "Your nine-level curriculum mapped onto this app. Each module says whether there is something to run here, and the tools below check retrieval, outputs, agents, evals, reliability, training data and safety without calling a model."} />
      <Tabs tabs={[{ id: "path", label: "Learning path" }, ...tools.map((t) => ({ id: t.id, label: t.label }))]} value={tab} onChange={setTab} label="Learning tools" />
      {tab === "path" && <PathView track={track} />}
      {spec && <ToolView key={spec.id} spec={spec} samples={samples} />}
    </section>
  );
}
