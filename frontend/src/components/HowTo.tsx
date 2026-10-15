"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { Badge, errMsg, Field } from "@/components/panels/kit";

export type Video = {
  id: number; title: string; field: string; job_type: string; kind: "youtube" | "vimeo" | "page";
  url: string; embed: string; chapters: { t: number; label: string }[]; notes: string; watched: boolean; rewatch: boolean;
};
type Lib = { videos: Video[]; fields: string[]; watched: number; total: number; note: string };

const mmss = (t: number) => `${Math.floor(t / 3600) ? `${Math.floor(t / 3600)}:` : ""}${String(Math.floor((t % 3600) / 60)).padStart(Math.floor(t / 3600) ? 2 : 1, "0")}:${String(t % 60).padStart(2, "0")}`;
const KIND: Record<string, string> = { youtube: "YouTube", vimeo: "Vimeo", page: "Web page" };

/** Turns lines like "1:05 Remove the bezel" into chapters, and back. */
function parseChapters(text: string): { t: string; label: string }[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const m = /^(\d+(?::\d{2}){1,2})\s+(.+)$/.exec(l);
    return m ? { t: m[1], label: m[2] } : { t: "", label: l };
  });
}
const chaptersText = (v: Video) => v.chapters.map((c) => `${mmss(c.t)} ${c.label}`).join("\n");

/** Where a chapter opens: YouTube and Vimeo jump to the time, a plain web page just opens. */
function openAt(v: Video, t: number): string {
  if (v.kind === "youtube") return `https://www.youtube.com/watch?v=${v.embed.split("/embed/")[1]}${t ? `&t=${t}s` : ""}`;
  if (v.kind === "vimeo") return `${v.url.split("#")[0]}${t ? `#t=${t}s` : ""}`;
  return v.url;
}

