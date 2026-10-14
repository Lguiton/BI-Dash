"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "budget", label: "Context and cost" }, { id: "rag", label: "RAG evaluation" }, { id: "tools", label: "Tool safety" }, { id: "prompts", label: "Prompt versions" }, { id: "list", label: "Checklist" }];
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const Code = ({ children }: { children: string }) => <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded border border-line bg-panel2 p-2 text-xs" tabIndex={0}><code>{children}</code></pre>;
const Num = ({ label, v, set }: { label: string; v: string; set: (s: string) => void }) => <Field label={label}><input className="field" inputMode="decimal" value={v} onChange={(e) => set(e.target.value)} /></Field>;

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body: unknown) => { setErr(null); postJson<T>(path, body).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Check your input.")); }); };
  return { res, err, run };
}
const Out = ({ c }: { c: { err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);

export function AiWorkbenchPanel() {
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("budget");
  useEffect(() => { getJson<R>("/api/aieng").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the AI workbench."))); }, []);
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading AI workbench…</p>;
  return (
    <section className="card space-y-4 p-4" aria-label="AI workbench">
      <h2 className="text-base font-semibold">AI workbench: check your own AI work</h2>
      <Lesson text="Free, deterministic checks that never call a model: size a prompt, test retrieval on your own questions, review an agent's tools for risk, version prompts and plan costs." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="AI workbench" />
      {tab === "budget" && <Budget ref_={ref} />}
      {tab === "rag" && <Rag ref_={ref} />}
      {tab === "tools" && <ToolSafety ref_={ref} />}
      {tab === "prompts" && <Prompts ref_={ref} />}
      {tab === "list" && <Checklist ref_={ref} />}
    </section>
  );
}

function Budget({ ref_ }: { ref_: R }) {
  const [txt, setTxt] = useState("Paste a prompt or document here to estimate its tokens.");
  const tk = useCall(); const ft = useCall(); const ck = useCall(); const co = useCall();
  const [win, setWin] = useState("128000"); const [pt, setPt] = useState(""); const [ot, setOt] = useState("1000");
  const [c, setC] = useState({ doc: "50000", chunk: "300", ov: "40", k: "3", q: "200", p: "3" });
  const [k, setK] = useState({ r: "1000", i: "2000", o: "500", pi: "3", po: "15", hit: "50", disc: "90", share: "40", cpi: "0.25", cpo: "1.25" });
  return (
    <div className="space-y-3">
      <Section title="1. How many tokens?" note="An estimate (about 25 to 30 percent either way). Use the provider's own counter for a hard limit.">
        <textarea className="field w-full text-xs" rows={4} aria-label="Text to measure" value={txt} onChange={(e) => setTxt(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={() => tk.run("/api/aieng/tokens", { text: txt })}>Estimate</button>
        <Out c={tk} />{tk.res && <div className="mt-2 space-y-1"><div className="grid gap-2 sm:grid-cols-3"><Stat label="Estimated tokens" value={tk.res.estimated_tokens.toLocaleString()} sub={`likely ${tk.res.range[0].toLocaleString()} to ${tk.res.range[1].toLocaleString()}`} /><Stat label="Words" value={String(tk.res.words)} /><Stat label="Characters" value={String(tk.res.characters)} /></div><Lesson text={tk.res.note} /></div>}
      </Section>
      <Section title="2. Does it fit the window?" note={ref_.window_note}>
        <div className="grid gap-2 sm:grid-cols-3"><Field label="Context window (tokens)"><input className="field" list="win" inputMode="numeric" value={win} onChange={(e) => setWin(e.target.value)} /><datalist id="win">{ref_.window_examples.map((w: number) => <option key={w} value={w} />)}</datalist></Field>
          <Num label="Prompt tokens" v={pt || String(tk.res?.estimated_tokens ?? "")} set={setPt} /><Num label="Room for the answer" v={ot} set={setOt} /></div>
        <button className="btn btn-primary mt-2" onClick={() => ft.run("/api/aieng/fit", { prompt_tokens: Number(pt || tk.res?.estimated_tokens || 0), window_tokens: Number(win), output_tokens: Number(ot) })}>Check</button>
        <Out c={ft} />{ft.res && <div className="mt-2 space-y-1 text-sm"><p>{ft.res.fits ? <Badge tone="ok">fits</Badge> : <Badge tone="bad">too big</Badge>} {ft.res.used_pct}% of the usable window; {ft.res.left.toLocaleString()} tokens left.</p><Warn items={ft.res.notes} /></div>}
      </Section>
      <Section title="3. Chunk size and RAG cost" note="Larger chunks keep context but cost more per question. Measure the quality side in RAG evaluation.">
        <div className="grid gap-2 sm:grid-cols-3">{([["doc", "Document tokens"], ["chunk", "Chunk size"], ["ov", "Overlap"], ["k", "Passages per question"], ["q", "Questions per day"], ["p", "Input price per million ($)"]] as const).map(([x, l]) => <Num key={x} label={l} v={c[x]} set={(s) => setC({ ...c, [x]: s })} />)}</div>
        <button className="btn btn-primary mt-2" onClick={() => ck.run("/api/aieng/chunks", { doc_tokens: Number(c.doc), chunk_tokens: Number(c.chunk), overlap_tokens: Number(c.ov), top_k: Number(c.k), queries_per_day: Number(c.q), price_in_per_million: Number(c.p) })}>Plan</button>
        <Out c={ck} />{ck.res && <div className="mt-2 space-y-1"><div className="grid gap-2 sm:grid-cols-4"><Stat label="Chunks" value={String(ck.res.chunks)} /><Stat label="Tokens per question" value={String(ck.res.tokens_per_question)} /><Stat label="Tokens per month" value={ck.res.tokens_per_month.toLocaleString()} /><Stat label="Input cost per month" value={`$${ck.res.input_cost_per_month}`} /></div><Warn items={ck.res.notes} /><Lesson text={ck.res.lesson} /></div>}
      </Section>
      <Section title="4. Monthly cost, with caching and routing" note="Type in the prices; they change often and are never assumed. Leave cache and cheap-model fields at 0 to see the base cost.">
        <div className="grid gap-2 sm:grid-cols-3">{([["r", "Requests per day"], ["i", "Input tokens each"], ["o", "Output tokens each"], ["pi", "Input $ per million"], ["po", "Output $ per million"], ["hit", "Share of input that is cached (%)"], ["disc", "Cache discount (%)"], ["share", "Share sent to cheaper model (%)"], ["cpi", "Cheaper input $ per million"], ["cpo", "Cheaper output $ per million"]] as const).map(([x, l]) => <Num key={x} label={l} v={k[x]} set={(s) => setK({ ...k, [x]: s })} />)}</div>
        <button className="btn btn-primary mt-2" onClick={() => co.run("/api/aieng/cost", { requests_per_day: Number(k.r), input_tokens: Number(k.i), output_tokens: Number(k.o), price_in_per_million: Number(k.pi), price_out_per_million: Number(k.po), cache_hit_pct: Number(k.hit), cache_discount_pct: Number(k.disc), cheap_share_pct: Number(k.share), cheap_price_in: Number(k.cpi), cheap_price_out: Number(k.cpo) })}>Calculate</button>
        <Out c={co} />{co.res && <div className="mt-2 space-y-2"><Table head={["Scenario", "Per month"]} rows={[["Base", `$${co.res.base}`], ["With caching", `$${co.res.with_cache}`], ["With routing", `$${co.res.with_routing}`], ["Both", `$${co.res.with_both}`]]} />
          <p className="text-sm">Saving {co.res.saving_pct}% (${co.res.saving}). About ${co.res.per_request} per request; ${co.res.at_double_volume} at double volume. Output tokens are {co.res.output_share_of_base}% of the base bill.</p><ul className="list-disc pl-5 text-xs text-muted">{co.res.notes.map((n: string) => <li key={n}>{n}</li>)}</ul><Warn items={[co.res.caution]} /></div>}
      </Section>
    </div>
  );
}

function Rag({ ref_ }: { ref_: R }) {
  const [docs, setDocs] = useState<string>(ref_.example_docs.join("\n\n---\n\n"));
  const [cases, setCases] = useState<string>(ref_.example_cases.map((c: R) => `${c.question} | ${c.expected.join("; ")}`).join("\n"));
  const ev = useCall();
  const go = () => ev.run("/api/aieng/rag-eval", { docs: docs.split(/\n\s*---\s*\n/).map((d) => d.trim()).filter(Boolean), cases: lines(cases).map((l) => { const [q, ...e] = l.split("|"); return { question: (q ?? "").trim(), expected: e.join("|").split(";").map((x) => x.trim()).filter(Boolean) }; }) });
  return (
    <Section title="Does retrieval find the answer?" note="Documents separated by a line with ---. Questions one per line as: question | phrase that must appear in the answer passage. Leave the phrase blank for a question the documents can't answer.">
      <div className="grid gap-2 sm:grid-cols-2"><Field label="Documents"><textarea className="field text-xs" rows={9} value={docs} onChange={(e) => setDocs(e.target.value)} /></Field><Field label="Test questions"><textarea className="field font-mono text-xs" rows={9} value={cases} onChange={(e) => setCases(e.target.value)} /></Field></div>
      <button className="btn btn-primary mt-2" onClick={go}>Evaluate three chunk sizes</button>
      <Out c={ev} />
      {ev.res && <div className="mt-2 space-y-2"><p className="text-sm">Best chunk size here: <Badge tone="ok">{ev.res.best_chunk_chars} characters</Badge> ({ev.res.answerable} answerable and {ev.res.unanswerable} unanswerable questions)</p>
        <Table head={["Chunk (chars)", "Chunks", "Hit rate", "MRR", "Correctly found nothing"]} rows={ev.res.sizes.map((s: R) => [s.chunk_chars, s.chunks, s.hit_rate ?? "-", s.mrr ?? "-", s.abstain_rate ?? "-"])} />
        <details><summary className="cursor-pointer text-xs">Per-question results at the best size</summary><Table head={["Question", "Kind", "OK", "Rank", "Top score"]} rows={(ev.res.sizes.find((s: R) => s.chunk_chars === ev.res?.best_chunk_chars)?.cases ?? []).map((c: R) => [c.question, c.kind, c.found ? <Badge key="o" tone="ok">yes</Badge> : <Badge key="o" tone="bad">no</Badge>, c.rank ?? "-", c.top_score])} /></details>
        <Warn items={ev.res.notes} /><Lesson text={ev.res.lesson} /><Warn items={[ev.res.caution]} /></div>}
    </Section>
  );
}

function ToolSafety({ ref_ }: { ref_: R }) {
  const flags: { id: string; label: string }[] = ref_.tool_flags;
  const [tools, setTools] = useState<R[]>(ref_.example_tools);
  const ts = useCall();
  const set = (i: number, f: (t: R) => R) => setTools(tools.map((t, j) => (j === i ? f(t) : t)));
  return (
    <Section title="Review an agent's tools" note="List every tool the agent can call and tick what each one can do. The risk comes from combinations, not single tools.">
      <div className="space-y-2">{tools.map((t, i) => (
        <div key={i} className="rounded border border-line p-2"><div className="flex flex-wrap items-end gap-2"><Field label="Tool name"><input className="field" value={t.name ?? ""} onChange={(e) => set(i, (x) => ({ ...x, name: e.target.value }))} /></Field><button className="btn" onClick={() => setTools(tools.filter((_, j) => j !== i))}>Remove</button></div>
          <div className="mt-1 grid gap-x-3 gap-y-1 sm:grid-cols-3">{flags.map((f) => <label key={f.id} className="text-xs"><input type="checkbox" checked={!!t[f.id]} onChange={(e) => set(i, (x) => ({ ...x, [f.id]: e.target.checked }))} /> {f.label}</label>)}</div></div>))}</div>
      <div className="mt-2 flex flex-wrap gap-2"><button className="btn" onClick={() => setTools([...tools, { name: "" }])}>Add tool</button><button className="btn btn-primary" onClick={() => ts.run("/api/aieng/tool-safety", { tools })}>Review</button></div>
      <Out c={ts} />
      {ts.res && <div className="mt-2 space-y-2"><div className="grid gap-2 sm:grid-cols-2"><Stat label="Design score" value={`${ts.res.score}/100`} sub={ts.res.verdict} /><Stat label="Tools reviewed" value={String(ts.res.tools)} /></div>
        {ts.res.findings.length ? <Table head={["Level", "Tool", "Problem", "Fix"]} rows={ts.res.findings.map((f: R) => [<Badge key="l" tone={f.level === "bad" ? "bad" : "warn"}>{f.level}</Badge>, f.tool, f.problem, f.fix])} /> : <Badge tone="ok">No design problems found</Badge>}
        <Lesson text={ts.res.lesson} /><Warn items={[ts.res.caution]} /></div>}
    </Section>
  );
}

function Prompts({ ref_ }: { ref_: R }) {
  const [list, setList] = useState<R[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("support bot"); const [text, setText] = useState("You answer customer questions using only the provided policy.\nIf the policy does not say, reply \"I don't know\".");
  const [note, setNote] = useState("");
  const [a, setA] = useState("1"); const [b, setB] = useState("2"); const df = useCall();
  const [cases, setCases] = useState(JSON.stringify(ref_.example_prompt_cases, null, 1));
  const [oa, setOa] = useState('{"refund": "Refunds take 5 business days.", "unknown": "I don\'t know."}');
  const [ob, setOb] = useState('{"refund": "Refunds are quick, we guarantee it.", "unknown": "I don\'t know."}');
  const cmp = useCall();
  const lp = useCall(); const lr = useCall(); const [ok, setOk] = useState(false); const [lb, setLb] = useState("2");
  const load = useCallback(() => { getJson<{ prompts: R[] }>("/api/aieng/prompts").then((d) => setList(d.prompts)).catch((e) => setErr(errMsg(e, "Couldn't load prompts."))); }, []);
  useEffect(load, [load]);
  const save = () => { setErr(null); postJson("/api/aieng/prompts", { name, text, note }).then(() => { setNote(""); load(); }).catch((e) => setErr(errMsg(e, "Couldn't save."))); };
  const del = (n: string) => { deleteJson(`/api/aieng/prompts/${encodeURIComponent(n)}`).then(load).catch((e) => setErr(errMsg(e, "Couldn't delete."))); };
  const load1 = (n: string, v: number) => getJson<R>(`/api/aieng/prompts/${encodeURIComponent(n)}/${v}`).then((r) => { setName(n); setText(r.text); }).catch((e) => setErr(errMsg(e, "Couldn't open that version.")));
  const parse = (s: string) => { try { return JSON.parse(s); } catch { return null; } };
  const runCmp = () => { const c = parse(cases), x = parse(oa), y = parse(ob); if (!c || !x || !y) { setErr("The test cases and outputs must be valid JSON."); return; } setErr(null); cmp.run("/api/aieng/prompts/compare", { cases: c, outputs_a: x, outputs_b: y }); };
  const liveBody = (confirm: boolean) => { const c = parse(cases); if (!c) { setErr("The test cases must be valid JSON."); return null; } setErr(null); return { name, a: Number(a), b: lb.trim() ? Number(lb) : null, cases: c, confirm }; };
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      <Section title="Save a prompt version" note="Each save with changed text becomes a new version. Stored in this workspace only.">
        <div className="grid gap-2 sm:grid-cols-2"><Field label="Prompt name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} /></Field><Field label="What changed"><input className="field" value={note} onChange={(e) => setNote(e.target.value)} /></Field></div>
        <textarea className="field mt-2 w-full text-xs" rows={5} aria-label="Prompt text" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn btn-primary mt-2" onClick={save}>Save version</button>
        {list.length > 0 && <div className="mt-3 space-y-2">{list.map((p) => <div key={p.name} className="rounded border border-line p-2 text-sm"><b>{p.name}</b> <button className="btn ml-2" onClick={() => del(p.name)}>Delete</button>
          <ul className="mt-1 text-xs">{p.versions.map((v: R) => <li key={v.v}>v{v.v}: {v.note || "(no note)"}, about {v.tokens} tokens <button className="underline" onClick={() => load1(p.name, v.v)}>open</button></li>)}</ul></div>)}</div>}
      </Section>
      <Section title="Compare two versions">
        <div className="flex flex-wrap items-end gap-2"><Field label="From version"><input className="field w-20" value={a} onChange={(e) => setA(e.target.value)} /></Field><Field label="To version"><input className="field w-20" value={b} onChange={(e) => setB(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => df.run("/api/aieng/prompts/diff", { name, a: Number(a), b: Number(b) })}>Show changes</button></div>
        <Out c={df} />{df.res && <div className="mt-2 space-y-1"><p className="text-xs">+{df.res.lines_added} / -{df.res.lines_removed} lines; token change {df.res.token_change >= 0 ? "+" : ""}{df.res.token_change}</p><Code>{df.res.diff}</Code></div>}
      </Section>
      <Section title="Run the tests live" note="Sends each saved prompt version plus each test case's input to your AI provider and counts against your daily caps. Preview first. Test cases need an id and an input; leave version B blank to test one version. Don't put personal or confidential data in inputs.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Prompt"><span className="text-sm">{name}</span></Field><Field label="Version A"><input className="field w-20" value={a} onChange={(e) => setA(e.target.value)} /></Field><Field label="Version B (optional)"><input className="field w-20" value={lb} onChange={(e) => setLb(e.target.value)} /></Field>
          <button className="btn" onClick={() => { const bd = liveBody(false); if (bd) lp.run("/api/aieng/live/plan", bd); }}>Preview (no calls)</button></div>
        <Out c={lp} />
        {lp.res && <div className="mt-2 space-y-1 text-sm"><p>{lp.res.calls} model call(s): {lp.res.cases} case(s) × {lp.res.versions.length} version(s). About {lp.res.estimated_input_tokens.toLocaleString()} input tokens and {lp.res.estimated_output_tokens.toLocaleString()} output tokens.</p>
          <p>{lp.res.ai_allowed ? <Badge tone="ok">AI is on for this workspace</Badge> : <Badge tone="bad">AI is off in Settings</Badge>} {lp.res.providers_ready.length ? <>Ready: {lp.res.providers_ready.join(", ")}</> : <Badge tone="bad">No provider has a key</Badge>}</p><Warn items={lp.res.warnings} /></div>}
        <label className="mt-2 block text-sm"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> I understand this makes real model calls and uses my daily allowance.</label>
        <button className="btn btn-primary mt-2" disabled={!ok} onClick={() => { const bd = liveBody(true); if (bd) lr.run("/api/aieng/live/run", bd); }}>Run live tests</button>
        <Out c={lr} />
        {lr.res && <div className="mt-2 space-y-2"><p className="text-sm">{lr.res.calls} call(s) made with {lr.res.models.join(", ") || "no model"}. {lr.res.comparison ? <Badge tone={lr.res.regressions.length ? "bad" : "ok"}>{lr.res.comparison.verdict}</Badge> : null}</p>
          {lr.res.aborted && <Warn items={["Stopped early: " + lr.res.aborted]} />}
          <Table head={["Case", "A", "B", "A reply", "B reply"]} rows={(lr.res.comparison ?? lr.res.single).rows.map((r: R) => [r.id, r.a_pass ? "pass" : "fail: " + r.a_problems.join("; "), (lr.res as R).comparison ? (r.b_pass ? "pass" : "fail: " + r.b_problems.join("; ")) : "-", ((lr.res as R).outputs_a[r.id] ?? "").slice(0, 160), ((lr.res as R).outputs_b[r.id] ?? "").slice(0, 160)])} />
          {lr.res.errors.length > 0 && <Warn items={lr.res.errors.map((e: R) => `v${e.version} ${e.case}: ${e.error}`)} />}<Lesson text={lr.res.note} /></div>}
      </Section>
      <Section title="Did the new version break anything? (outputs you paste in)" note="Paste the outputs each version produced for the same test cases (JSON). Checks are required text, forbidden text and length; they don't call a model.">
        <div className="grid gap-2 sm:grid-cols-3"><Field label="Test cases"><textarea className="field font-mono text-xs" rows={8} value={cases} onChange={(e) => setCases(e.target.value)} /></Field><Field label="Outputs from version A"><textarea className="field font-mono text-xs" rows={8} value={oa} onChange={(e) => setOa(e.target.value)} /></Field><Field label="Outputs from version B"><textarea className="field font-mono text-xs" rows={8} value={ob} onChange={(e) => setOb(e.target.value)} /></Field></div>
        <button className="btn btn-primary mt-2" onClick={runCmp}>Compare</button>
        <Out c={cmp} />{cmp.res && <div className="mt-2 space-y-2"><p className="text-sm"><Badge tone={cmp.res.regressions.length ? "bad" : "ok"}>{cmp.res.verdict}</Badge> A passed {cmp.res.a_passed}/{cmp.res.total}, B passed {cmp.res.b_passed}/{cmp.res.total}.</p>
          <Table head={["Case", "A", "B", "Problems in B"]} rows={cmp.res.rows.map((r: R) => [r.id, r.a_pass ? "pass" : "fail", r.b_pass ? "pass" : "fail", r.b_problems.join("; ") || "-"])} /><Lesson text={cmp.res.lesson} /><Warn items={[cmp.res.caution]} /></div>}
      </Section>
    </div>
  );
}

function Checklist({ ref_ }: { ref_: R }) {
  return (
    <div className="space-y-3">
      <Section title="Before you ship an AI feature"><ol className="list-decimal pl-5 text-sm">{ref_.checklist.map((c: string) => <li key={c}>{c}</li>)}</ol><p className="mt-2 text-xs text-muted">Record the results in Qual templates: AI use case brief, Model card, Data card and AI incident review.</p></Section>
      <Section title="What can't be built here"><Warn items={ref_.not_built} /></Section>
    </div>
  );
}
