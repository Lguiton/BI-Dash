"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, apiFetch, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Item = { id: string; title: string; severity: string };
type Found = { source: string; severity: string; title: string; why: string; fix: string; fix_id?: string | null };
type Report = { band: string; counts: Record<string, number>; start_with: Found[]; items: Found[]; checked: string[]; not_checked: string[]; caveat: string; sample: boolean };

export function CheckupReport({ onFix }: { onFix?: (id: string) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [f, setF] = useState({ client: "", prepared_by: "", scope: "", host: "", logs: "" });
  const [pcs, setPcs] = useState([{ label: "PC 1", text: "" }]);
  const [rep, setRep] = useState<Report | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [clients, setClients] = useState<{ id: number; name: string }[]>([]);
  const [cid, setCid] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => { getJson<{ items: Item[] }>("/api/security/report/checklist").then((r) => setItems(r.items)).catch((e) => setErr(errMsg(e, "Could not load the checklist."))); }, []);
  useEffect(() => { getJson<{ clients: { id: number; name: string }[] }>("/api/clients").then((r) => setClients(r.clients)).catch(() => {}); }, []);
  async function saveFor() {
    setErr(null); setSaved(null);
    try { const r = await postJson<{ date: string; band: string }>("/api/sectrack/reports/save", { ...body(), client_id: Number(cid) }); setSaved(`Saved on ${r.date}: ${r.band}.`); } catch (e) { setErr(errMsg(e, "Could not save the report.")); }
  }
  const body = () => ({ ...f, hosts: f.host.trim() ? [f.host.trim()] : [], endpoints: pcs.filter((p) => p.text.trim()), checklist: ans });
  async function make() {
    setErr(null); setBusy(true);
    try { setRep(await postJson<Report>("/api/security/report", body())); } catch (e) { setErr(errMsg(e, "Could not build the report.")); } finally { setBusy(false); }
  }
  async function open() {
    setErr(null);
    try {
      const r = await apiFetch(`${API_BASE}/api/security/report/html`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body()) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not build the report.");
      const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = "security_checkup.html"; a.click(); URL.revokeObjectURL(a.href);
    } catch (e) { setErr(errMsg(e, "Could not build the report.")); }
  }
  const tone = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "muted") as "bad" | "warn" | "muted";

  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Security checkup report" note="Pulls your other checks into one client-ready page with a fix order. Add whatever you have; every part is optional. It scans nothing new, and the website check only works on public sites you are allowed to check.">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Client"><input aria-label="Report client" className="input" value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} /></Field>
          <Field label="Prepared by"><input aria-label="Report prepared by" className="input" value={f.prepared_by} onChange={(e) => setF({ ...f, prepared_by: e.target.value })} /></Field>
          <Field label="Website (public, optional)"><input aria-label="Report website" className="input" placeholder="example.com" value={f.host} onChange={(e) => setF({ ...f, host: e.target.value })} /></Field>
        </div>
        <Field label="What this covers (one line)"><input aria-label="Report scope" className="input" value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value })} placeholder="Two Windows PCs and the shop website, checked on…" /></Field>
        {pcs.map((p, i) => (
          <div key={i} className="mt-3 grid gap-2">
            <Field label={`Windows PC ${i + 1}: name`}><input aria-label={`PC ${i + 1} name`} className="input" value={p.label} onChange={(e) => setPcs((o) => o.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} /></Field>
            <Field label="Paste the output of the read-only script (Endpoint hardening tab)"><textarea aria-label={`PC ${i + 1} script output`} className="input min-h-20 font-mono text-xs" value={p.text} onChange={(e) => setPcs((o) => o.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} /></Field>
          </div>
        ))}
        <button className="btn mt-2" disabled={pcs.length >= 10} onClick={() => setPcs((o) => [...o, { label: `PC ${o.length + 1}`, text: "" }])}>Add another PC</button>
        <Field label="A log to include (optional)"><textarea aria-label="Report log" className="input mt-3 min-h-20 font-mono text-xs" value={f.logs} onChange={(e) => setF({ ...f, logs: e.target.value })} /></Field>
        <fieldset className="mt-3 grid gap-2"><legend className="mb-1 text-xs text-muted">What you can see in person</legend>
          {items.map((it) => (
            <div key={it.id} className="flex flex-wrap items-center gap-2 text-sm"><span className="min-w-0 flex-1">{it.title}</span>
              <select aria-label={it.title} className="input" value={ans[it.id] ?? "unknown"} onChange={(e) => setAns({ ...ans, [it.id]: e.target.value })}>{["unknown", "yes", "partial", "no"].map((a) => <option key={a}>{a}</option>)}</select></div>
          ))}
        </fieldset>
        <div className="mt-3 flex gap-2"><button className="btn" disabled={busy} onClick={make}>{busy ? "Building…" : "Build the report"}</button><button className="btn" onClick={open}>Download as a web page</button></div>
        <div className="mt-3 flex flex-wrap items-end gap-2"><Field label="Save a snapshot for a client (for re-check comparison)"><select aria-label="Save report for client" className="input" value={cid} onChange={(e) => setCid(e.target.value)}><option value="">Choose a client…</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><button className="btn" disabled={!cid} onClick={saveFor}>Save for this client</button>{saved && <span className="text-sm">{saved}</span>}</div>
      </Section>
      {rep && (
        <Section title={`Overall: ${rep.band}`} note={rep.caveat}>
          {rep.sample && <p className="mb-2 text-xs text-amber-600">Practice workspace: the downloaded page is stamped SAMPLE.</p>}
          <p className="mb-2 text-sm">{rep.counts.high} to fix first, {rep.counts.medium} to plan, {rep.counts.low} to tidy. Checked: {rep.checked.join(", ")}.</p>
          <h4 className="text-sm font-medium">Start with these</h4>
          <ol className="mb-3 list-decimal pl-5 text-sm">{rep.start_with.map((i, k) => <li key={k}><b>{i.title}</b> <Badge tone={tone(i.severity)}>{i.severity}</Badge> <span className="text-muted">({i.source})</span> {i.fix} {i.fix_id && onFix && <button className="btn" onClick={() => onFix(i.fix_id!)}>How to fix</button>}</li>)}</ol>
          <details><summary className="cursor-pointer text-sm">All {rep.items.length} findings</summary><ul className="mt-2 grid gap-1 text-sm">{rep.items.map((i, k) => <li key={k}><Badge tone={tone(i.severity)}>{i.severity}</Badge> {i.title}. <span className="text-muted">{i.why}</span> {i.fix_id && onFix && <button className="btn" onClick={() => onFix(i.fix_id!)}>How to fix</button>}</li>)}</ul></details>
          <h4 className="mt-3 text-sm font-medium">Not checked</h4><ul className="list-disc pl-5 text-xs text-muted">{rep.not_checked.map((n, k) => <li key={k}>{n}</li>)}</ul>
        </Section>
      )}
    </div>
  );
}
