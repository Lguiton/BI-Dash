"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Stat, Table, errMsg, num } from "@/components/panels/kit";
import { getJson, postJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";
import type { AiProviderId, AiUsage, EvalOverview, EvalRun } from "@/lib/types";

const NAMES: Record<AiProviderId, string> = { google: "Gemini", openai: "OpenAI", anthropic: "Claude" };
const FILL: Record<AiProviderId, string> = { google: "var(--cat-1)", openai: "var(--cat-2)", anthropic: "var(--cat-3)" };
const P: AiProviderId[] = ["google", "openai", "anthropic"];

export function UsagePanel() {
  const [d, setD] = useState<AiUsage | null>(null);
  const [days, setDays] = useState(14);
  const [err, setErr] = useState<string | null>(null);
  const c = useChartColors();
  useEffect(() => {
    const ctl = new AbortController();
    getJson<AiUsage>(`/api/ai/usage?days=${days}`, ctl.signal).then((r) => { setD(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load usage.")); });
    return () => ctl.abort();
  }, [days]);
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {d.today.map((t) => (
          <div key={t.provider} className="card space-y-1 p-4 text-sm">
            <div className="flex items-center justify-between font-semibold">{NAMES[t.provider]} <Badge tone={t.configured ? (t.pct >= 90 ? "bad" : t.pct >= 70 ? "warn" : "ok") : "muted"}>{t.configured ? `${t.pct}% of today's cap` : "no key"}</Badge></div>
            <div className="h-2 rounded bg-panel2" role="progressbar" aria-valuenow={t.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${NAMES[t.provider]} cap used`}><div className="h-2 rounded" style={{ width: `${Math.min(t.pct, 100)}%`, background: FILL[t.provider] }} /></div>
            <div className="text-xs text-muted">{t.used}/{t.limit} questions today · {t.model}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={`Questions (${d.days} days)`} value={num(d.total_questions, 0)} />
        <Stat label="Tokens" value={num(d.total_tokens, 0)} sub="input + output" />
        <Stat label="Estimated cost" value={d.total_cost_usd == null ? "—" : `$${d.total_cost_usd.toFixed(2)}`} sub={d.total_cost_usd == null ? "set prices to see this" : "your prices x tokens"} />
      </div>
      <Section title="Questions per day, by model" note={d.caps_note}>
        <div className="mb-2 flex items-center gap-2 text-xs"><Field label="Window"><select className="field" value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 14, 30, 90].map((n) => <option key={n} value={n}>{n} days</option>)}</select></Field></div>
        <div className="h-56" role="img" aria-label="Stacked bar chart of questions per day by model">
          <ResponsiveContainer width="100%" height="100%" minWidth={200}>
            <BarChart data={d.daily} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis dataKey="day" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} />
              <YAxis stroke={c.axis} fontSize={11} width={28} allowDecimals={false} />
              <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} />
              <Legend />
              {P.map((p) => <Bar key={p} dataKey={p} name={NAMES[p]} stackId="a" fill={FILL[p]} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Which tier went to which model" note="Rows are what the router decided the question was; columns are who answered. A hard question in the Gemini column means the router fell back.">
          <Table head={["Tier", ...P.map((p) => NAMES[p])]} rows={(["simple", "medium", "complex"] as const).map((t) => [t, ...P.map((p) => num(d.matrix[t][p], 0))])} />
        </Section>
        <Section title="Tokens by model" note={d.cost_note}>
          <Table head={["Model", "In", "Out", "Cost"]} rows={P.map((p) => [NAMES[p], num(d.tokens[p].input, 0), num(d.tokens[p].output, 0), d.tokens[p].cost_usd == null ? "—" : `$${d.tokens[p].cost_usd.toFixed(3)}`])} />
        </Section>
      </div>
      {Object.keys(d.by_track).length > 0 && (
        <Section title="Agent questions by discipline"><div className="flex flex-wrap gap-2 text-sm">{Object.entries(d.by_track).map(([t, n]) => <Badge key={t}>{t}: {n}</Badge>)}</div></Section>
      )}
      <Section title="Latest questions">
        {d.recent.length === 0 ? <p className="text-sm text-muted">Nothing asked yet.</p> : (
          <Table head={["When (UTC)", "Question", "Tier", "Model", "Tokens"]} rows={d.recent.map((r) => [r.created_at.slice(5, 16), <span key="q" className="line-clamp-2 break-words">{r.question}</span>, r.tier || "—", NAMES[r.provider as AiProviderId] ?? r.provider, num((r.tin ?? 0) + (r.tout ?? 0), 0)])} />
        )}
      </Section>
    </div>
  );
}

function RunView({ r }: { r: EvalRun }) {
  return (
    <div className="space-y-2">
      <p className="text-sm"><b>{r.passed}/{r.total} passed ({r.pct}%)</b> · {r.mode === "live" ? `live run on ${r.models.join(", ") || "no model"}` : "route check (free)"} · {r.at} UTC</p>
      <ul className="space-y-2">
        {r.results.map((x) => (
          <li key={x.id} className="rounded-md border border-line p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2"><Badge tone={x.ok ? "ok" : "bad"}>{x.ok ? "pass" : "fail"}</Badge><span className="font-medium">{x.ask}</span><Badge>{x.expected_tier}</Badge></div>
            <ul className="mt-1 space-y-0.5 text-xs text-muted">{x.checks.map((k, i) => <li key={i}>{k.ok ? "✓" : "✗"} {k.name}{k.detail ? `: ${k.detail}` : ""}</li>)}</ul>
            {x.reply && <details className="mt-1 text-xs"><summary className="cursor-pointer text-muted">Read the reply ({x.provider}{x.seconds != null ? `, ${x.seconds}s` : ""})</summary><p className="mt-1 whitespace-pre-wrap">{x.reply}</p></details>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EvalsPanel() {
  const [ov, setOv] = useState<EvalOverview | null>(null);
  const [track, setTrack] = useState("pm");
  const [confirm, setConfirm] = useState(false);
  const [shown, setShown] = useState<EvalRun | null>(null);
  const [busy, setBusy] = useState<"route" | "live" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<EvalOverview>("/api/agent-evals", ctl.signal).then(setOv).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the evals.")); });
    return () => ctl.abort();
  }, [ver]);
  const run = async (mode: "route" | "live") => {
    setBusy(mode); setErr(null);
    try { const r = await postJson<EvalRun>("/api/agent-evals/run", { track, mode, confirm: mode === "live" && confirm }); setShown(r); setVer((v) => v + 1); setConfirm(false); }
    catch (e) { setErr(errMsg(e, "The run failed.")); }
    finally { setBusy(null); }
  };
  if (!ov) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const cur = ov.tracks.find((t) => t.track === track);
  const mine = ov.runs.filter((r) => r.track === track);
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Re-runnable checks for each agent" note={ov.note}>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Discipline"><select className="field" value={track} onChange={(e) => { setTrack(e.target.value); setShown(null); }}>{ov.tracks.map((t) => <option key={t.track} value={t.track}>{t.name}</option>)}</select></Field>
          <button className="btn" disabled={busy !== null} onClick={() => run("route")}>{busy === "route" ? "Checking…" : "Run route check (free)"}</button>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> I understand a live run makes real API calls (up to {ov.max_live_cases})</label>
          <button className="btn btn-primary" disabled={busy !== null || !confirm} onClick={() => run("live")}>{busy === "live" ? "Asking the agent…" : "Run live check"}</button>
        </div>
        {cur && <ul className="mt-3 list-disc space-y-0.5 pl-5 text-sm">{cur.cases.map((c) => <li key={c.id}>{c.ask} <Badge>{c.tier}</Badge></li>)}</ul>}
      </Section>
      {shown && <Section title="This run"><RunView r={shown} /></Section>}
      <Section title="History for this discipline" note="Compare the score before and after you change a model, a key or a routing rule. A drop means look at the failing checks.">
        {mine.length === 0 ? <p className="text-sm text-muted">No runs yet.</p> : (
          <Table head={["When (UTC)", "Mode", "Models", "Passed", "Score"]} rows={mine.map((r) => [r.at.slice(5, 16), r.mode, r.models.join(", ") || "—", `${r.passed}/${r.total}`, `${r.pct}%`])} />
        )}
      </Section>
    </div>
  );
}
