"use client";

import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";
import type { QualityCheck, QualityReport } from "@/lib/types";

const ST = {
  ok: { label: "Pass", bg: "var(--good-bg)", fg: "var(--good)", Icon: CheckCircle2 },
  warn: { label: "Review", bg: "var(--warn-bg)", fg: "var(--fg)", Icon: AlertTriangle },
  bad: { label: "Fix", bg: "var(--bad-bg)", fg: "var(--bad)", Icon: XCircle },
} as const;

function Sample({ rows }: { rows: QualityCheck["sample"] }) {
  const cols = Object.keys(rows[0] ?? {});
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-xs">
        <caption className="sr-only">Sample of affected rows</caption>
        <thead><tr>{cols.map((c) => <th key={c} className="th">{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line">{cols.map((c) => <td key={c} className="td font-mono">{r[c] === null ? "NULL" : String(r[c])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export default function QualityPage() {
  const [rep, setRep] = useState<QualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<QualityReport>("/api/quality", ctl.signal).then((r) => { setRep(r); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't run the checks."); });
    return () => ctl.abort();
  }, [attempt]);

  const scoreColor = !rep ? "var(--muted)" : rep.score_pct >= 90 ? "var(--good)" : rep.score_pct >= 70 ? "var(--fg)" : "var(--bad)";

  return (
    <PageShell title="Data quality" subtitle="The checks to run before you trust a dashboard. Garbage in, garbage out.">
      {error && <ErrorBanner message={error} onRetry={() => setAttempt((a) => a + 1)} />}
      {!rep && !error && <p className="text-sm text-muted">Running checks…</p>}
      {rep && (
        <>
          <section className="card flex flex-wrap items-center gap-6 p-5" aria-label="Summary">
            <div>
              <div className="text-5xl font-bold tabular-nums" style={{ color: scoreColor }}>{rep.score_pct}%</div>
              <div className="text-sm text-muted">{rep.passed} of {rep.total_checks} checks passed</div>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <dt className="text-muted">Fact rows</dt><dd className="text-right font-semibold tabular-nums">{rep.facts.toLocaleString("en-US")}</dd>
              <dt className="text-muted">Entities</dt><dd className="text-right font-semibold tabular-nums">{rep.entities.toLocaleString("en-US")}</dd>
            </dl>
            <button className="btn ml-auto" onClick={() => setAttempt((a) => a + 1)}>Re-run checks</button>
          </section>

          <section aria-label="Checks" className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide">Checks</h2>
            <ul className="space-y-3">
              {rep.checks.map((c) => {
                const s = ST[c.status];
                return (
                  <li key={c.id} className="card p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-semibold">{c.title}</h3>
                      <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: s.bg, color: s.fg }}>
                        <s.Icon className="h-3.5 w-3.5" aria-hidden /> {s.label}{c.count > 0 && ` · ${c.count.toLocaleString("en-US")}`}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-muted">{c.why}</p>
                    {c.sample.length > 0 && <Sample rows={c.sample} />}
                  </li>
                );
              })}
            </ul>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="card overflow-x-auto" aria-label="Completeness">
              <h2 className="p-4 pb-2 text-lg font-semibold">Completeness (nulls per column)</h2>
              <table className="w-full text-sm">
                <thead><tr><th className="th">Column</th><th className="th th-r">Nulls</th><th className="th th-r">%</th></tr></thead>
                <tbody>{rep.nulls.map((n) => (
                  <tr key={n.column} className="border-t border-line">
                    <td className="td font-mono text-xs">{n.column}</td>
                    <td className="td text-right tabular-nums">{n.nulls.toLocaleString("en-US")}</td>
                    <td className="td text-right tabular-nums" style={n.nulls ? { color: "var(--bad)" } : { color: "var(--muted)" }}>{n.null_pct}%</td>
                  </tr>))}</tbody>
              </table>
            </section>
            <section className="card overflow-x-auto" aria-label="Status values">
              <h2 className="p-4 pb-2 text-lg font-semibold">Status values</h2>
              <p className="px-4 pb-2 text-xs text-muted">Typos like &quot;completed&quot; vs &quot;Completed&quot; show up here as separate values.</p>
              <table className="w-full text-sm">
                <thead><tr><th className="th">Status</th><th className="th th-r">Rows</th></tr></thead>
                <tbody>{rep.statuses.map((s) => <tr key={s.status} className="border-t border-line"><td className="td">{s.status}</td><td className="td text-right tabular-nums">{s.rows.toLocaleString("en-US")}</td></tr>)}</tbody>
              </table>
            </section>
          </div>
        </>
      )}
    </PageShell>
  );
}
