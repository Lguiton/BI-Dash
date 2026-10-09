"use client";

import { CheckCircle2, Lightbulb, Play, Eye, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { DataFilesPanel } from "@/components/DataFilesPanel";
import { PageShell } from "@/components/PageShell";
import { SavedQueries } from "@/components/SavedQueries";
import { ResultTable } from "@/components/ResultTable";
import { SchemaBrowser } from "@/components/SchemaBrowser";
import { ApiError, getJson, postJson } from "@/lib/api";
import { useSolved } from "@/lib/useSolved";
import type { CheckResult, Exercise, SchemaObject, SqlResult } from "@/lib/types";

const EXAMPLES: { label: string; sql: string }[] = [
  { label: "Peek at the facts", sql: "SELECT *\nFROM fact_operations\nORDER BY record_date DESC\nLIMIT 20" },
  { label: "Revenue by entity (JOIN)", sql: "SELECT e.name, e.category, SUM(f.revenue) AS revenue\nFROM fact_operations f\nJOIN dim_entities e ON f.entity_id = e.entity_id\nGROUP BY e.name, e.category\nORDER BY revenue DESC" },
  { label: "Flat table for BI tools", sql: "SELECT *\nFROM v_operations_flat\nLIMIT 20" },
  { label: "Explain a query plan", sql: "EXPLAIN\nSELECT entity_id, SUM(revenue)\nFROM fact_operations\nGROUP BY entity_id" },
];

const LEVEL = ["", "Beginner", "Intermediate", "Advanced"];

export default function SqlLab() {
  const [mode, setMode] = useState<"sandbox" | "exercises">("sandbox");
  const [schema, setSchema] = useState<SchemaObject[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [sql, setSql] = useState(EXAMPLES[0].sql);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SqlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [solution, setSolution] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const { solved, markSolved } = useSolved();

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([
      getJson<{ objects: SchemaObject[] }>("/api/sql/schema", ctl.signal),
      getJson<{ exercises: Exercise[] }>("/api/sql/exercises", ctl.signal),
    ])
      .then(([s, e]) => { setSchema(s.objects); setExercises(e.exercises); setActiveId((id) => id || e.exercises[0]?.id || ""); })
      .catch((err) => { if (!ctl.signal.aborted) setLoadError(err instanceof ApiError ? err.message : "Couldn't load the SQL Lab."); });
    return () => ctl.abort();
  }, []);

  const active = exercises.find((e) => e.id === activeId);

  const insert = useCallback((text: string) => {
    const el = editor.current;
    if (!el) { setSql((s) => s + text); return; }
    const a = el.selectionStart, b = el.selectionEnd;
    setSql((s) => s.slice(0, a) + text + s.slice(b));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(a + text.length, a + text.length); });
  }, []);

  const run = useCallback(async () => {
    setBusy(true); setError(null); setCheck(null);
    try {
      setResult(await postJson<SqlResult>("/api/sql/run", { sql }));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? e.message : "Query failed.");
    } finally { setBusy(false); }
  }, [sql]);

  const checkAnswer = useCallback(async () => {
    if (!active) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await postJson<CheckResult>(`/api/sql/exercises/${active.id}/check`, { sql });
      setCheck(r);
      if (r.correct) markSolved(active.id);
    } catch (e) {
      setCheck(null);
      setError(e instanceof ApiError ? e.message : "Check failed.");
    } finally { setBusy(false); }
  }, [active, sql, markSolved]);

  const pick = (id: string) => {
    setActiveId(id); setCheck(null); setError(null); setResult(null); setShowHint(false); setSolution(null); setSql("");
    requestAnimationFrame(() => editor.current?.focus());
  };

  const revealSolution = async () => {
    if (!active) return;
    try {
      const r = await getJson<{ solution: string }>(`/api/sql/exercises/${active.id}/solution`);
      setSolution(r.solution);
    } catch { setError("Couldn't load the solution."); }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); if (!busy) { if (mode === "exercises") checkAnswer(); else run(); } }
  };

  return (
    <PageShell title="SQL Lab" subtitle="Practice SQL against your own dashboard data. Read-only, so you cannot break anything.">
      {loadError && (
        <div role="alert" className="rounded-lg border border-line px-4 py-3 text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>{loadError}</div>
      )}

      <div role="tablist" aria-label="Lab mode" className="flex gap-1">
        {(["sandbox", "exercises"] as const).map((m) => (
          <button key={m} role="tab" aria-selected={mode === m} className={`btn ${mode === m ? "btn-primary" : ""}`}
                  onClick={() => { setMode(m); setCheck(null); setError(null); setResult(null); if (m === "sandbox" && !sql) setSql(EXAMPLES[0].sql); }}>
            {m === "sandbox" ? "Sandbox" : `Exercises (${solved.size}/${exercises.length} solved)`}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="space-y-6">
          {mode === "exercises" && (
            <section className="card p-4" aria-label="Exercises">
              <h2 className="text-sm font-semibold uppercase tracking-wide">Exercises</h2>
              <ul className="mt-3 space-y-1">
                {exercises.map((e) => (
                  <li key={e.id}>
                    <button onClick={() => pick(e.id)} aria-current={e.id === activeId}
                            className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-panel2 ${e.id === activeId ? "bg-panel2 font-semibold" : ""}`}>
                      {solved.has(e.id)
                        ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--good)" }} aria-label="solved" />
                        : <span className="mt-0.5 h-4 w-4 shrink-0 rounded-full border border-line" aria-hidden />}
                      <span>{e.title}<span className="block text-xs font-normal text-muted">{LEVEL[e.level]}</span></span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <SavedQueries sql={sql} onLoad={setSql} />
          <SchemaBrowser objects={schema} onInsert={insert} />
          <DataFilesPanel />
        </aside>

        <div className="min-w-0 space-y-4">
          {mode === "exercises" && active && (
            <section className="card p-5" aria-label="Exercise">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">{active.title}</h2>
                <span className="rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{LEVEL[active.level]}</span>
                {active.concepts.map((c) => <span key={c} className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">{c}</span>)}
              </div>
              <p className="mt-3 text-sm">{active.prompt}</p>
              {active.ordered && <p className="mt-1 text-xs text-muted">Row order matters for this one.</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn" onClick={() => setShowHint(!showHint)} aria-expanded={showHint}><Lightbulb className="h-4 w-4" aria-hidden /> {showHint ? "Hide hint" : "Hint"}</button>
                <button className="btn" onClick={revealSolution} disabled={solution !== null}><Eye className="h-4 w-4" aria-hidden /> Show solution</button>
              </div>
              {showHint && <p className="mt-3 rounded-lg p-3 text-sm" style={{ background: "var(--info-bg)" }}>{active.hint}</p>}
              {solution && (
                <div className="mt-3">
                  <p className="text-xs text-muted">Reference solution (try to understand it, then rewrite it yourself):</p>
                  <pre className="mt-1 overflow-x-auto rounded-lg bg-panel2 p-3 font-mono text-xs">{solution}</pre>
                  <button className="btn mt-2" onClick={() => setSql(solution)}><RotateCcw className="h-4 w-4" aria-hidden /> Copy into editor</button>
                </div>
              )}
            </section>
          )}

          <section className="card p-4" aria-label="Query editor">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="sql-editor" className="text-sm font-semibold uppercase tracking-wide">Your query</label>
              {mode === "sandbox" && (
                <select className="field" aria-label="Load an example" value="" onChange={(e) => { const ex = EXAMPLES.find((x) => x.label === e.target.value); if (ex) setSql(ex.sql); }}>
                  <option value="">Examples…</option>
                  {EXAMPLES.map((x) => <option key={x.label} value={x.label}>{x.label}</option>)}
                </select>
              )}
            </div>
            <textarea id="sql-editor" ref={editor} value={sql} onChange={(e) => setSql(e.target.value)} onKeyDown={onKey}
                      spellCheck={false} rows={9} placeholder="SELECT ..."
                      className="field w-full resize-y font-mono text-sm leading-relaxed" />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button className="btn btn-primary" onClick={run} disabled={busy || !sql.trim()}>
                <Play className="h-4 w-4" aria-hidden /> {busy ? "Running…" : "Run"}
              </button>
              {mode === "exercises" && (
                <button className="btn" onClick={checkAnswer} disabled={busy || !sql.trim() || !active}>
                  <CheckCircle2 className="h-4 w-4" aria-hidden /> Check answer
                </button>
              )}
              <span className="text-xs text-muted">Ctrl/⌘ + Enter to {mode === "exercises" ? "check" : "run"}</span>
            </div>
          </section>

          {error && (
            <pre role="alert" className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-line p-3 font-mono text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>{error}</pre>
          )}

          {check && (
            <section aria-label="Check result" className="space-y-2">
              <div role="status" className="rounded-lg p-3 text-sm font-medium"
                   style={{ background: check.correct ? "var(--good-bg)" : "var(--warn-bg)", color: check.correct ? "var(--good)" : "var(--fg)" }}>
                {check.message}
              </div>
              <p className="text-xs text-muted">Your result{check.row_count > 10 ? " (first 10 rows)" : ""}:</p>
              <ResultTable columns={check.columns} rows={check.rows} caption="Your query result" />
            </section>
          )}

          {result && (
            <section aria-label="Results" className="space-y-2">
              <p className="text-xs text-muted">
                {result.row_count.toLocaleString("en-US")} row{result.row_count === 1 ? "" : "s"} · {result.elapsed_ms} ms
                {result.truncated && ` · showing the first ${result.max_rows.toLocaleString("en-US")} rows only`}
              </p>
              <ResultTable columns={result.columns} rows={result.rows} caption="Query results" />
            </section>
          )}
        </div>
      </div>
    </PageShell>
  );
}
