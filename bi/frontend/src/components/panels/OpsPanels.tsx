"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";
import type { AlertStatus, DrillEntry, PmItem, PmTime, QuizData, QuizGraded } from "@/lib/types";
import { Badge, Field, Section, Stat, Table, errMsg, num, usd } from "./kit";

// ------------------------------------------------------------------ restore drill (Database admin tab)
export function DrillSection({ onDone }: { onDone: () => void }) {
  const [hist, setHist] = useState<DrillEntry[]>([]);
  const [due, setDue] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ history: DrillEntry[]; due: boolean }>("/api/dba/drill", ctl.signal).then((r) => { setHist(r.history); setDue(r.due); }).catch(() => { /* optional */ });
    return () => ctl.abort();
  }, [ver]);
  const run = async () => {
    setBusy(true); setErr(null);
    try { await postJson("/api/dba/drill", {}); setVer((v) => v + 1); onDone(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "The drill couldn't run."); }
    finally { setBusy(false); }
  };
  const last = hist[0];
  return (
    <Section title="Restore drill" note="Copies the newest backup to a scratch folder, opens it the way a real restore would, runs the integrity checks and compares it with live data, then deletes the copy. Your live database is never touched.">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? "Restoring a copy…" : "Run restore drill"}</button>
        {due && <Badge tone="warn">{hist.length ? "last drill is over a week old" : "never run"}</Badge>}
      </div>
      {err && <div className="mt-2"><ErrorBanner message={err} /></div>}
      {last && (
        <div className="mt-3 space-y-2 text-sm">
          <p><Badge tone={last.ok ? "ok" : "bad"}>{last.ok ? "passed" : "FAILED"}</Badge> <b>{last.backup}</b> · {last.at} UTC · {last.seconds}s</p>
          <ul className="space-y-0.5 text-xs">{last.steps.map((s) => <li key={s.name}>{s.ok ? "✓" : "✗"} {s.name}: <span className="text-muted">{s.detail}</span></li>)}</ul>
          <p>{last.reading}</p>
          <p className="text-muted">{last.recovery_point}</p>
        </div>
      )}
      {hist.length > 1 && <details className="mt-3 text-xs"><summary className="cursor-pointer text-muted">Earlier drills ({hist.length - 1})</summary>
        <ul className="mt-1 space-y-0.5">{hist.slice(1).map((h) => <li key={h.at}>{h.at} · {h.backup} · {h.ok ? "passed" : "FAILED"}</li>)}</ul></details>}
    </Section>
  );
}

// ------------------------------------------------------------------ alerts
export function AlertsCard() {
  const [a, setA] = useState<AlertStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<AlertStatus>("/api/alerts", ctl.signal).then(setA).catch(() => { /* the card is optional */ });
    return () => ctl.abort();
  }, [ver]);
  if (!a) return null;
  const check = async () => { setBusy(true); try { await postJson("/api/alerts/check", { send: false }); setVer((v) => v + 1); } finally { setBusy(false); } };
  if (a.alerts.length === 0) {
    return <section className="card flex flex-wrap items-center justify-between gap-2 p-3 text-sm" aria-label="Alerts"><span>✓ Nothing needs attention right now.</span><Link href="/settings" className="btn text-xs">Alert settings</Link></section>;
  }
  return (
    <section className="card space-y-2 p-4" aria-label="Alerts">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Needs attention ({a.alerts.length}{a.red ? `, ${a.red} red` : ""})</h2>
        <div className="flex gap-2"><button className="btn text-xs" disabled={busy} onClick={check}>{busy ? "Checking…" : "Check again"}</button><Link href="/settings" className="btn text-xs">Alert settings</Link></div>
      </div>
      <ul className="space-y-1 text-sm">
        {a.alerts.slice(0, 6).map((x) => (
          <li key={x.id}><Badge tone={x.level === "red" ? "bad" : "warn"}>{x.level}</Badge> <Link href={x.href} className="font-medium underline decoration-dotted">{x.title}</Link> <span className="text-xs text-muted">{x.detail}</span></li>
        ))}
      </ul>
      {a.alerts.length > 6 && <p className="text-xs text-muted">and {a.alerts.length - 6} more.</p>}
    </section>
  );
}

