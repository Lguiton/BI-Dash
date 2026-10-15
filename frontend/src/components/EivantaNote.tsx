"use client";
import { useEffect, useState } from "react";
import { errMsg, Section } from "@/components/panels/kit";
import { API_BASE, apiFetch, deleteJson, getJson, postJson } from "@/lib/api";

type N = { id: number; tag: string; tag_label: string; text: string; at: string; sample: boolean };

/** One line after a job: what did this client's data or questions teach you for Eivanta? Client names are removed when it is saved. */
export function EivantaNote({ jobId }: { jobId: number }) {
  const [notes, setNotes] = useState<N[]>([]);
  const [tags, setTags] = useState<Record<string, string>>({});
  const [tag, setTag] = useState("ingestion");
  const [text, setText] = useState("");
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJson<{ notes: N[]; tags: Record<string, string> }>(`/api/auto/eivanta-notes?job_id=${jobId}`).then((r) => { if (live) { setNotes(r.notes); setTags(r.tags); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load notes.")); });
    return () => { live = false; };
  }, [jobId, tick]);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't save.")); }
  }
  async function download() {
    try {
      const r = await apiFetch(`${API_BASE}/api/auto/eivanta-notes/export`);
      if (!r.ok) throw new Error("Export failed");
      const url = URL.createObjectURL(new Blob([await r.text()], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url; a.download = "learned-for-eivanta.md"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErr(errMsg(e, "Couldn't download the notes.")); }
  }
  return (
    <Section title="Learned for Eivanta" note="One line on what this job taught you for the product you sell. Client names are removed when you save it. Use client data in Eivanta testing only with their permission.">
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Note type" className="input" value={tag} onChange={(e) => setTag(e.target.value)}>{Object.entries(tags).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <input aria-label="Learned for Eivanta" className="input min-w-56 flex-1" maxLength={300} placeholder="e.g. Dates came as text like 3rd Oct" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && text.trim()) run(async () => { await postJson("/api/auto/eivanta-notes", { job_id: jobId, tag, text }); setText(""); }); }} />
        <button className="btn" disabled={!text.trim()} onClick={() => run(async () => { await postJson("/api/auto/eivanta-notes", { job_id: jobId, tag, text }); setText(""); })}>Add</button>
        <button className="btn" onClick={download}>Download all notes</button>
      </div>
      <ul className="mt-2 space-y-1 text-sm">
        {notes.map((n) => <li key={n.id} className="flex flex-wrap items-center gap-2"><span className="text-xs text-muted">{n.tag_label} · {n.at}{n.sample ? " · sample" : ""}</span><span>{n.text}</span><button className="text-xs text-red-600 underline" onClick={() => run(() => deleteJson(`/api/auto/eivanta-notes/${n.id}`))}>Delete</button></li>)}
        {notes.length === 0 && <li className="text-xs text-muted">No notes for this job yet.</li>}
      </ul>
    </Section>
  );
}
