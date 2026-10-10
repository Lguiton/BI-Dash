"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Section, errMsg } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

interface Hit { title: string; source: string; href: string | null; score: number; snippet: string }
interface Res { query: string; indexed: number; results: Hit[]; note: string }

export default function KnowledgePage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!q.trim()) return;
    const ctl = new AbortController();
    const t = setTimeout(() => {
      getJson<Res>(`/api/kb?q=${encodeURIComponent(q)}&limit=10`, ctl.signal).then((r) => { setRes(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Search failed.")); });
    }, 250);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [q]);
  const shown = q.trim() ? res : null;
  return (
    <PageShell title="Knowledge search" subtitle="Search this project's docs and every track manual.">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Honest label: keyword search ranked by TF-IDF (rare words count more). It matches words, not meaning, so try the terms the docs would use. It is not a vector database.</p>
      {err && <ErrorBanner message={err} />}
      <input className="field w-full" aria-label="Search the knowledge base" placeholder="e.g. restore drill, earned value, incident checklist" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      {shown && shown.results.length === 0 && <p className="text-sm text-muted">No passages share words with that. Try fewer or different words.</p>}
      {shown && shown.results.length > 0 && (
        <Section title={`${shown.results.length} passage(s) from ${shown.indexed} indexed`}>
          <ul className="divide-y divide-line">{shown.results.map((h, i) => (
            <li key={i} className="py-2 text-sm">
              <div className="flex flex-wrap items-baseline gap-2">{h.href ? <Link className="font-medium underline" href={h.href}>{h.title}</Link> : <b>{h.title}</b>}<span className="text-xs text-muted">{h.source} · match {Math.round(h.score * 100)}%</span></div>
              <p className="mt-0.5 text-xs text-muted">{h.snippet}</p>
            </li>
          ))}</ul>
        </Section>
      )}
    </PageShell>
  );
}
