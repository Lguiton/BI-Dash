"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";

type Hit = { id: string; title: string; area: string; minutes: number; why: string };
type Guide = { id: string; title: string; area: string; why: string; steps: string[]; verify: string; minutes: number; caution: string; tool: string };
type Index = { areas: Record<string, { id: string; title: string; minutes: number }[]> };
const AGENT: Record<string, string> = { "Data Analyst": "analyst", BI: "analyst", "Data Science": "scientist", "Data Engineering": "engineering" };

export function HowTo({ openId }: { openId?: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [g, setG] = useState<Guide | null>(null);
  const [idx, setIdx] = useState<Index | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<Index>("/api/toolbox/howto").then((r) => { if (live) setIdx(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the guides.")); });
    return () => { live = false; };
  }, []);
  useEffect(() => {
    if (!openId) return;
    let live = true;
    getJson<Guide>(`/api/toolbox/howto/${openId}`).then((x) => { if (live) { setG(x); setReply(null); } }).catch(() => {});
    return () => { live = false; };
  }, [openId]);
  const count = idx ? Object.values(idx.areas).reduce((n, l) => n + l.length, 0) : 0;
  async function open(id: string) { setErr(null); setReply(null); try { setG(await getJson<Guide>(`/api/toolbox/howto/${id}`)); } catch (e) { setErr(errMsg(e, "Could not open that guide.")); } }
  async function walk() {
    if (!g) return; setErr(null); setBusy(true); setReply(null);
    try {
      const r = await postJson<{ reply: string }>(`/api/agents/${AGENT[g.area] ?? "analyst"}/chat`, { message: `Walk me through this, step by step, using the data_fix guide "${g.id}" (${g.title}). ${ask}`.slice(0, 1200) });
      setReply(r.reply);
    } catch (e) { setErr(errMsg(e, "The agent could not answer. If no AI provider is set up, the written steps above still work.")); } finally { setBusy(false); }
  }
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="How to do it or fix it" note={`${count || "…"} guides for analysis, BI reports, models and pipelines. Describe the problem in your own words. Guides are steps to follow; nothing here changes your data.`}>
        <form className="flex flex-wrap items-end gap-2" onSubmit={async (e) => { e.preventDefault(); setErr(null); try { setHits((await getJson<{ results: Hit[] }>(`/api/toolbox/howto/search?q=${encodeURIComponent(q)}`)).results); } catch (x) { setErr(errMsg(x, "Search failed.")); } }}>
          <Field label="What is going wrong?"><input aria-label="Search for a how-to" className="input w-96 max-w-full" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. totals doubled after a join, model no better than guessing" /></Field>
          <button className="btn" type="submit" disabled={!q.trim()}>Find the guide</button>
        </form>
        {hits && hits.length === 0 && <p className="mt-2 text-xs text-muted">Nothing matched. Try other words, or browse below.</p>}
        {hits && hits.length > 0 && <ul className="mt-3 grid gap-2 text-sm">{hits.map((h) => <li key={h.id}><button className="btn" onClick={() => open(h.id)}>{h.title}</button> <span className="text-xs text-muted">{h.area} · about {h.minutes} min. {h.why}</span></li>)}</ul>}
      </Section>
      {g && (
        <Section title={g.title} note={`${g.area} · about ${g.minutes} minutes`}>
          <p className="mb-2 text-sm"><b>Why it happens:</b> {g.why}</p>
          {g.caution && <p className="mb-2 rounded border border-amber-500 bg-amber-500/10 p-2 text-sm"><b>Before you start:</b> {g.caution}</p>}
          <ol aria-label="Guide steps" className="list-decimal space-y-1 pl-5 text-sm">{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <p className="mt-3 text-sm"><Badge tone="ok">Check it worked</Badge> {g.verify}</p>
          {g.tool && <p className="mt-1 text-xs text-muted">Dashboard tool: {g.tool}</p>}
          <div className="mt-4 border-t border-line pt-3">
            <Field label="Ask the agent to walk you through it (optional note about your data)"><input aria-label="Note for the agent" className="input" value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
            <button className="btn mt-2" disabled={busy} onClick={walk}>{busy ? "Asking…" : "Walk me through it"}</button>
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
