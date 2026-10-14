"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "@/components/panels/kit";
import { fetchText, HtmlFrame, Pick } from "./common";
import { FieldHowTo, Out, TA, TI, lines, useRun } from "./fieldcommon";

const TABS = [{ id: "how", label: "How to do / fix" }, { id: "evals", label: "Eval runner" }, { id: "prompts", label: "Prompt library" }, { id: "cost", label: "Cost estimator" }, { id: "risk", label: "Risk register" }, { id: "handoff", label: "Handoff pack" }];

export function AiTools() {
  const [tab, setTab] = useState("how");
  return (
    <div className="grid gap-4">
      <Tabs label="AI engineering tools" value={tab} onChange={setTab} tabs={TABS} />
      {tab === "how" && <FieldHowTo area="AI engineering" agent="ai" examples="e.g. assistant got worse after a change, bill is too high" />}
      {tab === "evals" && <Evals />}
      {tab === "prompts" && <Prompts />}
      {tab === "cost" && <Cost />}
      {tab === "risk" && <Risk />}
      {tab === "handoff" && <Handoff />}
    </div>
  );
}

type Suite = { id: string; name: string; cases?: number; runs?: number; last?: number | null };
type Case = { id: string; prompt: string; checks: { type: string; value: string }[] };
type SuiteFull = { id: string; name: string; system_prompt: string; cases: Case[] };
type RunOut = { label: string; pass_rate: number; passed: number; total: number; results: { id: string; prompt: string; pass: boolean; failed: string[] }[]; compare: { says: string; regressed: string[] } | null };

const CHECK_HELP = "One case per line: the question, then checks after |  — contains:word  not_contains:word  max_words:80  min_words:5  regex:pattern  equals:text";

function parseCases(t: string) {
  return lines(t).map((l) => {
    const [prompt, ...rest] = l.split("|");
    return { prompt: prompt.trim(), checks: rest.map((c) => { const i = c.indexOf(":"); return { type: c.slice(0, i).trim(), value: c.slice(i + 1).trim() }; }).filter((c) => c.type) };
  });
}

