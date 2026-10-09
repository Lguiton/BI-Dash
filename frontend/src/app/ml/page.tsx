"use client";

import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Bar, BarChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { MlOptions, MlResult } from "@/lib/types";

const fmt = (v: number | null | undefined, d = 3) => (v == null ? "n/a" : v.toLocaleString(undefined, { maximumFractionDigits: d }));
const DEFAULT_FEATURES = ["category", "weekday", "units_processed", "duration_minutes"];

export default function MlPage() {
  const [opts, setOpts] = useState<MlOptions | null>(null);
  const [task, setTask] = useState("revenue");
  const [model, setModel] = useState("ridge");
  const [features, setFeatures] = useState<string[]>(DEFAULT_FEATURES);
  const [testPct, setTestPct] = useState(20);
  const [balance, setBalance] = useState(false);
  const [threshold, setThreshold] = useState(0.5);
  const [result, setResult] = useState<MlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<MlOptions>("/api/ml/options", ctl.signal)
      .then((o) => { setOpts(o); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load ML options."); });
    return () => ctl.abort();
  }, [attempt]);

  const kind = opts?.tasks.find((t) => t.id === task)?.kind ?? "regression";
  const models = opts?.models[kind] ?? [];
  const taskInfo = opts?.tasks.find((t) => t.id === task);

  function pickTask(id: string) {
    setTask(id);
    const k = opts?.tasks.find((t) => t.id === id)?.kind ?? "regression";
    setModel(opts?.models[k][0]?.id ?? "");
    setResult(null);
  }
  const toggle = (id: string) => setFeatures((f) => (f.includes(id) ? f.filter((x) => x !== id) : [...f, id]));

  async function train() {
    setBusy(true); setError(null);
    try {
      const r = await postJson<MlResult>("/api/ml/train", {
        task, model, features, test_fraction: testPct / 100, balance_classes: balance, threshold,
      });
      setResult(r);
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "Training failed.");
    } finally { setBusy(false); }
  }

  const metricRows = useMemo(() => {
    if (!result) return [];
    return Object.entries(result.metrics).map(([k, v]) => ({ k, model: v, base: result.baseline[k] as number | null | undefined }));
  }, [result]);

  return (
    <PageShell title="ML Lab" subtitle="Train a real scikit-learn model on this data and learn to judge it honestly.">
      {error && <ErrorBanner message={error} onRetry={!opts ? () => setAttempt((a) => a + 1) : undefined} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section className="card space-y-4 p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">Predict
              <select className="field w-full" value={task} onChange={(e) => pickTask(e.target.value)}>
                {(opts?.tasks ?? [{ id: "revenue", label: "Revenue" }]).map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">Model
              <select className="field w-full" value={model} onChange={(e) => setModel(e.target.value)}>
                {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </label>
          </div>
          {taskInfo && <p className="text-xs text-muted">{taskInfo.description}</p>}

          <fieldset>
            <legend className="mb-2 text-sm font-medium">Features (what the model may look at)</legend>
            <div className="space-y-1.5">
              {opts?.features.map((f) => (
                <label key={f.id} className="flex items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-1" checked={features.includes(f.id)} onChange={() => toggle(f.id)} />
                  <span>{f.label} <span className="text-xs text-muted">{f.note}</span></span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block text-sm font-medium">Test set: the most recent {testPct}% of days
            <input type="range" min={10} max={40} step={5} value={testPct} onChange={(e) => setTestPct(Number(e.target.value))} className="w-full" />
          </label>

          {kind === "classification" && (
            <div className="space-y-3 rounded-lg bg-panel2 p-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={balance} onChange={(e) => setBalance(e.target.checked)} />
                Balance classes (weight the rare outcome up)
              </label>
              <label className="block text-sm font-medium">Decision threshold: {threshold.toFixed(2)}
                <input type="range" min={0.02} max={0.9} step={0.01} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-full" />
                <span className="block text-xs font-normal text-muted">Lower = catch more problems but raise more false alarms.</span>
              </label>
            </div>
          )}

          <button className="btn btn-primary" onClick={train} disabled={busy || !opts || features.length === 0}>
            {busy ? "Training…" : "Train and evaluate"}
          </button>
          {features.length === 0 && <p className="text-xs text-muted">Pick at least one feature.</p>}
        </section>

        <section className="min-w-0 space-y-4">
          {!result && !busy && <div className="card p-5 text-sm text-muted">Pick a task and press <b>Train and evaluate</b>. The data is split by <b>date</b> (never shuffled), and every score is shown next to a naive baseline.</div>}
          {result && (
            <>
              {result.lessons.map((l) => <div key={l} className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--accent)" }}>💡 {l}</div>)}
              {result.warnings.map((w) => <div key={w} role="status" className="rounded-lg border border-line px-3 py-2 text-sm" style={{ background: "var(--warn-bg)", color: "var(--fg)" }}>⚠ {w}</div>)}

              <div className="card p-4">
                <h2 className="mb-1 text-sm font-semibold">Split by time</h2>
                <p className="text-xs text-muted">
                  Train: {result.split.train_rows.toLocaleString()} rows, {result.split.train_range[0]} → {result.split.train_range[1]}.
                  Test: {result.split.test_rows.toLocaleString()} rows, {result.split.test_range[0]} → {result.split.test_range[1]}.
                  The model never saw the test period.
                </p>
              </div>

              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="px-4 pt-3 text-left text-sm font-semibold">Test-set scores vs baseline</caption>
                  <thead><tr><th className="th">Metric</th><th className="th th-r">Your model</th><th className="th th-r">Baseline</th></tr></thead>
                  <tbody>
                    {metricRows.map((r) => (
                      <tr key={r.k} className="border-t border-line">
                        <td className="px-4 py-2 uppercase">{r.k}</td>
                        <td className="px-4 py-2 text-right tabular-nums">{fmt(r.model, 4)}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-muted">{typeof r.base === "number" ? fmt(r.base, 4) : "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="px-4 pb-3 pt-1 text-xs text-muted">Baseline: {String(result.baseline.description ?? "")}</p>
              </div>

              {result.cv.scores.length > 0 && (
                <div className="card p-4 text-sm">
                  <b>Stability</b> (4 time-ordered folds, {result.cv.metric}): {result.cv.scores.map((s) => fmt(s, 3)).join(", ")}
                  <span className="text-muted"> — mean {fmt(result.cv.mean)} ± {fmt(result.cv.std)}. A big spread means the score is fragile.</span>
                </div>
              )}

              {result.confusion && (
                <div className="card p-4">
                  <h2 className="mb-2 text-sm font-semibold">Confusion matrix (test set)</h2>
                  <table className="text-sm" aria-label="Confusion matrix">
                    <thead><tr><th className="th" /><th className="th th-r">Predicted fine</th><th className="th th-r">Predicted problem</th></tr></thead>
                    <tbody>
                      <tr><th scope="row" className="th">Actually fine</th><td className="px-4 py-2 text-right tabular-nums">{result.confusion.tn}</td><td className="px-4 py-2 text-right tabular-nums">{result.confusion.fp} <span className="text-xs text-muted">false alarms</span></td></tr>
                      <tr><th scope="row" className="th">Actually a problem</th><td className="px-4 py-2 text-right tabular-nums">{result.confusion.fn} <span className="text-xs text-muted">missed</span></td><td className="px-4 py-2 text-right tabular-nums">{result.confusion.tp}</td></tr>
                    </tbody>
                  </table>
                </div>
              )}

              <div className="card p-4">
                <h2 className="mb-2 text-sm font-semibold">What mattered (permutation importance)</h2>
                <div style={{ height: Math.max(120, result.importance.length * 32) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={result.importance} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid horizontal={false} stroke="var(--line)" />
                      <XAxis type="number" stroke="var(--muted)" fontSize={11} />
                      <YAxis type="category" dataKey="label" width={130} stroke="var(--muted)" fontSize={11} />
                      <Tooltip />
                      <Bar dataKey="importance" fill="var(--accent)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-xs text-muted">Score drop when that feature is shuffled. A feature near 0 adds nothing.</p>
              </div>

              {result.kind === "regression" && (
                <div className="card p-4">
                  <h2 className="mb-2 text-sm font-semibold">Actual vs predicted (test set)</h2>
                  <div style={{ height: 260 }} role="img" aria-label="Scatter of actual versus predicted values">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ left: 8, right: 16, bottom: 16 }}>
                        <CartesianGrid stroke="var(--line)" />
                        <XAxis type="number" dataKey="actual" name="Actual" stroke="var(--muted)" fontSize={11} label={{ value: "Actual", position: "insideBottom", offset: -8, fontSize: 11 }} />
                        <YAxis type="number" dataKey="predicted" name="Predicted" stroke="var(--muted)" fontSize={11} />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                        <Scatter data={result.sample} fill="var(--accent)" fillOpacity={0.6} />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="text-xs text-muted">Points on the diagonal are perfect predictions.</p>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </PageShell>
  );
}
