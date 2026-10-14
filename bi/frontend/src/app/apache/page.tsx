"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";
import type { ApacheTool } from "@/lib/types";

export default function ApachePage() {
  const [tools, setTools] = useState<ApacheTool[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toolId, setToolId] = useState("spark");
  const [fileIdx, setFileIdx] = useState(0);
  const [copied, setCopied] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ tools: ApacheTool[] }>("/api/apache/tools", ctl.signal)
      .then((r) => { setTools(r.tools); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the Apache examples."); });
    return () => ctl.abort();
  }, [attempt]);

  const tool = tools?.find((t) => t.id === toolId);
  const file = tool?.files[Math.min(fileIdx, (tool?.files.length ?? 1) - 1)];

  async function copy() {
    if (!file) return;
    try {
      await navigator.clipboard.writeText(file.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: user can still select the text */ }
  }

  return (
    <PageShell title="Apache Lab" subtitle="Spark, Airflow and Superset, each wired to the data in this dashboard.">
      {error && <ErrorBanner message={error} onRetry={() => setAttempt((a) => a + 1)} />}

      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="tool" className="text-sm font-medium">Tool</label>
        <select id="tool" value={toolId} onChange={(e) => { setToolId(e.target.value); setFileIdx(0); }}
                className="field">
          {(tools ?? [{ id: "spark", name: "Apache Spark" }, { id: "airflow", name: "Apache Airflow" }, { id: "superset", name: "Apache Superset" }])
            .map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        {tool && <span className="rounded-full bg-panel2 px-3 py-1 text-xs text-muted">{tool.role}</span>}
      </div>

      {!tools && !error && <p className="text-sm text-muted">Loading…</p>}

      {tool && file && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <section className="space-y-4 rounded-xl border border-line bg-panel p-5">
            <p className="text-sm leading-relaxed">{tool.summary}</p>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Class concepts it practices</h2>
              <ul className="flex flex-wrap gap-2">
                {tool.concepts.map((c) => <li key={c} className="rounded-full bg-panel2 px-3 py-1 text-xs">{c}</li>)}
              </ul>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Try it</h2>
              <ol className="list-decimal space-y-2 pl-5 text-sm">
                {tool.steps.map((s) => <li key={s}>{s}</li>)}
              </ol>
            </div>
          </section>

          <section className="min-w-0 rounded-xl border border-line bg-panel">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
              <div role="tablist" aria-label="Files" className="flex flex-wrap gap-1">
                {tool.files.map((f, i) => (
                  <button key={f.path} role="tab" aria-selected={i === fileIdx} className={`btn ${i === fileIdx ? "btn-primary" : ""}`}
                          onClick={() => setFileIdx(i)}>{f.path.split("/").pop()}</button>
                ))}
              </div>
              <button className="btn" onClick={copy} aria-label="Copy file contents">
                {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />} {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="px-4 pt-3 text-xs text-muted">apache_practice/{file.path}</p>
            <pre className="max-h-[32rem] overflow-auto px-4 pb-4 pt-2 text-xs leading-relaxed" tabIndex={0}>
              <code>{file.content}</code>
            </pre>
          </section>
        </div>
      )}
    </PageShell>
  );
}
