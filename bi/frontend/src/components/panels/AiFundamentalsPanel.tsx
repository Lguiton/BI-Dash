"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "concepts", label: "Concepts" }, { id: "learning", label: "Learning" }, { id: "nn", label: "Neural networks" }, { id: "nlp", label: "Language (NLP)" }, { id: "bot", label: "Chatbot and RAG" }, { id: "ref", label: "Reference" }];
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const Code = ({ children }: { children: string }) => <pre className="max-h-64 overflow-auto rounded border border-line bg-panel2 p-2 text-xs" tabIndex={0}><code>{children}</code></pre>;
const Opt = ({ v, l }: { v: string; l?: string }) => <option value={v}>{l ?? v}</option>;

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body: unknown) => { setErr(null); postJson<T>(path, body).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Check your input.")); }); };
  return { res, err, run };
}
const Out = ({ c }: { c: { res: R | null; err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);

export function AiFundamentalsPanel() {
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("concepts");
  useEffect(() => { getJson<R>("/api/aiml").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load AI fundamentals."))); }, []);
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading AI fundamentals…</p>;
  return (
    <section className="card space-y-4 p-4" aria-label="AI fundamentals">
      <h2 className="text-base font-semibold">AI fundamentals</h2>
      <Lesson text={ref.note} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="AI fundamentals" />
      {tab === "concepts" && <Concepts ref_={ref} />}
      {tab === "learning" && <Learning />}
      {tab === "nn" && <Nn ref_={ref.nn} />}
      {tab === "nlp" && <Nlp ref_={ref.nlp} />}
      {tab === "bot" && <Bot ref_={ref.nlp} />}
      {tab === "ref" && <Reference ref_={ref} />}
    </section>
  );
}

function Concepts({ ref_ }: { ref_: R }) {
  const [f, setF] = useState({ task: "category", labeled_data: "some", data_size: "medium", need_explain: false, unstructured: false });
  const c = useCall();
  return (
    <div className="space-y-3">
      <Section title="How the terms nest" note="Each level is a subset of the one above.">
        <Table head={["Level", "What it is"]} rows={ref_.hierarchy.map((h: R, i: number) => [<span key="l" style={{ paddingLeft: i * 10 }}>{h.level}</span>, h.what])} />
      </Section>
      <Section title="Which approach fits your task?">
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="What do you need?"><select className="field" value={f.task} onChange={(e) => setF({ ...f, task: e.target.value })}>{Object.entries(ref_.approach_tasks as R).map(([k, v]) => <Opt key={k} v={k} l={String(v)} />)}</select></Field>
          <Field label="Labelled examples"><select className="field" value={f.labeled_data} onChange={(e) => setF({ ...f, labeled_data: e.target.value })}><Opt v="none" /><Opt v="some" /><Opt v="plenty" /></select></Field>
          <Field label="Data size"><select className="field" value={f.data_size} onChange={(e) => setF({ ...f, data_size: e.target.value })}><Opt v="small" /><Opt v="medium" /><Opt v="large" /></select></Field>
          <label className="text-sm"><input type="checkbox" checked={f.need_explain} onChange={(e) => setF({ ...f, need_explain: e.target.checked })} /> Must be explainable</label>
          <label className="text-sm"><input type="checkbox" checked={f.unstructured} onChange={(e) => setF({ ...f, unstructured: e.target.checked })} /> Images, audio or free text</label>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aiml/approach", f)}>Suggest an approach</button>
        <Out c={c} />
        {c.res && <div className="mt-2 space-y-1 text-sm"><p>Suggested: <Badge tone="ok">{c.res.pick}</Badge></p><ul className="list-disc pl-5 text-xs">{c.res.why.map((w: string, i: number) => <li key={i}>{w}</li>)}{c.res.also.map((w: string, i: number) => <li key={"a" + i}>Also: {w}</li>)}</ul><Lesson text={c.res.lesson} /></div>}
      </Section>
      <Section title="Types of AI">
        <Table head={["By strength", "What", "Status"]} rows={ref_.by_strength.map((x: R) => [x.type, x.what, x.status])} />
        <div className="mt-2" /><Table head={["By how it works", "What", "Example"]} rows={ref_.by_function.map((x: R) => [x.type, x.what, x.example])} />
        <div className="mt-2" /><Table head={["By purpose", "Asks", "Does"]} rows={ref_.by_purpose.map((x: R) => [x.type, x.asks, x.does])} />
      </Section>
      <Section title="Artificial or augmented?" note="Best results usually combine both.">
        <div className="grid gap-2 sm:grid-cols-2"><div><b className="text-sm">Machines</b><ul className="list-disc pl-5 text-xs">{ref_.strengths.machines.map((s: string) => <li key={s}>{s}</li>)}</ul></div><div><b className="text-sm">People</b><ul className="list-disc pl-5 text-xs">{ref_.strengths.humans.map((s: string) => <li key={s}>{s}</li>)}</ul></div></div>
        <Lesson text={ref_.strengths.augmented} />
      </Section>
      <Section title="Adopting AI in a business"><ol className="list-decimal pl-5 text-sm">{ref_.adoption.map((s: string) => <li key={s}>{s}</li>)}</ol><p className="mt-2 text-xs text-muted">Write the plan as an &ldquo;AI use case brief&rdquo; in Qual templates.</p></Section>
    </div>
  );
}

function Learning() {
  const rules = useCall(); const [depth, setDepth] = useState("3");
  const met = useCall(); const [m, setM] = useState({ tp: "40", fp: "10", fn: "20", tn: "930" });
  const spl = useCall(); const [n, setN] = useState("1000");
  const km = useCall(); const [k, setK] = useState("3");
  const rl = useCall(); const [ep, setEp] = useState("400");
  const th = useCall(); const [pro, setPro] = useState(false);
  const rpa = useCall(); const [rp, setRp] = useState({ rule_based: true, digital: true, repetitive: true, structured_input: true, stable_screens: false, volume_per_month: "2000", minutes_each: "4" });
  return (
    <div className="space-y-3">
      <Section title="Traditional programming vs machine learning" note="Invented data, not real health data. The tree learns if-then-else rules from examples; compare it with a rule written by hand.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Tree depth (1-6)"><input className="field" inputMode="numeric" value={depth} onChange={(e) => setDepth(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => rules.run("/api/aiml/rules", { n: 600, max_depth: Number(depth) })}>Learn the rules</button></div>
        <Out c={rules} />
        {rules.res && <div className="mt-2 space-y-2"><Table head={["Set", "Rows", "Accuracy", "Precision", "Recall"]} rows={rules.res.scores.map((s: R) => [s.set, s.rows, s.accuracy, s.precision, s.recall])} />
          <p className="text-xs">Majority-guess baseline accuracy: {rules.res.majority_baseline_accuracy}. Hand-written rule ({rules.res.hand_written_rule.rule}) on the test set: accuracy {rules.res.hand_written_rule.test.accuracy}, recall {rules.res.hand_written_rule.test.recall}.</p>
          {rules.res.overfit_warning && <Warn items={[rules.res.overfit_warning]} />}<Code>{rules.res.rules}</Code><Lesson text={rules.res.lesson} /><Warn items={[rules.res.caution]} /></div>}
      </Section>
      <Section title="Split sizes">
        <div className="flex flex-wrap items-end gap-2"><Field label="Rows"><input className="field" inputMode="numeric" value={n} onChange={(e) => setN(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => spl.run("/api/aiml/split", { n: Number(n) })}>60 / 20 / 20 split</button></div>
        <Out c={spl} />{spl.res && <p className="mt-2 text-sm">Training {spl.res.training}, validation {spl.res.validation}, test {spl.res.test}. <span className="text-xs text-muted">{spl.res.advice}</span></p>}
      </Section>
      <Section title="Accuracy, precision and recall" note="Enter the counts from a confusion matrix.">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{(["tp", "fp", "fn", "tn"] as const).map((x) => <Field key={x} label={{ tp: "True positives", fp: "False positives", fn: "False negatives", tn: "True negatives" }[x]}><input className="field" inputMode="numeric" value={m[x]} onChange={(e) => setM({ ...m, [x]: e.target.value })} /></Field>)}</div>
        <button className="btn btn-primary mt-2" onClick={() => met.run("/api/aiml/metrics", { tp: Number(m.tp), fp: Number(m.fp), fn: Number(m.fn), tn: Number(m.tn) })}>Calculate</button>
        <Out c={met} />
        {met.res && <div className="mt-2 space-y-2"><div className="grid gap-2 sm:grid-cols-4"><Stat label="Accuracy" value={String(met.res.accuracy)} /><Stat label="Precision" value={String(met.res.precision)} /><Stat label="Recall" value={String(met.res.recall)} /><Stat label="F1" value={String(met.res.f1)} /></div><Warn items={met.res.notes} /></div>}
      </Section>
      <Section title="Unsupervised: k-means groups" note="Three invented clusters. The algorithm finds groups but cannot name them.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Groups (k)"><input className="field" inputMode="numeric" value={k} onChange={(e) => setK(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => km.run("/api/aiml/kmeans", { k: Number(k) })}>Find groups</button></div>
        <Out c={km} />{km.res && <div className="mt-2 space-y-1 text-sm"><p>Group sizes: {km.res.sizes.join(", ")}. Inertia (total squared distance to centres): {km.res.inertia}. Try k = 2 and k = 5 and watch it still &ldquo;find&rdquo; groups.</p><Table head={["Group", "Centre x", "Centre y"]} rows={km.res.centers.map((c: number[], i: number) => [i + 1, c[0], c[1]])} /><Lesson text={km.res.lesson} /></div>}
      </Section>
      <Section title="Reinforcement: Q-learning on a grid" note="Arrows show the best action learned for each square. G = goal, X = pit.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Episodes"><input className="field" inputMode="numeric" value={ep} onChange={(e) => setEp(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => rl.run("/api/aiml/qlearning", { episodes: Number(ep) })}>Learn</button></div>
        <Out c={rl} />{rl.res && <div className="mt-2 space-y-1"><p className="text-xs text-muted">{rl.res.setup}</p><Code>{rl.res.policy.map((r: string[]) => r.join("  ")).join("\n")}</Code><p className="text-sm">Reaches the goal: {rl.res.reaches_goal ? "yes" : "no"}. Average reward: {rl.res.avg_reward_first_tenth} early, {rl.res.avg_reward_last_tenth} late.</p><Lesson text={rl.res.lesson} /></div>}
      </Section>
      <Section title="Reactive or proactive agent" note="A thermostat that senses and acts. Proactive mode acts on a prediction.">
        <label className="text-sm"><input type="checkbox" checked={pro} onChange={(e) => setPro(e.target.checked)} /> Proactive</label> <button className="btn btn-primary ml-2" onClick={() => th.run("/api/aiml/thermostat", { proactive: pro })}>Run 12 hours</button>
        <Out c={th} />{th.res && <div className="mt-2 space-y-1"><Table head={["Hour", "Temp", "Heater"]} rows={th.res.rows.map((r: R) => [r.hour, r.temp, r.heater ? "on" : "off"])} /><Lesson text={th.res.lesson} /></div>}
      </Section>
      <Section title="Is a task right for RPA?" note="Robotic process automation follows rules through software. It doesn't learn.">
        <div className="grid gap-2 sm:grid-cols-2">{([["rule_based", "Clear rules"], ["digital", "Done in software"], ["repetitive", "Repeats often"], ["structured_input", "Structured inputs"], ["stable_screens", "Screens rarely change"]] as const).map(([x, l]) => <label key={x} className="text-sm"><input type="checkbox" checked={rp[x]} onChange={(e) => setRp({ ...rp, [x]: e.target.checked })} /> {l}</label>)}
          <Field label="Cases per month"><input className="field" inputMode="numeric" value={rp.volume_per_month} onChange={(e) => setRp({ ...rp, volume_per_month: e.target.value })} /></Field><Field label="Minutes per case"><input className="field" inputMode="decimal" value={rp.minutes_each} onChange={(e) => setRp({ ...rp, minutes_each: e.target.value })} /></Field></div>
        <button className="btn btn-primary mt-2" onClick={() => rpa.run("/api/aiml/rpa", { ...rp, volume_per_month: Number(rp.volume_per_month), minutes_each: Number(rp.minutes_each) })}>Check</button>
        <Out c={rpa} />{rpa.res && <div className="mt-2 space-y-1 text-sm"><p><Badge tone={rpa.res.verdict === "good" ? "ok" : rpa.res.verdict === "maybe" ? "warn" : "bad"}>{rpa.res.verdict}</Badge> {rpa.res.advice} Up to {rpa.res.hours_per_month} hours a month of work.</p><Warn items={[rpa.res.caution]} /></div>}
      </Section>
    </div>
  );
}

function Grid({ rows }: { rows: number[][] }) {
  return <pre className="overflow-x-auto rounded border border-line bg-panel2 p-2 text-xs" tabIndex={0}>{rows.map((r) => r.map((v) => String(v).padStart(5)).join("")).join("\n")}</pre>;
}

function Nn({ ref_ }: { ref_: R }) {
  const [w, setW] = useState({ x: "1, 0, 1", w: "5, 3, 2", t: "5", a: "step" });
  const ne = useCall();
  const [layers, setLayers] = useState("3, 4, 1"); const pc = useCall();
  const [ds, setDs] = useState("xor"); const [hid, setHid] = useState("4"); const [act, setAct] = useState("tanh"); const [epochs, setEpochs] = useState("2000"); const [lr, setLr] = useState("0.5");
  const tr = useCall();
  const [img, setImg] = useState("square"); const [ker, setKer] = useState("vertical_edges"); const cv = useCall();
  const nums = (s: string) => s.split(",").map((x) => Number(x.trim())).filter((x) => !Number.isNaN(x));
  return (
    <div className="space-y-3">
      <Section title="One neuron, by hand" note="The course's pizza decision: inputs (saves time, loses weight, saves money) 1, 0, 1 with weights 5, 3, 2 and a threshold of 5.">
        <div className="grid gap-2 sm:grid-cols-4">
          <Field label="Inputs"><input className="field" value={w.x} onChange={(e) => setW({ ...w, x: e.target.value })} /></Field><Field label="Weights"><input className="field" value={w.w} onChange={(e) => setW({ ...w, w: e.target.value })} /></Field>
          <Field label="Threshold"><input className="field" inputMode="decimal" value={w.t} onChange={(e) => setW({ ...w, t: e.target.value })} /></Field>
          <Field label="Activation"><select className="field" value={w.a} onChange={(e) => setW({ ...w, a: e.target.value })}>{ref_.activations.map((a: R) => <Opt key={a.id} v={a.id} l={a.name} />)}</select></Field></div>
        <button className="btn btn-primary mt-2" onClick={() => ne.run("/api/aiml/neuron", { inputs: nums(w.x), weights: nums(w.w), threshold: Number(w.t), activation: w.a })}>Compute</button>
        <Out c={ne} />{ne.res && <div className="mt-2 space-y-1 text-sm"><p>{ne.res.text} {ne.res.decision !== null && <Badge tone={ne.res.decision ? "ok" : "muted"}>{ne.res.decision ? "yes: order it" : "no"}</Badge>}</p><Lesson text={ne.res.lesson} /></div>}
        <ul className="mt-2 list-disc pl-5 text-xs text-muted">{ref_.activations.map((a: R) => <li key={a.id}><b>{a.name}</b>: {a.what}</li>)}</ul>
      </Section>
      <Section title="Count the parameters" note="Layer sizes from input to output, separated by commas.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Layers"><input className="field" value={layers} onChange={(e) => setLayers(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => pc.run("/api/aiml/params", { layers: nums(layers) })}>Count</button></div>
        <Out c={pc} />{pc.res && <div className="mt-2 space-y-1 text-sm"><p>{pc.res.parameters} parameters across {pc.res.layer_count} layers: {pc.res.kind}. {pc.res.deep ? "Counts as deep by the course's rule." : "Not deep by the course's rule."}</p><Table head={["From", "To", "Weights", "Biases"]} rows={pc.res.connections.map((c: R) => [c.from, c.to, c.weights, c.biases])} /><Lesson text={pc.res.note} /></div>}
      </Section>
      <Section title="Train a tiny network" note="Try XOR with no hidden layer (leave hidden blank), then with 4 hidden neurons. One straight line cannot separate XOR.">
        <div className="grid gap-2 sm:grid-cols-5">
          <Field label="Problem"><select className="field" value={ds} onChange={(e) => setDs(e.target.value)}>{ref_.datasets.map((d: R) => <Opt key={d.id} v={d.id} l={d.id.toUpperCase()} />)}</select></Field>
          <Field label="Hidden layers (sizes)"><input className="field" value={hid} placeholder="none" onChange={(e) => setHid(e.target.value)} /></Field>
          <Field label="Hidden activation"><select className="field" value={act} onChange={(e) => setAct(e.target.value)}><Opt v="tanh" /><Opt v="sigmoid" /><Opt v="relu" /></select></Field>
          <Field label="Epochs"><input className="field" inputMode="numeric" value={epochs} onChange={(e) => setEpochs(e.target.value)} /></Field>
          <Field label="Learning rate"><input className="field" inputMode="decimal" value={lr} onChange={(e) => setLr(e.target.value)} /></Field></div>
        <button className="btn btn-primary mt-2" onClick={() => tr.run("/api/aiml/train", { dataset: ds, hidden: nums(hid), activation: act, epochs: Number(epochs), lr: Number(lr) })}>Train</button>
        <Out c={tr} />
        {tr.res && <div className="mt-2 space-y-2"><div className="grid gap-2 sm:grid-cols-3"><Stat label="Accuracy" value={`${Math.round(tr.res.accuracy * 100)}%`} /><Stat label="Final loss" value={String(tr.res.final_loss)} sub={`first loss ${tr.res.first_step.loss}`} /><Stat label="Parameters" value={String(tr.res.parameters)} sub={tr.res.layers.join(" - ")} /></div>
          <p className="text-sm">{tr.res.message}</p>
          <Table head={["Input", "Expected", "Output", "Right"]} rows={tr.res.predictions.map((p: R) => [p.input.join(", "), p.expected, p.output, p.right ? <Badge key="r" tone="ok">yes</Badge> : <Badge key="r" tone="bad">no</Badge>])} />
          <Table head={["Epoch", "Loss"]} rows={tr.res.loss_curve.filter((_: R, i: number) => i % 4 === 0).map((c: R) => [c.epoch, c.loss])} caption="Loss over training" />
          <Lesson text={tr.res.lesson} /></div>}
      </Section>
      <Section title="Convolution: how a CNN sees an image" note="A kernel slides over the picture. A real network learns its kernels.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Image"><select className="field" value={img} onChange={(e) => setImg(e.target.value)}>{ref_.images.map((d: R) => <Opt key={d.id} v={d.id} />)}</select></Field>
          <Field label="Kernel"><select className="field" value={ker} onChange={(e) => setKer(e.target.value)}>{ref_.kernels.map((d: R) => <Opt key={d.id} v={d.id} />)}</select></Field>
          <button className="btn btn-primary" onClick={() => cv.run("/api/aiml/convolve", { image: img, kernel: ker })}>Apply</button></div>
        <Out c={cv} />{cv.res && <div className="mt-2 grid gap-2 sm:grid-cols-3"><div><b className="text-xs">Image</b><Grid rows={cv.res.image} /></div><div><b className="text-xs">Kernel</b><Grid rows={cv.res.kernel} /><p className="text-xs text-muted">{cv.res.kernel_note}</p></div><div><b className="text-xs">Result</b><Grid rows={cv.res.output} /></div><div className="sm:col-span-3"><Lesson text={cv.res.lesson} /></div></div>}
      </Section>
      <Section title="Kinds of neural network"><Table head={["Type", "What it is"]} rows={ref_.types.map((t: R) => [t.name, t.what])} /></Section>
    </div>
  );
}

function Nlp({ ref_ }: { ref_: R }) {
  const [text, setText] = useState("Ralph flew to Arizona on 2026-10-11 and paid $2,500 to Acme Inc. The make of his laptop was not good, but support was very helpful.");
  const [tool, setTool] = useState("tokens");
  const c = useCall();
  const [phrase, setPhrase] = useState("Add eggs and milk to my shopping list");
  const u = useCall();
  const [ex, setEx] = useState<string>(ref_.example_classifier.map((e: R) => `${e.label} | ${e.text}`).join("\n"));
  const [tests, setTests] = useState("love it so fast\nbroken and slow\nxyzzy");
  const cl = useCall();
  const TOOLS: Record<string, string> = { tokens: "Tokens", stems: "Stem vs lemma", pos: "Part of speech", entities: "Entities", sentiment: "Sentiment", spam: "Spam cues" };
  const goCls = () => cl.run("/api/aiml/nlp/classify", { examples: lines(ex).map((l) => { const [label, ...t] = l.split("|"); return { label: (label ?? "").trim(), text: t.join("|").trim() }; }), tests: lines(tests) });
  return (
    <div className="space-y-3">
      <Section title="The steps of NLP" note="Run each step on the same text.">
        <textarea className="field w-full" rows={3} aria-label="Text" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Step"><select className="field" value={tool} onChange={(e) => { setTool(e.target.value); }}>{Object.entries(TOOLS).map(([k, v]) => <Opt key={k} v={k} l={v} />)}</select></Field><button className="btn btn-primary" onClick={() => c.run(`/api/aiml/nlp/${tool}`, { text })}>Run</button></div>
        <Out c={c} />
        {c.res && <div className="mt-2 space-y-2">
          {c.res.tokens && <div className="flex flex-wrap items-center gap-1 text-sm"><b>{c.res.count}</b> tokens: {c.res.tokens.map((t: string, i: number) => <code key={i} className="rounded bg-panel2 px-1">{t}</code>)}</div>}
          {c.res.rows && <Table head={["Word", "Stem", "Lemma"]} rows={c.res.rows.map((r: R) => [r.word, r.stem, r.lemma])} />}
          {c.res.tags && <div className="flex flex-wrap gap-2 text-sm">{c.res.tags.map((t: R, i: number) => <span key={i}><code>{t.token}</code> <Badge>{t.tag}</Badge></span>)}</div>}
          {c.res.entities && (c.res.entities.length ? <Table head={["Text", "Type"]} rows={c.res.entities.map((e: R) => [e.text, e.label])} /> : <p className="text-sm text-muted">No entities found.</p>)}
          {c.res.label && c.res.contributions && <div className="text-sm"><p>Sentiment: <Badge tone={c.res.label === "positive" ? "ok" : c.res.label === "negative" ? "bad" : "muted"}>{c.res.label}</Badge> (score {c.res.score})</p><p className="text-xs text-muted">{c.res.contributions.map((x: R) => `${x.word} ${x.score}${x.note ? ` (${x.note})` : ""}`).join(", ")}</p></div>}
          {c.res.verdict && <div className="text-sm"><p>Spam check: <Badge tone={c.res.verdict === "likely spam" ? "bad" : c.res.verdict === "suspicious" ? "warn" : "ok"}>{c.res.verdict}</Badge> score {c.res.score}</p><ul className="list-disc pl-5 text-xs">{c.res.reasons.map((r: R, i: number) => <li key={i}>{r.cue}{r.found?.length ? `: ${r.found.join(", ")}` : ""}</li>)}</ul></div>}
          <Lesson text={c.res.lesson} />{c.res.caution && <Warn items={[c.res.caution]} />}</div>}
      </Section>
      <Section title="From words to structure (NLU) and back (NLG)" note="Try: add eggs and milk to my shopping list; order a dozen yellow roses; what time do you open?; what is my balance?">
        <div className="flex flex-wrap items-end gap-2"><Field label="Say something"><input className="field w-72 max-w-full" value={phrase} onChange={(e) => setPhrase(e.target.value)} /></Field><button className="btn btn-primary" onClick={() => u.run("/api/aiml/nlp/understand", { text: phrase })}>Understand</button></div>
        <Out c={u} />{u.res && <div className="mt-2 space-y-1 text-sm">{u.res.intent ? <><Code>{JSON.stringify(u.res.structured, null, 2)}</Code><p>Reply generated: {u.res.reply}</p></> : <p>{u.res.message}</p>}<Lesson text={u.res.lesson} /></div>}
      </Section>
      <Section title="Train your own text classifier" note="One example per line as label | text. Add a few of each label. Then type texts to classify, one per line.">
        <div className="grid gap-2 sm:grid-cols-2"><textarea className="field font-mono text-xs" rows={7} aria-label="Examples" value={ex} onChange={(e) => setEx(e.target.value)} /><textarea className="field font-mono text-xs" rows={7} aria-label="Texts to classify" value={tests} onChange={(e) => setTests(e.target.value)} /></div>
        <button className="btn btn-primary mt-2" onClick={goCls}>Train and classify</button>
        <Out c={cl} />{cl.res && <div className="mt-2 space-y-2"><Table head={["Text", "Label", "Confidence", "Note"]} rows={cl.res.predictions.map((p: R) => [p.text, p.label, p.confidence, p.warning ?? ""])} />
          <p className="text-xs">Leave-one-out accuracy on your examples: {cl.res.leave_one_out_accuracy ?? "needs 6+ examples"}. Top words: {Object.entries(cl.res.top_words as R).map(([k, v]) => `${k}: ${(v as string[]).join(", ")}`).join(" | ")}</p><Lesson text={cl.res.lesson} /><Warn items={[cl.res.caution]} /></div>}
      </Section>
    </div>
  );
}

function Bot({ ref_ }: { ref_: R }) {
  const [intents, setIntents] = useState<R[]>(ref_.example_intents);
  const [msg, setMsg] = useState("what time do you open on friday");
  const [thr, setThr] = useState("0.25");
  const bot = useCall();
  const [docs, setDocs] = useState<string>(ref_.example_docs.join("\n\n"));
  const [q, setQ] = useState("which planet has the most moons");
  const rg = useCall();
  const setI = (i: number, f: (x: R) => R) => setIntents(intents.map((x, j) => (j === i ? f(x) : x)));
  return (
    <div className="space-y-3">
      <Section title="Intent chatbot" note="Each intent has example phrases and a reply. A message that matches nothing well is handed to a person.">
        <div className="space-y-2">{intents.map((it, i) => (
          <div key={i} className="rounded border border-line p-2"><div className="grid gap-2 sm:grid-cols-3"><Field label="Intent"><input className="field" value={it.name} onChange={(e) => setI(i, (x) => ({ ...x, name: e.target.value }))} /></Field>
            <Field label="Example phrases (one per line)"><textarea className="field text-xs" rows={3} value={it.examples.join("\n")} onChange={(e) => setI(i, (x) => ({ ...x, examples: lines(e.target.value) }))} /></Field>
            <Field label="Reply"><textarea className="field text-xs" rows={3} value={it.reply} onChange={(e) => setI(i, (x) => ({ ...x, reply: e.target.value }))} /></Field></div>
            <button className="btn mt-1" onClick={() => setIntents(intents.filter((_, j) => j !== i))}>Remove intent</button></div>))}</div>
        <button className="btn mt-2" onClick={() => setIntents([...intents, { name: "", examples: [], reply: "" }])}>Add intent</button>
        <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Customer says"><input className="field w-72 max-w-full" value={msg} onChange={(e) => setMsg(e.target.value)} /></Field><Field label="Hand-over below"><input className="field w-24" inputMode="decimal" value={thr} onChange={(e) => setThr(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => bot.run("/api/aiml/nlp/chatbot", { intents, utterance: msg, threshold: Number(thr) })}>Send</button></div>
        <Out c={bot} />{bot.res && <div className="mt-2 space-y-1 text-sm"><p>{bot.res.handed_over ? <Badge tone="warn">handed to a person</Badge> : <Badge tone="ok">{bot.res.matched}</Badge>} best match score {bot.res.score}</p><p>Bot: {bot.res.reply}</p><Table head={["Intent", "Score"]} rows={bot.res.ranking.map((r: R) => [r.intent, r.score])} /><Lesson text={bot.res.lesson} /><Warn items={[bot.res.caution]} /></div>}
        <ol className="mt-2 list-decimal pl-5 text-xs text-muted">{ref_.chatbot_flow.map((s: string) => <li key={s}>{s}</li>)}</ol>
      </Section>
      <Section title="Retrieval-augmented generation (RAG)" note="Paste your own passages (blank line between them). Ask something they answer, then something they don't.">
        <textarea className="field w-full text-xs" rows={6} aria-label="Passages" value={docs} onChange={(e) => setDocs(e.target.value)} />
        <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Question"><input className="field w-72 max-w-full" value={q} onChange={(e) => setQ(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => rg.run("/api/aiml/nlp/rag", { docs: docs.split(/\n\s*\n/).map((d) => d.trim()).filter(Boolean), question: q })}>Retrieve</button></div>
        <Out c={rg} />{rg.res && <div className="mt-2 space-y-2"><p className="text-sm">{rg.res.grounded ? <Badge tone="ok">answer found in your passages</Badge> : <Badge tone="warn">no source: say &ldquo;I don&rsquo;t know&rdquo;</Badge>} {rg.res.advice}</p>
          <Table head={["#", "Score", "Passage"]} rows={rg.res.retrieved.map((h: R) => [h.rank, h.score, h.passage])} /><p className="text-xs font-semibold">Prompt that would go to the model</p><Code>{rg.res.prompt}</Code><Lesson text={rg.res.lesson} /><Warn items={[rg.res.caution]} /></div>}
      </Section>
    </div>
  );
}

function Reference({ ref_ }: { ref_: R }) {
  const f = ref_.foundation;
  return (
    <div className="space-y-3">
      <Section title="Corrections to the source course"><Warn items={ref_.slips} /></Section>
      <Section title="What can't be built here"><Warn items={[...ref_.not_built, ...ref_.nn.not_built, ...ref_.nlp.not_built]} /></Section>
      <Section title="Generative models"><Table head={["Model", "How it works", "Used for"]} rows={ref_.generative_models.map((g: R) => [g.name, g.how, g.uses])} />
        <p className="mt-2 text-xs"><b>Unimodal</b>: {ref_.modality.unimodal} <b>Multimodal</b>: {ref_.modality.multimodal}</p></Section>
      <Section title="Foundation models"><div className="grid gap-2 sm:grid-cols-2"><div><b className="text-sm">Strengths</b><ul className="list-disc pl-5 text-xs">{f.pros.map((x: string) => <li key={x}>{x}</li>)}</ul></div><div><b className="text-sm">Costs and risks</b><ul className="list-disc pl-5 text-xs">{f.cons.map((x: string) => <li key={x}>{x}</li>)}</ul></div></div>
        <Table head={["Way to adapt", "What it is"]} rows={f.adapt.map((a: R) => [a.name, a.what])} /></Section>
      <Section title="Old and new AI architecture"><div className="grid gap-2 sm:grid-cols-2"><div><b className="text-sm">Traditional</b><ol className="list-decimal pl-5 text-xs">{ref_.architecture.traditional.map((x: string) => <li key={x}>{x}</li>)}</ol></div><div><b className="text-sm">Generative</b><ol className="list-decimal pl-5 text-xs">{ref_.architecture.generative.map((x: string) => <li key={x}>{x}</li>)}</ol></div></div><Lesson text={ref_.architecture.note} /></Section>
      <Section title="Agents, robots and automation"><Table head={["Characteristic", "Meaning"]} rows={ref_.agents.characteristics.map((a: R) => [a.name, a.what])} />
        <p className="mt-2 text-xs"><b>Loop:</b> {ref_.agents.loop.join(" → ")}</p><p className="text-xs"><b>Multi-agent:</b> {ref_.agents.multi_agent}</p>
        <Table head={["Robot part", "Does"]} rows={ref_.agents.robot_parts.map((a: R) => [a.part, a.does])} /><p className="text-xs">{ref_.agents.cobots} {ref_.agents.rpa}</p></Section>
      <Section title="Cognitive computing, edge and IoT"><p className="text-xs">{ref_.cognitive.what} Steps: {ref_.cognitive.steps.join(" → ")}. Elements: {ref_.cognitive.elements.join(", ")}.</p><Table head={["Term", "Meaning"]} rows={ref_.edge.map((e: R) => [e.term, e.what])} /></Section>
      <Section title="Speech and vision"><Table head={["Speech", "How"]} rows={ref_.nlp.speech.map((e: R) => [e.name, e.what])} /><div className="mt-2" /><Table head={["Vision task", "What"]} rows={ref_.nlp.vision.map((e: R) => [e.name, e.what])} /></Section>
      <Section title="Where AI is used"><Table head={["Area", "Examples"]} rows={ref_.uses.map((u: R) => [u.area, u.examples])} /></Section>
      <Section title="History"><Table head={["When", "What"]} rows={ref_.history.map((h: R) => [h.when, h.what])} /></Section>
      <Section title="AI-related roles"><Table head={["Role", "Does"]} rows={ref_.jobs.map((j: R) => [j.role, j.does])} /></Section>
    </div>
  );
}
