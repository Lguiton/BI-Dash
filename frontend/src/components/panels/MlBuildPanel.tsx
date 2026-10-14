"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const area = (k: string, label: string, def = "", rows = 5) => ({ k, label, type: "area" as const, def, rows });
const num = (k: string, label: string, def: string) => ({ k, label, type: "number" as const, def });

const TOOLS: ToolSpec[] = [
  { id: "drift", label: "Input and label drift", endpoint: "/api/mlbuild/drift", note: "Paste the numbers (or labels, separated by commas) your model was built on and the ones it sees now. Gives PSI, a KS test and the bin-by-bin shift.",
    fields: [{ k: "k", label: "Kind", type: "select", options: ["numeric", "labels"], def: "numeric" }, area("a", "Reference (training-time) values", "", 4), area("b", "Current values", "", 4)], build: (v) => ({ kind: v.k, reference: v.a, current: v.b }), sample: (s) => ({ k: "numeric", a: s.drift.reference, b: s.drift.current }) },
  { id: "perf", label: "Performance drift", endpoint: "/api/mlbuild/performance-drift", note: "One line per period: period, correct, total. The first line is the baseline. Shows an interval for each period and tests for a real drop.",
    fields: [area("r", "Periods", "", 7)], build: (v) => ({ rows: v.r }), sample: (s) => ({ r: s.perf }) },
  { id: "auto", label: "Automatic search", endpoint: "/api/mlbuild/automl", note: "Paste a CSV with column names. The tool picks features one at a time, cross-checks three kinds of model against a do-nothing baseline, and warns about luck and leakage. Up to 5,000 rows.",
    fields: [area("c", "CSV data", "", 8), { k: "t", label: "Target column", type: "text", def: "target" }, num("m", "Most features to keep", "6")], build: (v) => ({ csv: v.c, target: v.t, max_features: Number(v.m) }), sample: (s) => ({ c: s.automl, t: "target" }) },
  { id: "bpe", label: "Tokenizer (BPE)", endpoint: "/api/mlbuild/bpe", note: "Paste some text and learn how byte-pair encoding builds a vocabulary by merging the most common neighbouring pair.",
    fields: [area("t", "Training text", "", 5), num("m", "Merges", "10"), { k: "w", label: "Words to encode", type: "text", def: "lowest newer" }], build: (v) => ({ text: v.t, merges: Number(v.m), test: v.w }), sample: (s) => ({ t: s.bpe }) },
  { id: "lsa", label: "Meaning search (LSA)", endpoint: "/api/mlbuild/lsa", note: "One document per line. Compares plain word matching with a concept-based match that can find documents sharing none of the query's words.",
    fields: [area("d", "Documents", "", 6), { k: "q", label: "Query", type: "text", def: "car repair" }, num("k", "Concepts", "2")], build: (v) => ({ docs: v.d, query: v.q, k: Number(v.k) }), sample: (s) => ({ d: s.lsa.docs, q: s.lsa.query, k: String(s.lsa.k) }) },
];

function Boundary({ r }: { r: R }) {
  const g: number[][] = r.boundary_grid;
  const pts: R[] = r.points;
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const lo = Math.min(...xs, ...ys) - 0.1, hi = Math.max(...xs, ...ys) + 0.1, S = 240, c = S / g.length;
  const mx = (v: number) => ((v - lo) / (hi - lo)) * S, my = (v: number) => S - ((v - lo) / (hi - lo)) * S;
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="h-60 w-60 rounded border border-line" role="img" aria-label="Decision boundary of the network">
      {g.map((row, j) => row.map((v, i) => <rect key={`${i}-${j}`} x={i * c} y={S - (j + 1) * c} width={c} height={c} fill={v ? "#3b82f6" : "#f59e0b"} opacity={0.22} />))}
      {pts.map((p, i) => <circle key={i} cx={mx(p.x)} cy={my(p.y)} r={2.6} fill={p.label ? "#1d4ed8" : "#b45309"} stroke={p.split === "test" ? "#000" : "none"} strokeWidth={0.8} />)}
    </svg>
  );
}