export function AlertsSettings() {
  const [a, setA] = useState<AlertStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<AlertStatus>("/api/alerts", ctl.signal).then(setA).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load alerts.")); });
    return () => ctl.abort();
  }, [ver]);
  const save = async (changes: Record<string, unknown>) => {
    setErr(null); setMsg(null);
    try { setA(await putJson<AlertStatus>("/api/alerts/config", changes)); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  };
  const testMail = async () => {
    setErr(null); setMsg(null);
    try { const r = await postJson<{ sent_to: string[] }>("/api/alerts/test-email", {}); setMsg(`Test email sent to ${r.sent_to.join(", ")}.`); } catch (e) { setErr(errMsg(e, "Couldn't send the test email.")); }
  };
  if (!a) return err ? <ErrorBanner message={err} /> : null;
  const c = a.config;
  return (
    <section className="card space-y-3 p-5" aria-label="Alerts">
      <h2 className="text-sm font-semibold uppercase tracking-wide">Alerts for the active workspace</h2>
      <p className="text-sm text-muted">The dashboard checks your KPIs, backups, integrity, sources and deadlines and shows what needs attention on the home page. Turn these on to have the backend check every 15 minutes while it runs, and optionally email you.</p>
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="text-sm text-emerald-600">{msg}</p>}
      <div className="flex flex-wrap items-end gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={c.enabled} onChange={(e) => save({ enabled: e.target.checked })} /> Check automatically</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={c.email} disabled={!a.email_ready && !c.email} onChange={(e) => save({ email: e.target.checked })} /> Email me {!a.email_ready && <span className="text-xs text-muted">(set BI_SMTP_* and BI_REPORT_TO in backend/.env first)</span>}</label>
        <Field label="Email the same alert at most every"><select className="field" value={c.cooldown_hours} onChange={(e) => save({ cooldown_hours: Number(e.target.value) })}>{a.options.cooldown_hours.map((h) => <option key={h} value={h}>{h < 24 ? `${h} hour${h > 1 ? "s" : ""}` : `${h / 24} day${h > 24 ? "s" : ""}`}</option>)}</select></Field>
        <Field label="Backup older than (days)"><input type="number" min={1} max={90} className="field w-24" defaultValue={c.backup_days} onBlur={(e) => save({ backup_days: Number(e.target.value) })} /></Field>
        <Field label="Data older than (days)"><input type="number" min={1} max={365} className="field w-24" defaultValue={c.stale_days} onBlur={(e) => save({ stale_days: Number(e.target.value) })} /></Field>
        <button className="btn" disabled={!a.email_ready} onClick={testMail}>Send a test email</button>
        <button className="btn" onClick={() => setVer((v) => v + 1)}>Refresh</button>
      </div>
      <p className="text-xs text-muted">Alerts only use this workspace&apos;s own data. Email goes only to the addresses in BI_REPORT_TO. &ldquo;Data older than&rdquo; applies to Real: Practice is a fixed sample.</p>
    </section>
  );
}

