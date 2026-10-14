"use client";
import { useCallback, useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { NotebookButton } from "@/components/NotebookButton";
import { useChartColors } from "@/lib/useChartColors";
import { API_BASE, deleteJson, getJson, patchJson, postJson, putJson } from "@/lib/api";
import { Badge, Field, Section, Table, Tabs, errMsg } from "@/components/panels/kit";

interface Cfg { task: string; model: string; features: string[]; testFraction: number; balance: boolean; threshold: number }

export function MlExtras({ cfg }: { cfg: Cfg }) {
  const [tab, setTab] = useState("compare");
  return (
    <section className="space-y-4" aria-label="More ML tools">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Compare, track and serve</h2>
        <NotebookButton kind="ml" body={() => ({ config: cfg })} disabled={cfg.features.length === 0} />
      </div>
      <Tabs tabs={[{ id: "compare", label: "Compare all models" }, { id: "runs", label: "Experiment tracker" }, { id: "registry", label: "Model registry" }]} value={tab} onChange={setTab} label="ML tools" />
      {tab === "compare" && <Compare cfg={cfg} />}
      {tab === "runs" && <Runs />}
      {tab === "registry" && <Registry cfg={cfg} />}
    </section>
  );
}

// ---------------------------------------------------------------- compare
interface CmpRow { rank: number; model: string; label: string; metrics: Record<string, number>; score: number; seconds: number; run_id: number }
interface CmpRes { task: string; metric: string; baseline: number; models: CmpRow[]; failed: { model: string; error: string }[]; note: string; split: { train_rows: number; test_rows: number; cutoff: string } }

function Compare({ cfg }: { cfg: Cfg }) {
  const [res, setRes] = useState<CmpRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true); setErr(null);
    try { setRes(await postJson<CmpRes>("/api/ml/compare", { task: cfg.task, features: cfg.features, test_fraction: cfg.testFraction, balance_classes: cfg.balance, threshold: cfg.threshold })); } catch (e) { setErr(errMsg(e, "The comparison failed.")); setRes(null); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Train every model on the same split" note="Uses the task, features and test size chosen above. Each model is also saved as a run in the tracker. This takes a few seconds to a minute.">
        <button className="btn btn-primary" disabled={busy || cfg.features.length === 0} onClick={go}>{busy ? "Training everything…" : "Compare all models"}</button>
      </Section>
      {res && (
        <Section title={`Ranking by ${res.metric} (baseline ${res.baseline})`} note={`Trained on ${res.split.train_rows.toLocaleString()} rows, tested on ${res.split.test_rows.toLocaleString()} rows from ${res.split.cutoff}. ${res.note}`}>
          <Table head={["#", "Model", res.metric, "Other metrics", "Seconds"]} caption="Model ranking"
            rows={res.models.map((m) => [String(m.rank), m.label, String(m.score), Object.entries(m.metrics).filter(([k]) => k !== res.metric).map(([k, v]) => `${k} ${v}`).join(", "), String(m.seconds)])} />
          {res.failed.length > 0 && <p className="mt-2 text-xs text-amber-600">Couldn&apos;t train: {res.failed.map((f) => `${f.model} (${f.error})`).join("; ")}</p>}
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- tracker
interface Run { id: number; created_at: string; task: string; model: string; metric: string; model_score: number; baseline_score: number; note: string | null; starred: boolean; seconds: number | null; lift: number | null; features: string[] }
interface Cmp { metric: string; common_features: string[]; changed: string[]; best_id: number; hint: string; runs: { id: number; model: string; score: number; baseline: number; seconds: number | null; extra_features: string[]; note: string | null }[] }

function Runs() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [starred, setStarred] = useState(false);
  const [pick, setPick] = useState<number[]>([]);
  const [cmp, setCmp] = useState<Cmp | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ runs: Run[] }>(`/api/ml/runs?limit=60${starred ? "&starred=true" : ""}`, ctl.signal).then((d) => setRuns(d.runs)).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load runs.")); });
    return () => ctl.abort();
  }, [ver, starred]);
  const act = useCallback(async (f: () => Promise<unknown>, m: string) => { setErr(null); setMsg(null); try { await f(); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, m)); } }, []);
  const toggle = (id: number) => setPick((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 6 ? p : [...p, id]));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="rounded-lg p-2 text-sm" style={{ background: "var(--good-bg)", color: "var(--good)" }}>{msg}</p>}
      <Section title="Every training run, kept" note="Pick 2 to 6 runs of the same task to compare them. 'Copy to MLflow' needs the optional mlflow package.">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={starred} onChange={(e) => setStarred(e.target.checked)} /> starred only</label>
          <button className="btn" disabled={pick.length < 2} onClick={() => act(async () => { setCmp(await postJson<Cmp>("/api/ml/runs/compare", { ids: pick })); }, "Couldn't compare those.")}>Compare {pick.length} selected</button>
          <a className="btn" href={`${API_BASE}/api/ml/runs/export.csv`}>Download CSV</a>
          <button className="btn" onClick={() => act(async () => { const r = await postJson<{ copied: number; location?: string }>("/api/ml/runs/mlflow", {}); setMsg(`Copied ${r.copied} runs to MLflow${r.location ? ` (${r.location})` : ""}.`); }, "Couldn't copy to MLflow.")}>Copy to MLflow</button>
        </div>
        {!runs && !err && <p className="text-sm text-muted">Loading…</p>}
        {runs && runs.length === 0 && <p className="text-sm text-muted">No runs yet. Train a model above.</p>}
        {runs && runs.length > 0 && (
          <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Experiment runs</caption>
            <thead><tr><th className="th" /><th className="th">★</th><th className="th">When</th><th className="th">Task</th><th className="th">Model</th><th className="th">Score</th><th className="th">Baseline</th><th className="th">Note</th><th className="th" /></tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <td className="td"><input type="checkbox" aria-label={`Select run ${r.id}`} checked={pick.includes(r.id)} onChange={() => toggle(r.id)} /></td>
                <td className="td"><button className="btn" aria-label={r.starred ? "Unstar" : "Star"} aria-pressed={r.starred} onClick={() => act(() => patchJson(`/api/ml/runs/${r.id}`, { starred: !r.starred }), "Couldn't star it.")}>{r.starred ? "★" : "☆"}</button></td>
                <td className="td whitespace-nowrap">{r.created_at}</td><td className="td">{r.task}</td><td className="td">{r.model}</td>
                <td className="td tabular-nums">{r.model_score} <span className="text-xs text-muted">{r.metric}</span></td><td className="td tabular-nums">{r.baseline_score}</td>
                <td className="td"><input className="field w-40" aria-label={`Note for run ${r.id}`} defaultValue={r.note ?? ""} onBlur={(e) => { if ((e.target.value || "") !== (r.note ?? "")) act(() => patchJson(`/api/ml/runs/${r.id}`, { note: e.target.value }), "Couldn't save the note."); }} /></td>
                <td className="td"><button className="btn" aria-label={`Delete run ${r.id}`} onClick={() => act(() => deleteJson(`/api/ml/runs/${r.id}`), "Couldn't delete.")}>Delete</button></td>
              </tr>
            ))}</tbody></table></div>
        )}
      </Section>
      {cmp && (
        <Section title={`Comparison on ${cmp.metric}`} note={cmp.hint}>
          <p className="mb-2 text-xs text-muted">Changed between runs: {cmp.changed.join(", ") || "nothing"}. Shared features: {cmp.common_features.join(", ")}.</p>
          <Table head={["Run", "Model", "Score", "Baseline", "Seconds", "Extra features", "Note"]} caption="Run comparison"
            rows={cmp.runs.map((r) => [<span key="i">{r.id} {r.id === cmp.best_id && <Badge tone="ok">best</Badge>}</span>, r.model, String(r.score), String(r.baseline), String(r.seconds ?? "—"), r.extra_features.join(", ") || "—", r.note ?? ""])} />
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- registry
interface Ver { id: number; name: string; version: number; stage: string; task: string; model: string; features: string[]; metrics: Record<string, number>; note: string; created_at: string }
interface Card extends Ver { inputs: { feature: string; label: string; kind: string; seen_range?: (number | null)[]; common_values?: string[] }[]; primary: { name: string; model: number | null; baseline: number | null }; baseline: Record<string, number | string>; caveats: string[] }
interface Drift { overall: string; advice: string; note: string; recent_rows: number; recent_from: string; features: { feature: string; label: string; psi: number; level: string }[] }
const STAGES = ["none", "staging", "production", "archived"];

function Registry({ cfg }: { cfg: Cfg }) {
  const [list, setList] = useState<Ver[] | null>(null);
  const [name, setName] = useState("");
  const [sel, setSel] = useState<Ver | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ models: Ver[] }>("/api/models", ctl.signal).then((d) => setList(d.models)).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the registry.")); });
    return () => ctl.abort();
  }, [ver]);
  const register = async () => {
    setBusy(true); setErr(null);
    try { await postJson("/api/models", { name, task: cfg.task, model: cfg.model, features: cfg.features, test_fraction: cfg.testFraction, balance_classes: cfg.balance, threshold: cfg.threshold }); setName(""); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, "Couldn't register that model.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Honest limits: a registered model is a saved file on this computer with a version number and a stage. Predictions run inside this app, one process, no autoscaling. Only load a models folder you created yourself.</p>
      <Section title="Register the model configured above" note={`${cfg.model} predicting ${cfg.task} from ${cfg.features.length} feature(s). Registering trains it and saves a new version under that name.`}>
        <div className="flex flex-wrap items-end gap-2"><Field label="Model name"><input className="field" placeholder="revenue_model" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <button className="btn btn-primary" disabled={busy || !name.trim() || cfg.features.length === 0} onClick={register}>{busy ? "Training…" : "Register"}</button></div>
      </Section>
      {list && list.length > 0 && (
        <Section title="Registered versions">
          <ul className="space-y-1 text-sm">{list.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-2"><b>{m.name}</b> v{m.version} <Badge tone={m.stage === "production" ? "ok" : m.stage === "staging" ? "warn" : "muted"}>{m.stage}</Badge><span className="text-xs text-muted">{m.model} · {Object.entries(m.metrics).slice(0, 2).map(([k, v]) => `${k} ${v}`).join(", ")}</span>
              <button className="btn ml-auto" onClick={() => setSel(m)}>Open</button></li>
          ))}</ul>
        </Section>
      )}
      {sel && <ModelDetail key={`${sel.name}-${sel.version}`} m={sel} onChange={() => { setVer((v) => v + 1); }} onClose={() => setSel(null)} />}
    </div>
  );
}

