"use client";
import { useEffect, useState } from "react";
import { errMsg } from "@/components/panels/kit";
import { getJson, putJson } from "@/lib/api";

type L = { id: number; name: string; url: string; folder: string };
type St = { id: number; state: "up" | "down" | "none" | "not-checked" };
const LABEL: Record<string, string> = { up: "running", down: "not running", none: "", "not-checked": "not checked (not on this computer)" };

/** Quick links to Eivanta Analytics and Project AIDA. Open the app, copy its folder path, see whether it is running on this computer. */
export function ProjectLinks() {
  const [rows, setRows] = useState<L[]>([]);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(true);
  const [st, setSt] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    getJson<{ links: L[]; saved: boolean; note: string }>("/api/auto/links").then((r) => { if (live) { setRows(r.links); setNote(r.note); setSaved(r.saved); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load your links.")); });
    return () => { live = false; };
  }, []);

  const set = (i: number, k: keyof L, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  async function save() {
    setErr(null); setMsg(null);
    try { const r = await putJson<{ links: L[]; saved: boolean }>("/api/auto/links", { links: rows }); setRows(r.links); setSaved(true); setMsg("Saved."); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  }
  async function check() {
    setErr(null);
    try { const r = await getJson<{ status: St[] }>("/api/auto/links/status"); setSt(Object.fromEntries(r.status.map((x) => [x.id, x.state]))); } catch (e) { setErr(errMsg(e, "Couldn't check.")); }
  }
  async function copy(id: number, text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(id); setTimeout(() => setCopied(null), 2000); } catch { setErr("Couldn't copy. Select the path and copy it by hand."); }
  }
  return (
    <section className="card space-y-3 p-5" aria-label="Project links">
      <div>
        <h2 className="text-lg font-semibold">My projects</h2>
        <p className="text-sm text-muted">Quick links to Eivanta Analytics and Project AIDA. A browser page can&apos;t open a folder, so copy the path and paste it into File Explorer. {!saved && note}</p>
      </div>
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      <ul className="space-y-3">
        {rows.map((r, i) => (
          <li key={i} className="space-y-1 rounded border border-line p-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <input aria-label={`Link ${i + 1} name`} className="input w-56" value={r.name} onChange={(e) => set(i, "name", e.target.value)} />
              {r.url && <a className="btn" href={r.url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${r.name}`}>Open</a>}
              {r.folder && <button className="btn" onClick={() => copy(r.id, r.folder)} aria-label={`Copy folder path for ${r.name}`}>{copied === r.id ? "Copied" : "Copy folder path"}</button>}
              {st[r.id] && LABEL[st[r.id]] && <span className={`text-xs ${st[r.id] === "up" ? "text-emerald-600" : "text-muted"}`}>● {LABEL[st[r.id]]}</span>}
              <button className="text-xs text-red-600 underline" onClick={() => setRows(rows.filter((_, j) => j !== i))}>Remove</button>
            </div>
            <div className="flex flex-wrap gap-2">
              <input aria-label={`Link ${i + 1} address`} className="input min-w-56 flex-1" placeholder="http://localhost:8501" value={r.url} onChange={(e) => set(i, "url", e.target.value)} />
              <input aria-label={`Link ${i + 1} folder`} className="input min-w-56 flex-1" placeholder="C:\Users\Guito\project-folder" value={r.folder} onChange={(e) => set(i, "folder", e.target.value)} />
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={() => setRows([...rows, { id: 0, name: "", url: "", folder: "" }])} disabled={rows.length >= 12}>Add a link</button>
        <button className="btn" onClick={save}>Save links</button>
        <button className="btn" onClick={check}>Check what is running</button>
        {msg && <span role="status" className="text-xs text-muted">{msg}</span>}
      </div>
    </section>
  );
}
