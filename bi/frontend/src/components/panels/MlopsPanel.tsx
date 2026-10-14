"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "release", label: "Release a model" }, { id: "rollout", label: "Rollout and load" }, { id: "watch", label: "Watch and retrain" }, { id: "llm", label: "LLM approach" }, { id: "feedback", label: "Feedback" }, { id: "ref", label: "Reference" }];
const Num = ({ label, v, set }: { label: string; v: string; set: (s: string) => void }) => <Field label={label}><input className="field" inputMode="decimal" value={v} onChange={(e) => set(e.target.value)} /></Field>;

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body?: unknown, method: "post" | "get" = "post") => {
    setErr(null);
    (method === "get" ? getJson<T>(path) : postJson<T>(path, body)).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That didn't work.")); });
  };
  return { res, err, run };
}
const Out = ({ c }: { c: { err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);

export function MlopsPanel() {
  const [ref, setRef] = useState<R | null>(null);
  const [models, setModels] = useState<R[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("release");
  const load = () => {
    getJson<R>("/api/mlops").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the MLOps lab.")));
    getJson<R>("/api/models").then((r) => setModels(r.models || [])).catch(() => setModels([]));
  };
  useEffect(load, []);
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading MLOps lab…</p>;
  const names = Array.from(new Set(models.map((m) => m.name)));
  return (
    <section className="card space-y-4 p-4" aria-label="MLOps lab">
      <h2 className="text-base font-semibold">MLOps lab: keep a model working after you train it</h2>
      <Lesson text="MLOps = data operations + software operations + model operations. Train a model in the ML Lab and register it under Models, then use these tools to gate it, compare it with the live one, rehearse a rollout, load test it and decide when to retrain." />
      {names.length === 0 && tab !== "llm" && tab !== "feedback" && tab !== "ref" && tab !== "rollout" && <p className="text-sm text-muted">No registered models yet. Train one in the ML Lab (Models section) and it will show up here.</p>}
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="MLOps lab" />
      {tab === "release" && <Release names={names} models={models} aliases={ref.aliases} reload={load} />}
      {tab === "rollout" && <Rollout names={names} />}
      {tab === "watch" && <Watch names={names} />}
      {tab === "llm" && <LlmApproach ref_={ref} />}
      {tab === "feedback" && <Feedback ref_={ref} />}
      {tab === "ref" && <Reference ref_={ref} />}
    </section>
  );
}

function ModelPick({ names, value, set }: { names: string[]; value: string; set: (s: string) => void }) {
  return <Field label="Model"><select className="field" value={value} onChange={(e) => set(e.target.value)}><option value="">Choose…</option>{names.map((n) => <option key={n}>{n}</option>)}</select></Field>;
}

function Release({ names, models, aliases, reload }: { names: string[]; models: R[]; aliases: R; reload: () => void }) {
  const [name, setName] = useState(""); const [ver, setVer] = useState(""); const [gain, setGain] = useState("0.02"); const [ok, setOk] = useState(false);
  const g = useCall(); const c = useCall(); const p = useCall();
  const versions = models.filter((m) => m.name === name);
  const al = aliases[name] || {};
  return (
    <div className="space-y-3">
      <Section title="1. Gate: may this version challenge the live one?" note="Automatic checks before a new version is allowed near production.">
        <div className="grid gap-2 sm:grid-cols-3">
          <ModelPick names={names} value={name} set={(n) => { setName(n); setVer(""); }} />
          <Field label="Version"><select className="field" value={ver} onChange={(e) => setVer(e.target.value)}><option value="">Choose…</option>{versions.map((m) => <option key={m.version} value={m.version}>v{m.version} ({m.stage})</option>)}</select></Field>
          <Num label="Must beat baseline by" v={gain} set={setGain} />
        </div>
        <button className="btn btn-primary mt-2" disabled={!name || !ver} onClick={() => { g.run("/api/mlops/gate", { name, version: Number(ver), min_gain: Number(gain) }); reload(); }}>Run the gate</button>
        <Out c={g} />
        {g.res && <div className="mt-2 space-y-2">
          <p>{g.res.passed ? <Badge tone="ok">passed</Badge> : <Badge tone="bad">failed</Badge>} {g.res.next}</p>
          <Table head={["Check", "Result", "Detail"]} rows={g.res.checks.map((x: R) => [x.label, x.ok ? <Badge key="a" tone="ok">pass</Badge> : <Badge key="b" tone={x.level === "warn" ? "warn" : "bad"}>{x.level === "warn" ? "warning" : "fail"}</Badge>, x.detail])} />
          <Lesson text={g.res.lesson} /><Warn items={[g.res.limit]} />
        </div>}
      </Section>
      <Section title="2. Champion and challenger" note="The champion answers predictions. A version that passes the gate becomes the challenger.">
        <p className="text-sm">{name ? <>Aliases for <b>{name}</b>: champion {al.champion ? `v${al.champion}` : "none yet"}, challenger {al.challenger ? `v${al.challenger}` : "none yet"}.</> : "Choose a model above."}</p>
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <button className="btn" disabled={!name} onClick={() => c.run(`/api/mlops/compare?name=${encodeURIComponent(name)}&min_gain=0.01`, undefined, "get")}>Compare</button>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> I understand this changes which model answers predictions</label>
          <button className="btn btn-primary" disabled={!name || !ok} onClick={() => { p.run("/api/mlops/promote", { name, confirm: ok }); reload(); }}>Promote challenger</button>
        </div>
        <Out c={c} /><Out c={p} />
        {c.res && <div className="mt-2 space-y-1 text-sm"><p>{c.res.decision === "promote" ? <Badge tone="ok">promote</Badge> : <Badge tone="warn">hold</Badge>} {c.res.reason}</p><Warn items={[c.res.limit]} /></div>}
        {p.res && <p className="mt-2 text-sm"><Badge tone="ok">done</Badge> v{p.res.champion} is now the champion. {p.res.rollback}</p>}
      </Section>
    </div>
  );
}

function Rollout({ names }: { names: string[] }) {
  const [name, setName] = useState(""); const [rows, setRows] = useState("40");
  const [req, setReq] = useState("1000"); const [pct, setPct] = useState("10");
  const [steps, setSteps] = useState("5, 25, 50, 100"); const [minReq, setMinReq] = useState("500"); const [err_, setErr_] = useState("1"); const [drop, setDrop] = useState("3");
  const [lr, setLr] = useState("60"); const [rpr, setRpr] = useState("1"); const [p95, setP95] = useState("250");
  const sh = useCall(); const sp = useCall(); const ro = useCall(); const ld = useCall();
  return (
    <div className="space-y-3">
      <Section title="Shadow run" note="Both models score the same made-up rows. Only the champion would be used.">
        <div className="grid gap-2 sm:grid-cols-2"><ModelPick names={names} value={name} set={setName} /><Num label="Rows" v={rows} set={setRows} /></div>
        <button className="btn btn-primary mt-2" disabled={!name} onClick={() => sh.run("/api/mlops/shadow", { name, rows: Number(rows) })}>Run shadow comparison</button>
        <Out c={sh} />
        {sh.res && <div className="mt-2 space-y-2"><div className="grid gap-2 sm:grid-cols-3">
          {sh.res.kind === "classification" ? <><Stat label="Disagree" value={`${sh.res.disagree_pct}%`} sub={`${sh.res.disagree} of ${sh.res.rows} rows`} /><Stat label="Mean probability gap" value={String(sh.res.mean_probability_gap)} /></> : <><Stat label="Mean gap" value={String(sh.res.mean_abs_gap)} sub={`${sh.res.mean_gap_pct}% of the champion's size`} /><Stat label="Correlation" value={String(sh.res.correlation ?? "—")} /></>}
          <Stat label="Champion / challenger" value={`v${sh.res.champion} / v${sh.res.challenger}`} /></div><p className="text-sm">{sh.res.reading}</p><Warn items={[sh.res.limit]} /></div>}
      </Section>
      <Section title="Traffic split" note="How a canary or A/B split behaves. The same id always lands on the same model.">
        <div className="grid gap-2 sm:grid-cols-2"><Num label="Requests" v={req} set={setReq} /><Num label="Challenger share (%)" v={pct} set={setPct} /></div>
        <button className="btn mt-2" onClick={() => sp.run("/api/mlops/split", { requests: Number(req), challenger_pct: Number(pct) })}>Simulate</button>
        <Out c={sp} />
        {sp.res && <div className="mt-2 space-y-1"><div className="grid gap-2 sm:grid-cols-3"><Stat label="Challenger got" value={String(sp.res.challenger_requests)} sub={`${sp.res.observed_pct}% (aimed for ${sp.res.target_pct}%)`} /><Stat label="Champion got" value={String(sp.res.champion_requests)} /><Stat label="Normal wobble" value={`${sp.res.expected_range_pct[0]}–${sp.res.expected_range_pct[1]}%`} /></div><Lesson text={sp.res.lesson} /></div>}
      </Section>
      <Section title="Gradual rollout plan" note="Write the advance and rollback rules before the first step.">
        <div className="grid gap-2 sm:grid-cols-4"><Field label="Traffic steps (%)"><input className="field" value={steps} onChange={(e) => setSteps(e.target.value)} /></Field><Num label="Requests per step" v={minReq} set={setMinReq} /><Num label="Max errors (%)" v={err_} set={setErr_} /><Num label="Max quality drop (%)" v={drop} set={setDrop} /></div>
        <button className="btn mt-2" onClick={() => ro.run("/api/mlops/rollout", { steps_pct: steps.split(",").map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n)), min_requests_per_step: Number(minReq), max_error_pct: Number(err_), max_metric_drop_pct: Number(drop) })}>Make the plan</button>
        <Out c={ro} />
        {ro.res && <div className="mt-2 space-y-2"><Table head={["Step", "Challenger share", "Needs", "Advance when", "Roll back when"]} rows={ro.res.steps.map((s: R) => [s.step, `${s.challenger_pct}%`, `${s.challenger_requests_needed} requests`, s.advance_when, s.roll_back_when])} /><Table head={["Pattern", "Serves users?", "Use it"]} rows={ro.res.compare.map((c: R) => [c.pattern, c.serves_users ? "yes" : "no", c.use])} /><Lesson text={ro.res.lesson} /><Warn items={[ro.res.limit]} /></div>}
      </Section>
      <Section title="Load test" note="Latency percentiles and errors against a target you set.">
        <div className="grid gap-2 sm:grid-cols-4"><ModelPick names={names} value={name} set={setName} /><Num label="Requests (max 200)" v={lr} set={setLr} /><Num label="Rows per request" v={rpr} set={setRpr} /><Num label="p95 target (ms)" v={p95} set={setP95} /></div>
        <button className="btn btn-primary mt-2" disabled={!name} onClick={() => ld.run("/api/mlops/load", { name, requests: Number(lr), rows_per_request: Number(rpr), p95_ms: Number(p95) })}>Run load test</button>
        <Out c={ld} />
        {ld.res && <div className="mt-2 space-y-2"><p>{ld.res.verdict === "meets the target" ? <Badge tone="ok">meets the target</Badge> : <Badge tone="bad">misses the target</Badge>} {ld.res.requests_done} requests{ld.res.stopped_early ? " (stopped early to stay within the time budget)" : ""}.</p>
          <div className="grid gap-2 sm:grid-cols-4"><Stat label="p50" value={`${ld.res.p50_ms} ms`} /><Stat label="p95" value={`${ld.res.p95_ms} ms`} sub={`target ${ld.res.target.p95_ms} ms`} /><Stat label="p99" value={`${ld.res.p99_ms} ms`} /><Stat label="Throughput" value={`${ld.res.throughput_qps}/s`} sub={`${ld.res.error_pct}% errors`} /></div>
          <Lesson text={ld.res.lesson} /><Warn items={[ld.res.limit]} /></div>}
      </Section>
    </div>
  );
}

function Watch({ names }: { names: string[] }) {
  const [name, setName] = useState(""); const r = useCall();
  return (
    <Section title="Should this model be retrained?" note="Reads the saved drift checks of the model in production.">
      <div className="grid gap-2 sm:grid-cols-2"><ModelPick names={names} value={name} set={setName} /></div>
      <button className="btn btn-primary mt-2" disabled={!name} onClick={() => r.run(`/api/mlops/retrain?name=${encodeURIComponent(name)}`, undefined, "get")}>Get advice</button>
      <Out c={r} />
      {r.res && <div className="mt-2 space-y-2">
        <p><Badge tone={r.res.status === "investigate" ? "bad" : r.res.status === "watch" ? "warn" : "ok"}>{r.res.status}</Badge> {r.res.why}</p>
        <ul className="list-disc pl-5 text-sm">{r.res.steps.map((s: string) => <li key={s}>{s}</li>)}</ul>
        {r.res.recent.length > 0 && <Table head={["When", "Overall", "Most-moved input", "PSI"]} rows={r.res.recent.map((x: R) => [x.at, x.overall, x.worst, x.psi])} />}
        <Table head={["Retrain policy", "When", "Note"]} rows={r.res.policy.map((p: R) => [p.option, p.when, p.note])} />
        <Warn items={[r.res.limit]} />
      </div>}
    </Section>
  );
}

function LlmApproach({ ref_ }: { ref_: R }) {
  const [a, setA] = useState<R>({}); const [ex, setEx] = useState("0"); const [vol, setVol] = useState("100"); const [tok, setTok] = useState("0");
  const r = useCall();
  const qs: R[] = ref_.approach_questions;
  return (
    <Section title="Prompt, retrieval, fine-tune or pre-train?" note="Answer what is true for your project. The rule: start with the simplest approach and add a layer only when measurements say so.">
      <div className="grid gap-1 sm:grid-cols-2">{qs.map((q) => <label key={q.id} className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={!!a[q.id]} onChange={(e) => setA({ ...a, [q.id]: e.target.checked })} />{q.label}</label>)}</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3"><Num label="Labelled examples you have" v={ex} set={setEx} /><Num label="Requests per day" v={vol} set={setVol} /><Num label="Your text corpus (tokens)" v={tok} set={setTok} /></div>
      <button className="btn btn-primary mt-2" onClick={() => r.run("/api/mlops/llm-plan", { answers: { ...a, labeled_examples: Number(ex), requests_per_day: Number(vol), corpus_tokens: Number(tok) } })}>Suggest a plan</button>
      <Out c={r} />
      {r.res && <div className="mt-2 space-y-2">
        <Table head={["Layer", "Why", "Built in this app"]} rows={r.res.stack.map((s: R) => [s.step, s.why, s.builds_here])} />
        <p className="text-sm"><b>Where it runs:</b> {r.res.hosting.choice}. {r.res.hosting.reasons.join(" ")}</p>
        <p className="text-sm"><b>Retrieval store:</b> {r.res.retrieval_store.choice}. {r.res.retrieval_store.why}</p>
        <div className="grid gap-2 sm:grid-cols-2"><div><h4 className="text-sm font-semibold">Ways to cut cost</h4><ul className="list-disc pl-5 text-sm">{r.res.cost_levers.map((x: string) => <li key={x}>{x}</li>)}</ul></div><div><h4 className="text-sm font-semibold">How to evaluate</h4><ul className="list-disc pl-5 text-sm">{r.res.evaluation.map((x: string) => <li key={x}>{x}</li>)}</ul></div></div>
        <Lesson text={r.res.rule} /><Warn items={[r.res.limit]} />
      </div>}
    </Section>
  );
}

function Feedback({ ref_ }: { ref_: R }) {
  const [kind, setKind] = useState("thumbs_up"); const [prompt, setPrompt] = useState(""); const [ver, setVer] = useState(""); const [note, setNote] = useState("");
  const [sum, setSum] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  const load = () => getJson<R>("/api/mlops/feedback").then(setSum).catch((e) => setErr(errMsg(e, "Couldn't load feedback.")));
  useEffect(() => { load(); }, []);
  const add = () => { setErr(null); postJson("/api/mlops/feedback", { kind, prompt, version: ver ? Number(ver) : null, note }).then(() => { setNote(""); load(); }).catch((e) => setErr(errMsg(e, "Couldn't save that."))); };
  const clear = () => { setErr(null); deleteJson("/api/mlops/feedback").then(load).catch((e) => setErr(errMsg(e, "Couldn't clear."))); };
  return (
    <Section title="Human feedback log" note="Thumbs and 'asked for a human' signals, grouped by prompt version. For LLM apps, user feedback is the real test.">
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Signal"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>{ref_.feedback_kinds.map((k: string) => <option key={k}>{k}</option>)}</select></Field>
        <Field label="Prompt name"><input className="field" value={prompt} maxLength={50} onChange={(e) => setPrompt(e.target.value)} /></Field>
        <Num label="Prompt version" v={ver} set={setVer} />
        <Field label="Note (no personal details)"><input className="field" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} /></Field>
      </div>
      <div className="mt-2 flex gap-2"><button className="btn btn-primary" onClick={add}>Add</button><button className="btn" onClick={clear}>Clear log</button></div>
      {err && <ErrorBanner message={err} />}
      {sum && <div className="mt-2 space-y-2">
        <p className="text-sm text-muted">{sum.total} signal(s) kept (latest 500).</p>
        {sum.groups.length > 0 && <Table head={["Prompt", "Signals", "Good", "Bad", "Helpful", ""]} rows={sum.groups.map((g: R) => [g.prompt, g.n, g.good, g.bad, `${g.helpful_pct}%`, g.note])} />}
        <Lesson text={sum.lesson} /><Warn items={[sum.limit]} />
      </div>}
    </Section>
  );
}

