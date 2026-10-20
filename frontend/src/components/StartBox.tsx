"use client";
import { useEffect, useState } from "react";
import { errMsg } from "@/components/panels/kit";
import { getJson, postJson } from "@/lib/api";

type Fld = { key: string; label: string };

export function StartBox({ onStarted }: { onStarted: (id: number) => void }) {
  const [text, setText] = useState("");
  const [client, setClient] = useState("");
  const [field, setField] = useState("");
  const [fields, setFields] = useState<Fld[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<{ fields: Fld[] }>("/api/jobs/fields/list").then((r) => setFields(r.fields)).catch(() => {}); }, []);
  async function go() {
    setBusy(true); setErr(null);
    try { const r = await postJson<{ job_id: number }>("/api/workroom/begin", { request: text, client, field: field || null }); onStarted(r.job_id); }
    catch (e) { setErr(errMsg(e, "Couldn't start the job.")); } finally { setBusy(false); }
  }
  return (
    <section className="card space-y-2 p-3" aria-label="Start a job from pasted text">
      <h2 className="text-base font-semibold">Paste the client&apos;s issue, or say what to build or fix</h2>
      <p className="text-xs text-muted">No field knowledge needed. The app picks the field, makes the job and its ordered steps, and the agents do them. Nothing is sent to anyone.</p>
      <textarea className="input w-full" rows={6} aria-label="Client message or request" placeholder={'Paste an email or message from the client, or type: "Build a form that saves feedback to a database" / "Fix the office Wi-Fi that keeps dropping"'} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs">Client (optional)<input className="input mt-1 block" value={client} onChange={(e) => setClient(e.target.value)} placeholder="Found in the message if blank" /></label>
        <label className="text-xs">Field (optional)
          <select className="input mt-1 block" value={field} onChange={(e) => setField(e.target.value)}>
            <option value="">Pick it for me</option>
            {fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
        </label>
        <button className="btn btn-primary" disabled={busy || text.trim().length < 5} onClick={go}>{busy ? "Setting up…" : "Start the job"}</button>
      </div>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
    </section>
  );
}
