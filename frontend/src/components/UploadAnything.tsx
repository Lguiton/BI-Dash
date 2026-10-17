"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Badge, errMsg } from "@/components/panels/kit";
import { postFile, postJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";

type Finding = { severity: string; title: string; detail: string; advice: string };
type Ev = { events: number; distinct_ids: number; findings: Finding[]; table: { id: number; count: number; meaning: string }[]; caveat: string };
type Kind = "event" | "business" | "text";
const TEXT_EXT = /\.(csv|txt|log|json|tsv|md)$/i;
const DOC_EXT = /\.(xlsx|xlsm|pdf|docx)$/i;
const norm = (h: string) => h.trim().toLowerCase().replace(/[\s-]+/g, "_");

function decode(buf: ArrayBuffer): string {
  const b = new Uint8Array(buf);
  const utf16 = (b[0] === 0xff && b[1] === 0xfe) || (b[0] === 0xfe && b[1] === 0xff);
  return new TextDecoder(utf16 ? "utf-16" : "utf-8").decode(buf);
}
function sniff(text: string): Kind {
  const head = (text.split(/\r?\n/, 1)[0] ?? "").split(/[,\t;]/).map(norm);
  if (head.includes("record_date") && head.includes("entity_id")) return "business";
  if (head.some((h) => h === "event_id" || h === "eventid") || (head.includes("id") && head.some((h) => h === "level" || h === "source"))) return "event";
  return "text";
}

/** One upload button for every page. It looks at the file and sends it to the right reader; nothing is stored and nothing changes your data. */
export function UploadAnything() {
  const path = usePathname();
  const [jobId] = useActiveJob();
  const ref = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Kind | null>(null);
  const [text, setText] = useState("");
  const [ev, setEv] = useState<Ev | null>(null);
  const [ask, setAsk] = useState("What is in this file? List anything that looks wrong or important and what to do next.");
  const [out, setOut] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const track = /^\/tracks\/([a-z]+)/.exec(path)?.[1] ?? "itsupport";

  async function pick(f: File) {
    setErr(null); setEv(null); setOut(null); setKind(null); setText(""); setName(f.name); setBusy(true);
    try {
      if (/\.evtx$/i.test(f.name)) { setErr("An .evtx file is binary. In Event Viewer choose Action, Save All Events As, and pick CSV, then upload that."); return; }
      if (!TEXT_EXT.test(f.name) && !DOC_EXT.test(f.name)) { setErr("This button reads Excel, PDF, Word, csv, tsv, txt, log, json and md files."); return; }
      if (f.size > 25 * 1024 * 1024) { setErr("That file is over 25 MB. Export a smaller slice."); return; }
      let t: string;
      if (DOC_EXT.test(f.name)) {
        const r = await postFile<{ text: string; note: string }>("/api/files/text", f);
        t = r.text; setNote(r.note);
      } else { t = decode(await f.arrayBuffer()); setNote(""); }
      const k = sniff(t);
      setKind(k); setText(t.slice(0, 12000));
      if (k === "event") setEv(await postFile<Ev>("/api/it/events/upload", f));
    } catch (e) { setErr(errMsg(e, "Couldn't read that file.")); } finally { setBusy(false); }
  }
  async function askAgent() {
    setErr(null); setBusy(true); setOut(null);
    try {
      const evNote = ev ? `Event log read: ${ev.events} events. Findings: ${ev.findings.map((x) => x.title).join("; ") || "none"}. Top IDs: ${ev.table.slice(0, 6).map((t) => `${t.id} x${t.count} (${t.meaning})`).join("; ")}.\n` : "";
      const r = await postJson<{ reply: string }>(`/api/agents/${track}/chat`, { message: ask.slice(0, 1200), history: [], source_text: (evNote + text).slice(0, 12000), job_id: jobId });
      setOut(r.reply);
    } catch (e) { setErr(errMsg(e, "The agent couldn't answer.")); } finally { setBusy(false); }
  }

  return (
    <div className="print:hidden">
      <input ref={ref} type="file" accept=".csv,.tsv,.txt,.log,.json,.md,.evtx,.xlsx,.xlsm,.pdf,.docx" className="hidden" aria-label="Upload a file" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) { setOpen(true); void pick(f); } }} />
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={() => ref.current?.click()}><Upload className="h-4 w-4" aria-hidden /> Upload a file</button>
        {open && <button className="text-xs underline" onClick={() => setOpen(false)}>Hide</button>}
        {!open && <span className="text-xs text-muted">Excel, PDF, Word, event logs, CSVs and notes. It picks the right reader.</span>}
      </div>
      {open && (
        <div className="card mt-2 space-y-2 p-3 text-sm" aria-label="Uploaded file">
          {name && <p><strong>{name}</strong> {kind === "event" && <Badge tone="ok">Windows event log</Badge>} {kind === "business" && <Badge tone="warn">business data</Badge>} {kind === "text" && <Badge tone="muted">text file</Badge>}</p>}
          {busy && <p className="text-muted">Reading…</p>}
          {note && <p className="text-xs text-muted">{note}</p>}
          {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
          {kind === "business" && <p>This is business data (dates, entities, revenue). Import it from the Import box on <Link href="/" className="underline">Home</Link>, where you can see the checks first.</p>}
          {ev && (
            <div className="space-y-2">
              <p>{ev.events.toLocaleString()} events, {ev.distinct_ids} distinct IDs. <Link href="/tracks/itsupport" className="underline">More in IT, Events tab</Link></p>
              {ev.findings.length === 0 ? <p className="text-muted">No notable patterns.</p> : (
                <ul className="space-y-1">{ev.findings.slice(0, 6).map((x, i) => <li key={i} className="rounded border border-line p-2"><Badge tone={x.severity === "high" ? "bad" : x.severity === "medium" ? "warn" : "muted"}>{x.severity}</Badge> <strong>{x.title}</strong><div className="text-xs text-muted">{x.detail}</div><div className="text-xs">{x.advice}</div></li>)}</ul>
              )}
            </div>
          )}
          {kind && kind !== "business" && (
            <div className="space-y-2 border-t border-line pt-2">
              <label className="block text-xs">Ask the {track} agent about this file (a draft you check; the first 12,000 characters are sent, with secrets removed)
                <textarea className="input mt-1 w-full" rows={2} value={ask} onChange={(e) => setAsk(e.target.value)} />
              </label>
              <button className="btn" disabled={busy || ask.trim().length < 2} onClick={askAgent}>{busy ? "Working…" : "Get agent output"}</button>
              {out && (
                <div className="space-y-1 rounded border border-line p-2" role="status">
                  <pre className="whitespace-pre-wrap font-sans text-sm">{out}</pre>
                  <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(out); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setErr("Couldn't copy. Select the text and copy it by hand."); } }}>{copied ? "Copied" : "Copy output"}</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