function Reference({ ref_ }: { ref_: R }) {
  return (
    <div className="space-y-3">
      <Section title="Words to know"><Table head={["Term", "Meaning"]} rows={ref_.hierarchy.map((h: R) => [h.term, h.meaning])} /></Section>
      <Section title="Three environments"><Table head={["Environment", "Data", "Code", "Goal"]} rows={ref_.environments.map((e: R) => [e.env, e.data, e.code, e.goal])} /></Section>
      <Section title="From idea to production"><ol className="list-decimal space-y-1 pl-5 text-sm">{ref_.pipeline.map((s: string) => <li key={s}>{s}</li>)}</ol></Section>
      <Section title="Tests before a real-time deploy"><Table head={["Test", "Checks", "When"]} rows={ref_.testing.map((t: R) => [t.test, t.checks, t.when])} /></Section>
      <Section title="What changes with LLMs"><Table head={["Change", "What it means for operations"]} rows={ref_.llm_changes.map((c: R) => [c.change, c.means])} /></Section>
      <Section title="Naming"><p className="text-sm">Book: {ref_.naming.book}</p><p className="text-sm">Here: {ref_.naming.here}</p><p className="text-sm text-muted">{ref_.naming.tip}</p></Section>
      <Section title="Slips and caveats in the source"><Warn items={ref_.slips} /></Section>
      <Section title="Not built here, and why"><Table head={["Item", "Why"]} rows={ref_.not_built.map((n: R) => [n.item, n.why])} /></Section>
    </div>
  );
}
