"use client";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, postJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";

type Kind = { id: string; label: string };
type Draft = { template: string; ai: { text: string; provider: string; tokens: number } | null; note: string };
type Person = { who: string; why: string; kind: string; what: string };

function CopyBlock({ title, text, tag }: { title: string; text: string; tag?: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-1 rounded border border-line p-2">
      <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold">{title}</span>{tag && <Badge tone="warn">{tag}</Badge>}</div>
      <pre className="whitespace-pre-wrap font-sans text-sm">{text}</pre>
      <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { /* user can select the text */ } }}>{done ? "Copied" : "Copy"}</button>
    </div>
  );
}

/** Draft a message to a client: a free template always, an AI version if you ask. You send it yourself. */
export function ClientMessages() {
  const [jobId] = useActiveJob();
  const [kinds, setKinds] = useState<Kind[]>([]);
  const [kind, setKind] = useState("reply");
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [ai, setAi] = useState(false);
  const [d, setD] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<{ kinds: Kind[] }>("/api/comms/kinds").then((r) => setKinds(r.kinds)).catch(() => {}); }, []);
  async function go() {
    setErr(null); setBusy(true);
    try { setD(await postJson<Draft>("/api/comms/draft", { kind, message: msg, name, ai, job_id: jobId })); } catch (e) { setErr(errMsg(e, "Couldn't make the draft.")); } finally { setBusy(false); }
  }
  return (
    <details className="card p-3 text-sm">
      <summary className="cursor-pointer font-semibold">Write a client message</summary>
      <div className="mt-2 space-y-2">
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs">Type<select className="input w-full" value={kind} onChange={(e) => setKind(e.target.value)}>{kinds.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></label>
          <label className="text-xs">Client first name (optional, the pinned job fills it in)<input className="input w-full" value={name} onChange={(e) => setName(e.target.value)} /></label>
        </div>
        <textarea className="input min-h-20 w-full" aria-label="Their message" placeholder="Paste their message here if you are replying (leave out passwords)" value={msg} onChange={(e) => setMsg(e.target.value)} />
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} /> Also write an AI version (uses tokens; names, emails and phone numbers are removed first)</label>
        <button className="btn" disabled={busy} onClick={go}>{busy ? "Working…" : "Make the draft"}</button>
        {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
        {d && (
          <div className="space-y-2">
            <CopyBlock title="Template (free)" text={d.template} />
            {d.ai && <CopyBlock title={`AI version · ${d.ai.provider} · ${d.ai.tokens} tokens`} text={d.ai.text} tag="check it, can be wrong" />}
            <p className="text-xs text-muted">{d.note}</p>
          </div>
        )}
      </div>
    </details>
  );
}

/** Who to contact this week, from your own leads, old quotes and past clients. */
export function WeekList() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [d, setD] = useState<Draft | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<{ people: Person[] }>("/api/comms/week").then((r) => { if (live) setPeople(r.people); }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the list.")); });
    return () => { live = false; };
  }, []);
  async function draft(i: number, p: Person, ai: boolean) {
    setErr(null); setBusy(true); setOpen(i);
    try { setD(await postJson<Draft>("/api/comms/outreach", { kind: p.kind, name: p.who, what: p.what, ai })); } catch (e) { setErr(errMsg(e, "Couldn't make the draft.")); } finally { setBusy(false); }
  }
  return (
    <section className="card space-y-2 p-4" aria-label="Who to contact this week">
      <h2 className="text-sm font-semibold">Who to contact this week</h2>
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      {!people && !err && <p className="text-sm text-muted">Loading…</p>}
      {people?.length === 0 && <p className="text-sm">No one is waiting on you. Add leads below, or quote a job, and they show up here when it is time to follow up.</p>}
      <ul className="space-y-2 text-sm">
        {people?.map((p, i) => (
          <li key={`${p.who}${p.kind}`} className="space-y-1">
            <div className="flex flex-wrap items-center justify-between gap-2"><span><strong>{p.who}</strong> <span className="text-muted">{p.why}</span></span>
              <span className="flex gap-2"><button className="btn" disabled={busy} onClick={() => draft(i, p, false)}>Free draft</button><button className="btn" disabled={busy} onClick={() => draft(i, p, true)}>AI draft</button></span></div>
            {open === i && d && (
              <div className="space-y-2">
                <CopyBlock title="Template (free)" text={d.template} />
                {d.ai && <CopyBlock title={`AI version · ${d.ai.provider} · ${d.ai.tokens} tokens`} text={d.ai.text} tag="check it, can be wrong" />}
              </div>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Drafts only. You send them yourself.</p>
    </section>
  );
}
