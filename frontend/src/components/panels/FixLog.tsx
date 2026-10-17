"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, apiFetch, deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Badge, Field, Section, errMsg } from "./kit";

export type FixArea = "it" | "security" | "network" | "data" | "ml" | "fullstack";
export type Fix = { id: number; area: FixArea; area_label: string; title: string; category: string; device: string; symptoms: string; cause: string; steps: string[]; result: string; result_label: string; minutes: number; tools: string; prevention: string; client: string; ticket_id: number | null; tags: string[]; created_at: string; score?: number };
type Draft = Partial<Omit<Fix, "steps" | "tags">> & { steps?: string[]; tags?: string[] };
type Found = { fixes: Fix[]; guides: { id: string; title: string; area: string }[] };
type List = { fixes: Fix[]; stats: { total: number; by_result: Record<string, number>; avg_minutes: number | null }; note: string };

const RESULTS: [string, string][] = [["fixed", "Fixed"], ["workaround", "Workaround only"], ["not_fixed", "Not fixed yet"]];
const tone = (r: string) => (r === "fixed" ? "ok" : r === "workaround" ? "warn" : "bad");
const HINT: Record<FixArea, string> = { it: "e.g. laptop will not charge, printer offline after router change", security: "e.g. user clicked a phishing link, admin account locked out", network: "e.g. wifi drops every hour, cannot reach the printer by name", data: "e.g. report total does not match the ledger, import dropped rows", ml: "e.g. model scores high in testing but fails on new data", fullstack: "e.g. login works locally but fails after deploy" };

/** Shows past fixes that match the words you typed: what was tried and what worked. */
export function SeenBefore({ q, area }: { q: string; area: FixArea }) {
  const [res, setRes] = useState<Found | null>(null);
  const [asked, setAsked] = useState("");
  useEffect(() => {
    const text = q.trim();
    if (text.length < 4) return;
    let live = true;
    getJson<Found>(`/api/fixlog/search?q=${encodeURIComponent(text)}&area=${area}`).then((r) => { if (live) { setRes(r); setAsked(text); } }).catch(() => { if (live) { setRes(null); setAsked(""); } });
    return () => { live = false; };
  }, [q, area]);
  if (!res || asked !== q.trim() || res.fixes.length === 0) return null;
  return (
    <div className="rounded border border-line bg-panel2 p-3 text-sm" aria-label="Seen before">
      <div className="mb-1 font-medium">You have fixed something like this before</div>
      <ul className="space-y-2">{res.fixes.slice(0, 3).map((f) => <li key={f.id}><FixCard f={f} compact /></li>)}</ul>
    </div>
  );
}

function FixCard({ f, compact }: { f: Fix; compact?: boolean }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{f.title}</span><Badge tone={tone(f.result)}>{f.result_label}</Badge>{f.device && <Badge>{f.device}</Badge>}<span className="text-xs text-muted">{f.created_at.slice(0, 10)}</span></div>
      {f.cause && <p className="text-xs"><strong>Cause:</strong> {f.cause}</p>}
      {f.steps.length > 0 && (compact
        ? <details><summary className="cursor-pointer text-xs underline">What was done ({f.steps.length} steps)</summary><ol className="list-decimal pl-5 text-xs">{f.steps.map((s, i) => <li key={i}>{s}</li>)}</ol></details>
        : <ol className="list-decimal pl-5 text-xs">{f.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>)}
    </div>
  );
}

const blank = (area: FixArea): Record<string, string> => ({ area, title: "", category: "", device: "", symptoms: "", cause: "", steps: "", result: "fixed", minutes: "", tools: "", prevention: "", client: "", tags: "" });
const toForm = (area: FixArea, d?: Draft | Fix | null): Record<string, string> => d
  ? { ...blank(area), area: d.area ?? area, title: d.title ?? "", category: d.category ?? "", device: d.device ?? "", symptoms: d.symptoms ?? "", cause: d.cause ?? "", steps: (d.steps ?? []).join("\n"), result: d.result ?? "fixed", minutes: d.minutes ? String(d.minutes) : "", tools: d.tools ?? "", prevention: d.prevention ?? "", client: d.client ?? "", tags: (d.tags ?? []).join(", ") }
  : blank(area);

