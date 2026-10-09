"use client";
import { Play } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { PipelineStatus } from "@/lib/types";

const n = (v: number) => v.toLocaleString();

/** Live view of the medallion pipeline (data_engineering/): row counts per layer, health checks, quarantine reasons, run history. */
export function PipelinePanel({ initial }: { initial?: PipelineStatus }) {
  const [st, setSt] = useState<PipelineStatus | null>(initial ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<"clean" | "messy">("clean");
  const [reset, setReset] = useState(false);

  const load = useCallback((signal?: AbortSignal) =>
    getJson<PipelineStatus>("/api/pipeline", signal).then((s) => { setSt(s); setError(null); })
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the pipeline status."); }), []);
  useEffect(() => {
    if (initial) return;
    const ctl = new AbortController();
    load(ctl.signal);
    return () => ctl.abort();
  }, [initial, load]);

  async function run() {
    setBusy(true); setError(null);
    try { const r = await postJson<{ status: PipelineStatus }>("/api/pipeline/run", { source, reset }); setSt(r.status); }
    catch (e) { setError(e instanceof ApiError ? e.message : "The run failed."); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} />}
      <div className="card flex flex-wrap items-center gap-3 p-4 text-sm">
        <label>Source{" "}
          <select className="field" value={source} onChange={(e) => setSource(e.target.value as "clean" | "messy")}>
            <option value="clean">Clean sample (3,650 rows)</option>
            <option value="messy">Messy sample (duplicates, bad rows)</option>
          </select>
        </label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={reset} onChange={(e) => setReset(e.target.checked)} /> Start over (wipe the lake)</label>
        <button className="btn btn-primary" onClick={run} disabled={busy}><Play className="h-4 w-4" aria-hidden /> {busy ? "Running…" : "Run pipeline"}</button>
        <span className="text-xs text-muted">Run twice without &quot;start over&quot;: only the newest day is re-read, and the totals don&apos;t change (idempotent).</span>
      </div>

      {st && !st.exists && <div className="card p-4 text-sm text-muted">{st.message}</div>}

      {st?.exists && st.layers && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {st.layers.map((l) => (
              <div key={l.layer} className="card p-4">
                <div className="text-xs uppercase tracking-wide text-muted">{l.layer}</div>
                <div className="text-2xl font-bold tabular-nums">{n(l.rows)}</div>
                <div className="text-xs text-muted">{l.label}</div>
              </div>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="card p-4">
              <h3 className="mb-2 text-sm font-semibold">Health checks <span className="font-normal text-muted">(watermark {st.watermark ?? "none"}, {st.loads} loads)</span></h3>
              <ul className="space-y-1.5 text-sm">
                {st.checks?.map((c) => (
                  <li key={c.name} className="flex gap-2">
                    <span aria-label={c.ok ? "pass" : "fail"} style={{ color: c.ok ? "var(--good)" : "var(--bad)" }}>{c.ok ? "✓" : "✗"}</span>
                    <span><b>{c.name}</b> <span className="text-muted">{c.detail}</span></span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="card p-4">
              <h3 className="mb-2 text-sm font-semibold">Why rows were quarantined</h3>
              {st.quarantine_reasons?.length ? (
                <ul className="space-y-1 text-sm">{st.quarantine_reasons.map((q) => <li key={q.reason} className="flex justify-between"><span>{q.reason}</span><span className="tabular-nums text-muted">{n(q.rows)}</span></li>)}</ul>
              ) : <p className="text-sm text-muted">Nothing quarantined. Try the messy sample.</p>}
            </section>
          </div>
        </>
      )}

      {st && st.history.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="px-4 pt-3 text-left text-sm font-semibold">Run history</caption>
            <thead><tr><th className="th">When (UTC)</th><th className="th">Source</th><th className="th th-r">Bronze read</th><th className="th th-r">Silver</th><th className="th th-r">Quarantined</th><th className="th th-r">Seconds</th></tr></thead>
            <tbody>
              {st.history.map((h) => (
                <tr key={h.at + h.seconds} className="border-t border-line">
                  <td className="px-4 py-2">{h.at}</td><td className="px-4 py-2">{h.source}{h.reset ? " (reset)" : ""}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{n(h.bronze_rows)}</td><td className="px-4 py-2 text-right tabular-nums">{n(h.silver_rows)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{n(h.quarantined)}</td><td className="px-4 py-2 text-right tabular-nums">{h.seconds}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
