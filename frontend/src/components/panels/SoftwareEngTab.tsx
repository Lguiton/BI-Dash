"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

type Rec = Record<string, string>;
interface Ref {
  note: string; phases: { phase: string; does: string; output: string }[]; methods: { name: string; what: string; good: string; bad: string }[];
  test_levels: { level: string; tests: string; who: string; when: string }[]; test_types: { type: string; checks: string }[]; docs: { doc: string; what: string }[];
  tools: { group: string; items: string }[]; library_vs_framework: { library: string; framework: string; note: string }; stacks: { name: string; parts: string; note: string }[];
  languages: { kind: string; examples: string; how: string }[]; environments: { env: string; for: string; data: string }[]; hosting: { name: string; what: string }[];
  production: { part: string; does: string }[]; concepts: { term: string; what: string }[]; architecture: { name: string; what: string }[]; uml: { diagram: string; shows: string }[];
  slips: string[]; not_built: string[]; example_pseudocode: string;
  example_states: { states: string[]; start: string; finals: string[]; transitions: { from: string; event: string; to: string }[] };
  example_classes: { name: string; parent?: string; attributes?: string[]; methods?: string[] }[];
}
interface Ranked { ranking: { method?: string; pattern?: string; score: number; reasons: string[] }[]; pick: string; caution: string }
const TABS = [{ id: "process", label: "Process" }, { id: "req", label: "Requirements" }, { id: "ver", label: "Versions" }, { id: "test", label: "Testing" }, { id: "arch", label: "Architecture" }, { id: "flow", label: "Pseudocode" }, { id: "ref", label: "Reference" }];
const Code = ({ children }: { children: string }) => <pre className="max-h-72 overflow-auto rounded border border-line bg-panel2 p-2 text-xs" tabIndex={0}><code>{children}</code></pre>;
const Opt = ({ v, l }: { v: string; l?: string }) => <option value={v}>{l ?? v}</option>;
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export function SoftwareEngTab() {
  const [ref, setRef] = useState<Ref | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("process");
  useEffect(() => { getJson<Ref>("/api/se").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the lab."))); }, []);
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <Lesson text={ref.note} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Software engineering" />
      {tab === "process" && <Process ref_={ref} />}
      {tab === "req" && <Requirements />}
      {tab === "ver" && <Versions />}
      {tab === "test" && <Testing ref_={ref} />}
      {tab === "arch" && <Architecture ref_={ref} />}
      {tab === "flow" && <Flow ref_={ref} />}
      {tab === "ref" && <Reference ref_={ref} />}
    </div>
  );
}

function useCall<T>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body: unknown) => { setErr(null); postJson<T>(path, body).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Check your input.")); }); };
  return { res, err, run };
}

function Process({ ref_ }: { ref_: Ref }) {
  const [f, setF] = useState({ req_change: "medium", customer_access: "sometimes", regulated: false, fixed_contract: false, cadence: "months", team_size: "small" });
  const c = useCall<Ranked>();
  return (
    <div className="space-y-3">
      <Section title="The six phases" note="Every method uses these; they differ in how they order and repeat them.">
        <Table head={["Phase", "What happens", "Output"]} rows={ref_.phases.map((p) => [p.phase, p.does, p.output])} />
      </Section>
      <Section title="Which method fits?" note="Answer about the project and see the reasons behind each score.">
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="Will requirements change?"><select className="field" value={f.req_change} onChange={(e) => setF({ ...f, req_change: e.target.value })}><Opt v="low" /><Opt v="medium" /><Opt v="high" /></select></Field>
          <Field label="Customer available to give feedback?"><select className="field" value={f.customer_access} onChange={(e) => setF({ ...f, customer_access: e.target.value })}><Opt v="rare" /><Opt v="sometimes" /><Opt v="often" /></select></Field>
          <Field label="Release cadence"><select className="field" value={f.cadence} onChange={(e) => setF({ ...f, cadence: e.target.value })}><Opt v="years" /><Opt v="months" /><Opt v="weeks" /></select></Field>
          <Field label="Team size"><select className="field" value={f.team_size} onChange={(e) => setF({ ...f, team_size: e.target.value })}><Opt v="small" /><Opt v="medium" /><Opt v="large" /></select></Field>
          <label className="text-sm"><input type="checkbox" checked={f.regulated} onChange={(e) => setF({ ...f, regulated: e.target.checked })} /> Regulated (medical, aviation…)</label>
          <label className="text-sm"><input type="checkbox" checked={f.fixed_contract} onChange={(e) => setF({ ...f, fixed_contract: e.target.checked })} /> Fixed scope and price</label>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => c.run("/api/se/method", f)}>Compare methods</button>
        {c.err && <ErrorBanner message={c.err} />}
        {c.res && <Ranking r={c.res} />}
      </Section>
      <Section title="The methods"><Table head={["Method", "What it is", "Good for", "Watch out for"]} rows={ref_.methods.map((m) => [m.name, m.what, m.good, m.bad])} /></Section>
    </div>
  );
}

