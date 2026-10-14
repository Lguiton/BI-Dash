"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";

type Kind = "data" | "field";
type Spec = { a: string; agent: string; kind: Kind };
type Item = { id: string; title: string; area: string; minutes: number; kind: Kind };
type Guide = { id: string; title: string; area: string; why: string; steps: string[]; verify: string; minutes: number; caution: string; tool: string };
type Idx = Record<string, { id: string; title: string; minutes: number }[]>;

const d = (a: string, agent: string): Spec => ({ a, agent, kind: "data" });
const f = (a: string, agent: string): Spec => ({ a, agent, kind: "field" });
// Each field's guides, the agent that walks through them, and an example to type.
export const FIX: Record<string, { specs: Spec[]; example: string }> = {
  analyst: { specs: [d("Data Analyst", "analyst")], example: "e.g. totals doubled after a join, dates look wrong" },
  bi: { specs: [d("BI", "analyst"), f("Revenue operations", "analyst")], example: "e.g. the KPI is red but nobody knows why, report numbers disagree" },
  science: { specs: [d("Data Science", "scientist")], example: "e.g. model barely beats guessing, forecast is flat" },
  eng: { specs: [d("Data Engineering", "engineering")], example: "e.g. nightly load failed, duplicates after a re-run" },
  cpe: { specs: [f("Computer engineering", "cpe")], example: "e.g. board resets when the motor starts, battery dies too fast" },
  ai: { specs: [f("AI engineering", "ai")], example: "e.g. assistant got worse after a change, bill is too high" },
  ml: { specs: [f("ML, NLP and deep learning", "ml"), f("Computer vision", "ml")], example: "e.g. text sorter barely better than guessing, overfitting" },
  pm: { specs: [f("Project management", "pm"), f("IT project management", "pm")], example: "e.g. client keeps adding things, project is late" },
  consulting: { specs: [f("Business consulting", "pm")], example: "e.g. owner wants everything at once, no clear goal" },
  devsecops: { specs: [f("DevSecOps", "security"), f("Revenue-system security", "security")], example: "e.g. secret in the repo, pipeline has no tests" },
  fs: { specs: [f("Full stack", "fullstack"), f("DevOps", "fullstack")], example: "e.g. api has no login, how do I deploy safely" },
  cloud: { specs: [f("Cloud architecture", "sysanalyst")], example: "e.g. cloud bill doubled, single point of failure" },
  health: { specs: [f("Clinical data science", "scientist"), f("Health analytics", "analyst"), f("Health BI", "analyst"), f("Health informatics", "sysanalyst")], example: "e.g. readmission rate looks off, HL7 message will not parse" },
  research: { specs: [f("Statistics", "scientist"), f("Genomic data science", "scientist"), f("Science and research", "scientist")], example: "e.g. p-value looks too good, groups are different sizes" },
  marketing: { specs: [f("Digital marketing", "analyst"), f("UI/UX and graphic design", "fullstack")], example: "e.g. clicks but no sales, page confuses visitors" },
};
const base = (k: Kind) => (k === "data" ? "/api/toolbox/howto" : "/api/fieldbox/howto");
const SHOW = 10;

