"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Pin } from "lucide-react";
import { Badge, errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";
import { useStoredJson } from "@/lib/useStoredJson";
import { downloadFile } from "@/lib/download";
import { WorkTeam } from "@/components/WorkTeam";

type Fld = { key: string; label: string; href: string };
type Over = { job: { id: number; title: string; status: string; quote: number; field_info: Fld | null }; client: { id: number; name: string } | null; hours: number; unbilled_hours: number; unbilled_amount: number; ready_to_close?: boolean };
type Item = { id: number; title: string; status: "todo" | "doing" | "waiting" | "done"; job_id: number | null; running: boolean; elapsed: number; log: { at: string; text: string }[] };
type OpenJob = { id: number; title: string; client: string; field: Fld | null };
type Bill = "time" | "quote" | "none";

const usd = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const clock = (s: number) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** The job you picked, pinned under the top box on every page: timer, steps, a quick note and Close job, so the work happens where you are. */
export function JobBar() {
  const router = useRouter();
  const [id, setId] = useActiveJob();
  const [open, setOpen] = useStoredJson<boolean>("bi.jobBarOpen", true);
  const [o, setO] = useState<Over | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [other, setOther] = useState<Item | null>(null);
  const [jobs, setJobs] = useState<OpenJob[]>([]);
  const [fields, setFields] = useState<Fld[]>([]);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [gone, setGone] = useState(false);
  const [step, setStep] = useState("");
  const [note, setNote] = useState("");
  const [bill, setBill] = useState<Bill>("time");
  const [confirm, setConfirm] = useState(false);
  const [closed, setClosed] = useState<string | null>(null);
  const [helpBusy, setHelpBusy] = useState(false);
  const [helpText, setHelpText] = useState<{ step: string; text: string } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [loadedAt, setLoadedAt] = useState(() => Date.now());

  useEffect(() => {
    if (!id) return;
    let live = true;
    Promise.all([getJson<Over>(`/api/jobs/${id}`), getJson<{ items: Item[]; done_recent: Item[] }>("/api/worklog?include_done=true")])
      .then(([ov, wl]) => { if (!live) return; setO(ov); setGone(false); setItems(wl.items.filter((i) => i.job_id === id).sort((a, b) => (a.status === "done" ? 1 : 0) - (b.status === "done" ? 1 : 0) || a.id - b.id)); setOther(wl.items.find((i) => i.running && i.job_id !== id) ?? null); setLoadedAt(Date.now()); })
      .catch(() => { if (live) { setGone(true); setO(null); } });
    return () => { live = false; };
  }, [id, tick]);

  useEffect(() => {
    let live = true;
    getJson<{ jobs: OpenJob[] }>("/api/clients/open-jobs").then((r) => { if (live) setJobs(r.jobs); }).catch(() => {});
    getJson<{ fields: Fld[] }>("/api/jobs/fields/list").then((r) => { if (live) setFields(r.fields); }).catch(() => {});
    return () => { live = false; };
  }, [tick]);

  const stepRef = useRef<HTMLInputElement>(null);
  const noteRef = useRef<HTMLInputElement>(null);
  const [help, setHelp] = useState(false);
  const jobDone = o?.job.status === "done";

  // One-key shortcuts, only while you are NOT typing in a box: T timer, D done and next, N note, A add step, C close, ? list.
  useEffect(() => {
    if (!id || jobDone || !o) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) { if (e.key === "Escape") t.blur(); return; }
      const cur = items.find((i) => i.running) ?? items.find((i) => i.status !== "done");
      const act = async (fn: () => Promise<unknown>) => { try { await fn(); setTick((n) => n + 1); } catch (er) { setErr(errMsg(er, "That didn't save.")); } };
      const k = e.key.toLowerCase();
      if (k === "t" && cur) { e.preventDefault(); void act(() => postJson(`/api/worklog/${cur.id}/timer/${cur.running ? "stop" : "start"}`, {})); }
      else if (k === "d" && cur) {
        e.preventDefault();
        const next = items.find((i) => i.id !== cur.id && i.status !== "done");
        void act(async () => { if (cur.running) await postJson(`/api/worklog/${cur.id}/timer/stop`, {}); await putJson(`/api/worklog/${cur.id}`, { status: "done" }); if (next) await postJson(`/api/worklog/${next.id}/timer/start`, {}); });
      }
      else if (k === "n") { e.preventDefault(); setOpen(true); setTimeout(() => noteRef.current?.focus(), 0); }
      else if (k === "a") { e.preventDefault(); setOpen(true); setTimeout(() => stepRef.current?.focus(), 0); }
      else if (k === "c") { e.preventDefault(); setOpen(true); setConfirm(true); }
      else if (k === "?") { e.preventDefault(); setHelp((h) => !h); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id, jobDone, o, items, setOpen]);

  const running = items.some((i) => i.running);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);

  if (!id) return null;
  const run = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't save.")); } };
  const elapsed = (i: Item) => (i.running ? i.elapsed + Math.max(0, Math.round((now - loadedAt) / 1000)) : i.elapsed);
  const total = items.reduce((s, i) => s + elapsed(i), 0);
  const field = o?.job.field_info ?? null;
  const current = items.find((i) => i.running) ?? items.find((i) => i.status !== "done");
  const done = o?.job.status === "done";
  const switchTo = (v: string) => {
    const j = jobs.find((x) => x.id === Number(v));
    if (!j) return;
    setClosed(null); setConfirm(false); setId(j.id);
    if (j.field) router.push(j.field.href);
  };
  const nextStep = async () => {
    if (!current || helpBusy) return;
    setErr(null); setHelpBusy(true); setHelpText(null);
    try {
      const track = field?.key ?? "itsupport";
      const r = await postJson<{ reply: string }>(`/api/agents/${track}/chat`, { message: `Help me with the current step of this job: "${current.title}". Use the job details, my tools and my past fixes. Give concrete next actions and what to check. Draft only.`, history: [], job_id: id });
      setHelpText({ step: current.title, text: r.reply });
    } catch (e) { setErr(errMsg(e, "The agent couldn't help with that step.")); } finally { setHelpBusy(false); }
  };
  const close = () => run(async () => {
    const r = await postJson<{ invoice: { number: string } | null; note: string }>(`/api/jobs/${id}/close`, { bill });
    setClosed([r.invoice ? `Job closed. Draft invoice ${r.invoice.number} created.` : "Job closed.", r.note].filter(Boolean).join(" ")); setConfirm(false);
  });

  return (
    <section className="card space-y-3 border-l-4 border-l-accent p-3 print:hidden" aria-label="Job you are working on">
      <div className="flex flex-wrap items-center gap-2">
        <Pin className="h-4 w-4 shrink-0 text-accent" aria-hidden />
        <div className="min-w-0 flex-1">
          {gone && <span className="text-sm">That job isn&apos;t in this workspace.</span>}
          {o && <span className="text-sm"><strong>{o.job.title}</strong>{o.client ? <span className="text-muted"> · {o.client.name}</span> : null} {done && <Badge tone="ok">closed</Badge>}</span>}
          {!o && !gone && <span className="text-sm text-muted">Loading the job…</span>}
        </div>
        {o && <span className={`font-mono text-sm ${running ? "text-emerald-600" : "text-muted"}`} aria-label={running ? "Timer running" : "Time on this job"}>{running ? "● " : ""}{clock(total)}</span>}
        {jobs.length > 1 && (
          <select className="input w-52" aria-label="Switch job" value="" onChange={(e) => switchTo(e.target.value)}>
            <option value="">Switch job…</option>
            {jobs.filter((j) => j.id !== id).map((j) => <option key={j.id} value={j.id}>{j.title} · {j.client}</option>)}
          </select>
        )}
        <button className="btn" aria-expanded={open} aria-label={open ? "Collapse the job bar" : "Expand the job bar"} onClick={() => setOpen(!open)}>{open ? <ChevronUp className="h-4 w-4" aria-hidden /> : <ChevronDown className="h-4 w-4" aria-hidden />}</button>
        <button className="btn" onClick={() => { setId(null); setClosed(null); setConfirm(false); }}>Unpin</button>
      </div>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      {other && (
        <p role="status" className="flex flex-wrap items-center gap-2 text-sm">
          <Badge tone="warn">timer running elsewhere</Badge> {other.title}
          <button className="btn" onClick={() => run(() => postJson(`/api/worklog/${other.id}/timer/stop`, {}))}>Stop it</button>
        </p>
      )}
      {open && o && (
        <div className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            {field ? <Link href={field.href} className="btn btn-primary">Open {field.label} dashboard</Link> : <span className="text-xs text-muted">No field picked yet.</span>}
            <label className="flex items-center gap-1 text-xs text-muted">Field
              <select className="input w-44" value={field?.key ?? ""} onChange={(e) => run(async () => { await putJson(`/api/clients/jobs/${id}`, { field: e.target.value || null }); })}>
                <option value="">Not set</option>
                {fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
              </select>
            </label>
            <Link href={`/job?id=${id}`} className="text-xs underline">Full job page</Link>
            <span className="text-xs text-muted">{o.hours} h recorded · unbilled {usd(o.unbilled_amount)}</span>
          </div>

          {!done && (
            <>
              <ul className="space-y-1" aria-label="Steps">
                {items.map((i) => (
                  <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line px-2 py-1">
                    <span className={i.status === "done" ? "text-muted line-through" : ""}>{i.title}{i.running && <span className="ml-2 font-mono text-xs text-emerald-600">● {clock(elapsed(i))}</span>}{!i.running && i.elapsed > 0 && <span className="ml-2 font-mono text-xs text-muted">{clock(i.elapsed)}</span>}</span>
                    <span className="flex gap-2">
                      {i.status !== "done" && <button className="btn" aria-label={`${i.running ? "Stop" : "Start"} timer: ${i.title}`} onClick={() => run(() => postJson(`/api/worklog/${i.id}/timer/${i.running ? "stop" : "start"}`, {}))}>{i.running ? "Stop" : "Start"}</button>}
                      <button className="btn" aria-label={`${i.status === "done" ? "Reopen" : "Mark done"}: ${i.title}`} onClick={() => run(() => putJson(`/api/worklog/${i.id}`, { status: i.status === "done" ? "doing" : "done" }))}>{i.status === "done" ? "Reopen" : "Done"}</button>
                      <button className="text-xs text-red-600 underline" aria-label={`Remove step: ${i.title}`} onClick={() => run(() => deleteJson(`/api/worklog/${i.id}`))}>remove</button>
                    </span>
                  </li>
                ))}
                {items.length === 0 && <li className="text-xs text-muted">No steps yet. Add the first one below.</li>}
              </ul>
              <div className="flex flex-wrap gap-2">
                <input ref={stepRef} className="input min-w-56 flex-1" aria-label="Add a step" placeholder="Add a step" value={step} onChange={(e) => setStep(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && step.trim()) run(async () => { await postJson("/api/worklog", { title: step, status: "todo", job_id: id }); setStep(""); }); }} />
                <button className="btn" disabled={!step.trim()} onClick={() => run(async () => { await postJson("/api/worklog", { title: step, status: "todo", job_id: id }); setStep(""); })}>Add step</button>
              </div>
              {current && (
                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn" disabled={helpBusy} onClick={nextStep}>{helpBusy ? "Working…" : "Do the next step"}</button>
                  <span className="text-xs text-muted">Drafts help for &quot;{current.title.slice(0, 40)}&quot;. Nothing changes on its own.</span>
                </div>
              )}
              {helpText && (
                <div className="space-y-1 rounded border border-line p-2 text-sm" role="status">
                  <div className="flex items-center justify-between gap-2"><span className="text-xs text-muted">AI draft for &quot;{helpText.step.slice(0, 50)}&quot; (can be wrong, check it)</span><button className="text-xs underline" onClick={() => setHelpText(null)}>Hide</button></div>
                  <pre className="whitespace-pre-wrap font-sans text-sm">{helpText.text}</pre>
                  <button className="btn" onClick={() => { void navigator.clipboard?.writeText(helpText.text).catch(() => {}); }}>Copy</button>
                  <button className="btn" onClick={() => { setNote(helpText.text.slice(0, 500)); setTimeout(() => noteRef.current?.focus(), 0); }}>Use as note</button>
                </div>
              )}
              {current && (
                <div className="flex flex-wrap gap-2">
                  <input ref={noteRef} className="input min-w-56 flex-1" aria-label="Note on the current step" placeholder={`Note on "${current.title.slice(0, 40)}": what you did or found (no passwords)`} value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && note.trim()) run(async () => { await postJson(`/api/worklog/${current.id}/log`, { text: note }); setNote(""); }); }} />
                  <button className="btn" disabled={!note.trim()} onClick={() => run(async () => { await postJson(`/api/worklog/${current.id}/log`, { text: note }); setNote(""); })}>Add note</button>
                </div>
              )}
              <WorkTeam key={id} jobId={id} advice={["itsupport", "network", "security"].includes(field?.key ?? "")} />
              {o.ready_to_close && <p role="status" className="text-xs">Every step is done. You can close the job.</p>}
              <p className="text-xs text-muted">{help
                ? <>Keys (when not typing in a box): <kbd>T</kbd> timer · <kbd>D</kbd> done and next step · <kbd>N</kbd> note · <kbd>A</kbd> add step · <kbd>C</kbd> close job · <kbd>Esc</kbd> leave a box · <kbd>?</kbd> hide this</>
                : <>Press <kbd>?</kbd> for one-key shortcuts.</>}</p>
              <div className="space-y-2 border-t border-line pt-2">
                <fieldset className="flex flex-wrap items-center gap-3">
                  <legend className="sr-only">What to invoice</legend>
                  <label className="flex items-center gap-1"><input type="radio" name="jb-bill" checked={bill === "time"} onChange={() => setBill("time")} /> Unbilled hours ({usd(o.unbilled_amount)})</label>
                  <label className="flex items-center gap-1"><input type="radio" name="jb-bill" checked={bill === "quote"} onChange={() => setBill("quote")} /> Quoted price{o.job.quote ? ` (${usd(o.job.quote)})` : " (none set)"}</label>
                  <label className="flex items-center gap-1"><input type="radio" name="jb-bill" checked={bill === "none"} onChange={() => setBill("none")} /> Just close it</label>
                </fieldset>
                {!confirm ? <button className="btn" onClick={() => setConfirm(true)}>Close job…</button> : (
                  <div className="flex flex-wrap items-center gap-2">
                    <span>Stops the timer, marks steps done{bill !== "none" ? ", makes a draft invoice" : ""}. Nothing is sent to the client.</span>
                    <button className="btn btn-primary" onClick={close}>Yes, close it</button>
                    <button className="btn" onClick={() => setConfirm(false)}>Cancel</button>
                  </div>
                )}
              </div>
            </>
          )}
          {(done || closed) && (
            <div className="flex flex-wrap items-center gap-2">
              {closed && <p role="status">{closed}</p>}
              <button className="btn" onClick={() => downloadFile(`/api/jobs/${id}/summary.pdf`, `job-summary-${id}.pdf`).catch((e) => setErr(errMsg(e, "Download failed")))}>Client summary (PDF)</button>
              <button className="btn" onClick={() => { setId(null); setClosed(null); }}>Unpin</button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