function Ranking({ r }: { r: Ranked }) {
  return (
    <div className="mt-3 space-y-2">
      <p className="text-sm">Best fit: <Badge tone="ok">{r.pick}</Badge></p>
      <Table head={["Option", "Score", "Why"]} rows={r.ranking.map((x) => [x.method ?? x.pattern, x.score, <ul key="w" className="list-disc pl-4 text-xs">{x.reasons.map((t, i) => <li key={i}>{t}</li>)}</ul>])} />
      <Lesson text={r.caution} />
    </div>
  );
}

function Requirements() {
  const [story, setStory] = useState("As a customer I want fast checkout so that I buy again");
  const sc = useCall<{ who: string; what: string; why: string; issues: string[]; ok: boolean; lesson: string }>();
  const [reqs, setReqs] = useState("R1 | must | Customer can pay by card\nR2 | must | Receipt is emailed within 1 minute\nR3 | could | Save a card for later");
  const [tests, setTests] = useState("T1 | R1\nT2 | R1\nT3 | R9\nT4 |");
  const tc = useCall<{ matrix: { requirement: string; priority: string; text: string; tests: string[]; covered: boolean }[]; coverage_pct: number; orphan_tests: { test: string; problem: string }[]; must_have_gaps: string[]; lesson: string }>();
  const go = () => {
    const rq = lines(reqs).map((l) => { const [id, priority, text] = l.split("|").map((x) => x.trim()); return { id, priority: priority || "must", text: text ?? "" }; });
    const ts = lines(tests).map((l) => { const [id, cv] = l.split("|").map((x) => x.trim()); return { id, covers: (cv ?? "").split(",").map((x) => x.trim()).filter(Boolean) }; });
    tc.run("/api/se/traceability", { requirements: rq, tests: ts });
  };
  return (
    <div className="space-y-3">
      <Section title="User story checker" note="A story answers who, what and why. Vague words can't be tested.">
        <textarea className="field w-full" rows={2} aria-label="User story" value={story} onChange={(e) => setStory(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={() => sc.run("/api/se/story", { text: story })}>Check the story</button>
        {sc.err && <ErrorBanner message={sc.err} />}
        {sc.res && <div className="mt-2 space-y-2"><div className="grid gap-2 sm:grid-cols-3"><Stat label="Who" value={sc.res.who || "missing"} /><Stat label="What" value={sc.res.what || "missing"} /><Stat label="Why" value={sc.res.why || "missing"} /></div>
          {sc.res.ok ? <Badge tone="ok">Looks testable</Badge> : <Warn items={sc.res.issues} />}<Lesson text={sc.res.lesson} /></div>}
      </Section>
      <Section title="Traceability matrix" note="One requirement per line as id | priority | text. One test per line as id | requirement ids (comma separated).">
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Requirements"><textarea className="field w-full font-mono text-xs" rows={5} value={reqs} onChange={(e) => setReqs(e.target.value)} /></Field>
          <Field label="Tests"><textarea className="field w-full font-mono text-xs" rows={5} value={tests} onChange={(e) => setTests(e.target.value)} /></Field>
        </div>
        <button className="btn btn-primary mt-2" onClick={go}>Build the matrix</button>
        {tc.err && <ErrorBanner message={tc.err} />}
        {tc.res && <div className="mt-2 space-y-2"><Stat label="Requirements with a test" value={`${tc.res.coverage_pct}%`} sub={tc.res.must_have_gaps.length ? `Untested must-haves: ${tc.res.must_have_gaps.join(", ")}` : "All must-haves covered"} />
          <Table head={["Requirement", "Priority", "Tests", "Covered"]} rows={tc.res.matrix.map((m) => [`${m.requirement} ${m.text}`, m.priority, m.tests.join(", ") || "-", m.covered ? <Badge key="c" tone="ok">yes</Badge> : <Badge key="c" tone="bad">no</Badge>])} />
          <Warn items={tc.res.orphan_tests.map((o) => `${o.test} ${o.problem}`)} /><Lesson text={tc.res.lesson} /></div>}
      </Section>
    </div>
  );
}

function Versions() {
  const [a, setA] = useState("1.2.3");
  const [b, setB] = useState("1.10.0");
  const [lvl, setLvl] = useState("minor");
  const [spec, setSpec] = useState("^1.2.0");
  const cmp = useCall<{ text: string; meaning: string }>();
  const bump = useCall<{ to: string; when: string }>();
  const sat = useCall<{ matches: boolean; why: string }>();
  return (
    <div className="space-y-3">
      <Lesson text="Semantic versioning is MAJOR.MINOR.PATCH: major = breaking change, minor = new backward-compatible feature, patch = bug fix. (Three parts; calendar versions like Ubuntu 18.04 are a different scheme.)" />
      <Section title="Compare two versions">
        <div className="flex flex-wrap items-end gap-2"><Field label="A"><input className="field" value={a} onChange={(e) => setA(e.target.value)} /></Field><Field label="B"><input className="field" value={b} onChange={(e) => setB(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => cmp.run("/api/se/version/compare", { a, b })}>Compare</button></div>
        {cmp.err && <ErrorBanner message={cmp.err} />}{cmp.res && <p className="mt-2 text-sm">{cmp.res.text}. {cmp.res.meaning}</p>}
      </Section>
      <Section title="Bump a version">
        <div className="flex flex-wrap items-end gap-2"><Field label="Current"><input className="field" value={a} onChange={(e) => setA(e.target.value)} /></Field>
          <Field label="Level"><select className="field" value={lvl} onChange={(e) => setLvl(e.target.value)}><Opt v="major" /><Opt v="minor" /><Opt v="patch" /></select></Field>
          <button className="btn btn-primary" onClick={() => bump.run("/api/se/version/bump", { version: a, level: lvl })}>Bump</button></div>
        {bump.err && <ErrorBanner message={bump.err} />}{bump.res && <p className="mt-2 text-sm">Next version: <b>{bump.res.to}</b>. {bump.res.when}</p>}
      </Section>
      <Section title="Does a version fit a range?" note="Try ^1.2.0, ~1.2, >=1.0 <2.0 or 1.x.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Version"><input className="field" value={a} onChange={(e) => setA(e.target.value)} /></Field><Field label="Range"><input className="field" value={spec} onChange={(e) => setSpec(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => sat.run("/api/se/version/satisfies", { version: a, spec })}>Check</button></div>
        {sat.err && <ErrorBanner message={sat.err} />}{sat.res && <p className="mt-2 text-sm">{sat.res.matches ? <Badge tone="ok">matches</Badge> : <Badge tone="bad">does not match</Badge>} {sat.res.why}</p>}
      </Section>
    </div>
  );
}

function Testing({ ref_ }: { ref_: Ref }) {
  const [txt, setTxt] = useState("T1 | changed, used\nT2 | failed\nT3 | complex, flaky\nT4 |");
  const r = useCall<{ order: { id: string; score: number; reasons: string[]; order: number }[]; run_all_if: string; lesson: string }>();
  const go = () => r.run("/api/se/regression", { cases: lines(txt).map((l) => { const [id, fl = ""] = l.split("|").map((x) => x.trim()); return { id, uses_changed_code: /chang/.test(fl), failed_recently: /fail/.test(fl), frequently_used: /used/.test(fl), complex: /complex/.test(fl), flaky: /flaky/.test(fl) }; }) });
  return (
    <div className="space-y-3">
      <Section title="Levels"><Table head={["Level", "Tests", "Who", "When"]} rows={ref_.test_levels.map((l) => [l.level, l.tests, l.who, l.when])} /></Section>
      <Section title="Types"><Table head={["Type", "Checks"]} rows={ref_.test_types.map((t) => [t.type, t.checks])} /></Section>
      <Section title="Regression test order" note="One test per line as id | flags. Flags: changed (touches changed code), failed (failed recently), used (frequently used), complex, flaky.">
        <textarea className="field w-full font-mono text-xs" rows={5} aria-label="Test cases" value={txt} onChange={(e) => setTxt(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={go}>Order the tests</button>
        {r.err && <ErrorBanner message={r.err} />}
        {r.res && <div className="mt-2 space-y-2"><Table head={["#", "Test", "Score", "Why"]} rows={r.res.order.map((o) => [o.order, o.id, o.score, o.reasons.join("; ") || "-"])} /><p className="text-xs text-muted">Run all if: {r.res.run_all_if}</p><Lesson text={r.res.lesson} /></div>}
      </Section>
    </div>
  );
}

function Architecture({ ref_ }: { ref_: Ref }) {
  const [f, setF] = useState({ users: "thousands", team: "small", realtime_events: false, decentralized: false, independent_deploy: false, strong_consistency: false });
  const ar = useCall<Ranked>();
  const [t, setT] = useState({ web_servers: 2, app_servers: 2, db_replicas: 1, load_balancer: true, firewall: true, proxy: false, part_availability_pct: 99.5 });
  const tp = useCall<{ diagram: string | string[]; single_points_of_failure: string[]; illustrative_availability_pct: number; downtime_hours_per_year: number; caution: string; lesson: string }>();
  const ex = ref_.example_states;
  const [st, setSt] = useState(ex.transitions.map((x) => `${x.from} | ${x.event} | ${x.to}`).join("\n"));
  const [start, setStart] = useState(ex.start);
  const [fin, setFin] = useState(ex.finals.join(", "));
  const [states, setStates] = useState(ex.states.join(", "));
  const sr = useCall<{ issues: { level: string; text: string }[]; ok: boolean; mermaid: string; lesson: string }>();
  const [cls, setCls] = useState(ref_.example_classes.map((c) => `${c.name} | ${c.parent ?? ""} | ${(c.attributes ?? []).join(",")} | ${(c.methods ?? []).join(",")}`).join("\n"));
  const cr = useCall<{ mermaid: string; outline: string[]; notes: string[]; lesson: string }>();
  const split = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
  const goStates = () => sr.run("/api/se/states", { states: split(states), start, finals: split(fin), transitions: lines(st).map((l) => { const [from, event, to] = l.split("|").map((x) => x.trim()); return { from, event, to }; }) });
  const goCls = () => cr.run("/api/se/classes", { classes: lines(cls).map((l) => { const [name, parent, at, me] = l.split("|").map((x) => x.trim()); return { name, parent, attributes: split(at ?? ""), methods: split(me ?? "") }; }) });
  const num = (k: "web_servers" | "app_servers" | "db_replicas") => <input className="field" type="number" min={0} max={50} value={t[k]} onChange={(e) => setT({ ...t, [k]: Number(e.target.value) })} />;
  return (
    <div className="space-y-3">
      <Section title="Which architecture pattern?">
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Users"><select className="field" value={f.users} onChange={(e) => setF({ ...f, users: e.target.value })}><Opt v="hundreds" /><Opt v="thousands" /><Opt v="millions" /></select></Field>
          <Field label="Team"><select className="field" value={f.team} onChange={(e) => setF({ ...f, team: e.target.value })}><Opt v="solo" /><Opt v="small" /><Opt v="large" /></select></Field>
          {([["realtime_events", "Lots of reactions to events"], ["decentralized", "No central server wanted"], ["independent_deploy", "Parts must deploy separately"], ["strong_consistency", "Strict data consistency needed"]] as const).map(([k, l]) => <label key={k} className="text-sm"><input type="checkbox" checked={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} /> {l}</label>)}
        </div>
        <button className="btn btn-primary mt-2" onClick={() => ar.run("/api/se/architecture", f)}>Compare patterns</button>
        {ar.err && <ErrorBanner message={ar.err} />}{ar.res && <Ranking r={ar.res} />}
      </Section>
      <Section title="The patterns"><Table head={["Pattern", "What it is"]} rows={ref_.architecture.map((a) => [a.name, a.what])} /></Section>
      <Section title="Production topology" note="How many of each part? The tool lists what would take the system down if it failed.">
        <div className="grid gap-2 sm:grid-cols-4">
          <Field label="Web servers">{num("web_servers")}</Field><Field label="App servers">{num("app_servers")}</Field><Field label="Database replicas">{num("db_replicas")}</Field>
          <Field label="Availability of each part (%)"><input className="field" type="number" step="0.1" min={1} max={100} value={t.part_availability_pct} onChange={(e) => setT({ ...t, part_availability_pct: Number(e.target.value) })} /></Field>
          {([["load_balancer", "Load balancer"], ["firewall", "Firewall"], ["proxy", "Reverse proxy"]] as const).map(([k, l]) => <label key={k} className="text-sm"><input type="checkbox" checked={t[k]} onChange={(e) => setT({ ...t, [k]: e.target.checked })} /> {l}</label>)}
        </div>
        <button className="btn btn-primary mt-2" onClick={() => tp.run("/api/se/topology", t)}>Draw it</button>
        {tp.err && <ErrorBanner message={tp.err} />}
        {tp.res && <div className="mt-2 space-y-2"><Code>{Array.isArray(tp.res.diagram) ? tp.res.diagram.join("\n") : tp.res.diagram}</Code>
          <div className="grid gap-2 sm:grid-cols-2"><Stat label="Illustrative availability" value={`${tp.res.illustrative_availability_pct}%`} sub={`about ${tp.res.downtime_hours_per_year} h down a year`} /><Stat label="Single points of failure" value={String(tp.res.single_points_of_failure.length)} sub={tp.res.single_points_of_failure.join(", ") || "none found"} /></div>
          <Lesson text={tp.res.caution} /></div>}
      </Section>
      <Section title="State diagram checker" note="States separated by commas; one transition per line as from | event | to.">
        <div className="grid gap-2 sm:grid-cols-3"><Field label="States"><input className="field" value={states} onChange={(e) => setStates(e.target.value)} /></Field><Field label="Start"><input className="field" value={start} onChange={(e) => setStart(e.target.value)} /></Field><Field label="Final states"><input className="field" value={fin} onChange={(e) => setFin(e.target.value)} /></Field></div>
        <textarea className="field mt-2 w-full font-mono text-xs" rows={5} aria-label="Transitions" value={st} onChange={(e) => setSt(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={goStates}>Check the states</button>
        {sr.err && <ErrorBanner message={sr.err} />}
        {sr.res && <div className="mt-2 space-y-2">{sr.res.issues.length ? sr.res.issues.map((i, k) => <p key={k} className="text-sm"><Badge tone={i.level === "bad" ? "bad" : i.level === "warn" ? "warn" : "muted"}>{i.level}</Badge> {i.text}</p>) : <Badge tone="ok">No problems</Badge>}<Code>{sr.res.mermaid}</Code><Lesson text={sr.res.lesson} /></div>}
      </Section>
      <Section title="Class diagram" note="One class per line as name | parent | attributes (commas) | methods (commas).">
        <textarea className="field w-full font-mono text-xs" rows={4} aria-label="Classes" value={cls} onChange={(e) => setCls(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={goCls}>Build the diagram</button>
        {cr.err && <ErrorBanner message={cr.err} />}
        {cr.res && <div className="mt-2 space-y-2"><Code>{cr.res.outline.join("\n")}</Code><Code>{cr.res.mermaid}</Code><Warn items={cr.res.notes} /><Lesson text={cr.res.lesson} /></div>}
      </Section>
    </div>
  );
}

function Flow({ ref_ }: { ref_: Ref }) {
  const [src, setSrc] = useState(ref_.example_pseudocode);
  const r = useCall<{ mermaid: string; nodes: { id: string; kind: string; text: string }[]; symbols: Rec; lesson: string }>();
  return (
    <Section title="Pseudocode to flowchart" note="Use START, END, INPUT, PRINT, IF … THEN / ELSE / END IF, WHILE … END WHILE and FOR i = 1 TO n … END FOR. Anything else becomes a step.">
      <textarea className="field w-full font-mono text-xs" rows={12} aria-label="Pseudocode" value={src} onChange={(e) => setSrc(e.target.value)} />
      <button className="btn btn-primary mt-2" onClick={() => r.run("/api/se/flow", { src })}>Make the flowchart</button>
      {r.err && <ErrorBanner message={r.err} />}
      {r.res && <div className="mt-2 space-y-2"><p className="text-xs text-muted">Paste this into mermaid.live to see the picture.</p><Code>{r.res.mermaid}</Code>
        <Table head={["Shape", "Meaning"]} rows={Object.entries(r.res.symbols).map(([k, v]) => [k, v])} /><Lesson text={r.res.lesson} /></div>}
    </Section>
  );
}

function Reference({ ref_ }: { ref_: Ref }) {
  const fw = ref_.library_vs_framework;
  return (
    <div className="space-y-3">
      <Section title="Corrections to common course errors"><Warn items={ref_.slips} /></Section>
      <Section title="What can't run here"><Warn items={ref_.not_built} /></Section>
      <Section title="Documents"><Table head={["Document", "What it is"]} rows={ref_.docs.map((d) => [d.doc, d.what])} /></Section>
      <Section title="Tools"><Table head={["Group", "Examples and use"]} rows={ref_.tools.map((t) => [t.group, t.items])} /></Section>
      <Section title="Library vs framework"><Table head={["", ""]} rows={[["Library", fw.library], ["Framework", fw.framework]]} /><Lesson text={fw.note} /></Section>
      <Section title="Stacks"><Table head={["Stack", "Parts", "Note"]} rows={ref_.stacks.map((s) => [s.name, s.parts, s.note])} /></Section>
      <Section title="Languages"><Table head={["Kind", "Examples", "How it runs"]} rows={ref_.languages.map((l) => [l.kind, l.examples, l.how])} /></Section>
      <Section title="Programming concepts"><Table head={["Term", "Meaning"]} rows={ref_.concepts.map((c) => [c.term, c.what])} /></Section>
      <Section title="UML and diagrams"><Table head={["Diagram", "Shows"]} rows={ref_.uml.map((u) => [u.diagram, u.shows])} /></Section>
      <Section title="Environments"><Table head={["Environment", "Used for", "Data"]} rows={ref_.environments.map((e) => [e.env, e.for, e.data])} /></Section>
      <Section title="Hosting"><Table head={["Model", "What it is"]} rows={ref_.hosting.map((h) => [h.name, h.what])} /></Section>
      <Section title="Production components"><Table head={["Part", "What it does"]} rows={ref_.production.map((p) => [p.part, p.does])} /></Section>
    </div>
  );
}