/** The form for writing a fix down. Pass `draft` to start from a ticket; `editing` to change a saved record. */
export function FixForm({ area, draft, editing, ticketId, onSaved, onCancel }: { area: FixArea; draft?: Draft | null; editing?: Fix | null; ticketId?: number | null; onSaved: (f: Fix) => void; onCancel?: () => void }) {
  const [f, setF] = useState(() => toForm(area, editing ?? draft));
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const set = (k: string) => (e: { target: { value: string } }) => setF((v) => ({ ...v, [k]: e.target.value }));
  async function save() {
    setErr(null); setNote(null);
    const body = { ...f, steps: f.steps.split("\n"), tags: f.tags.split(","), minutes: f.minutes || 0, ticket_id: editing?.ticket_id ?? ticketId ?? draft?.ticket_id ?? null };
    try {
      const r = editing ? await putJson<Fix & { masked: number }>(`/api/fixlog/${editing.id}`, body) : await postJson<Fix & { masked: number }>("/api/fixlog", body);
      setNote(r.masked ? `Saved. ${r.masked} password, key or token ${r.masked === 1 ? "was" : "were"} blanked.` : "Saved to the fix log.");
      if (!editing) setF(blank(area));
      onSaved(r);
    } catch (e) { setErr(errMsg(e, "Could not save the fix.")); }
  }
  return (
    <div className="space-y-2" aria-label="Fix form">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Short title"><input className="field" maxLength={120} value={f.title} onChange={set("title")} aria-label="Fix title" /></Field>
        <Field label="Device or system"><input className="field" maxLength={120} value={f.device} onChange={set("device")} aria-label="Device or system" /></Field>
        <Field label="Category"><input className="field" maxLength={60} value={f.category} onChange={set("category")} aria-label="Fix category" /></Field>
        <Field label="Client (optional)"><input className="field" maxLength={80} value={f.client} onChange={set("client")} aria-label="Fix client" /></Field>
      </div>
      <Field label="What was wrong (symptoms, error text)"><textarea className="field" rows={2} maxLength={1200} value={f.symptoms} onChange={set("symptoms")} aria-label="Symptoms" /></Field>
      <Field label="Cause, if you found it"><textarea className="field" rows={2} maxLength={1200} value={f.cause} onChange={set("cause")} aria-label="Cause" /></Field>
      <Field label="Steps you took, one per line"><textarea className="field" rows={5} value={f.steps} onChange={set("steps")} aria-label="Steps taken" /></Field>
      <div className="grid gap-2 sm:grid-cols-3">
        <Field label="Result"><select className="field" value={f.result} onChange={set("result")} aria-label="Result">{RESULTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        <Field label="Minutes spent"><input className="field" inputMode="numeric" value={f.minutes} onChange={set("minutes")} aria-label="Minutes spent" /></Field>
        <Field label="Tags (comma separated)"><input className="field" value={f.tags} onChange={set("tags")} aria-label="Tags" /></Field>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Tools or parts used"><input className="field" maxLength={300} value={f.tools} onChange={set("tools")} aria-label="Tools or parts" /></Field>
        <Field label="How to stop it happening again"><input className="field" maxLength={800} value={f.prevention} onChange={set("prevention")} aria-label="Prevention" /></Field>
      </div>
      <p className="text-xs text-muted">Write what you did, not the secret itself. Passwords, keys and tokens are blanked before saving.</p>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" onClick={save}>{editing ? "Save changes" : "Save to fix log"}</button>
        {onCancel && <button className="btn" onClick={onCancel}>Cancel</button>}
        {note && <span className="text-sm text-emerald-600" role="status">{note}</span>}
      </div>
    </div>
  );
}

/** The whole fix log for one area: search first, then write a fix down, then browse and print. */
export function FixLog({ area }: { area: FixArea }) {
  const [list, setList] = useState<List | null>(null);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Found | null>(null);
  const [editing, setEditing] = useState<Fix | null>(null);
  const [doc, setDoc] = useState<{ id: number; text: string } | null>(null);

  useEffect(() => {
    let live = true;
    getJson<List>(`/api/fixlog?area=${area}`).then((r) => { if (live) setList(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the fix log.")); });
    return () => { live = false; };
  }, [area, tick]);
  const reload = () => setTick((t) => t + 1);
  async function find() {
    setErr(null);
    try { setFound(await getJson<Found>(`/api/fixlog/search?q=${encodeURIComponent(q)}&area=${area}`)); } catch (e) { setErr(errMsg(e, "Search failed.")); }
  }
  async function show(id: number) {
    setErr(null);
    try { const r = await apiFetch(`${API_BASE}/api/fixlog/${id}/doc`); setDoc({ id, text: await r.text() }); } catch (e) { setErr(errMsg(e, "Could not open the write-up.")); }
  }
  const dl = (path: string, name: string) => downloadFile(path, name).catch((e) => setErr(errMsg(e, "Download failed.")));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Have I fixed this before?" note="Searches your own saved fixes by the words you use, and shows the built-in guides for the same words. It matches words, not meaning, so use the words you would have written down.">
        <div className="flex flex-wrap gap-2">
          <input className="input min-w-64 flex-1" aria-label="Describe the problem" placeholder={HINT[area]} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void find(); }} />
          <button className="btn btn-primary" onClick={find}>Search</button>
        </div>
        {found && (
          <div className="mt-3 space-y-3 text-sm">
            {found.fixes.length === 0 ? <p className="text-muted">Nothing in your log matches yet. Fix it, then write it down below so next time it is here.</p>
              : <ul className="space-y-3">{found.fixes.map((x) => <li key={x.id} className="rounded border border-line p-3"><FixCard f={x} /></li>)}</ul>}
            {found.guides.length > 0 && <p className="text-xs text-muted">Built-in guides on this: {found.guides.map((g) => g.title).join("; ")}.</p>}
          </div>
        )}
      </Section>
      <Section title={editing ? `Edit fix #${editing.id}` : "Write a fix down"}>
        <FixForm key={editing?.id ?? "new"} area={area} editing={editing} onSaved={() => { setEditing(null); reload(); }} onCancel={editing ? () => setEditing(null) : undefined} />
      </Section>
      <Section title={`Your fixes${list ? ` (${list.stats.total})` : ""}`} note={list?.note}>
        {list && list.stats.total > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted">
            {Object.entries(list.stats.by_result).map(([k, n]) => <Badge key={k} tone={tone(k)}>{n} {k.replace("_", " ")}</Badge>)}
            {list.stats.avg_minutes != null && <span>Average {list.stats.avg_minutes} minutes</span>}
            <button className="btn" onClick={() => dl(`/api/fixlog/export?area=${area}`, `fix-log-${area}.html`)}>Download everything</button>
          </div>
        )}
        {!list ? <p className="text-sm text-muted">Loading…</p> : list.fixes.length === 0 ? <p className="text-sm text-muted">Nothing saved yet. Your first fix goes in the form above.</p> : (
          <ul className="divide-y divide-line">
            {list.fixes.map((x) => (
              <li key={x.id} className="space-y-2 py-3 text-sm">
                <FixCard f={x} compact />
                <div className="flex flex-wrap gap-2">
                  <button className="btn" onClick={() => show(x.id)}>Write-up</button>
                  <button className="btn" onClick={() => dl(`/api/fixlog/${x.id}/doc?format=md`, `fix-${x.id}.md`)}>Download (.md)</button>
                  <button className="btn" onClick={() => dl(`/api/fixlog/${x.id}/doc?format=html&client=true`, `fix-${x.id}-client-copy.html`)}>Client copy (.html)</button>
                  <button className="btn" onClick={() => dl(`/api/fixlog/${x.id}/checklist.pdf`, `fix-${x.id}-checklist.pdf`)}>Checklist (PDF)</button>
                  <button className="btn" onClick={() => setEditing(x)}>Edit</button>
                  <button className="btn" onClick={() => deleteJson(`/api/fixlog/${x.id}`).then(reload).catch((e) => setErr(errMsg(e, "Could not delete.")))}>Delete</button>
                </div>
                {doc?.id === x.id && <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-3 text-xs" tabIndex={0}>{doc.text}</pre>}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
