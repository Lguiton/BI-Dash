"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";
import type { GlossaryTerm } from "@/lib/types";

export default function GlossaryPage() {
  const [terms, setTerms] = useState<GlossaryTerm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState("All");
  const [q, setQ] = useState("");

  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ terms: GlossaryTerm[] }>("/api/glossary", ctl.signal).then((r) => setTerms(r.terms))
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the glossary."); });
    return () => ctl.abort();
  }, []);

  const shown = useMemo(() => (terms ?? []).filter((t) =>
    (kind === "All" || t.kind === kind) && (`${t.term} ${t.definition}`.toLowerCase().includes(q.trim().toLowerCase()))), [terms, kind, q]);

  return (
    <PageShell title="Metrics glossary" subtitle="One agreed definition per metric, with the SQL behind it. Every example is tested against the data model.">
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap items-center gap-3">
        <input className="field" placeholder="Search terms…" aria-label="Search terms" value={q} onChange={(e) => setQ(e.target.value)} />
        <div role="group" aria-label="Filter by kind" className="flex flex-wrap gap-1">
          {["All", "Metric", "KPI", "Concept", "Method"].map((k) => <button key={k} className={`btn ${kind === k ? "btn-primary" : ""}`} aria-pressed={kind === k} onClick={() => setKind(k)}>{k}</button>)}
        </div>
      </div>
      {!terms && !error && <p className="text-sm text-muted">Loading…</p>}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {shown.map((t) => (
          <article key={t.id} className="card min-w-0 space-y-2 p-5">
            <header className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold">{t.term}</h2>
              <span className="rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{t.kind}</span>
              {t.additive != null && <span className="rounded-full px-2 py-0.5 text-xs" style={{ background: t.additive ? "var(--good-bg)" : "var(--warn-bg)" }}>{t.additive ? "additive" : "non-additive"}</span>}
            </header>
            <p className="text-sm">{t.definition}</p>
            <p className="text-sm"><b>Formula:</b> <code>{t.formula}</code></p>
            <pre className="overflow-auto rounded bg-panel2 p-2 text-xs" tabIndex={0}><code>{t.sql}</code></pre>
            <p className="text-xs text-muted">⚠ {t.pitfall}</p>
          </article>
        ))}
        {terms && shown.length === 0 && <p className="text-sm text-muted">No terms match.</p>}
      </div>
    </PageShell>
  );
}
