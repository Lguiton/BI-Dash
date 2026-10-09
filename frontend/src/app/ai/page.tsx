"use client";

import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { AiChart } from "@/components/AiChart";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { AiAnswer, AiProviderId, AiStatus } from "@/lib/types";

const EXAMPLES = [
  "Which entity has the highest profit margin, and how many records is that based on?",
  "Is revenue higher on weekends or weekdays?",
  "Chart weekly revenue for the last 12 weeks.",
  "Show a bar chart of profit margin by category.",
];
const NAMES: Record<AiProviderId, string> = { google: "Gemini", openai: "OpenAI", anthropic: "Claude" };

export default function AiPage() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [question, setQuestion] = useState(EXAMPLES[0]);
  const [provider, setProvider] = useState<"auto" | AiProviderId>("auto");
  const [effort, setEffort] = useState<"auto" | "simple" | "medium" | "complex">("auto");
  const [res, setRes] = useState<AiAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadStatus = (signal?: AbortSignal) =>
    getJson<AiStatus>("/api/ai/status", signal).then(setStatus)
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : "Couldn't reach the API."); });

  useEffect(() => {
    const ctl = new AbortController();
    loadStatus(ctl.signal);
    return () => ctl.abort();
  }, []);

  const ready = (status?.ready.length ?? 0) > 0;
  const allowed = status?.policy?.allowed ?? true;
  const canAsk = allowed && (provider === "auto" ? ready : status?.ready.includes(provider));

  async function ask() {
    setBusy(true); setError(null); setRes(null);
    try { setRes(await postJson<AiAnswer>("/api/ai/ask", { question, provider, effort })); }
    catch (e) { setError(e instanceof ApiError ? e.message : "The request failed."); }
    finally { setBusy(false); loadStatus(); }
  }

  return (
    <PageShell title="AI Lab" subtitle="An agent that answers questions by writing SQL, spread across Gemini, OpenAI and Claude.">
      {error && <ErrorBanner message={error} />}

      {status && (
        <section className="card p-4" aria-label="Providers">
          <div className="grid gap-3 sm:grid-cols-3">
            {status.providers.map((p) => {
              const ok = p.configured && p.sdk_installed;
              return (
                <div key={p.id} className="rounded-lg bg-panel2 p-3 text-sm">
                  <div className="flex items-center justify-between font-semibold">
                    {NAMES[p.id]}
                    <span className="rounded-full px-2 py-0.5 text-xs" style={{ background: ok ? "var(--good-bg)" : "var(--bad-bg)", color: ok ? "var(--good)" : "var(--bad)" }}>
                      {ok ? "ready" : "not set up"}
                    </span>
                  </div>
                  <div className="text-xs text-muted">{p.role}</div>
                  {ok ? (
                    <div className="mt-1 text-xs">{p.model} · {p.used_today}/{p.daily_limit} used today</div>
                  ) : (
                    <div className="mt-1 text-xs text-muted">
                      {!p.configured && <>Add <code>{p.key_env}</code> to <code>backend/.env</code>. </>}
                      {!p.sdk_installed && <>Run <code>pip install {p.pip}</code>. </>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {!ready && <p className="mt-3 text-xs text-muted">Add at least one key, then restart the backend. No keys? The offline exercises in <code>ai_engineering/</code> still run.</p>}
        </section>
      )}

      {status?.policy && !allowed && (
        <div role="status" className="rounded-lg px-4 py-3 text-sm" style={{ background: "var(--warn-bg)" }}>
          AI is switched off for the {status.policy.workspace === "real" ? "Real" : "Practice"} workspace, so no question leaves this computer. Turn it on in <a className="underline" href="/settings">Settings</a>; &ldquo;Summaries only&rdquo; keeps row-level data private.
        </div>
      )}
      {status?.policy && allowed && (status.policy.mode === "aggregate" || status.policy.blocked_columns.length > 0) && (
        <p className="text-xs text-muted">
          Privacy for this workspace: {status.policy.mode === "aggregate" ? "summaries only" : "full access"}
          {status.policy.blocked_columns.length > 0 && `, hidden columns: ${status.policy.blocked_columns.join(", ")}`}.
        </p>
      )}

      <section className="card space-y-3 p-5">
        <label htmlFor="q" className="text-sm font-medium">Your question</label>
        <textarea id="q" className="field w-full" rows={3} maxLength={500} value={question} onChange={(e) => setQuestion(e.target.value)} />
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm">Model{" "}
            <select className="field" value={provider} onChange={(e) => setProvider(e.target.value as typeof provider)}>
              <option value="auto">Auto (spread across keys)</option>
              {(["google", "openai", "anthropic"] as const).map((p) => <option key={p} value={p}>{NAMES[p]} only</option>)}
            </select>
          </label>
          <label className="text-sm">Question type{" "}
            <select className="field" value={effort} onChange={(e) => setEffort(e.target.value as typeof effort)} disabled={provider !== "auto"}>
              <option value="auto">Auto-detect</option>
              <option value="simple">Simple (Gemini first)</option>
              <option value="medium">Medium (OpenAI first)</option>
              <option value="complex">Complex / code (Claude first)</option>
            </select>
          </label>
          <button className="btn btn-primary" onClick={ask} disabled={busy || !canAsk || question.trim().length < 3}>{busy ? "Thinking…" : "Ask"}</button>
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((e) => <button key={e} className="btn text-xs" onClick={() => setQuestion(e)}>{e.slice(0, 38)}…</button>)}
        </div>
        <p className="text-xs text-muted">Each question makes several API calls. Gemini&apos;s free tier is limited; paid providers cost money. Limit: 10 questions per minute. Only read-only SELECTs can run. Try asking for a chart.</p>
      </section>

      {res && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <section className="card space-y-2 p-5">
            <h2 className="text-sm font-semibold">Answer</h2>
            {res.chart && <AiChart chart={res.chart} />}
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{res.answer}</p>
            {res.stopped_early && <p className="text-xs">The agent hit its step limit; the answer may be incomplete.</p>}
            <p className="text-xs text-muted">
              Answered by <b>{NAMES[res.provider]}</b> ({res.model}) · {res.usage.input_tokens.toLocaleString()} tokens in, {res.usage.output_tokens.toLocaleString()} out
            </p>
            {res.route && (
              <p className="text-xs text-muted">
                Routing: {res.route.forced ? "you chose this model" : `${res.route.kind} question (${res.route.reason})`}.
                {res.attempts.length > 1 && <> Tried: {res.attempts.map((a) => `${NAMES[a.provider]} ${a.ok ? "✓" : a.skipped ? `skipped (${a.error})` : `failed (${a.error})`}`).join("; ")}.</>}
              </p>
            )}
            <p className="text-xs text-muted">Always check the SQL in the steps: the answer is only as right as the query behind it.</p>
          </section>
          <section className="card min-w-0 space-y-3 p-5">
            <h2 className="text-sm font-semibold">How it got there ({res.steps.length} tool calls)</h2>
            {res.steps.map((s, i) => (
              <div key={i} className="space-y-1 text-xs">
                <div className="font-semibold">{i + 1}. {s.tool}{s.is_error ? " (error)" : ""}</div>
                {typeof s.input.sql === "string" && <pre className="overflow-auto rounded bg-panel2 p-2" tabIndex={0}><code>{s.input.sql}</code></pre>}
                <pre className="max-h-40 overflow-auto rounded bg-panel2 p-2 text-muted" tabIndex={0}><code>{s.output}</code></pre>
              </div>
            ))}
          </section>
        </div>
      )}
    </PageShell>
  );
}
