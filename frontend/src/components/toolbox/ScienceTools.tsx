"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Tabs, errMsg } from "@/components/panels/kit";
import { Notes, Pick, Rows, SourcePick, isDate, isNum, useCols } from "./common";

type Fc = { history: { date: string; value: number }[]; backtest: { method: string; label: string; mae: number; better_than_naive_pct: number }[]; windows_tested: number; method_used: string; forecast: { date: string; forecast: number; low: number; high: number }[]; verdict: string; range_note: string; caution: string };
type Model = { id: string; label: string; verdict: string; useful: boolean };
type Dr = { status: string; says: string; unit: string; older: { rows: number; error: number; guess: number }; recent: { rows: number; error: number; guess: number }; change_pct: number; inputs: { input: string; flag: boolean; says: string }[]; how: string; caution: string };
type Sg = { k: number; silhouette: number; separation: string; rows_used: number; segments: { segment: number; name: string; rows: number; share_pct: number; profile: { column: string; average: number; overall: number; level: string }[] }[]; caution: string };

function Chart({ hist, fc }: { hist: { date: string; value: number }[]; fc: { date: string; forecast: number; low: number; high: number }[] }) {
  const h = hist.slice(-60), W = 640, H = 180, P = 8;
  const all = [...h.map((x) => x.value), ...fc.flatMap((x) => [x.low, x.high])];
  const lo = Math.min(...all), hi = Math.max(...all), n = h.length + fc.length;
  const x = (i: number) => P + (i * (W - 2 * P)) / Math.max(1, n - 1);
  const y = (v: number) => H - P - ((v - lo) / Math.max(1e-9, hi - lo)) * (H - 2 * P);
  const line = h.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const f = fc.map((p, i) => `${i ? "L" : "M"}${x(h.length + i).toFixed(1)},${y(p.forecast).toFixed(1)}`).join("");
  const band = fc.map((p, i) => `${x(h.length + i).toFixed(1)},${y(p.high).toFixed(1)}`).join(" ") + " " + [...fc].reverse().map((p, i) => `${x(h.length + fc.length - 1 - i).toFixed(1)},${y(p.low).toFixed(1)}`).join(" ");
  return (
    <svg role="img" aria-label="Forecast chart: history, forecast and range" viewBox={`0 0 ${W} ${H}`} className="w-full max-w-2xl rounded border border-line bg-panel2">
      <polygon points={band} fill="currentColor" opacity="0.15" />
      <path d={line} fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d={f} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 3" />
    </svg>
  );
}