interface DriftPoint { at: string; overall: string; worst_feature: string; worst_psi: number; recent_rows: number }

/** Every drift check is kept; this charts the worst input's PSI over time against the 0.1 and 0.25 lines. Inputs only, never accuracy. */
function DriftHistory({ points }: { points: DriftPoint[] }) {
  const c = useChartColors();
  if (points.length === 0) return <p className="mt-1 text-xs text-muted">No drift checks recorded yet. Each check you run is kept here.</p>;
  const data = points.map((p, i) => ({ n: i + 1, at: p.at, psi: p.worst_psi, feature: p.worst_feature, level: p.overall }));
  return (
    <div className="mt-2">
      <p className="text-xs text-muted">Worst input over time ({points.length} check{points.length === 1 ? "" : "s"}). Lines mark 0.1 (some drift) and 0.25 (significant).</p>
      <div className="h-40 w-full" role="img" aria-label="Drift readings over time">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
            <XAxis dataKey="n" tick={{ fill: c.axis, fontSize: 11 }} stroke={c.axis} allowDecimals={false} />
            <YAxis tick={{ fill: c.axis, fontSize: 11 }} stroke={c.axis} width={40} />
            <ReferenceLine y={0.1} stroke="#d97706" strokeDasharray="4 4" />
            <ReferenceLine y={0.25} stroke={c.cost} strokeDasharray="4 4" />
            <Tooltip contentStyle={{ background: c.panel, border: `1px solid ${c.line}`, color: c.fg }}
                     formatter={(v) => [String(v), "PSI"]} labelFormatter={(_, p) => { const d = p?.[0]?.payload; return d ? `${d.at} UTC · ${d.feature} · ${d.level}` : ""; }} />
            <Line type="monotone" dataKey="psi" stroke={c.revenue} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Table head={["Checked (UTC)", "Worst input", "PSI", "Level"]} caption="Drift history" rows={[...points].reverse().slice(0, 8).map((p) => [p.at, p.worst_feature, String(p.worst_psi), p.overall])} />
    </div>
  );
}