function Evals() {
  const [list, setList] = useState<Suite[]>([]);
  const [tick, setTick] = useState(0);
  const [name, setName] = useState("");
  const [sys, setSys] = useState("");
  const [cases, setCases] = useState("");
  const [sel, setSel] = useState("");
  const [suite, setSuite] = useState<SuiteFull | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [label, setLabel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const run = useRun<RunOut>();
  useEffect(() => {
    let live = true;
    getJson<{ suites: Suite[] }>("/api/fieldbox/ai/evals").then((r) => { if (live) setList(r.suites); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load test suites.")); });
    return () => { live = false; };
  }, [tick]);
  const open = useCallback(async (id: string) => {
    setSel(id); run.setRes(null); setAnswers({});
    if (!id) { setSuite(null); return; }
    try { setSuite(await getJson<SuiteFull>(`/api/fieldbox/ai/evals/${id}`)); } catch (e) { setErr(errMsg(e, "Could not open the suite.")); }
  }, [run]);
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Make a test suite" note="Tests are rules, not full answers: words that must or must not appear, a length limit. Run the same suite before and after every change.">
        <div className="grid gap-2">
          <TI label="Suite name" value={name} onChange={setName} w="w-64" />
          <TA label="Instructions the assistant follows (optional)" value={sys} onChange={setSys} rows={3} />
          <TA label="Test cases" value={cases} onChange={setCases} rows={5} placeholder="What is your refund policy? | contains:30 days | not_contains:lifetime | max_words:80" />
          <p className="text-xs text-muted">{CHECK_HELP}</p>
          <div><button className="btn" disabled={!name.trim() || !cases.trim()} onClick={async () => { setErr(null); try { const r = await postJson<{ id: string }>("/api/fieldbox/ai/evals", { name, system_prompt: sys, cases: parseCases(cases) }); setTick((t) => t + 1); await open(r.id); } catch (e) { setErr(errMsg(e, "Could not save the suite.")); } }}>Save suite</button></div>
        </div>
      </Section>
      <Section title="Run a suite">
        <div className="flex flex-wrap items-end gap-2">
          <Pick label="Test suite" value={sel} onChange={open} options={list.map((s) => ({ id: s.id, label: `${s.name}${s.last != null ? ` (${s.last}% last run)` : ""}` }))} />
          <TI label="Name this run (e.g. new prompt v2)" value={label} onChange={setLabel} w="w-64" />
          {sel && <button className="btn" onClick={async () => { try { await deleteJson(`/api/fieldbox/ai/evals/${sel}`); setSel(""); setSuite(null); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not delete.")); } }}>Delete suite</button>}
        </div>
        {suite && (
          <div className="mt-3 grid gap-3">
            <p className="text-xs text-muted">Paste what your assistant answered for each question, then score. Or let the dashboard ask your connected AI provider (up to 30 cases, uses your quota).</p>
            {suite.cases.map((c) => (
              <div key={c.id} className="grid gap-1">
                <p className="text-sm"><b>{c.prompt}</b> <span className="text-xs text-muted">{c.checks.map((k) => `${k.type}:${k.value}`).join(" · ")}</span></p>
                <textarea aria-label={`Answer for ${c.prompt}`} className="input text-sm" rows={2} value={answers[c.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [c.id]: e.target.value })} />
              </div>
            ))}
            <div className="flex gap-2">
              <button className="btn" disabled={run.busy} onClick={() => run.run(() => postJson<RunOut>(`/api/fieldbox/ai/evals/${sel}/score`, { outputs: answers, label }), "Could not score the answers.")}>Score my answers</button>
              <button className="btn" disabled={run.busy} onClick={() => run.run(() => postJson<RunOut>(`/api/fieldbox/ai/evals/${sel}/run`, { label }), "The AI provider could not answer.")}>{run.busy ? "Working…" : "Run live with my AI provider"}</button>
            </div>
          </div>
        )}
        {run.err && <div className="mt-2"><ErrorBanner message={run.err} /></div>}
        {run.res && (
          <div className="mt-3 text-sm" aria-label="Eval result">
            <p className="font-medium">{run.res.label}: {run.res.passed} of {run.res.total} passed ({run.res.pass_rate}%)</p>
            {run.res.compare && <p className="mt-1 rounded border border-line bg-panel2 p-2">{run.res.compare.says}</p>}
            <ul className="mt-2 grid gap-1">{run.res.results.map((x) => <li key={x.id}><Badge tone={x.pass ? "ok" : "bad"}>{x.pass ? "pass" : "fail"}</Badge> {x.prompt} {x.failed.length > 0 && <span className="text-xs text-muted">— {x.failed.join("; ")}</span>}</li>)}</ul>
          </div>
        )}
      </Section>
    </div>
  );
}

type PV = { v: number; text: string; note: string; at: string };
function Prompts() {
  const [names, setNames] = useState<{ name: string; versions: number }[]>([]);
  const [tick, setTick] = useState(0);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [sel, setSel] = useState("");
  const [vers, setVers] = useState<PV[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const diff = useRun<Record<string, unknown>>();
  useEffect(() => {
    let live = true;
    getJson<{ prompts: { name: string; versions: number }[] }>("/api/fieldbox/ai/prompts").then((r) => { if (live) setNames(r.prompts); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load prompts.")); });
    return () => { live = false; };
  }, [tick]);
  async function open(n: string) { setSel(n); diff.setRes(null); if (!n) { setVers([]); return; } try { setVers((await getJson<{ versions: PV[] }>(`/api/fieldbox/ai/prompts/${encodeURIComponent(n)}`)).versions); } catch (e) { setErr(errMsg(e, "Could not open.")); } }
  const last = vers[vers.length - 1], prev = vers[vers.length - 2];
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Save a prompt version" note="Every save keeps the old version, so you can see what changed.">
        <div className="grid gap-2">
          <TI label="Prompt name" value={name} onChange={setName} w="w-64" />
          <TA label="Prompt text" value={text} onChange={setText} rows={5} />
          <TI label="Why did you change it?" value={note} onChange={setNote} w="w-96" />
          <div><button className="btn" disabled={!name.trim() || !text.trim()} onClick={async () => { setErr(null); try { await postJson("/api/fieldbox/ai/prompts", { name, text, note }); setTick((t) => t + 1); await open(name); } catch (e) { setErr(errMsg(e, "Could not save.")); } }}>Save version</button></div>
        </div>
      </Section>
      <Section title="History">
        <Pick label="Prompt" value={sel} onChange={open} options={names.map((n) => ({ id: n.name, label: `${n.name} (${n.versions} versions)` }))} />
        {vers.length > 0 && <ul className="mt-3 grid gap-2 text-sm">{[...vers].reverse().map((v) => <li key={v.v}><b>v{v.v}</b> <span className="text-xs text-muted">{v.at} {v.note && `· ${v.note}`}</span><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 text-xs">{v.text}</pre></li>)}</ul>}
        {last && prev && <button className="btn mt-2" onClick={() => diff.run(() => getJson(`/api/fieldbox/ai/prompts/${encodeURIComponent(sel)}/diff?v1=${prev.v}&v2=${last.v}`), "Could not compare.")}>Compare the last two versions</button>}
        {diff.err && <ErrorBanner message={diff.err} />}
        <Out data={diff.res} />
      </Section>
    </div>
  );
}

function Cost() {
  const [v, setV] = useState({ requests_per_day: "500", in_tokens: "800", out_tokens: "300", extra_context_tokens: "0", retry_pct: "5" });
  const [tier, setTier] = useState("medium");
  const r = useRun<Record<string, unknown>>();
  const set = (k: keyof typeof v) => (x: string) => setV({ ...v, [k]: x });
  return (
    <Section title="LLM cost estimator" note="Uses example prices you can change in your own copy of the numbers. Check your provider's price page before quoting a client.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="flex flex-wrap items-end gap-2">
        <TI label="Requests per day" value={v.requests_per_day} onChange={set("requests_per_day")} w="w-32" />
        <TI label="Words or tokens in" value={v.in_tokens} onChange={set("in_tokens")} w="w-32" />
        <TI label="Tokens out" value={v.out_tokens} onChange={set("out_tokens")} w="w-32" />
        <TI label="Extra context tokens" value={v.extra_context_tokens} onChange={set("extra_context_tokens")} w="w-36" />
        <TI label="Retry %" value={v.retry_pct} onChange={set("retry_pct")} w="w-24" />
        <Pick label="Model size" value={tier} onChange={setTier} options={[{ id: "small", label: "Small" }, { id: "medium", label: "Medium" }, { id: "large", label: "Large" }]} />
        <button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/ai/cost", { ...Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x)])), tier }), "Could not estimate.")}>Estimate</button>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Risk() {
  const [system, setSystem] = useState("");
  const [owner, setOwner] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="AI risk register" note="Starts from the usual risks (wrong answers, private data, prompt injection, cost) with a fix for each. Edit it for the client.">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2">
        <TI label="System name" value={system} onChange={setSystem} w="w-64" />
        <TI label="Owner" value={owner} onChange={setOwner} w="w-48" />
        <button className="btn" disabled={!system.trim()} onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/ai/risks", { system, owner })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); } }}>Build register</button>
      </div>
      {html && <HtmlFrame html={html} name="ai-risk-register.html" />}
    </Section>
  );
}

function Handoff() {
  const [f, setF] = useState({ name: "", owner: "", purpose: "", users: "", model: "", system_prompt: "", limits: "", testing: "", cost: "", monitoring: "", tools: "" });
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (x: string) => setF({ ...f, [k]: x });
  return (
    <Section title="Handoff pack" note="One page a client can keep: what it does, how it is tested, what it must not do and who watches it.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <div className="flex flex-wrap gap-2"><TI label="Assistant name" value={f.name} onChange={set("name")} w="w-64" /><TI label="Owner" value={f.owner} onChange={set("owner")} w="w-48" /><TI label="Model and provider" value={f.model} onChange={set("model")} w="w-64" /></div>
        <TA label="What it is for" value={f.purpose} onChange={set("purpose")} rows={2} />
        <TA label="Who uses it" value={f.users} onChange={set("users")} rows={2} />
        <TA label="Instructions it follows" value={f.system_prompt} onChange={set("system_prompt")} rows={3} />
        <TA label="Tools and data it can reach (one per line)" value={f.tools} onChange={set("tools")} rows={2} />
        <TA label="What it must not do" value={f.limits} onChange={set("limits")} rows={2} />
        <TA label="How it is tested" value={f.testing} onChange={set("testing")} rows={2} />
        <TI label="Expected monthly cost" value={f.cost} onChange={set("cost")} w="w-64" />
        <TA label="Who monitors it, and how often" value={f.monitoring} onChange={set("monitoring")} rows={2} />
        <div><button className="btn" onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/ai/handoff", { ...f, tools: lines(f.tools) })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); } }}>Build handoff pack</button></div>
      </div>
      {html && <HtmlFrame html={html} name="handoff-pack.html" />}
    </Section>
  );
}
