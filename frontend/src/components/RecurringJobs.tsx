"use client";
import { useEffect, useState } from "react";
import { errMsg, Field, Section } from "@/components/panels/kit";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";

type R = { id: number; client_id: number; client: string; title: string; quote: number; every: "weekly" | "monthly"; day: number; items: string[]; active: boolean; last_run: string };
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** "Every month on the 1st, make this job with these steps." Created when the app runs on or after that day, once per period. */
export function RecurringJobs({ clientId }: { clientId: number }) {
  const [rows, setRows] = useState<R[]>([]);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ title: "", every: "monthly", day: "1", quote: "", items: "" });

  useEffect(() => {
    let live = true;
    getJson<{ recurring: R[] }>("/api/auto/recurring").then((r) => { if (live) setRows(r.recurring.filter((x) => x.client_id === clientId)); }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load recurring jobs.")); });
    return () => { live = false; };
  }, [clientId, tick]);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't save.")); }
  }
  const add = () => run(async () => {
    await postJson("/api/auto/recurring", { client_id: clientId, title: f.title, every: f.every, day: Number(f.day), quote: Number(f.quote || 0), items: f.items.split("\n") });
    setF({ title: "", every: f.every, day: f.day, quote: "", items: "" });
  });
  return (
    <Section title="Recurring jobs" note="A job that repeats, like a monthly report. It is created, with its steps, the first time the app runs on or after the day you pick, once per week or month.">
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      <ul className="space-y-1 text-sm">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-2">
            <span className={r.active ? "" : "text-muted line-through"}>{r.title}</span>
            <span className="text-xs text-muted">{r.every === "monthly" ? `monthly on day ${r.day}` : `weekly on ${DAYS[r.day]}`}{r.last_run ? ` · last made ${r.last_run}` : ""}</span>
            <button className="btn" onClick={() => run(() => putJson(`/api/auto/recurring/${r.id}`, { active: !r.active }))}>{r.active ? "Pause" : "Resume"}</button>
            <button className="text-xs text-red-600 underline" onClick={() => run(() => deleteJson(`/api/auto/recurring/${r.id}`))}>Delete</button>
          </li>
        ))}
        {rows.length === 0 && <li className="text-muted">None yet.</li>}
      </ul>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <Field label="Job title"><input aria-label="Recurring job title" className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Repeats"><select aria-label="Recurring repeats" className="input" value={f.every} onChange={(e) => setF({ ...f, every: e.target.value, day: e.target.value === "monthly" ? "1" : "0" })}><option value="monthly">Monthly</option><option value="weekly">Weekly</option></select></Field>
        <Field label={f.every === "monthly" ? "Day (1 to 28)" : "Weekday"}>
          {f.every === "monthly" ? <input aria-label="Recurring day" className="input w-20" value={f.day} onChange={(e) => setF({ ...f, day: e.target.value })} />
            : <select aria-label="Recurring weekday" className="input" value={f.day} onChange={(e) => setF({ ...f, day: e.target.value })}>{DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select>}
        </Field>
        <Field label="Quote $"><input aria-label="Recurring quote" className="input w-24" value={f.quote} onChange={(e) => setF({ ...f, quote: e.target.value })} /></Field>
      </div>
      <Field label="Steps, one per line (optional)"><textarea aria-label="Recurring steps" className="input mt-2 w-full" rows={3} value={f.items} onChange={(e) => setF({ ...f, items: e.target.value })} /></Field>
      <button className="btn mt-2" disabled={!f.title.trim()} onClick={add}>Add recurring job</button>
    </Section>
  );
}