// ------------------------------------------------------------------ time tracker (Project & Product tab)
export function TimePanel({ items, onChanged }: { items: PmItem[]; onChanged: () => void }) {
  const c = useChartColors();
  const [t, setT] = useState<PmTime | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ item_id: "", day: "", hours: "1", note: "" });
  const [rate, setRate] = useState("");
  useEffect(() => {
    const ctl = new AbortController();
    getJson<PmTime>("/api/pm/time", ctl.signal).then((r) => { setT(r); setRate((x) => x || (r.rate ? String(r.rate) : "")); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load time entries.")); });
    return () => ctl.abort();
  }, []);
  const act = async (fn: () => Promise<PmTime>) => { setErr(null); try { setT(await fn()); onChanged(); } catch (e) { setErr(errMsg(e, "That didn't save.")); } };
  if (!t) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Hours logged" value={num(t.total_hours, 1)} sub={t.unassigned_hours ? `${num(t.unassigned_hours, 1)} not on an item` : "all on items"} />
        <Stat label="Hourly rate" value={t.rate ? usd(t.rate) : "not set"} />
        <Stat label="Time cost" value={t.cost == null ? "—" : usd(t.cost)} sub="hours x rate" />
        <Stat label="Feeds earned value" value={t.feeds_earned_value ? "yes" : "no"} sub={t.feeds_earned_value ? "see the Earned value tab" : "needs a rate and item hours"} />
      </div>
      <Section title="Log time" note={t.note}>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Item"><select className="field" value={f.item_id} onChange={(e) => setF({ ...f, item_id: e.target.value })}><option value="">(no item: overhead)</option>{items.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}</select></Field>
          <Field label="Day"><input type="date" className="field" value={f.day} onChange={(e) => setF({ ...f, day: e.target.value })} /></Field>
          <Field label="Hours"><input type="number" min={0.25} max={24} step={0.25} className="field w-24" value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} /></Field>
          <Field label="Note"><input className="field" maxLength={200} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
          <button className="btn btn-primary" onClick={() => act(() => postJson<PmTime>("/api/pm/time", { item_id: f.item_id || null, day: f.day || null, hours: Number(f.hours), note: f.note }).then((r) => { setF({ ...f, note: "" }); return r; }))}>Log it</button>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Field label="Hourly rate (USD)"><input type="number" min={0} max={10000} step={1} className="field w-28" value={rate} onChange={(e) => setRate(e.target.value)} /></Field>
          <button className="btn" onClick={() => act(() => putJson<PmTime>("/api/pm/rate", { rate: Number(rate || 0) }))}>Save rate</button>
        </div>
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Hours per week">
          {t.weeks.length === 0 ? <p className="text-sm text-muted">Nothing logged yet.</p> : (
            <div className="h-48" role="img" aria-label="Hours logged per week"><ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <BarChart data={t.weeks}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="week" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} /><YAxis stroke={c.axis} fontSize={11} width={32} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Bar dataKey="hours" fill={c.revenue} /></BarChart></ResponsiveContainer></div>)}
        </Section>
        <Section title="By item" note="Cost is hours x rate. 'Over plan' means the time cost already exceeds the item's planned cost.">
          {t.by_item.length === 0 ? <p className="text-sm text-muted">No hours on items yet.</p> : <Table head={["Item", "Hours", "Cost", "Planned", ""]} rows={t.by_item.map((b) => [b.title, num(b.hours, 1), b.cost == null ? "—" : usd(b.cost), b.planned_cost == null ? "—" : usd(b.planned_cost), b.over_plan ? <Badge key="o" tone="bad">over plan</Badge> : ""])} />}
        </Section>
      </div>
      <Section title="Entries">
        {t.entries.length === 0 ? <p className="text-sm text-muted">No entries.</p> : (
          <Table head={["Day", "Item", "Hours", "Note", ""]} rows={t.entries.slice(0, 40).map((e) => [e.day, e.item_title || "(overhead)", num(e.hours, 2), e.note, <button key="d" className="btn !py-0.5 text-xs" aria-label={`Delete the ${e.hours} hour entry on ${e.day}`} onClick={() => act(() => deleteJson<PmTime>(`/api/pm/time/${e.id}`))}>Delete</button>])} />
        )}
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ manual checkpoint quiz
export function QuizSection({ track, onReview }: { track: string; onReview: (stepId: string) => void }) {
  const [q, setQ] = useState<QuizData | null>(null);
  const [picked, setPicked] = useState<(number | null)[]>([]);
  const [res, setRes] = useState<QuizGraded | null>(null);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<QuizData>(`/api/quizzes/${track}`, ctl.signal).then((r) => { setQ(r); setPicked(r.questions.map(() => null)); }).catch(() => { /* a manual works without its quiz */ });
    return () => ctl.abort();
  }, [track, ver]);
  if (!q) return null;
  const done = picked.every((x) => x !== null);
  const submit = async () => {
    setErr(null);
    try { setRes(await postJson<QuizGraded>(`/api/quizzes/${track}`, { answers: picked })); } catch (e) { setErr(errMsg(e, "Couldn't grade the quiz.")); }
  };
  const retry = () => { setRes(null); setVer((v) => v + 1); };
  const r = q.result;
  return (
    <section className="card min-w-0 p-5" aria-label="Checkpoint quiz">
      <button className="flex w-full flex-wrap items-center justify-between gap-2 text-left" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="text-base font-semibold">Checkpoint quiz</span>
        <span className="flex items-center gap-2 text-xs text-muted">{q.questions.length} questions · {q.pass_pct}% passes {r ? (r.passed ? <Badge tone="ok">passed, best {r.best_pct}%</Badge> : <Badge tone="warn">best {r.best_pct}%</Badge>) : <Badge>not taken</Badge>}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-4">
          {err && <ErrorBanner message={err} />}
          {res && (
            <div role="status" className="rounded-md bg-panel2 p-3 text-sm">
              <b>{res.score}/{res.total} ({res.pct}%)</b>: {res.passed_now ? "passed." : `not yet: ${q.pass_pct}% passes.`} {res.review.length > 0 && <>Review: {res.review.map((sid) => <button key={sid} className="mr-2 underline decoration-dotted" onClick={() => onReview(sid)}>{q.questions.find((x) => x.step === sid)?.step_title ?? sid}</button>)}</>}
              <div className="mt-2"><button className="btn text-xs" onClick={retry}>Try again</button></div>
            </div>
          )}
          <ol className="space-y-4">
            {q.questions.map((x, i) => {
              const g = res?.graded[i];
              return (
                <li key={x.id} className="space-y-1 text-sm">
                  <fieldset>
                    <legend className="font-medium">{i + 1}. {x.q}</legend>
                    <div className="mt-1 space-y-1">
                      {x.options.map((o, k) => {
                        const right = g && k === g.correct, wrong = g && k === g.picked && !g.ok;
                        return (
                          <label key={k} className={`flex cursor-pointer items-start gap-2 rounded-md border p-2 ${right ? "border-emerald-500" : wrong ? "border-red-500" : "border-line"}`}>
                            <input type="radio" name={`q${x.id}`} className="mt-0.5" disabled={!!res} checked={picked[i] === k} onChange={() => setPicked(picked.map((p, j) => (j === i ? k : p)))} />
                            <span>{o}{right ? " ✓" : wrong ? " ✗" : ""}</span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                  {g && <p className="text-xs text-muted">{g.ok ? "Right. " : "Not quite. "}{g.why}</p>}
                </li>
              );
            })}
          </ol>
          {!res && <button className="btn btn-primary" disabled={!done} onClick={submit}>{done ? "Check my answers" : `Answer all ${q.questions.length} to check`}</button>}
        </div>
      )}
    </section>
  );
}
