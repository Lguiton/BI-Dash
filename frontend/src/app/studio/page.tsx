"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, deleteJson, getJson, postJson } from "@/lib/api";

type Pack = { id: string; title: string; industry: string; rows: number | null; columns: string[] };
type Scores = Record<string, number | null>;
type Report = {
  id: string; task: "regression" | "classification"; target: string; rows: number; train_rows: number; test_rows: number; split: string; how_chosen: string; best: string; useful: boolean; verdict: string; tuning: string; notes: string[]; seconds: number;
  inputs: string[]; input_types: Record<string, string>; classes: string[] | null; baseline_test: Scores;
  leaderboard: { model: string; cv_mean: number; cv_std: number | null; test: Scores; seconds: number; tuned: boolean; params?: Record<string, unknown> }[];
  skipped: { model: string; why: string }[];
  importance: { input: string; importance: number }[];
  effects: { input: string; values: number[]; average_prediction: number[]; meaning: string }[];
  detail: {
    confusion?: { labels: string[]; matrix: number[][] }; per_class?: { class: string; precision: number; recall: number; f1: number; rows: number }[];
    threshold?: { note: string; best_cutoff: number; cost_at_best: number; cost_at_0_5?: number; curve: { cutoff: number; cost: number }[] };
    errors?: { median_abs_error: number; p90_abs_error: number; share_within_10pct: number | null; bias: number };
    learning_curve?: { says: string; points: { rows: number; score: number }[]; metric: string };
  };
};
type Saved = { id: string; label: string; target: string; task: string; best: string; useful: boolean; created: string };
type Why = { prediction: string | number; score: number; score_means: string; reasons: { input: string; value: unknown; typical: unknown; effect: number }[]; how: string };

const MODEL_NAMES: Record<string, string> = { ridge: "Ridge", lasso: "Lasso", elasticnet: "Elastic net", logistic: "Logistic", bayes: "Naive Bayes", knn: "KNN", tree: "Decision tree", forest: "Random forest", extra: "Extra trees", boosting: "Gradient boosting", svm: "SVM", neural: "Neural net" };
const f3 = (v: number | null | undefined) => (v == null ? "–" : String(v));

