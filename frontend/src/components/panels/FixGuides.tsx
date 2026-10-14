"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Hit = { id: string; title: string; area: string; minutes: number; why: string };
type Guide = { id: string; title: string; area: string; why: string; steps: string[]; verify: string; minutes: number; caution: string; tool: string };
type Index = { areas: Record<string, { id: string; title: string; minutes: number }[]>; count: number };

export function FixGuides({ openId }: { openId?: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [g, setG] = useState<Guide | null>(null);
  const [idx, setIdx] = useState<Index | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { getJson<Index>("/api/security/fixes").then(setIdx).catch((e) => setErr(errMsg(e, "Could not load the guides."))); }, []);
  useEffect(() => { if (openId) getJson<Guide>(`/api/security/fixes/${openId}`).then((x) => { setG(x); setReply(null); }).catch((e) => setErr(errMsg(e, "Could not open that guide."))); }, [openId]);
  async function search() {
    setErr(null);
    try { setHits((await getJson<{ results: Hit[] }>(`/api/security/fixes/search?q=${encodeURIComponent(q)}`)).results); } catch (e) { setErr(errMsg(e, "Search failed.")); }
  }
  async function open(id: string) { setErr(null); setReply(null); try { setG(await getJson<Guide>(`/api/security/fixes/${id}`)); } catch (e) { setErr(errMsg(e, "Could not open that guide.")); } }
  async function askAgent() {
    if (!g) return; setErr(null); setBusy(true); setReply(null);
    try {
      const r = await postJson<{ reply: string }>("/api/agents/security/chat", { message: `Walk me through this fix, step by step, using the sec_fix guide "${g.id}" (${g.title}). ${ask}`.slice(0, 1200) });
      setReply(r.reply);
    } catch (e) { setErr(errMsg(e, "The agent could not answer. If no AI provider is set up, the written steps above still work.")); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="How to fix it" note={`${idx?.count ?? "…"} guides. Type the finding or the problem in your own words. Guides are steps to read and follow yourself on systems you own; nothing here changes a setting.`}>
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); search(); }}>
          <Field label="What needs fixing?"><input aria-label="Search for a fix" className="input w-80 max-w-full" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. smb1, RDP open, expired certificate, clicked a phishing link" /></Field>
          <button className="btn" type="submit" disabled={!q.trim()}>Find the fix</button>
        </form>
        {hits.length > 0 && <ul className="mt-3 grid gap-2 text-sm">{hits.map((h) => <li key={h.id}><button className="btn" onClick={() => open(h.id)}>{h.title}</button> <span className="text-xs text-muted">{h.area} · about {h.minutes} min. {h.why}</span></li>)}</ul>}
        {hits.length === 0 && q && <p className="mt-2 text-xs text-muted">Press Find the fix. If nothing matches, browse below.</p>}
      </Section>

      {g && (
        <Section title={g.title} note={`${g.area} · about ${g.minutes} minutes`}>
          <p className="mb-2 text-sm"><b>Why it matters:</b> {g.why}</p>
          {g.caution && <p className="mb-2 rounded border border-amber-500 bg-amber-500/10 p-2 text-sm"><b>Before you start:</b> {g.caution}</p>}
          <ol aria-label="Fix steps" className="list-decimal space-y-1 pl-5 text-sm">{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <p className="mt-3 text-sm"><Badge tone="ok">Check it worked</Badge> {g.verify}</p>
          {g.tool && <p className="mt-1 text-xs text-muted">Dashboard tool: {g.tool}</p>}
          <div className="mt-4 border-t border-line pt-3">
            <Field label="Ask the Cybersecurity agent to walk you through it (optional note about your setup)"><input aria-label="Note for the agent" className="input" value={ask} onChange={(e) => setAsk(e.target.value)} placeholder="e.g. it is a Windows 10 Home laptop" /></Field>
            <button className="btn mt-2" disabled={busy} onClick={askAgent}>{busy ? "Asking…" : "Walk me through it"}</button>
            {reply && <pre aria-label="Agent reply" className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-3 text-sm">{reply}</pre>}
          </div>
        </Section>
      )}

      <Section title="Browse all guides">
        {idx && Object.entries(idx.areas).map(([area, list]) => (
          <div key={area} className="mb-3"><h4 className="text-xs font-medium text-muted">{area}</h4><div className="mt-1 flex flex-wrap gap-2">{list.map((x) => <button key={x.id} className="btn" onClick={() => open(x.id)}>{x.title}</button>)}</div></div>
        ))}
      </Section>
    </div>
  );
}