function Curve({ pts }: { pts: R[] }) {
  const W = 300, H = 90, mx = Math.max(...pts.map((p) => p.loss)), e = pts[pts.length - 1].epoch || 1;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${(p.epoch / e) * W},${H - (p.loss / mx) * (H - 6) - 3}`).join(" ");
  return <svg viewBox={`0 0 ${W} ${H}`} className="h-24 w-full max-w-sm rounded border border-line" role="img" aria-label="Training loss over time"><path d={d} fill="none" stroke="#3b82f6" strokeWidth={2} /></svg>;
}

function NnTab() {
  const [v, setV] = useState<R>({ data: "xor", hidden: "8", activation: "tanh", lr: "0.1", epochs: "300" });
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [chk, setChk] = useState<R | null>(null);
  const run = () => { setErr(null); postJson<R>("/api/mlbuild/neural-net", { data: v.data, hidden: v.hidden, activation: v.activation, lr: Number(v.lr), epochs: Number(v.epochs) }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That did not work.")); }); };
  const set = (k: string) => (e: any) => setV({ ...v, [k]: e.target.value });
  return (
    <Section title="Neural network from scratch" note="A small network written in numpy, trained by backpropagation on 2D points. Change the layers and watch the boundary. Dots with a black ring are test points the network never trained on.">
      <div className="grid gap-2 sm:grid-cols-3">
        <Field label="Data"><select className="field" value={v.data} onChange={set("data")} aria-label="Data"><option>xor</option><option>circles</option><option>moons</option><option>line</option></select></Field>
        <Field label="Hidden layers (e.g. 8 or 8,4; blank for none)"><input className="field" value={v.hidden} onChange={set("hidden")} aria-label="Hidden layers" /></Field>
        <Field label="Activation"><select className="field" value={v.activation} onChange={set("activation")} aria-label="Activation"><option>tanh</option><option>relu</option><option>sigmoid</option></select></Field>
        <Field label="Learning rate"><input className="field" type="number" step="any" value={v.lr} onChange={set("lr")} aria-label="Learning rate" /></Field>
        <Field label="Epochs"><input className="field" type="number" value={v.epochs} onChange={set("epochs")} aria-label="Epochs" /></Field>
      </div>
      <div className="mt-2 flex gap-2"><button className="btn btn-primary" onClick={run}>Train</button><button className="btn" onClick={() => getJson<R>("/api/mlbuild/gradient-check").then(setChk).catch((e) => setErr(errMsg(e, "That did not work.")))}>Check the gradients</button></div>
      {err && <ErrorBanner message={err} />}
      {chk && <div className="mt-3"><Table head={["Weight", "Backprop", "Numerical", "Difference"]} rows={chk.checks.map((c: R) => [c.weight, c.backprop_gradient, c.numerical_gradient, c.difference])} caption={chk.ok ? "Gradient check passed" : "Gradient check failed"} /><p className="mt-1 text-xs text-muted">{chk.lesson}</p></div>}
      {res && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Parameters" value={String(res.parameters)} /><Stat label="Train accuracy" value={`${res.train_accuracy_pct}%`} /><Stat label="Test accuracy" value={`${res.test_accuracy_pct}%`} /><Stat label="Layers" value={res.architecture.join(" - ")} /></div>
          <div className="flex flex-wrap items-start gap-4"><Boundary r={res} /><div><p className="text-xs text-muted">Training loss (lower is better)</p><Curve pts={res.loss_curve} /></div></div>
          {res.notes.length > 0 && <ul className="list-disc pl-5 text-sm">{res.notes.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>}
          <p className="text-xs text-muted">{res.lesson}</p>
        </div>
      )}
    </Section>
  );
}

function AttentionTab() {
  const [t, setT] = useState("the cat sat on the mat");
  const [causal, setCausal] = useState(false);
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = () => { setErr(null); postJson<R>("/api/mlbuild/attention", { text: t, dim: 8, causal }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That did not work.")); }); };
  return (
    <Section title="Attention" note="Scaled dot-product attention with random (untrained) weights, to show the mechanism. Each row says how much one word looks at every word. The pattern has no meaning until a model is trained.">
      <Field label="Sentence (2 to 16 words)"><input className="field" value={t} onChange={(e) => setT(e.target.value)} aria-label="Sentence" /></Field>
      <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={causal} onChange={(e) => setCausal(e.target.checked)} /> Causal mask (a word cannot look at later words)</label>
      <div className="mt-2"><button className="btn btn-primary" onClick={run}>Run</button></div>
      {err && <ErrorBanner message={err} />}
      {res && (
        <div className="mt-3 space-y-2 overflow-x-auto">
          <table className="text-xs" aria-label="Attention weights"><thead><tr><th className="p-1 text-left">looks from \ at</th>{res.tokens.map((x: string, i: number) => <th key={i} className="p-1">{x}</th>)}</tr></thead>
            <tbody>{res.weights.map((row: number[], i: number) => <tr key={i}><th className="p-1 text-left">{res.tokens[i]}</th>{row.map((w, j) => <td key={j} className="p-1 text-center" style={{ background: `rgba(59,130,246,${Math.min(1, w * 1.5)})`, color: w > 0.5 ? "#fff" : undefined }}>{w.toFixed(2)}</td>)}</tr>)}</tbody></table>
          <p className="text-xs text-muted">{res.lesson}</p><p className="text-xs text-muted">{res.limits}</p>
        </div>
      )}
    </Section>
  );
}

export function MlBuildPanel() {
  const [ref, setRef] = useState<R | null>(null);
  const [id, setId] = useState("drift");
  useEffect(() => { getJson<R>("/api/mlbuild/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id);
  return (
    <Section title="Build and check ML pieces" note="Drift checks, automatic search, a network and attention written from scratch, a tokenizer and a meaning search. Small, repeatable and honest about their limits.">
      <Tabs tabs={[...TOOLS.map((t) => ({ id: t.id, label: t.label })), { id: "nn", label: "Neural network" }, { id: "att", label: "Attention" }]} value={id} onChange={setId} label="ML build tools" />
      {id === "nn" ? <NnTab /> : id === "att" ? <AttentionTab /> : spec && <ToolView key={spec.id} spec={spec} samples={ref?.samples ?? null} />}
      {ref && <>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes common in the sources</summary><ul className="list-disc pl-5">{ref.slips.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary><ul className="list-disc pl-5">{ref.not_built.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      </>}
    </Section>
  );
}
