"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, postJson } from "@/lib/api";

type Brief = { name: string; table: string | null; text: string; ask: string };

/** Shown on a dashboard you opened from Intake: the file you uploaded, and one click to have this dashboard's agent start on it. A draft you check; nothing is changed. */
export function WorkingFile({ runId, track }: { runId: string; track: string }) {
  const [b, setB] = useState<Brief | null>(null);
  const [ask, setAsk] = useState("");
  const [out, setOut] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [hide, setHide] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<Brief>(`/api/intake/${encodeURIComponent(runId)}/brief?track=${encodeURIComponent(track)}`)
      .then((r) => { if (live) { setB(r); setAsk(r.ask); } })
      .catch((e) => { if (live) setErr(errMsg(e, "Couldn't load your uploaded file.")); });
    return () => { live = false; };
  }, [runId, track]);
  if (hide) return null;
  const run = async () => {
    if (!b) return;
    setBusy(true); setErr(null);
    try { const r = await postJson<{ reply: string }>(`/api/agents/${track}/chat`, { message: ask.slice(0, 1200), history: [], source_text: b.text.slice(0, 12000) }); setOut(r.reply); }
    catch (e) { setErr(errMsg(e, "The agent couldn't answer.")); }
    setBusy(false);
  };
  const copy = async () => { if (!out) return; try { await navigator.clipboard.writeText(out); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* select the text instead */ } };
  return (
    <section className="card space-y-2 border-l-4 p-4" style={{ borderLeftColor: "var(--accent, #4f9d69)" }} aria-label="Your uploaded file">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">Your uploaded file is ready here</h2>
        {b && <Badge tone="ok">{b.name} dashboard</Badge>}
        <button className="ml-auto text-xs underline" onClick={() => setHide(true)}>Hide</button>
      </div>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      {b && (
        <>
          <p className="text-xs text-muted">{b.text.split("\n").slice(0, 2).join(" ")} {b.table && <Link href="/data" className="underline">Browse the table</Link>}</p>
          <label className="block text-xs">What should the agent do first?
            <textarea className="input mt-1 w-full" rows={2} value={ask} onChange={(e) => setAsk(e.target.value)} />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn btn-primary" disabled={busy || ask.trim().length < 2} onClick={run}>{busy ? "Working…" : "Start the work on this file"}</button>
            <span className="text-xs text-muted">A draft you check. The agent sees the columns and the first rows, with personal-data columns left out and secrets removed.</span>
          </div>
          {out && (
            <div className="space-y-1 rounded border border-line p-2" role="status">
              <pre className="whitespace-pre-wrap font-sans text-sm">{out}</pre>
              <button className="btn" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