function ForecastStudio() {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [f, setF] = useState({ date_col: "", value_col: "", agg: "sum", freq: "day", horizon: "14" });
  const [r, setR] = useState<Fc | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dates = cols.filter((c) => isDate(c.type)).map((c) => ({ id: c.name, label: c.name }));
  const nums = cols.filter((c) => isNum(c.type)).map((c) => ({ id: c.name, label: c.name }));
  async function run() {
    setErr(null); setR(null); setBusy(true);
    try { setR(await postJson<Fc>("/api/toolbox/ds/forecast", { source: src, ...f, value_col: f.agg === "count" ? null : f.value_col, horizon: +f.horizon })); } catch (e) { setErr(errMsg(e, "Could not forecast.")); } finally { setBusy(false); }
  }
  return (
    <Section title="Forecast studio" note="Four methods are tested on past data and compared with just repeating the last value. The range is how wrong the method really was before.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <SourcePick value={src} onChange={(v) => { setSrc(v); setF({ ...f, date_col: "", value_col: "" }); setR(null); }} />
        <Pick label="Date column" value={f.date_col} onChange={(v) => setF({ ...f, date_col: v })} options={dates} />
        <Pick label="Per period" value={f.freq} onChange={(v) => setF({ ...f, freq: v })} options={[{ id: "day", label: "day" }, { id: "week", label: "week" }, { id: "month", label: "month" }]} blank="" />
        <Pick label="How" value={f.agg} onChange={(v) => setF({ ...f, agg: v })} options={[{ id: "sum", label: "Add up" }, { id: "avg", label: "Average" }, { id: "count", label: "Count rows" }]} blank="" />
        {f.agg !== "count" && <Pick label="Of this column" value={f.value_col} onChange={(v) => setF({ ...f, value_col: v })} options={nums} />}
        <Field label="Periods ahead"><input aria-label="Periods ahead" className="input" inputMode="numeric" value={f.horizon} onChange={(e) => setF({ ...f, horizon: e.target.value })} /></Field>
      </div>
      <button className="btn mt-3" disabled={busy || !src || !f.date_col || (f.agg !== "count" && !f.value_col)} onClick={run}>{busy ? "Testing methods…" : "Forecast"}</button>
      {r && (
        <div className="mt-3 grid gap-2">
          <p className="text-sm" aria-label="Forecast verdict"><Badge tone={r.method_used === "naive" ? "warn" : "ok"}>{r.method_used.replace("_", " ")}</Badge> {r.verdict}</p>
          <Chart hist={r.history} fc={r.forecast} />
          <Rows columns={["Method", "Typical miss", "Better than repeating last value"]} rows={r.backtest.map((b) => [b.label, b.mae, `${b.better_than_naive_pct}%`])} caption={`Tested over ${r.windows_tested} past window(s)`} />
          <Rows columns={["Date", "Forecast", "Low", "High"]} rows={r.forecast.map((p) => [p.date, p.forecast, p.low, p.high])} caption="Forecast with honest range" />
          <Notes tone="info" items={[r.range_note, r.caution]} />
        </div>
      )}
    </Section>
  );
}

function useModels(): Model[] {
  const [m, setM] = useState<Model[]>([]);
  useEffect(() => {
    let live = true;
    getJson<{ models: Model[] }>("/api/biz-models").then((r) => { if (live) setM(r.models); }).catch(() => {});
    return () => { live = false; };
  }, []);
  return m;
}

function ModelCard() {
  const models = useModels();
  const [mid, setMid] = useState("");
  const [owner, setOwner] = useState("");
  const [purpose, setPurpose] = useState("");
  const q = `owner=${encodeURIComponent(owner)}&purpose=${encodeURIComponent(purpose)}`;
  return (
    <Section title="Model card and handoff" note="A plain-English page a client can read: what the model does, how it was tested, where it fails and how to keep it healthy.">
      {models.length === 0 && <p className="text-sm text-muted">No saved models yet. Build one in the Model studio first.</p>}
      <div className="grid gap-2 sm:grid-cols-3">
        <Pick label="Saved model" value={mid} onChange={setMid} options={models.map((m) => ({ id: m.id, label: m.label }))} />
        <Field label="Owner"><input aria-label="Model owner" className="input" value={owner} onChange={(e) => setOwner(e.target.value)} /></Field>
        <Field label="Purpose (optional)"><input aria-label="Model purpose" className="input" value={purpose} onChange={(e) => setPurpose(e.target.value)} /></Field>
      </div>
      {mid && <p className="mt-3"><a className="btn" href={`${API_BASE}/api/toolbox/ds/modelcard/${mid}?${q}`} target="_blank" rel="noreferrer">Open the model card (print to PDF)</a></p>}
    </Section>
  );
}

