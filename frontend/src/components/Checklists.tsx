"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Badge, errMsg } from "@/components/panels/kit";

type Item = { id: string; text: string; why: string };
type Tpl = { id: string; title: string; field: string; source: string; when: string; total: number; sections: { title: string; items: Item[] }[] };
type Mine = { template_id: string; title: string; checked: string[]; notes: string; started: string; total: number; done: number };

function Sections({ t, checked, onToggle }: { t: Tpl; checked?: Set<string>; onToggle?: (id: string) => void }) {
  return (
    <div className="space-y-3">
      {t.sections.map((s) => (
        <div key={s.title} className="space-y-1">
          <h4 className="text-xs font-semibold text-muted">{s.title}</h4>
          <ul className="space-y-1">
            {s.items.map((i) => (
              <li key={i.id} className="text-sm">
                <label className="flex items-start gap-2">
                  {onToggle ? <input type="checkbox" className="mt-1" checked={checked?.has(i.id) ?? false} onChange={() => onToggle(i.id)} aria-label={i.text} /> : <span aria-hidden className="mt-1 inline-block h-3 w-3 shrink-0 rounded-sm border border-line" />}
                  <span><span className={checked?.has(i.id) ? "text-muted line-through" : ""}>{i.text}</span>{i.why && <span className="block text-xs text-muted">{i.why}</span>}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Active({ jobId, t, m, onChanged }: { jobId: number; t: Tpl; m: Mine; onChanged: () => void }) {
  const [notes, setNotes] = useState(m.notes);
  const [err, setErr] = useState<string | null>(null);
  const [sure, setSure] = useState(false);
  const [saved, setSaved] = useState(false);
  const checked = new Set(m.checked);
  async function toggle(id: string) {
    const next = new Set(checked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setErr(null);
    try { await putJson(`/api/checklists/job/${jobId}/${t.id}`, { checked: [...next] }); onChanged(); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  }
  async function saveNotes() {
    setErr(null); setSaved(false);
    try { await putJson(`/api/checklists/job/${jobId}/${t.id}`, { notes }); setSaved(true); onChanged(); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  }
  async function remove() {
    try { await deleteJson(`/api/checklists/job/${jobId}/${t.id}`); onChanged(); } catch (e) { setErr(errMsg(e, "Couldn't remove it.")); }
  }
  return (
    <details open className="rounded-md border border-line p-3">
      <summary className="cursor-pointer text-sm font-medium">{t.title} <Badge tone={m.done === m.total ? "ok" : "muted"}>{m.done} of {m.total}</Badge></summary>
      <div className="mt-3 space-y-3">
        {err && <ErrorBanner message={err} />}
        <Sections t={t} checked={checked} onToggle={toggle} />
        <label className="flex flex-col gap-1 text-xs text-muted">Notes for this checklist (passwords and keys are blanked)
          <textarea aria-label={`Notes for ${t.title}`} className="input min-h-20" maxLength={2000} value={notes} onChange={(e) => { setNotes(e.target.value); setSaved(false); }} /></label>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={saveNotes}>Save notes</button>
          <button className="btn" onClick={() => window.print()}>Print</button>
          <button className="btn" onClick={() => downloadFile(`/api/checklists/job/${jobId}/${t.id}/pdf`, `${t.id}-checklist.pdf`).catch((e) => setErr(errMsg(e, "Download failed.")))}>Download PDF</button>
          {!sure ? <button className="btn" onClick={() => setSure(true)}>Remove from this job</button>
            : <span className="flex items-center gap-2 text-sm">Remove this checklist and its ticks? <button className="btn" onClick={remove}>Yes, remove</button><button className="btn" onClick={() => setSure(false)}>Keep it</button></span>}
          {saved && <span role="status" className="text-xs text-emerald-600">Saved.</span>}
        </div>
      </div>
    </details>
  );
}

/** On a job page: start a triage checklist and tick it off. */
export function JobChecklists({ jobId }: { jobId: number }) {
  const [tpls, setTpls] = useState<Tpl[]>([]);
  const [mine, setMine] = useState<Mine[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    Promise.all([getJson<{ templates: Tpl[] }>("/api/checklists"), getJson<{ lists: Mine[] }>(`/api/checklists/job/${jobId}`)])
      .then(([a, b]) => { if (live) { setTpls(a.templates); setMine(b.lists); setErr(null); } })
      .catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the checklists.")); });
    return () => { live = false; };
  }, [jobId, tick]);
  const started = new Set(mine.map((m) => m.template_id));
  async function start(id: string) {
    try { await postJson(`/api/checklists/job/${jobId}/${id}`, {}); setTick((n) => n + 1); } catch (e) { setErr(errMsg(e, "Couldn't start it.")); }
  }
  return (
    <section className="card space-y-3 p-4" aria-label="Triage checklists">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Triage checklists</h2><Link href="/checklists" className="text-xs underline">All checklists</Link></div>
      {err && <ErrorBanner message={err} />}
      {mine.map((m) => { const t = tpls.find((x) => x.id === m.template_id); return t ? <Active key={m.template_id} jobId={jobId} t={t} m={m} onChanged={() => setTick((n) => n + 1)} /> : null; })}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted">Start one:</span>
        {tpls.filter((t) => !started.has(t.id)).map((t) => <button key={t.id} className="btn" onClick={() => start(t.id)}>{t.title}</button>)}
        {tpls.length > 0 && started.size === tpls.length && <span className="text-xs text-muted">All three are on this job.</span>}
      </div>
    </section>
  );
}

/** The checklist library: read it, print it. */
export function ChecklistLibrary() {
  const [tpls, setTpls] = useState<Tpl[]>([]);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ templates: Tpl[]; note: string }>("/api/checklists").then((r) => { if (live) { setTpls(r.templates); setNote(r.note); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the checklists.")); });
    return () => { live = false; };
  }, []);
  const cur = tpls.find((t) => t.id === open) ?? null;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <p className="text-xs text-muted">{note} To tick items off, open a job and start a checklist there.</p>
      <div className="grid gap-3 md:grid-cols-3">
        {tpls.map((t) => (
          <button key={t.id} onClick={() => setOpen(t.id)} className={`card space-y-1 p-4 text-left text-sm ${open === t.id ? "border-accent" : ""}`} aria-label={`Open ${t.title}`}>
            <span className="block font-semibold">{t.title}</span>
            <span className="block text-xs text-muted">{t.field} · {t.total} steps</span>
            <span className="block">{t.when}</span>
          </button>
        ))}
      </div>
      {cur && (
        <section className="card space-y-3 p-4" aria-label={cur.title}>
          <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-base font-semibold">{cur.title}</h2><span className="flex gap-2"><button className="btn" onClick={() => window.print()}>Print</button><button className="btn" onClick={() => downloadFile(`/api/checklists/${cur.id}/pdf`, `${cur.id}-checklist.pdf`).catch((e) => setErr(errMsg(e, "Download failed.")))}>Download PDF</button></span></div>
          <Sections t={cur} />
          <p className="text-xs text-muted">{cur.source}</p>
        </section>
      )}
    </div>
  );
}
