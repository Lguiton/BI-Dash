"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, Stat, errMsg } from "@/components/panels/kit";
import { API_BASE, deleteJson, getJson, postJson, putJson } from "@/lib/api";

interface Case { id: string; track: string; title: string; problem: string; actions: string; result: string; skills: string }
interface T { track: string; name: string; outcome: string; active: boolean; steps_done: number; steps_total: number; steps: string[]; quiz: { best_pct: number; attempts: number; passed: boolean } | null; review: { seen: number; mastered: number; accuracy_pct: number | null } | null; cases: Case[] }
interface P { tracks: T[]; active: number; quizzes_passed: number; steps_done: number; cases: number; streak: number; note: string }
const EMPTY = { track: "itsupport", title: "", problem: "", actions: "", result: "", skills: "" };

export default function PortfolioPage() {
  const [p, setP] = useState<P | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<string[]>([]);

  const load = useCallback(() => { getJson<P>("/api/portfolio").then(setP).catch((e) => setErr(errMsg(e, "Couldn't load the portfolio."))); }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { getJson<{ prompts: string[] }>(`/api/portfolio/prompts/${f.track}`).then((r) => setIdeas(r.prompts)).catch(() => setIdeas([])); }, [f.track, p?.steps_done]);

  const save = () => {
    setErr(null);
    const req = editing ? putJson(`/api/portfolio/cases/${editing}`, f) : postJson("/api/portfolio/cases", f);
    req.then(() => { setF({ ...EMPTY, track: f.track }); setEditing(null); load(); }).catch((e) => setErr(errMsg(e, "Couldn't save the case study.")));
  };
  const del = (id: string) => { deleteJson(`/api/portfolio/cases/${id}`).then(load).catch((e) => setErr(errMsg(e, "Couldn't delete it."))); };
  const edit = (c: Case) => { setEditing(c.id); setF({ track: c.track, title: c.title, problem: c.problem, actions: c.actions, result: c.result, skills: c.skills }); window.scrollTo({ top: 0 }); };
  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  return (
    <PageShell title="Portfolio" subtitle="What you have actually done, in a form you can show. Quiz and review scores are graded by the app; steps and case studies are your own record.">
      {err && <ErrorBanner message={err} />}
      {p && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <Stat label="Disciplines active" value={String(p.active)} /><Stat label="Steps done" value={String(p.steps_done)} /><Stat label="Quizzes passed" value={String(p.quizzes_passed)} />
            <Stat label="Case studies" value={String(p.cases)} /><Stat label="Review streak" value={`${p.streak} d`} />
          </div>
          <div className="flex flex-wrap gap-2">
            <a className="btn btn-primary" href={`${API_BASE}/api/portfolio/markdown`} download>Download as Markdown</a>
            <button className="btn" onClick={() => window.print()}>Print</button>
          </div>
          <Section title={editing ? "Edit case study" : "Write a case study"} note="A real or practice situation: what was wrong, what you did, what happened. Specific beats impressive.">
            <div className="grid gap-2 sm:grid-cols-2">
              <Field label="Discipline"><select className="field" value={f.track} onChange={set("track")} aria-label="Discipline">{p.tracks.map((t) => <option key={t.track} value={t.track}>{t.name}</option>)}</select></Field>
              <Field label="Title"><input className="field" value={f.title} onChange={set("title")} aria-label="Title" /></Field>
              <div className="sm:col-span-2"><Field label="Situation"><textarea className="field" rows={3} value={f.problem} onChange={set("problem")} aria-label="Situation" /></Field></div>
              <div className="sm:col-span-2"><Field label="What I did"><textarea className="field" rows={3} value={f.actions} onChange={set("actions")} aria-label="What I did" /></Field></div>
              <div className="sm:col-span-2"><Field label="Result"><textarea className="field" rows={2} value={f.result} onChange={set("result")} aria-label="Result" /></Field></div>
              <div className="sm:col-span-2"><Field label="Skills (comma separated)"><input className="field" value={f.skills} onChange={set("skills")} aria-label="Skills" /></Field></div>
            </div>
            {ideas.length > 0 && <div className="mt-2 text-xs text-muted"><b>Ideas from steps you ticked:</b><ul className="list-disc pl-5">{ideas.map((x) => <li key={x}>{x}</li>)}</ul></div>}
            <div className="mt-2 flex gap-2"><button className="btn btn-primary" onClick={save}>{editing ? "Save changes" : "Add case study"}</button>{editing && <button className="btn" onClick={() => { setEditing(null); setF(EMPTY); }}>Cancel</button>}</div>
          </Section>
          {p.tracks.filter((t) => t.active).length === 0 && <p className="text-sm text-muted">Nothing to show yet. Tick a manual step, pass a quiz or write a case study and it will appear here.</p>}
          {p.tracks.filter((t) => t.active).map((t) => (
            <Section key={t.track} title={t.name} note={t.outcome}>
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge tone="muted">{t.steps_done} of {t.steps_total} steps (self-ticked)</Badge>
                {t.quiz && <Badge tone={t.quiz.passed ? "ok" : "warn"}>Quiz best {t.quiz.best_pct}% ({t.quiz.passed ? "passed" : "not passed"})</Badge>}
                {t.review && <Badge tone="muted">{t.review.mastered} of {t.review.seen} review questions mastered</Badge>}
              </div>
              {t.steps.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm">{t.steps.map((s) => <li key={s}>{s}</li>)}</ul>}
              {t.cases.map((c) => (
                <article key={c.id} className="mt-3 rounded border border-line p-3 text-sm">
                  <h4 className="font-semibold">{c.title}</h4>
                  {c.problem && <p><b>Situation.</b> {c.problem}</p>}{c.actions && <p><b>What I did.</b> {c.actions}</p>}{c.result && <p><b>Result.</b> {c.result}</p>}{c.skills && <p className="text-muted"><b>Skills:</b> {c.skills}</p>}
                  <div className="mt-2 flex gap-2"><button className="btn" onClick={() => edit(c)}>Edit</button><button className="btn" onClick={() => del(c.id)}>Delete</button></div>
                </article>
              ))}
            </Section>
          ))}
        </>
      )}
    </PageShell>
  );
}
