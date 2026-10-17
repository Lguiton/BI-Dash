"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

type Model = { id: string; name: string; short: string; what: string; examples: string; you_manage: string; provider_manages: string; good_for: string; watch_out: string; cost: string; small_business: string };
type Ref = { reviewed: string; note: string; models: Model[]; responsibility: { layers: string[]; rows: { model: string; cells: { layer: string; who: string }[] }[]; note: string } };
type Iac = { lesson: { h: string; p: string }[]; templates: { id: string; title: string; language: string; text: string; note: string }[]; checklist: string[]; note: string };
type Pick = { matches: { id: string; name: string; why: string; you_manage: string; watch_out: string }[]; ask_first: string[]; note: string };
type Find = { severity: "high" | "medium" | "low"; line: number; problem: string; fix: string; snippet: string };
type Rev = { findings: Find[]; counts: Record<string, number>; notes: string[]; caveat: string };
type Quiz = { questions: { id: number; q: string; options: string[] }[]; pass_pct: number };
type Grade = { score: number; total: number; pct: number; passed: boolean; results: { id: number; correct: boolean; right: number; why: string }[] };
const TABS = [{ id: "models", label: "Service models" }, { id: "who", label: "Who manages what" }, { id: "pick", label: "Pick one" }, { id: "iac", label: "Infrastructure as Code" }, { id: "real", label: "Real-work checklist" }, { id: "quiz", label: "Quiz" }];
const SAMPLE = 'resource "aws_security_group" "x" {\n  ingress {\n    from_port   = 22\n    to_port     = 22\n    protocol    = "tcp"\n    cidr_blocks = ["0.0.0.0/0"]\n  }\n}\n';

function Copy({ text }: { text: string }) {
  const [d, setD] = useState(false);
  return <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); setD(true); setTimeout(() => setD(false), 2000); } catch { /* select the text */ } }}>{d ? "Copied" : "Copy"}</button>;
}

