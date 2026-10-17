"use client";
import { ExternalLink } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Section, errMsg } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

type Brief = { id: string; name: string; short: string; kind: string; where: string };
type Lib = { reviewed: string; note: string; laws: Brief[]; glossary: { term: string; meaning: string }[]; checklist: string[] };
type Law = Brief & { applies: string; covers: string; duties: string[]; penalties: string; freelancer: string[]; links: { label: string; url: string }[]; reviewed: string; note: string };

function List({ title, items }: { title: string; items: string[] }) {
  return <div><h4 className="text-xs font-semibold uppercase text-muted">{title}</h4><ul className="list-disc space-y-1 pl-5 text-sm">{items.map((i) => <li key={i}>{i}</li>)}</ul></div>;
}

/** Plain-language rules library: summaries with official links. Not legal advice. */
export function ComplianceLibrary() {
  const [lib, setLib] = useState<Lib | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [law, setLaw] = useState<Law | null>(null);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { const c = new AbortController(); getJson<Lib>("/api/compliance", c.signal).then(setLib).catch((e) => { if (!c.signal.aborted) setErr(errMsg(e, "Could not load the library.")); }); return () => c.abort(); }, []);
  const pick = (id: string) => {
    if (open === id) { setOpen(null); setLaw(null); return; }
    setOpen(id); setLaw(null);
    getJson<Law>(`/api/compliance/${id}`).then(setLaw).catch((e) => setErr(errMsg(e, "Could not load that entry.")));
  };
  const shown = useMemo(() => {
    if (!lib) return [];
    const t = q.toLowerCase().trim();
    return t ? lib.laws.filter((l) => `${l.name} ${l.short} ${l.kind} ${l.where}`.toLowerCase().includes(t)) : lib.laws;
  }, [lib, q]);
  if (err) return <p className="text-sm text-bad" role="alert">{err}</p>;
  if (!lib) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="grid gap-4">
      <p className="rounded border border-warn/40 p-2 text-sm">{lib.note} Reviewed {lib.reviewed}.</p>
      <Section title="Laws and standards">
        <input className="input mb-2 w-full" placeholder="Filter: HIPAA, email, Nevada, payments…" aria-label="Filter laws" value={q} onChange={(e) => setQ(e.target.value)} />
        <ul className="grid gap-2">
          {shown.map((l) => (
            <li key={l.id} className="rounded border border-line">
              <button className="flex w-full items-center justify-between gap-2 p-2 text-left" aria-expanded={open === l.id} onClick={() => pick(l.id)}>
                <span><span className="text-sm font-semibold">{l.name}</span><br /><span className="text-xs text-muted">{l.short}</span></span>
                <span className="flex gap-1"><Badge>{l.kind}</Badge></span>
              </button>
              {open === l.id && (
                <div className="space-y-3 border-t border-line p-3">
                  {!law ? <p className="text-sm text-muted">Loading…</p> : (<>
                    <p className="text-sm"><b>Where:</b> {law.where}</p>
                    <p className="text-sm"><b>Who it applies to:</b> {law.applies}</p>
                    <p className="text-sm"><b>What it covers:</b> {law.covers}</p>
                    <List title="Key duties" items={law.duties} />
                    <p className="text-sm"><b>Penalties:</b> {law.penalties}</p>
                    <List title="What this means for you" items={law.freelancer} />
                    <div><h4 className="text-xs font-semibold uppercase text-muted">Official sources</h4>
                      <ul className="space-y-1 text-sm">{law.links.map((k) => <li key={k.url}><a className="inline-flex items-center gap-1 underline" href={k.url} target="_blank" rel="noopener noreferrer">{k.label}<ExternalLink size={12} aria-hidden /></a></li>)}</ul></div>
                  </>)}
                </div>
              )}
            </li>
          ))}
          {!shown.length && <li className="text-sm text-muted">Nothing matches that filter.</li>}
        </ul>
      </Section>
      <Section title="Before every job"><ul className="list-disc space-y-1 pl-5 text-sm">{lib.checklist.map((c) => <li key={c}>{c}</li>)}</ul></Section>
      <Section title="Plain-English glossary">
        <dl className="grid gap-2 text-sm">{lib.glossary.map((g) => <div key={g.term}><dt className="font-semibold">{g.term}</dt><dd className="text-muted">{g.meaning}</dd></div>)}</dl>
      </Section>
    </div>
  );
}