/** A field dashboard's fix-it panel: a search bar, the list of fix-it questions, the guide, and an agent that walks you through it. */
export function FieldFix({ field }: { field: string }) {
  const cfg = FIX[field];
  const [items, setItems] = useState<Item[] | null>(null);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Item[] | null>(null);
  const [g, setG] = useState<(Guide & { kind: Kind }) | null>(null);
  const [all, setAll] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ask, setAsk] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!cfg) return;
    let live = true;
    const kinds = [...new Set(cfg.specs.map((s) => s.kind))];
    Promise.all(kinds.map((k) => getJson<{ areas: Idx }>(base(k)).then((r) => [k, r.areas] as const)))
      .then((res) => {
        if (!live) return;
        const byKind = Object.fromEntries(res) as Record<Kind, Idx>;
        setItems(cfg.specs.flatMap((s) => (byKind[s.kind]?.[s.a] ?? []).map((x) => ({ ...x, area: s.a, kind: s.kind }))));
      })
      .catch((e) => { if (live) setErr(errMsg(e, "Could not load the guides.")); });
    return () => { live = false; };
  }, [cfg]);

  if (!cfg) return null;
  async function find() {
    setErr(null);
    try {
      const out: Item[] = [];
      for (const k of [...new Set(cfg.specs.map((s) => s.kind))]) {
        if (k === "data") {
          const r = await getJson<{ results: Item[] }>(`${base(k)}/search?q=${encodeURIComponent(q)}`);
          out.push(...r.results.filter((x) => cfg.specs.some((s) => s.kind === k && s.a === x.area)).map((x) => ({ ...x, kind: k })));
        } else {
          for (const s of cfg.specs.filter((x) => x.kind === k)) {
            const r = await getJson<{ results: Item[] }>(`${base(k)}/search?q=${encodeURIComponent(q)}&area=${encodeURIComponent(s.a)}`);
            out.push(...r.results.filter((x) => x.area === s.a).map((x) => ({ ...x, kind: k })));
          }
        }
      }
      setHits(out);
    } catch (e) { setErr(errMsg(e, "Search failed.")); }
  }
  async function open(it: Item) {
    setErr(null); setReply(null);
    try { setG({ ...(await getJson<Guide>(`${base(it.kind)}/${it.id}`)), kind: it.kind }); } catch (e) { setErr(errMsg(e, "Could not open that guide.")); }
  }
  async function walk() {
    if (!g) return;
    setErr(null); setBusy(true); setReply(null);
    const agent = cfg.specs.find((s) => s.a === g.area)?.agent ?? cfg.specs[0].agent;
    try {
      const r = await postJson<{ reply: string }>(`/api/agents/${agent}/chat`, { message: `Walk me through this, step by step, using the ${g.kind === "data" ? "data_fix" : "field_fix"} guide "${g.id}" (${g.title}). ${ask}`.slice(0, 1200) });
      setReply(r.reply);
    } catch (e) { setErr(errMsg(e, "The agent could not answer. If no AI provider is set up, the written steps above still work.")); } finally { setBusy(false); }
  }
  const list = items ?? [];
  const shown = all ? list : list.slice(0, SHOW);
  return (
    <div className="grid gap-4" aria-label="Fix it">
      {err && <ErrorBanner message={err} />}
      <Section title="Fix it or look it up" note="Describe the problem in your own words, or pick a question below. Guides are steps to follow; nothing here changes your data.">
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); void find(); }}>
          <Field label="What is going wrong, or what do you need to do?"><input aria-label="Search fix-it guides" className="input w-96 max-w-full" value={q} onChange={(e) => setQ(e.target.value)} placeholder={cfg.example} /></Field>
          <button className="btn btn-primary" type="submit" disabled={!q.trim()}>Find the guide</button>
        </form>
        {hits && hits.length === 0 && <p className="mt-2 text-xs text-muted">Nothing matched. Try other words, or pick from the list below.</p>}
        {hits && hits.length > 0 && <ul className="mt-3 grid gap-2 text-sm" aria-label="Search results">{hits.map((h) => <li key={`${h.kind}${h.id}`}><button className="btn" onClick={() => open(h)}>{h.title}</button> <span className="text-xs text-muted">about {h.minutes} min</span></li>)}</ul>}
        <div className="mt-3" role="group" aria-label="Fix-it questions">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Common problems{items ? ` (${list.length})` : ""}</div>
          {!items ? <p className="text-sm text-muted">Loading…</p> : (
            <div className="flex flex-wrap gap-2">
              {shown.map((x) => <button key={`${x.kind}${x.id}`} className="btn" onClick={() => open(x)}>{x.title}</button>)}
              {list.length > SHOW && <button className="btn" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${list.length}`}</button>}
            </div>
          )}
        </div>
      </Section>
      {g && (
        <Section title={g.title} note={`${g.area} · about ${g.minutes} minutes`}>
          <p className="mb-2 text-sm"><b>Why it happens:</b> {g.why}</p>
          {g.caution && <p className="mb-2 rounded border border-amber-500 bg-amber-500/10 p-2 text-sm"><b>Before you start:</b> {g.caution}</p>}
          <ol aria-label="Guide steps" className="list-decimal space-y-1 pl-5 text-sm">{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <p className="mt-3 text-sm"><Badge tone="ok">Check it worked</Badge> {g.verify}</p>
          {g.tool && <p className="mt-1 text-xs text-muted">Dashboard tool: {g.tool}</p>}
          <div className="mt-4 border-t border-line pt-3">
            <Field label="Ask the agent to walk you through it (optional note about your situation)"><input aria-label="Note for the agent" className="input" value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
            <button className="btn mt-2" disabled={busy} onClick={walk}>{busy ? "Asking…" : "Walk me through it"}</button>
            {reply && <pre aria-label="Agent reply" className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-3 text-sm">{reply}</pre>}
          </div>
        </Section>
      )}
    </div>
  );
}