function ModelDetail({ m, onChange, onClose }: { m: Ver; onChange: () => void; onClose: () => void }) {
  const [card, setCard] = useState<Card | null>(null);
  const [drift, setDrift] = useState<Drift | null>(null);
  const [hist, setHist] = useState<DriftPoint[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [pred, setPred] = useState<{ predictions: { prediction?: number; label?: string; probability?: number }[]; warnings: string[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const base = `/api/models/${encodeURIComponent(m.name)}`;
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Card>(`${base}/card?version=${m.version}`, ctl.signal).then((c) => { setCard(c); setVals(Object.fromEntries(c.inputs.map((i) => [i.feature, i.kind === "cat" ? i.common_values?.[0] ?? "" : String(i.seen_range?.[0] ?? 0)]))); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the model card.")); });
    return () => ctl.abort();
  }, [base, m.version]);
  const loadHist = useCallback(() => { getJson<{ history: DriftPoint[] }>(`${base}/drift/history?version=${m.version}`).then((r) => setHist(r.history)).catch(() => { /* optional */ }); }, [base, m.version]);
  useEffect(() => { loadHist(); }, [loadHist]);
  const act = async (f: () => Promise<void>, msg: string) => { setErr(null); try { await f(); } catch (e) { setErr(errMsg(e, msg)); } };
  if (!card) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <Section title={`${card.name} v${card.version} · model card`}>
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Field label="Stage"><select className="field" value={card.stage} onChange={(e) => act(async () => { await putJson(`${base}/versions/${card.version}/stage`, { stage: e.target.value }); setCard({ ...card, stage: e.target.value }); onChange(); }, "Couldn't change the stage.")}>{STAGES.map((s) => <option key={s}>{s}</option>)}</select></Field>
        <span>{card.primary.name}: <b>{card.primary.model}</b> vs baseline {card.primary.baseline}</span>
        <button className="btn ml-auto" onClick={() => act(async () => { await deleteJson(`${base}/versions/${card.version}`); onChange(); onClose(); }, "Couldn't delete that version.")}>Delete version</button>
        <button className="btn" onClick={onClose}>Close</button>
      </div>
      <ul className="mt-2 list-disc pl-5 text-xs text-muted">{card.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      <h4 className="mt-4 text-sm font-semibold">Try a prediction</h4>
      <div className="mt-1 flex flex-wrap items-end gap-2">
        {card.inputs.map((i) => (
          <Field key={i.feature} label={`${i.label}${i.seen_range ? ` (seen ${i.seen_range[0]} to ${i.seen_range[1]})` : ""}`}>
            {i.kind === "cat" ? <select className="field" value={vals[i.feature] ?? ""} onChange={(e) => setVals({ ...vals, [i.feature]: e.target.value })}>{(i.common_values ?? []).map((v) => <option key={v}>{v}</option>)}</select>
              : <input className="field w-28" type="number" value={vals[i.feature] ?? ""} onChange={(e) => setVals({ ...vals, [i.feature]: e.target.value })} />}
          </Field>
        ))}
        <button className="btn btn-primary" onClick={() => act(async () => setPred(await postJson(`${base}/predict`, { version: card.version, rows: [Object.fromEntries(card.inputs.map((i) => [i.feature, i.kind === "num" ? Number(vals[i.feature]) : vals[i.feature]]))] })), "The prediction failed.")}>Predict</button>
      </div>
      {pred && <div className="mt-2 text-sm"><b>{pred.predictions.map((p) => p.prediction ?? `${p.label} (${p.probability})`).join(", ")}</b>{pred.warnings.map((w) => <p key={w} className="text-xs text-amber-600">{w}</p>)}</div>}
      <h4 className="mt-4 text-sm font-semibold">Has the input data drifted?</h4>
      <button className="btn mt-1" onClick={() => act(async () => { setDrift(await getJson<Drift>(`${base}/drift?version=${card.version}`)); loadHist(); }, "Couldn't check drift.")}>Check drift</button>
      <DriftHistory points={hist} />
      {drift && (
        <div className="mt-2 text-sm">
          <p><Badge tone={drift.overall === "stable" ? "ok" : drift.overall.startsWith("significant") ? "bad" : "warn"}>{drift.overall}</Badge> {drift.advice}</p>
          <Table head={["Input", "PSI", "Level"]} caption="Drift by input" rows={drift.features.map((f) => [f.label, String(f.psi), f.level])} />
          <p className="mt-1 text-xs text-muted">Compared the last {drift.recent_rows} rows (from {drift.recent_from}). {drift.note}</p>
        </div>
      )}
    </Section>
  );
}
