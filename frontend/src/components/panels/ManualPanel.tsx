"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, putJson } from "@/lib/api";
import type { Manual, ManualStep } from "@/lib/types";
import { QuizSection } from "./OpsPanels";
import { errMsg } from "./kit";

export function ManualPanel({ track, focus, onGo, onAsk }: { track: string; focus?: string; onGo: (tool: NonNullable<ManualStep["tool"]>) => void; onAsk: (s: ManualStep) => void }) {
  const [m, setM] = useState<Manual | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Manual>(`/api/manuals/${track}`, ctl.signal).then((r) => { setM(r); setOpen(focus && r.steps.some((s) => s.id === focus) ? focus : r.steps.find((s) => !r.done.includes(s.id))?.id ?? r.steps[0].id); })
      .catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the manual.")); });
    return () => ctl.abort();
  }, [track, focus]);
  useEffect(() => { if (open) document.getElementById(`step-${open}`)?.scrollIntoView?.({ block: "nearest" }); }, [open]);
  if (err) return <ErrorBanner message={err} />;
  if (!m) return <p className="text-sm text-muted">Loading the manual…</p>;
  const tick = async (s: ManualStep, done: boolean) => {
    try {
      const r = await putJson<Manual>(`/api/manuals/${track}/steps/${s.id}`, { done });
      setM(r);
      if (done) { const nxt = r.steps.find((x) => !r.done.includes(x.id)); if (nxt) setOpen(nxt.id); }
    } catch (e) { setErr(errMsg(e, "Couldn't save that tick.")); }
  };
  const pct = Math.round((100 * m.done.length) / m.steps.length);
  return (
    <div className="space-y-4">
      <section className="card space-y-2 p-5">
        <h2 className="text-base font-semibold">{m.title}</h2>
        <p className="text-sm">{m.intro}</p>
        <p className="text-sm"><b>You finish with:</b> {m.outcome}</p>
        <div className="flex items-center gap-3 text-xs text-muted">
          <div className="h-2 flex-1 rounded bg-panel2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Manual progress"><div className="h-2 rounded bg-accent" style={{ width: `${pct}%` }} /></div>
          {m.done.length}/{m.steps.length} steps ticked
        </div>
        <p className="text-xs text-muted">Ticking is your own record: the app doesn&apos;t check it. The Company page detects progress from your data.</p>
      </section>
      <ol className="space-y-2">
        {m.steps.map((s, i) => {
          const isDone = m.done.includes(s.id), isOpen = open === s.id;
          return (
            <li key={s.id} id={`step-${s.id}`} className="card min-w-0">
              <div className="flex items-start gap-3 p-4">
                <input type="checkbox" className="mt-1" checked={isDone} aria-label={`Step ${i + 1} done: ${s.title}`} onChange={(e) => tick(s, e.target.checked)} />
                <button className="min-w-0 flex-1 text-left" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : s.id)}>
                  <span className="text-xs text-muted">Step {i + 1}</span>
                  <span className={`block text-sm font-semibold ${isDone ? "text-muted line-through" : ""}`}>{s.title}</span>
                  {!isOpen && <span className="block truncate text-xs text-muted">{s.what}</span>}
                </button>
              </div>
              {isOpen && (
                <div className="space-y-3 border-t border-line p-4 text-sm">
                  <p>{s.what}</p>
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-muted">How</h4>
                    <ol className="mt-1 list-decimal space-y-1 pl-5">{s.how.map((h) => <li key={h}>{h}</li>)}</ol></div>
                  <p><b>Done when:</b> {s.done_when}</p>
                  <div><h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Common mistakes</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5">{s.mistakes.map((h) => <li key={h}>{h}</li>)}</ul></div>
                  <div className="flex flex-wrap gap-2">
                    {s.tool && <button className="btn btn-primary" onClick={() => onGo(s.tool!)}>Open: {s.tool.label}</button>}
                    <button className="btn" onClick={() => onAsk(s)}>Ask the agent about this step</button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <QuizSection track={track} onReview={(sid) => { setOpen(sid); }} />
    </div>
  );
}