export default function StudioPage() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [pid, setPid] = useState("");
  const [target, setTarget] = useState("");
  const [tune, setTune] = useState(false);
  const [fp, setFp] = useState(1);
  const [fn, setFn] = useState(1);
  const [off, setOff] = useState<string[]>([]);
  const [rep, setRep] = useState<Report | null>(null);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [row, setRow] = useState<Record<string, string>>({});
  const [pred, setPred] = useState<{ predictions: (string | number)[]; probabilities?: Record<string, number>[] } | null>(null);
  const [why, setWhy] = useState<Why | null>(null);
  const [csv, setCsv] = useState("");
  const [scored, setScored] = useState<string | null>(null);

  const m = (e: unknown, d: string) => (e instanceof ApiError ? e.message : d);
  const loadSaved = () => getJson<{ models: Saved[] }>("/api/biz-models").then((r) => setSaved(r.models)).catch(() => {});
  useEffect(() => {
    getJson<{ packs: Pack[] }>("/api/biz-packs").then((r) => setPacks(r.packs.filter((p) => p.rows))).catch((e) => setErr(m(e, "Couldn't load your dashboards.")));
    void loadSaved();
  }, []);

  const pack = packs.find((p) => p.id === pid);
  const build = async () => {
    setBusy(true); setErr(null); setRep(null); setPred(null); setWhy(null); setScored(null);
    try {
      const all = Object.keys(MODEL_NAMES);
      const r = await postJson<Report>("/api/ml-studio/build", { source: pid, target, tune, fp_cost: fp, fn_cost: fn, models: off.length ? all.filter((k) => !off.includes(k)) : "all" });
      setRep(r); setRow({}); void loadSaved();
    } catch (e) { setErr(m(e, "The build failed.")); } finally { setBusy(false); }
  };
  const open = async (id: string) => { setErr(null); try { setRep(await getJson<Report>(`/api/biz-models/${id}`)); setPred(null); setWhy(null); } catch (e) { setErr(m(e, "Couldn't open that model.")); } };
  const del = async (id: string) => { try { await deleteJson(`/api/biz-models/${id}`); if (rep?.id === id) setRep(null); void loadSaved(); } catch (e) { setErr(m(e, "Couldn't delete it.")); } };
  const body = () => ({ ...Object.fromEntries(Object.entries(row).filter(([, v]) => v !== "")) });
  const predict = async () => {
    if (!rep) return; setErr(null); setWhy(null);
    try {
      setPred(await postJson(`/api/ml-studio/${rep.id}/predict`, { rows: [body()] }));
      setWhy(await postJson<Why>(`/api/ml-studio/${rep.id}/explain`, { row: body() }));
    } catch (e) { setErr(m(e, "Couldn't predict.")); }
  };
  const score = async () => {
    if (!rep) return; setErr(null); setScored(null);
    try { setScored((await postJson<{ csv: string }>(`/api/ml-studio/${rep.id}/score`, { csv })).csv); } catch (e) { setErr(m(e, "Couldn't score that file.")); }
  };
  const download = () => {
    if (!scored) return;
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([scored], { type: "text/csv" })); a.download = "predictions.csv"; a.click(); URL.revokeObjectURL(a.href);
  };

  return (
    <PageShell title="Model Studio" subtitle="Pick a table and a column to predict. The Studio tries many real models, picks the winner without peeking at the test rows, and tells you plainly if it can't beat guessing.">
      <section className="card space-y-3 p-4" aria-label="Build a model">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-sm">Dashboard table
            <select className="field" value={pid} onChange={(e) => { setPid(e.target.value); setTarget(""); }}><option value="">Choose…</option>{packs.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.rows} rows)</option>)}</select></label>
          <label className="flex flex-col gap-1 text-sm">Column to predict
            <select className="field" value={target} onChange={(e) => setTarget(e.target.value)} disabled={!pack}><option value="">Choose…</option>{pack?.columns.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
          <label className="flex items-end gap-2 text-sm"><input type="checkbox" checked={tune} onChange={(e) => setTune(e.target.checked)} /> Also tune the top two (slower)</label>
        </div>
        <details className="text-sm"><summary className="cursor-pointer">Options: models to try and the cost of mistakes</summary>
          <div className="mt-2 flex flex-wrap gap-3">
            {Object.entries(MODEL_NAMES).map(([k, n]) => <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={!off.includes(k)} onChange={(e) => setOff(e.target.checked ? off.filter((x) => x !== k) : [...off, k])} /> {n}</label>)}
          </div>
          <div className="mt-2 flex flex-wrap gap-3">
            <label className="flex items-center gap-1">Cost of a false alarm <input className="field w-20" type="number" min={0} value={fp} onChange={(e) => setFp(Number(e.target.value))} /></label>
            <label className="flex items-center gap-1">Cost of a miss <input className="field w-20" type="number" min={0} value={fn} onChange={(e) => setFn(Number(e.target.value))} /></label>
            <span className="text-xs text-muted">Used for yes/no targets to suggest the best cut-off.</span>
          </div>
        </details>
        <button className="btn btn-primary" disabled={busy || !pid || !target} onClick={build}>{busy ? "Training models… (up to ~2 minutes)" : "Build and compare models"}</button>
      </section>
      {err && <ErrorBanner message={err} />}

      {rep && (
        <section className="space-y-4" aria-label="Model results">
          <div className="card space-y-1 p-4" style={{ borderColor: rep.useful ? "var(--good)" : "var(--bad)" }}>
            <h2 className="text-sm font-semibold">{rep.useful ? "Useful model" : "Not reliable"} · predicting {rep.target} ({rep.task})</h2>
            <p className="text-sm">{rep.verdict}</p>
            <p className="text-xs text-muted">{rep.rows.toLocaleString()} rows · trained on {rep.train_rows.toLocaleString()}, tested on {rep.test_rows.toLocaleString()} · {rep.split}. {rep.how_chosen} {rep.tuning}</p>
            {rep.notes.map((n, i) => <p key={i} className="text-xs text-muted">Note: {n}</p>)}
          </div>
          <div className="card overflow-auto p-4">
            <h3 className="mb-2 text-sm font-semibold">Leaderboard</h3>
            <table className="w-full text-left text-sm"><thead><tr>
              <th className="border-b border-line px-2 py-1">Model</th><th className="border-b border-line px-2 py-1">CV {rep.task === "regression" ? "error" : "F1"}</th>
              {rep.task === "regression" ? <><th className="border-b border-line px-2 py-1">Test error (MAE)</th><th className="border-b border-line px-2 py-1">R²</th></> : <><th className="border-b border-line px-2 py-1">Test accuracy</th><th className="border-b border-line px-2 py-1">Macro F1</th><th className="border-b border-line px-2 py-1">ROC AUC</th></>}
              <th className="border-b border-line px-2 py-1">Seconds</th></tr></thead>
              <tbody>{rep.leaderboard.map((r, i) => (
                <tr key={r.model} className={r.model === rep.best || r.model.startsWith(rep.best) ? "font-semibold" : ""}><td className="border-b border-line px-2 py-1">{i === 0 && r.model !== "Baseline (no learning)" ? "★ " : ""}{r.model}{r.params ? <span className="block text-xs font-normal text-muted">{JSON.stringify(r.params)}</span> : null}</td>
                  <td className="border-b border-line px-2 py-1">{f3(r.cv_mean)}</td>
                  {rep.task === "regression" ? <><td className="border-b border-line px-2 py-1">{f3(r.test.mae)}</td><td className="border-b border-line px-2 py-1">{f3(r.test.r2)}</td></> : <><td className="border-b border-line px-2 py-1">{f3(r.test.accuracy)}</td><td className="border-b border-line px-2 py-1">{f3(r.test.macro_f1)}</td><td className="border-b border-line px-2 py-1">{f3(r.test.roc_auc)}</td></>}
                  <td className="border-b border-line px-2 py-1">{r.seconds}</td></tr>))}</tbody></table>
            {rep.skipped.map((s) => <p key={s.model} className="mt-1 text-xs text-muted">Skipped {s.model}: {s.why}</p>)}
          </div>
          {rep.importance.length > 0 && (
            <div className="card p-4 text-sm"><h3 className="mb-1 font-semibold">What drives it</h3>
              <ul>{rep.importance.map((i) => <li key={i.input}>{i.input}: {i.importance}</li>)}</ul>
              {rep.effects.map((e) => <p key={e.input} className="mt-2 text-xs text-muted">As {e.input} goes from {e.values[0]} to {e.values[e.values.length - 1]}, the {e.meaning} goes from {e.average_prediction[0]} to {e.average_prediction[e.average_prediction.length - 1]}.</p>)}
            </div>)}
          {rep.detail.threshold && <div className="card p-4 text-sm"><h3 className="mb-1 font-semibold">Best cut-off for your costs</h3><p>{rep.detail.threshold.note}</p></div>}
          {rep.detail.confusion && (
            <div className="card overflow-auto p-4 text-sm"><h3 className="mb-2 font-semibold">What it got right and wrong (rows = real, columns = predicted)</h3>
              <table><thead><tr><th className="px-2" />{rep.detail.confusion.labels.map((l) => <th key={l} className="px-2">{l}</th>)}</tr></thead>
                <tbody>{rep.detail.confusion.matrix.map((r, i) => <tr key={i}><th className="px-2 text-left">{rep.detail.confusion!.labels[i]}</th>{r.map((v, j) => <td key={j} className="px-2" style={i === j ? { fontWeight: 700 } : undefined}>{v}</td>)}</tr>)}</tbody></table>
              {rep.detail.per_class && <p className="mt-2 text-xs text-muted">{rep.detail.per_class.map((c) => `${c.class}: precision ${c.precision}, recall ${c.recall} (${c.rows} rows)`).join(" · ")}</p>}
            </div>)}
          {rep.detail.errors && <div className="card p-4 text-sm">Typical miss {rep.detail.errors.median_abs_error}; 9 in 10 misses are under {rep.detail.errors.p90_abs_error}.{rep.detail.errors.share_within_10pct != null ? ` ${Math.round(rep.detail.errors.share_within_10pct * 100)}% of predictions land within 10% of the real value.` : ""}</div>}
          {rep.detail.learning_curve && <div className="card p-4 text-sm">Would more data help? {rep.detail.learning_curve.says}</div>}

          {rep.useful && (
            <div className="card space-y-3 p-4" aria-label="Use the model">
              <h3 className="text-sm font-semibold">Use it</h3>
              <div className="grid gap-2 md:grid-cols-4">
                {rep.inputs.map((c) => <label key={c} className="flex flex-col gap-1 text-xs">{c}<input className="field" type={rep.input_types[c] === "number" ? "number" : "text"} value={row[c] ?? ""} onChange={(e) => setRow({ ...row, [c]: e.target.value })} /></label>)}
              </div>
              <button className="btn" onClick={predict}>Predict and explain</button>
              {pred && <p className="text-sm font-medium">Prediction: {String(pred.predictions[0])}{pred.probabilities ? ` (${Object.entries(pred.probabilities[0]).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(", ")})` : ""}</p>}
              {why && <div className="text-sm"><p className="text-xs text-muted">{why.how}</p><ul>{why.reasons.map((r) => <li key={r.input}>{r.input} = {String(r.value)} (typical {String(r.typical)}): {r.effect > 0 ? "+" : ""}{r.effect}</li>)}</ul></div>}
              <label className="flex flex-col gap-1 text-sm">Score a whole file: paste CSV with columns {rep.inputs.join(", ")}
                <textarea className="field min-h-24 font-mono" value={csv} onChange={(e) => setCsv(e.target.value)} spellCheck={false} /></label>
              <div className="flex gap-2"><button className="btn" disabled={!csv.trim()} onClick={score}>Score file</button>{scored && <button className="btn btn-primary" onClick={download}>Download predictions.csv</button>}</div>
              {scored && <pre className="max-h-40 overflow-auto rounded-md bg-panel2 p-2 text-xs">{scored.split("\n").slice(0, 8).join("\n")}</pre>}
            </div>)}
        </section>
      )}

      {saved.length > 0 && (
        <section className="card p-4 text-sm" aria-label="Saved models">
          <h3 className="mb-2 font-semibold">Saved models</h3>
          <ul className="space-y-1">{saved.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2"><span>{s.label}: {s.target} ({s.task}) · {s.best} · {s.useful ? "useful" : "not reliable"} · {s.created}</span>
              <span className="flex gap-1"><button className="btn !px-2 !py-1 text-xs" onClick={() => open(s.id)}>Open</button><button className="btn !px-2 !py-1 text-xs" aria-label={`Delete ${s.id}`} onClick={() => del(s.id)}>Delete</button></span></li>))}</ul>
        </section>
      )}
    </PageShell>
  );
}
