"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, putJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Field, Section, errMsg } from "@/components/panels/kit";

type Dev = { name: string; kind: string; where: string; model: string; address: string; notes: string };
type Notes = { client: string; network: string; issues: string; notes: string; devices: Dev[]; kinds: string[]; masked?: number };
const blank = (): Dev => ({ name: "", kind: "computer", where: "", model: "", address: "", notes: "" });

/** What you need on a repeat visit: devices, how the network is laid out, problems that come back. Secrets are blanked when you save. */
export function ClientNotes({ clientId }: { clientId: number }) {
  const [n, setN] = useState<Notes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<Notes>(`/api/client-notes/${clientId}`).then((r) => { if (live) { setN(r); setMsg(null); } }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the site notes.")); });
    return () => { live = false; };
  }, [clientId]);
  if (!n) return err ? <ErrorBanner message={err} /> : null;
  const setDev = (i: number, k: keyof Dev, v: string) => setN({ ...n, devices: n.devices.map((d, j) => (j === i ? { ...d, [k]: v } : d)) });
  async function save() {
    if (!n) return;
    setErr(null);
    try {
      const r = await putJson<Notes>(`/api/client-notes/${clientId}`, { network: n.network, issues: n.issues, notes: n.notes, devices: n.devices });
      setN(r);
      setMsg(r.masked ? `Saved. ${r.masked} password or key${r.masked === 1 ? " was" : "s were"} blanked: keep real logins in a password manager.` : "Saved.");
    } catch (e) { setErr(errMsg(e, "Could not save.")); }
  }
  return (
    <Section title="Site notes" note="For repeat visits. No passwords here: anything that looks like one is blanked when you save.">
      {err && <ErrorBanner message={err} />}
      <div className="space-y-3 text-sm">
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase text-muted">Devices</h4>
          {n.devices.map((d, i) => (
            <div key={i} className="grid gap-2 md:grid-cols-6">
              <input aria-label={`Device ${i + 1} name`} className="input" placeholder="Name" value={d.name} onChange={(e) => setDev(i, "name", e.target.value)} />
              <select aria-label={`Device ${i + 1} kind`} className="input" value={d.kind} onChange={(e) => setDev(i, "kind", e.target.value)}>{n.kinds.map((k) => <option key={k}>{k}</option>)}</select>
              <input aria-label={`Device ${i + 1} location`} className="input" placeholder="Where" value={d.where} onChange={(e) => setDev(i, "where", e.target.value)} />
              <input aria-label={`Device ${i + 1} model`} className="input" placeholder="Model" value={d.model} onChange={(e) => setDev(i, "model", e.target.value)} />
              <input aria-label={`Device ${i + 1} address`} className="input" placeholder="IP or hostname" value={d.address} onChange={(e) => setDev(i, "address", e.target.value)} />
              <button className="btn" aria-label={`Remove device ${i + 1}`} onClick={() => setN({ ...n, devices: n.devices.filter((_, j) => j !== i) })}>Remove</button>
            </div>
          ))}
          <button className="btn" disabled={n.devices.length >= 60} onClick={() => setN({ ...n, devices: [...n.devices, blank()] })}>Add device</button>
        </div>
        <Field label="Network layout"><textarea aria-label="Network layout" className="input min-h-20" value={n.network} onChange={(e) => setN({ ...n, network: e.target.value })} placeholder="Modem in the back office, router in the closet, two access points..." /></Field>
        <Field label="Problems that keep coming back"><textarea aria-label="Recurring problems" className="input min-h-20" value={n.issues} onChange={(e) => setN({ ...n, issues: e.target.value })} /></Field>
        <Field label="Other notes"><textarea aria-label="Other site notes" className="input min-h-16" value={n.notes} onChange={(e) => setN({ ...n, notes: e.target.value })} /></Field>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" onClick={save}>Save notes</button>
          <button className="btn" onClick={() => downloadFile(`/api/client-notes/${clientId}/sheet.pdf`, `site-sheet-${clientId}.pdf`).catch((e) => setErr(errMsg(e, "Download failed.")))}>Site sheet (PDF)</button>
          {msg && <span role="status" className="text-xs text-muted">{msg}</span>}
        </div>
      </div>
    </Section>
  );
}
