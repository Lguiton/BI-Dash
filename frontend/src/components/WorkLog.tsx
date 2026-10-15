"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { PrepDraft } from "@/components/PrepDraft";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";

type Entry = { at: string; text: string };
type Item = { id: number; title: string; client: string; status: "todo" | "doing" | "waiting" | "done"; status_label: string; due: string; note: string; log: Entry[]; overdue: boolean; due_today: boolean; job_id: number | null; job: { id: number; title: string; client: string } | null; running: boolean; elapsed: number; seconds: number };
type OpenJob = { id: number; title: string; client: string };
type Data = { items: Item[]; done_recent: Item[]; counts: Record<string, number>; overdue: number; due_today: number };

const NEXT: Record<string, Item["status"]> = { todo: "doing", doing: "waiting", waiting: "done", done: "todo" };
const WHY: Record<string, string> = { todo: "Start it", doing: "Put on hold", waiting: "Finish it", done: "Reopen" };
const tone = (s: string) => (s === "doing" ? "ok" : s === "waiting" ? "warn" : "muted");
const when = (s: string) => s.slice(0, 16).replace("T", " ");
const clock = (s: number) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** The "what am I working on" list on the home screen: one line per item, with a note for where you left off and a log underneath. */
export function WorkLog({ jobId }: { jobId?: number } = {}) {
  const [data, setData] = useState<Data | null>(null);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [client, setClient] = useState("");
  const [due, setDue] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [showDone, setShowDone] = useState(false);
  const [entry, setEntry] = useState("");
  const [note, setNote] = useState("");
  const [jobs, setJobs] = useState<OpenJob[]>([]);
  const [job, setJob] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [loadedAt, setLoadedAt] = useState(() => Date.now());

  useEffect(() => {
    let live = true;
    getJson<Data>("/api/worklog").then((r) => { if (live) { setData(r); setLoadedAt(Date.now()); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the work log.")); });
    return () => { live = false; };
  }, [tick]);

  useEffect(() => {
    if (jobId) return;
    let live = true;
    getJson<{ jobs: OpenJob[] }>("/api/clients/open-jobs").then((r) => { if (live) setJobs(r.jobs); }).catch(() => {});
    return () => { live = false; };
  }, [jobId]);
  const anyRunning = !!data?.items.some((i) => i.running);
  useEffect(() => {
    if (!anyRunning) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [anyRunning]);
  const elapsed = (i: Item) => (i.running ? i.elapsed + Math.max(0, Math.round((now - loadedAt) / 1000)) : i.elapsed);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't save.")); }
  }
  const add = () => run(async () => { await postJson("/api/worklog", { title, client, due, status: "todo", job_id: jobId ?? (job ? Number(job) : null) }); setTitle(""); setClient(""); setDue(""); setJob(""); });
  const move = (i: Item) => run(() => putJson(`/api/worklog/${i.id}`, { status: NEXT[i.status] }));
  const toggle = (i: Item) => { setOpen(open === i.id ? null : i.id); setNote(i.note); setEntry(""); };
  const saveNote = (i: Item) => run(() => putJson(`/api/worklog/${i.id}`, { note }));
  const addEntry = (i: Item) => run(async () => { await postJson(`/api/worklog/${i.id}/log`, { text: entry }); setEntry(""); });
  const remove = (i: Item) => run(async () => { await deleteJson(`/api/worklog/${i.id}`); setOpen(null); });

  const timer = (i: Item) => run(() => postJson(`/api/worklog/${i.id}/timer/${i.running ? "stop" : "start"}`, {}));
  const all = [...(data?.items ?? []), ...(showDone ? data?.done_recent ?? [] : [])];
  const items = jobId ? all.filter((i) => i.job_id === jobId) : all;
  return (
    <section className="card space-y-3 p-4" aria-label="Work log">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{jobId ? "Work on this job" : "What I'm working on"}</h2>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {data && data.overdue > 0 && <Badge tone="bad">{data.overdue} overdue</Badge>}
          {data && data.due_today > 0 && <Badge tone="warn">{data.due_today} due today</Badge>}
          {data && <span className="text-muted">{data.counts.doing} doing · {data.counts.todo} to do · {data.counts.waiting} waiting</span>}
        </div>
      </div>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <input className="input min-w-56 flex-1" aria-label="New work item" placeholder="What are you working on? e.g. Fix printer for Silver State" value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && title.trim()) void add(); }} />
        {!jobId && jobs.length > 0 && <select className="input w-44" aria-label="Job" value={job} onChange={(e) => setJob(e.target.value)}><option value="">No job (yet)</option>{jobs.map((j) => <option key={j.id} value={j.id}>{j.title} · {j.client}</option>)}</select>}
        {!jobId && !job && <input className="input w-40" aria-label="Client" placeholder="Client (optional)" value={client} onChange={(e) => setClient(e.target.value)} />}
        <input className="input w-40" type="date" aria-label="Due date" value={due} onChange={(e) => setDue(e.target.value)} />
        <button className="btn btn-primary" disabled={!title.trim()} onClick={add}>Add</button>
      </div>
      {data && items.length === 0 && <p className="text-sm text-muted">Nothing on the list. Add what you are working on, and it stays here until you finish it.</p>}
      <ul className="space-y-2">
        {items.map((i) => (
          <li key={i.id} className="rounded border border-line p-2 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button className="min-w-0 flex-1 text-left" aria-expanded={open === i.id} onClick={() => toggle(i)}>
                <span className={i.status === "done" ? "line-through text-muted" : "font-medium"}>{i.title}</span>
                {i.client && <span className="text-muted"> · {i.client}</span>}
                {i.running && <span className="ml-2 font-mono text-xs text-emerald-600" aria-label="Timer running">● {clock(elapsed(i))}</span>}
                {!i.running && i.elapsed > 0 && <span className="ml-2 font-mono text-xs text-muted" aria-label="Time on this item">{clock(i.elapsed)}</span>}
                {i.note && open !== i.id && <span className="block truncate text-xs text-muted">Left off: {i.note}</span>}
              </button>
              <div className="flex items-center gap-2">
                {i.job && !jobId && <Link href={`/job?id=${i.job.id}`} className="text-xs underline" aria-label={`Open job ${i.job.title}`}>job</Link>}
                {i.status !== "done" && <button className="btn" aria-label={`${i.running ? "Stop" : "Start"} timer: ${i.title}`} onClick={() => timer(i)}>{i.running ? "Stop timer" : "Start timer"}</button>}
                {i.overdue && <Badge tone="bad">overdue</Badge>}
                {i.due_today && <Badge tone="warn">due today</Badge>}
                {i.due && !i.overdue && !i.due_today && <span className="text-xs text-muted">due {i.due}</span>}
                <Badge tone={tone(i.status)}>{i.status_label}</Badge>
                <button className="btn" aria-label={`${WHY[i.status]}: ${i.title}`} onClick={() => move(i)}>{WHY[i.status]}</button>
              </div>
            </div>
            {open === i.id && (
              <div className="mt-2 space-y-2 border-t border-line pt-2">
                <div className="flex flex-wrap gap-2">
                  <input className="input min-w-56 flex-1" aria-label="Where I left off" placeholder="Where did you leave off?" value={note} onChange={(e) => setNote(e.target.value)} />
                  <button className="btn" onClick={() => saveNote(i)}>Save note</button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <input className="input min-w-56 flex-1" aria-label="Add a log entry" placeholder="Add to the log: what you did or found" value={entry} onChange={(e) => setEntry(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && entry.trim()) void addEntry(i); }} />
                  <button className="btn" disabled={!entry.trim()} onClick={() => addEntry(i)}>Add to log</button>
                </div>
                <PrepDraft draftKey={`item:${i.id}`} path={`/api/auto/prep/item/${i.id}`} label="Draft a first pass (AI)" />
                {!i.job && i.status !== "done" && <p className="text-xs text-muted">Not linked to a job, so timer time stays on this item and is not billed. Add it to a job from the Clients page to bill it.</p>}
                <ul className="space-y-0.5 text-xs text-muted">{[...i.log].reverse().slice(0, 12).map((e, k) => <li key={k}>{when(e.at)} (UTC) · {e.text}</li>)}</ul>
                <button className="text-xs text-red-600 underline" onClick={() => remove(i)}>Delete this item</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {data && data.done_recent.length > 0 && <button className="text-xs underline" onClick={() => setShowDone((v) => !v)}>{showDone ? "Hide finished" : `Show recently finished (${data.done_recent.length})`}</button>}
    </section>
  );
}
