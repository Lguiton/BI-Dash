"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, deleteJson, getJson, postJson } from "@/lib/api";

type Report = {
  id: string; target: string; task: string; split: string; rows: number; best: string; useful: boolean; verdict: string;
  results: Record<string, string | number>[]; importance: { input: string; importance: number }[]; notes: string[];
};
type SavedModel = { id: string; label: string; target: string; task: string; useful: boolean; verdict: string; created: string };
type Info = { role: string; suggestions: string[]; cfo_suggestions?: string[]; math_suggestions?: string[]; can: string[] };
type Reply = { reply: string; provider: string; actions: { label: string }[]; tools_used: { tool: string; error: boolean; what: string }[] };
type Turn = { who: "me" | "ai"; text: string; meta?: Reply };

const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");

/** Per-dashboard assistant: build a model with one click (no AI needed), or ask the department's analyst to do the job. */
export function BizAssistant({ pid, columns, onChange }: { pid: string; columns: string[]; onChange?: () => void }) {
  const targets = columns.filter((c) => c !== "record_date");
  const [info, setInfo] = useState<Info | null>(null);
  const [target, setTarget] = useState(targets[0] ?? "");
  const [rep, setRep] = useState<Report | null>(null);
  const [models, setModels] = useState<SavedModel[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [asking, setAsking] = useState(false);
  const [who, setWho] = useState<"analyst" | "cfo" | "math">("analyst");
  const [ver, setVer] = useState(0);

  useEffect(() => { getJson<Info>(`/api/biz-packs/${pid}/assistant`).then(setInfo).catch((e) => setErr(msg(e))); }, [pid]);
  useEffect(() => { getJson<{ models: SavedModel[] }>("/api/biz-models").then((r) => setModels(r.models)).catch(() => {}); }, [ver]);

  async function build() {
    setBusy(true); setErr(null); setRep(null);
    try { setRep(await postJson<Report>(`/api/biz-packs/${pid}/model`, { target })); setVer((v) => v + 1); onChange?.(); } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  }
  async function ask(text: string) {
    if (!text.trim() || asking) return;
    const history = turns.map((t) => ({ role: t.who === "me" ? "user" : "agent", content: t.text }));
    setTurns((t) => [...t, { who: "me", text }]); setQ(""); setAsking(true); setErr(null);
    try {
      const r = await postJson<Reply>(`/api/biz-packs/${pid}/assistant/chat`, { message: text, history, persona: who });
      setTurns((t) => [...t, { who: "ai", text: r.reply, meta: r }]); setVer((v) => v + 1);
    } catch (e) { setErr(msg(e)); } finally { setAsking(false); }
  }
  const cols = rep ? Object.keys(rep.results[0] ?? {}).filter((k) => k !== "model") : [];

  return (
    <section className="card space-y-4 p-4" aria-label="Assistant and models">
      <h2 className="font-semibold">{info?.role ?? "Assistant"}</h2>
      {err && <ErrorBanner message={err} />}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Build a model <span className="font-normal text-muted">(no AI needed)</span></h3>
        <p className="text-xs text-muted">Pick the column you want to predict. It tests against a do-nothing baseline on rows it never saw, and says plainly if the model isn&apos;t useful.</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm">Predict <select className="field ml-1" aria-label="Column to predict" value={target} onChange={(e) => setTarget(e.target.value)}>{targets.map((c) => <option key={c}>{c}</option>)}</select></label>
          <button className="btn btn-primary" disabled={busy || !target} onClick={build}>{busy ? "Building…" : "Build model"}</button>
        </div>
        {rep && (
          <div className="space-y-2 rounded-lg p-3 text-sm" style={{ background: rep.useful ? "var(--good-bg)" : "var(--warn-bg)" }} role="status">
            <p><strong>{rep.useful ? "Useful. " : "Not useful. "}</strong>{rep.verdict}</p>
            <p className="text-xs text-muted">{rep.task}, {rep.rows.toLocaleString()} rows, {rep.split}</p>
            <table className="w-full text-xs"><thead><tr><th className="text-left">Model</th>{cols.map((c) => <th key={c} className="text-right">{c}</th>)}</tr></thead>
              <tbody>{rep.results.map((r) => <tr key={String(r.model)} style={{ fontWeight: r.model === rep.best ? 700 : 400 }}><td>{String(r.model)}</td>{cols.map((c) => <td key={c} className="text-right">{String(r[c])}</td>)}</tr>)}</tbody></table>
            {rep.importance.length > 0 && <p className="text-xs">What drives it: {rep.importance.map((i) => i.input).join(", ")}</p>}
            {rep.notes.map((n) => <p key={n} className="text-xs">Note: {n}</p>)}
          </div>
        )}
        {models.length > 0 && (
          <details><summary className="cursor-pointer text-xs text-muted">Saved models ({models.length})</summary>
            <ul className="mt-1 space-y-1 text-xs">{models.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2"><span><strong>{m.label}</strong>: predicts {m.target} ({m.task}), {m.useful ? "useful" : "not useful"}, {m.created}</span>
                <button className="btn text-xs" onClick={async () => { await deleteJson(`/api/biz-models/${m.id}`).catch(() => {}); setVer((v) => v + 1); }}>Delete</button></li>))}</ul></details>
        )}
      </div>
      <div className="space-y-2 border-t pt-3" style={{ borderColor: "var(--border)" }}>
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold">Ask the {who === "cfo" ? "Chief Financial Officer (CFO)" : who === "math" ? "Mathematician" : info?.role ?? "analyst"}</h3>
          <div role="group" aria-label="Who to ask" className="flex gap-1 text-xs">{(["analyst", "cfo", "math"] as const).map((w) => (
            <button key={w} className={`btn ${who === w ? "font-semibold underline" : ""}`} aria-pressed={who === w} onClick={() => setWho(w)}>{w === "analyst" ? "Analyst" : w === "cfo" ? "CFO" : "Mathematician"}</button>))}</div></div>
        <div className="flex flex-wrap gap-2">{(who === "cfo" ? info?.cfo_suggestions : who === "math" ? info?.math_suggestions : info?.suggestions)?.map((s) => <button key={s} className="btn text-xs" disabled={asking} onClick={() => ask(s)}>{s}</button>)}</div>
        <div className="space-y-2" aria-live="polite">
          {turns.map((t, i) => (
            <div key={i} className={`rounded-lg p-3 text-sm ${t.who === "me" ? "ml-8" : "mr-8"}`} style={{ background: t.who === "me" ? "var(--info-bg)" : "var(--panel-2)", whiteSpace: "pre-wrap" }}>
              {t.text}
              {t.meta && t.meta.tools_used.length > 0 && <div className="mt-2 text-[11px] text-muted">Used: {t.meta.tools_used.map((u) => u.tool + (u.error ? " (failed)" : "")).join(", ")}{t.meta.actions.map((a) => " · " + a.label).join("")}</div>}
            </div>))}
          {asking && <p className="text-sm text-muted">Working on it…</p>}
        </div>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void ask(q); }}>
          <input className="field flex-1" aria-label="Ask the assistant" value={q} maxLength={1200} onChange={(e) => setQ(e.target.value)} placeholder="Ask a question or tell it what to build" />
          <button className="btn btn-primary" disabled={asking || q.trim().length < 2}>Send</button>
        </form>
        <p className="text-xs text-muted">Everyday questions go to Google Gemini; calculations, forecasts and models go to Claude. Needs <code>GEMINI_API_KEY</code> and/or <code>ANTHROPIC_API_KEY</code> in <code>backend/.env</code> (with only one, it answers everything). It reads your data and can build models; it never edits or deletes your records. What it reads goes to the AI provider you configured.</p>
      </div>
    </section>
  );
}