function Drift() {
  const models = useModels();
  const [mid, setMid] = useState("");
  const [days, setDays] = useState("30");
  const [r, setR] = useState<Dr | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="Model drift check" note="Scores the saved model on recent rows with known answers and compares with older rows and with the simple guess.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <Pick label="Saved model" value={mid} onChange={(v) => { setMid(v); setR(null); }} options={models.map((m) => ({ id: m.id, label: m.label }))} />
        <Field label="Recent window (days)"><input aria-label="Recent days" className="input" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value)} /></Field>
      </div>
      <button className="btn mt-3" disabled={!mid} onClick={async () => { setErr(null); setR(null); try { setR(await postJson<Dr>("/api/toolbox/ds/drift", { model: mid, recent_days: +days })); } catch (e) { setErr(errMsg(e, "Could not check.")); } }}>Check drift</button>
      {r && (
        <div className="mt-3 grid gap-2">
          <p aria-label="Drift verdict" className="text-sm"><Badge tone={r.status === "ok" ? "ok" : r.status === "watch" ? "warn" : "bad"}>{r.status}</Badge> {r.says}</p>
          <Rows columns={["", "Rows", r.unit, "Simple guess"]} rows={[["Older", r.older.rows, r.older.error, r.older.guess], ["Recent", r.recent.rows, r.recent.error, r.recent.guess]]} caption={`${r.how} (${r.change_pct}% change)`} />
          <Rows columns={["Input", "Flag", "What changed"]} rows={r.inputs.map((i) => [i.input, i.flag ? "check" : "ok", i.says])} caption="Inputs" />
          <Notes tone="info" items={[r.caution]} />
        </div>
      )}
    </Section>
  );
}

function Segments() {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [sel, setSel] = useState<string[]>([]);
  const [k, setK] = useState("");
  const [r, setR] = useState<Sg | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const nums = cols.filter((c) => isNum(c.type));
  return (
    <Section title="Customer segments" note="Groups rows that look alike on the columns you pick, then describes each group in words.">
      {err && <ErrorBanner message={err} />}
      <SourcePick value={src} onChange={(v) => { setSrc(v); setSel([]); setR(null); }} />
      <div className="mt-2 flex flex-wrap gap-3 text-sm">{nums.map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={sel.includes(c.name)} onChange={(e) => setSel(e.target.checked ? [...sel, c.name] : sel.filter((x) => x !== c.name))} />{c.name}</label>)}</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3"><Field label="Number of groups (blank = pick best)"><input aria-label="Groups" className="input" inputMode="numeric" value={k} onChange={(e) => setK(e.target.value)} /></Field></div>
      <button className="btn mt-3" disabled={sel.length < 2} onClick={async () => { setErr(null); setR(null); try { setR(await postJson<Sg>("/api/toolbox/ds/segments", { source: src, features: sel, k: k ? +k : null })); } catch (e) { setErr(errMsg(e, "Could not segment.")); } }}>Find segments</button>
      {r && (
        <div className="mt-3 grid gap-2">
          <p className="text-sm" aria-label="Segment summary">{r.k} groups from {r.rows_used.toLocaleString()} rows. Separation: <Badge tone={r.separation === "clear" ? "ok" : r.separation === "fair" ? "muted" : "warn"}>{r.separation}</Badge></p>
          {r.segments.map((s) => (
            <div key={s.segment} className="rounded border border-line p-2 text-sm"><b>Segment {s.segment}: {s.name}</b> <span className="text-xs text-muted">{s.rows.toLocaleString()} rows ({s.share_pct}%)</span>
              <ul className="mt-1 text-xs">{s.profile.map((p) => <li key={p.column}>{p.column}: {p.average.toLocaleString()} vs {p.overall.toLocaleString()} overall ({p.level})</li>)}</ul></div>
          ))}
          <Notes tone="info" items={[r.caution]} />
        </div>
      )}
    </Section>
  );
}

export function ScienceTools() {
  const [tab, setTab] = useState("fc");
  return (
    <div className="grid gap-3">
      <Tabs label="Data science tools" value={tab} onChange={setTab} tabs={[{ id: "fc", label: "Forecast studio" }, { id: "card", label: "Model card" }, { id: "drift", label: "Drift check" }, { id: "seg", label: "Segments" }]} />
      {tab === "fc" && <ForecastStudio />}
      {tab === "card" && <ModelCard />}
      {tab === "drift" && <Drift />}
      {tab === "seg" && <Segments />}
    </div>
  );
}