/** Cloud and "as a service" models, Infrastructure as Code, and a safe-change checklist for real client work. Reference only: nothing connects to a cloud or runs pasted code. */
export function CloudLab() {
  const [tab, setTab] = useState("models");
  const [ref, setRef] = useState<Ref | null>(null);
  const [iac, setIac] = useState<Iac | null>(null);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [need, setNeed] = useState("");
  const [pick, setPick] = useState<Pick | null>(null);
  const [code, setCode] = useState(SAMPLE);
  const [rev, setRev] = useState<Rev | null>(null);
  const [ans, setAns] = useState<Record<number, number>>({});
  const [grade, setGrade] = useState<Grade | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const bad = (e: unknown) => setErr(errMsg(e, "Couldn't load that."));
    if ((tab === "models" || tab === "who") && !ref) getJson<Ref>("/api/cloud/reference").then(setRef).catch(bad);
    if ((tab === "iac" || tab === "real") && !iac) getJson<Iac>("/api/cloud/iac").then(setIac).catch(bad);
    if (tab === "quiz" && !quiz) getJson<Quiz>("/api/cloud/quiz").then(setQuiz).catch(bad);
  }, [tab, ref, iac, quiz]);
  const act = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <section className="card space-y-3 p-4" aria-label="Cloud and as a service lab">
      <h2 className="text-base font-semibold">Cloud and “as a service”: IaaS, PaaS, SaaS, DBaaS, Infrastructure as Code and more</h2>
      <p className="text-xs text-muted">Reference for planning and supporting clients. Nothing here connects to a cloud or runs code. Never paste real passwords, keys or client data.</p>
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Cloud lab" />
      {err && <ErrorBanner message={err} />}

      {tab === "models" && ref && (
        <ul className="grid gap-2">
          {ref.models.map((m) => (
            <li key={m.id} className="rounded border border-line">
              <button className="flex w-full items-center justify-between gap-2 p-2 text-left" aria-expanded={open === m.id} onClick={() => setOpen(open === m.id ? null : m.id)}>
                <span><span className="text-sm font-semibold">{m.name}</span><br /><span className="text-xs text-muted">{m.short}</span></span>
              </button>
              {open === m.id && (
                <div className="space-y-1 border-t border-line p-3 text-sm">
                  <p>{m.what}</p>
                  <p><b>Examples:</b> {m.examples}</p>
                  <p><b>You manage:</b> {m.you_manage}</p>
                  <p><b>Provider manages:</b> {m.provider_manages}</p>
                  <p><b>Good for:</b> {m.good_for}</p>
                  <p><b>Watch out:</b> {m.watch_out}</p>
                  <p><b>How it is billed:</b> {m.cost}</p>
                  <p><b>For your clients:</b> {m.small_business}</p>
                </div>
              )}
            </li>
          ))}
          <li className="text-xs text-muted">{ref.note} Reviewed {ref.reviewed}.</li>
        </ul>
      )}

      {tab === "who" && ref && (
        <Section title="Who manages each layer" note={ref.responsibility.note}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr><th className="th">Model</th>{ref.responsibility.layers.map((l) => <th key={l} className="th">{l}</th>)}</tr></thead>
              <tbody>{ref.responsibility.rows.map((r) => (
                <tr key={r.model} className="border-t border-line"><td className="td font-semibold">{r.model}</td>
                  {r.cells.map((c) => <td key={c.layer} className="td"><Badge tone={c.who === "you" ? "warn" : "ok"}>{c.who === "you" ? "You" : "Provider"}</Badge></td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
      )}

      {tab === "pick" && (
        <Section title="Pick a model for a client need" note="Type what they need in plain words. It suggests starting points from keywords; you confirm with the client.">
          <div className="flex flex-wrap gap-2">
            <input className="input min-w-64 flex-1" aria-label="What the client needs" placeholder="e.g. email for 8 people, database for a booking app" value={need} onChange={(e) => setNeed(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && need.trim()) void act(async () => setPick(await postJson<Pick>("/api/cloud/pick", { need })), "Couldn't suggest."); }} />
            <button className="btn btn-primary" disabled={!need.trim()} onClick={() => act(async () => setPick(await postJson<Pick>("/api/cloud/pick", { need })), "Couldn't suggest.")}>Suggest</button>
          </div>
          {pick && (
            <div className="mt-3 space-y-2 text-sm">
              {pick.matches.length === 0 && <p className="text-muted">Nothing matched. Try other words, like server, database, email, backup or phones.</p>}
              {pick.matches.map((m) => <div key={m.id} className="rounded border border-line p-2"><p className="font-semibold">{m.name}</p><p>{m.why}</p><p className="text-xs text-muted">You manage: {m.you_manage}. Watch out: {m.watch_out}</p></div>)}
              <p className="text-xs font-semibold uppercase text-muted">Ask the client first</p>
              <ul className="list-disc space-y-1 pl-5">{pick.ask_first.map((a) => <li key={a}>{a}</li>)}</ul>
              <p className="text-xs text-muted">{pick.note}</p>
            </div>
          )}
        </Section>
      )}

      {tab === "iac" && iac && (
        <div className="space-y-4">
          <Section title="Infrastructure as Code in plain words">
            <dl className="space-y-2 text-sm">{iac.lesson.map((l) => <div key={l.h}><dt className="font-semibold">{l.h}</dt><dd className="text-muted">{l.p}</dd></div>)}</dl>
          </Section>
          <Section title="Review pasted IaC" note="Paste one Terraform, Ansible or CloudFormation file. It checks for common risky settings. It is pattern matching, not a security audit, and the pasted text is never run or sent anywhere.">
            <textarea className="field h-40 w-full font-mono text-xs" aria-label="IaC to review" value={code} onChange={(e) => setCode(e.target.value)} />
            <div className="mt-2"><button className="btn btn-primary" disabled={code.trim().length < 10} onClick={() => act(async () => setRev(await postJson<Rev>("/api/cloud/review", { text: code })), "Couldn't review that.")}>Review</button></div>
            {rev && (
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-xs">High {rev.counts.high} · Medium {rev.counts.medium} · Low {rev.counts.low}</p>
                {rev.findings.map((f, i) => (
                  <div key={i} className="rounded border border-line p-2"><Badge tone={f.severity === "high" ? "bad" : f.severity === "medium" ? "warn" : "muted"}>{f.severity}</Badge> line {f.line}: {f.problem}
                    <p className="font-mono text-xs text-muted">{f.snippet}</p><p className="text-xs"><b>Fix:</b> {f.fix}</p></div>
                ))}
                <ul className="list-disc space-y-1 pl-5 text-xs">{rev.notes.map((n) => <li key={n}>{n}</li>)}</ul>
                <p className="text-xs text-muted">{rev.caveat}</p>
              </div>
            )}
          </Section>
          <Section title="Starter templates" note="Edit the REPLACE parts. Test with the preview first. Practice in your own account before any client work.">
            <div className="space-y-3">{iac.templates.map((t) => (
              <div key={t.id} className="space-y-1 rounded border border-line p-2">
                <div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{t.title}</span><Copy text={t.text} /></div>
                <pre className="max-h-64 overflow-auto whitespace-pre rounded bg-panel2 p-2 text-xs">{t.text}</pre>
                <p className="text-xs text-muted">{t.note}</p>
              </div>
            ))}</div>
          </Section>
        </div>
      )}

      {tab === "real" && iac && (
        <Section title="Safe changes on a real client's systems" note="Work through this before and during any change. The change plan template is in the Infrastructure as Code tab.">
          <ol className="list-decimal space-y-1 pl-5 text-sm">{iac.checklist.map((c) => <li key={c}>{c}</li>)}</ol>
          <div className="mt-2"><Copy text={iac.checklist.map((c, i) => `${i + 1}. ${c}`).join("\n")} /></div>
          <p className="mt-2 text-xs text-muted">Compliance questions: see Settings, Legal and compliance. Do not touch a licensed system or a client&apos;s cloud account without written approval.</p>
        </Section>
      )}

      {tab === "quiz" && quiz && (
        <Section title="Checkpoint quiz" note={`${quiz.pass_pct}% passes.`}>
          <ol className="space-y-3 text-sm">{quiz.questions.map((q) => (
            <li key={q.id}><p className="font-semibold">{q.q}</p>
              <div role="radiogroup" aria-label={q.q} className="mt-1 space-y-1">{q.options.map((o, i) => (
                <label key={i} className="flex items-start gap-2"><input type="radio" name={`q${q.id}`} checked={ans[q.id] === i} onChange={() => setAns({ ...ans, [q.id]: i })} /> {o}</label>
              ))}</div>
              {grade && <p className={`mt-1 text-xs ${grade.results[q.id].correct ? "text-emerald-600" : "text-red-600"}`}>{grade.results[q.id].correct ? "Right. " : `Not quite. Answer: ${q.options[grade.results[q.id].right]}. `}{grade.results[q.id].why}</p>}
            </li>
          ))}</ol>
          <div className="mt-3 flex items-center gap-3">
            <button className="btn btn-primary" onClick={() => act(async () => setGrade(await postJson<Grade>("/api/cloud/quiz/grade", { answers: ans })), "Couldn't grade that.")}>Check my answers</button>
            {grade && <Badge tone={grade.passed ? "ok" : "warn"}>{grade.score} of {grade.total} ({grade.pct}%) {grade.passed ? "passed" : "keep going"}</Badge>}
            {grade && <button className="underline text-xs" onClick={() => { setGrade(null); setAns({}); }}>Try again</button>}
          </div>
        </Section>
      )}
    </section>
  );
}
