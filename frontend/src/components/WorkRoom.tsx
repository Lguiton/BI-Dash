"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, postFile, putJson } from "@/lib/api";
import { acceptFor, checkFile } from "@/lib/fileCheck";

type Check = { lang: string; status: "ok" | "warn" | "fail" | "skipped"; plain: string };
type Agent = { status: "ready" | "failed"; text: string; error?: string; model?: string; at: string; checks?: Check[] };
type Step = { id: number; title: string; done: boolean; agent: Agent | null };
type Ap = { file: string; error?: string; summary?: string; counts?: { ran: number; skipped: number; failed: number }; notes?: string[]; steps?: { id: string; title: string; status: string; plain: string; caveats: string[] }[] };
type View = {
  job: { id: number; title: string; status: string; field: { key: string; label: string; href: string } | null };
  request: string; instructions: string; steps: Step[]; autopilot: Ap | null; reply: { text: string } | null;
  run: { state: string; done: number; total: number; current: string; error?: string | null }; advice_only: boolean; disclaimer: string;
};
type Screen = "both" | "steps" | "agents";

/** The Work Room: the owner's ordered checklist on one screen, the agents' finished work on the other (or side by side). Agents never tick a step and never send anything. */
export function WorkRoom({ jobId }: { jobId: number }) {
  const [v, setV] = useState<View | null>(null);
  const [screen, setScreen] = useState<Screen>("both");
  const [err, setErr] = useState<string | null>(null);
  const [ins, setIns] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [starting, setStarting] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setV(await getJson<View>(`/api/workroom/${jobId}`)); setErr(null); } catch (e) { setErr(errMsg(e, "Couldn't load the Work Room.")); }
  }, [jobId]);
  useEffect(() => { let live = true; getJson<View>(`/api/workroom/${jobId}`).then((r) => { if (live) setV(r); }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the Work Room.")); }); return () => { live = false; }; }, [jobId]);
  const running = v?.run.state === "running" || starting;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => void load(), 2000);
    return () => clearInterval(t);
  }, [running, load]);

  async function start() {
    setStarting(true); setErr(null);
    try { await postFile<View>(`/api/workroom/${jobId}/run`, file ?? new File([], ""), { instructions: ins }); await load(); }
    catch (e) { setErr(errMsg(e, "The agents couldn't start.")); }
    finally { setStarting(false); }
  }
  async function tick(s: Step) {
    try { setV(await putJson<View>(`/api/workroom/${jobId}/steps/${s.id}`, { done: !s.done })); } catch (e) { setErr(errMsg(e, "Couldn't save that.")); }
  }
  async function copy(key: string, text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(key); setTimeout(() => setCopied(null), 1800); } catch { setErr("Couldn't copy. Select the text and press Ctrl+C."); }
  }
  if (!v) return err ? <p role="alert" className="text-sm text-red-600">{err}</p> : <p className="text-sm text-muted">Loading…</p>;
  const doneN = v.steps.filter((s) => s.done).length;
  const readyN = v.steps.filter((s) => s.agent?.status === "ready").length;
  const hasRun = readyN > 0 || v.autopilot != null;

  const checklist = (
    <section className="card space-y-2 p-3" aria-label="My checklist">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">My checklist</h2>
        <span className="text-xs text-muted">{doneN} of {v.steps.length} done by me</span>
      </div>
      <p className="text-xs text-muted">The steps in order. Only you tick them, after you have checked the work with your own tools.</p>
      <ol className="space-y-1" aria-label="Steps in order">
        {v.steps.map((s, i) => (
          <li key={s.id} className="flex items-start gap-2 rounded border border-line p-2">
            <input type="checkbox" className="mt-1" checked={s.done} onChange={() => void tick(s)} aria-label={`Done: ${s.title}`} />
            <div className="min-w-0 flex-1">
              <p className={s.done ? "text-muted line-through" : ""}><span className="font-mono text-xs text-muted">{i + 1}.</span> {s.title}</p>
              <p className="text-xs">
                {s.agent?.status === "ready" && <Badge tone="ok">agent finished it</Badge>}
                {s.agent?.status === "failed" && <Badge tone="bad">agent could not</Badge>}
                {!s.agent && running && <Badge tone="muted">waiting</Badge>}
                {!s.agent && !running && <Badge tone="muted">not run yet</Badge>}
                {s.agent && screen === "steps" && <button className="ml-2 underline" onClick={() => setScreen("both")}>See its work</button>}
              </p>
            </div>
          </li>
        ))}
        {v.steps.length === 0 && <li className="text-xs text-muted">This job has no steps yet.</li>}
      </ol>
      <p className="text-xs"><Link href={`/job?id=${v.job.id}`} className="underline">Open the full job page</Link> for the timer, notes, hours and closing.</p>
    </section>
  );

  const work = (
    <section className="card space-y-3 p-3" aria-label="Agents' work">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Agents&apos; work{v.job.field ? ` (${v.job.field.label})` : ""}</h2>
        {hasRun && <span className="text-xs text-muted">{readyN} of {v.steps.length} steps worked</span>}
      </div>
      <details open={!hasRun} className="space-y-2 text-sm">
        <summary className="cursor-pointer text-xs underline">The client&apos;s request and what to give the agents</summary>
        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 font-sans text-xs">{v.request || v.job.title}</pre>
        <input ref={ref} type="file" className="hidden" accept={acceptFor("anything")} aria-label="File for the agents" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (!f) return; const bad = checkFile(f, "anything"); setErr(bad); if (!bad) setFile(f); }} />
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={() => ref.current?.click()}><Upload className="h-4 w-4" aria-hidden /> {file ? "Change file" : "Add the client's file (optional)"}</button>
          {file && <span className="text-xs"><strong>{file.name}</strong></span>}
        </div>
        <input className="input w-full" aria-label="Anything the agents should know" placeholder="Optional: anything to focus on (no passwords)" value={ins} onChange={(e) => setIns(e.target.value)} />
      </details>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" disabled={running || v.steps.length === 0} onClick={start}>{running ? "Agents working…" : hasRun ? "Have the agents redo it" : "Have the agents do the whole job"}</button>
        {running && <span className="text-xs text-muted" role="status">{v.run.current}: {v.run.done} of {v.run.total}</span>}
      </div>
      {v.advice_only && <p className="text-xs text-muted">This field is hands-on, so the agents write the checklist, likely causes and what each result means. They can&apos;t see the equipment, so you do the checking.</p>}
      {(err || v.run.error) && <p role="alert" className="text-sm text-red-600">{err || v.run.error}</p>}

      {v.autopilot && (
        <div className="rounded border border-line p-2 text-sm">
          <p className="font-semibold">Automatic analysis of {v.autopilot.file}</p>
          {v.autopilot.error ? <p className="text-red-600">{v.autopilot.error}</p> : (
            <>
              <p>{v.autopilot.summary}</p>
              <p className="text-xs text-muted">{v.autopilot.counts?.ran} ran, {v.autopilot.counts?.skipped} skipped, {v.autopilot.counts?.failed} failed. {(v.autopilot.notes ?? []).join(" ")}</p>
              <details className="text-xs"><summary className="cursor-pointer underline">Every analysis, in plain English</summary>
                <ul className="mt-1 space-y-1">{v.autopilot.steps?.map((s) => <li key={s.id}><Badge tone={s.status === "ran" ? "ok" : s.status === "failed" ? "bad" : "muted"}>{s.status}</Badge> <strong>{s.title}</strong>: {s.plain}{s.caveats.length > 0 && <span className="text-muted"> Careful: {s.caveats.join(" ")}</span>}</li>)}</ul>
              </details>
            </>
          )}
        </div>
      )}

      <ol className="space-y-2" aria-label="Agent work by step">
        {v.steps.map((s, i) => (
          <li key={s.id} className="rounded border border-line p-2">
            <button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(open === s.id ? null : s.id)} aria-expanded={open === s.id}>
              <span><span className="font-mono text-xs text-muted">{i + 1}.</span> <strong>{s.title}</strong></span>
              <span className="text-xs">{s.agent?.status === "ready" ? <Badge tone="ok">ready</Badge> : s.agent?.status === "failed" ? <Badge tone="bad">failed</Badge> : <Badge tone="muted">{running ? "waiting" : "not run"}</Badge>}</span>
            </button>
            {s.agent?.status === "failed" && <p className="text-xs text-red-600">{s.agent.error}</p>}
            {s.agent?.status === "ready" && (open === s.id || v.steps.length <= 3) && (
              <div className="mt-2 space-y-1">
                <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 font-sans text-sm">{s.agent.text}</pre>
                {s.agent.checks?.map((c, k) => <p key={k} className="text-xs"><Badge tone={c.status === "ok" ? "ok" : c.status === "fail" ? "bad" : c.status === "warn" ? "warn" : "muted"}>{c.lang} {c.status === "ok" ? "checked" : c.status}</Badge> {c.plain}</p>)}
                <button className="btn" onClick={() => void copy(`s${s.id}`, s.agent!.text)}>{copied === `s${s.id}` ? "Copied" : "Copy"}</button>
              </div>
            )}
          </li>
        ))}
      </ol>

      {v.reply && (
        <div className="space-y-1 rounded border border-line p-2">
          <p className="font-semibold">Draft reply to the client (not sent)</p>
          <pre className="whitespace-pre-wrap font-sans text-sm">{v.reply.text}</pre>
          <button className="btn" onClick={() => void copy("reply", v.reply!.text)}>{copied === "reply" ? "Copied" : "Copy"}</button>
        </div>
      )}
      <p className="text-xs text-muted">{v.disclaimer}</p>
    </section>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden" role="tablist" aria-label="Screens">
        {([["both", "Side by side"], ["steps", "My checklist"], ["agents", "Agents' work"]] as [Screen, string][]).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={screen === k} className={`btn ${screen === k ? "btn-primary" : ""}`} onClick={() => setScreen(k)}>{label}</button>
        ))}
        <span className="text-sm font-semibold">{v.job.title}</span> <Badge tone={v.job.status === "done" ? "ok" : "warn"}>{v.job.status}</Badge>
      </div>
      <div className={screen === "both" ? "grid gap-4 lg:grid-cols-2" : "grid gap-4"}>
        {screen !== "agents" && checklist}
        {screen !== "steps" && work}
      </div>
    </div>
  );
}