function Lesson({ v, fields, onChanged, onGone }: { v: Video; fields: string[]; onChanged: () => void; onGone: () => void }) {
  const [notes, setNotes] = useState(v.notes);
  const [chap, setChap] = useState(chaptersText(v));
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [sure, setSure] = useState(false);

  async function patch(body: Record<string, unknown>, ok?: string) {
    setErr(null); setMsg(null);
    try { await putJson(`/api/howto/${v.id}`, body); if (ok) setMsg(ok); onChanged(); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  }
  async function remove() {
    try { await deleteJson(`/api/howto/${v.id}`); onGone(); } catch (e) { setErr(errMsg(e, "Couldn't remove it.")); }
  }
  return (
    <section className="space-y-3" aria-label="Lesson">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">{v.title}</h2>
        <Badge>{v.field}</Badge><Badge>{KIND[v.kind]}</Badge>
        {v.watched && <Badge tone="ok">Watched</Badge>}{v.rewatch && <Badge tone="warn">Watch again</Badge>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <a href={v.url} target="_blank" rel="noopener noreferrer" className="btn btn-primary w-fit">Watch on {v.kind === "page" ? "its website" : KIND[v.kind]} (opens a new tab)</a>
        <span className="text-xs text-muted">Nothing is downloaded or stored here, only the link.</span>
      </div>
      {v.chapters.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Chapters">
          {v.chapters.map((c) => v.kind === "page"
            ? <span key={`${c.t}-${c.label}`} className="rounded-md border border-line px-3 py-1 text-sm">{mmss(c.t)} {c.label}</span>
            : <a key={`${c.t}-${c.label}`} className="btn" href={openAt(v, c.t)} target="_blank" rel="noopener noreferrer">{mmss(c.t)} {c.label}</a>)}
        </div>
      )}
      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={v.watched} onChange={(e) => patch({ watched: e.target.checked })} />I watched this</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={v.rewatch} onChange={(e) => patch({ rewatch: e.target.checked })} />Watch again</label>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="My notes (passwords and keys are blanked)"><textarea aria-label="My notes" className="input min-h-28" maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <Field label="Chapters, one per line like 1:05 Remove the bezel"><textarea aria-label="Chapters" className="input min-h-28" value={chap} onChange={(e) => setChap(e.target.value)} /></Field>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" onClick={() => patch({ notes, chapters: parseChapters(chap) }, "Saved.")}>Save notes and chapters</button>
        <label className="flex items-center gap-2 text-xs text-muted">Field
          <select aria-label="Field" className="input" value={v.field} onChange={(e) => patch({ field: e.target.value })}>
            {[...new Set([...fields, v.field])].map((f) => <option key={f}>{f}</option>)}
          </select></label>
        {!sure ? <button className="btn" onClick={() => setSure(true)}>Remove</button> : (
          <span className="flex items-center gap-2 text-sm">Remove this lesson from the library? <button className="btn" onClick={remove}>Yes, remove</button><button className="btn" onClick={() => setSure(false)}>Keep it</button></span>
        )}
        {msg && <span role="status" className="text-xs text-emerald-600">{msg}</span>}
      </div>
    </section>
  );
}

function AddVideo({ fields, onAdded }: { fields: string[]; onAdded: (id: number) => void }) {
  const [f, setF] = useState({ title: "", url: "", field: "", job_type: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const field = f.field || fields[0] || "Other";
  async function go() {
    setErr(null); setBusy(true);
    try {
      const v = await postJson<Video>("/api/howto/link", { title: f.title, url: f.url, field, job_type: f.job_type });
      setF({ title: "", url: "", field: "", job_type: "" }); onAdded(v.id);
    } catch (e) { setErr(errMsg(e, "Couldn't add it.")); } finally { setBusy(false); }
  }
  return (
    <section className="card space-y-3 p-4" aria-label="Add a video">
      <h2 className="text-sm font-semibold">Add a video link</h2>
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Title"><input aria-label="Video title" className="input" maxLength={120} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Field"><select aria-label="Video field" className="input" value={field} onChange={(e) => setF({ ...f, field: e.target.value })}>{fields.map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Video link (YouTube, Vimeo or any web page)"><input aria-label="Video link" className="input" placeholder="https://" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} /></Field>
        <Field label="Job type (optional, helps match it to jobs)"><input aria-label="Job type" className="input" maxLength={80} placeholder="Laptop screen replacement" value={f.job_type} onChange={(e) => setF({ ...f, job_type: e.target.value })} /></Field>
      </div>
      <button className="btn btn-primary" disabled={!f.title.trim() || !f.url.trim() || busy} onClick={go}>{busy ? "Adding…" : "Add to library"}</button>
    </section>
  );
}

/** The how-to library: pick a lesson, watch it, keep notes. */
export function HowToLibrary({ initialId }: { initialId: number | null }) {
  const [lib, setLib] = useState<Lib | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [pick, setPick] = useState<number | null>(initialId);
  const [field, setField] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    let live = true;
    getJson<Lib>("/api/howto").then((r) => { if (live) { setLib(r); setErr(null); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the library.")); });
    return () => { live = false; };
  }, [tick]);
  const shown = useMemo(() => (lib?.videos ?? []).filter((v) => (!field || v.field === field) && (!q.trim() || `${v.title} ${v.job_type}`.toLowerCase().includes(q.trim().toLowerCase()))), [lib, field, q]);
  const cur = lib?.videos.find((v) => v.id === pick) ?? null;
  const used = useMemo(() => [...new Set((lib?.videos ?? []).map((v) => v.field))], [lib]);
  const byField = used.filter((f) => shown.some((v) => v.field === f));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} onRetry={() => setTick((t) => t + 1)} />}
      {lib && (
        <>
          <p className="text-xs text-muted">{lib.total ? `${lib.watched} of ${lib.total} watched. ` : ""}{lib.note}</p>
          <AddVideo fields={lib.fields} onAdded={(id) => { setPick(id); setTick((t) => t + 1); }} />
          {lib.total === 0 && <p className="text-sm">No lessons yet. Paste a video link above.</p>}
          {lib.total > 0 && (
            <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
              <aside className="space-y-3" aria-label="Lessons">
                <input aria-label="Search lessons" className="input w-full" placeholder="Search lessons" value={q} onChange={(e) => setQ(e.target.value)} />
                <div className="flex flex-wrap gap-1" role="tablist" aria-label="Fields">
                  <button role="tab" aria-selected={!field} className={`btn ${!field ? "btn-primary" : ""}`} onClick={() => setField("")}>All</button>
                  {used.map((f) => <button key={f} role="tab" aria-selected={field === f} className={`btn ${field === f ? "btn-primary" : ""}`} onClick={() => setField(f)}>{f}</button>)}
                </div>
                {shown.length === 0 && <p className="text-sm text-muted">Nothing matches.</p>}
                {byField.map((f) => (
                  <div key={f} className="space-y-1">
                    <h3 className="text-xs font-semibold text-muted">{f}</h3>
                    <ul className="space-y-1">
                      {shown.filter((v) => v.field === f).map((v) => (
                        <li key={v.id}>
                          <button className={`w-full rounded-md border px-3 py-2 text-left text-sm ${pick === v.id ? "border-accent" : "border-line"}`} onClick={() => setPick(v.id)} aria-label={`Watch ${v.title}`}>
                            <span className="block font-medium">{v.title}</span>
                            <span className="text-xs text-muted">{KIND[v.kind]}{v.watched ? " · watched" : ""}{v.rewatch ? " · watch again" : ""}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </aside>
              <div>{cur ? <Lesson key={cur.id} v={cur} fields={lib.fields} onChanged={() => setTick((t) => t + 1)} onGone={() => { setPick(null); setTick((t) => t + 1); }} /> : <p className="text-sm text-muted">Pick a lesson, then open it in a new tab.</p>}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** On a job page: lessons that look related to the job. */
export function JobVideos({ jobId }: { jobId: number }) {
  const [vids, setVids] = useState<Video[]>([]);
  useEffect(() => {
    let live = true;
    getJson<{ videos: Video[] }>(`/api/howto/for-job/${jobId}`).then((r) => { if (live) setVids(r.videos); }).catch(() => { if (live) setVids([]); });
    return () => { live = false; };
  }, [jobId]);
  return (
    <section className="card space-y-2 p-4" aria-label="How-to videos">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">How-to videos</h2><Link href="/howto" className="text-xs underline">All lessons</Link></div>
      {vids.length === 0
        ? <p className="text-sm text-muted">No lesson matches this job yet. <Link href="/howto" className="underline">Add one</Link> and give it a job type that shares a word with the job title.</p>
        : <ul className="space-y-1 text-sm">{vids.map((v) => <li key={v.id}><Link href={`/howto?v=${v.id}`} className="underline">{v.title}</Link> <span className="text-xs text-muted">{v.field}{v.watched ? " · watched" : ""}</span></li>)}</ul>}
    </section>
  );
}
