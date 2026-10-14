"use client";

import { Check, Copy, Download, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { API_BASE, ApiError, getJson } from "@/lib/api";
import type { NotebookInfo } from "@/lib/types";

const JUPYTER = "http://localhost:8888";
const SETUP = `# one time, from the project folder
pip install -r python_practice/requirements-practice.txt

# every time
cd python_practice/notebooks
jupyter lab`;

export default function PythonPage() {
  const [notebooks, setNotebooks] = useState<NotebookInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [jupyter, setJupyter] = useState<"checking" | "up" | "down">("checking");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ notebooks: NotebookInfo[] }>("/api/python/notebooks", ctl.signal)
      .then((r) => { setNotebooks(r.notebooks); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the notebooks."); });
    return () => ctl.abort();
  }, [attempt]);

  useEffect(() => {
    // no-cors: we can't read the reply, but the request only resolves if something is listening on that port
    const ctl = new AbortController();
    fetch(`${JUPYTER}/api/status`, { mode: "no-cors", signal: ctl.signal }).then(() => setJupyter("up")).catch(() => { if (!ctl.signal.aborted) setJupyter("down"); });
    return () => ctl.abort();
  }, [attempt]);

  async function copy() {
    try { await navigator.clipboard.writeText(SETUP); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* user can select the text */ }
  }

  return (
    <PageShell title="Python Lab" subtitle="Jupyter notebooks that load this dashboard's data, with exercises that check themselves.">
      {error && <ErrorBanner message={error} onRetry={() => setAttempt((a) => a + 1)} />}

      <section className="card space-y-4 p-5" aria-label="Launch Jupyter">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Launch Jupyter</h2>
            <span className="rounded-full px-3 py-1 text-xs font-medium" role="status"
                  style={{ background: jupyter === "up" ? "var(--good-bg)" : "var(--panel-2)", color: jupyter === "up" ? "var(--good)" : "var(--muted)" }}>
              {jupyter === "up" ? "Jupyter is running" : jupyter === "checking" ? "Checking…" : "Jupyter not detected on port 8888"}
            </span>
          </div>
          <a className={`btn ${jupyter === "up" ? "btn-primary" : ""}`} href={`${JUPYTER}/lab`} target="_blank" rel="noreferrer">
            <ExternalLink className="h-4 w-4" aria-hidden /> Open Jupyter Lab
          </a>
        </div>
        <div className="relative">
          <pre className="overflow-x-auto rounded-lg bg-panel2 p-4 pr-24 font-mono text-xs leading-relaxed" tabIndex={0}>{SETUP}</pre>
          <button className="btn absolute right-2 top-2" onClick={copy} aria-label="Copy commands">
            {copied ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />} {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="text-xs text-muted">
          Run these in the same terminal you use for the backend (WSL works: Jupyter prints a link, and the page above opens it from Windows).
          Start the backend first so the notebooks read live dashboard data. If it isn&apos;t running they fall back to <span className="font-mono">data_samples/operations_clean.csv</span>.
        </p>
      </section>

      <section aria-label="Notebooks">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide">Notebooks, in order</h2>
        {!notebooks && !error && <p className="text-sm text-muted">Loading…</p>}
        <ol className="grid gap-4 md:grid-cols-2">
          {notebooks?.map((n) => (
            <li key={n.file} className="card flex flex-col gap-3 p-4">
              <div>
                <h3 className="font-semibold">{n.title}</h3>
                <p className="mt-1 text-sm text-muted">{n.summary}</p>
              </div>
              <ul className="flex flex-wrap gap-1.5">
                {n.concepts.map((c) => <li key={c} className="rounded-full bg-panel2 px-2.5 py-0.5 text-xs">{c}</li>)}
                {n.needs_java && <li className="rounded-full px-2.5 py-0.5 text-xs" style={{ background: "var(--warn-bg)" }}>needs Java 17+ and pyspark</li>}
              </ul>
              <div className="mt-auto flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted">{n.file}</span>
                <a className="btn !px-2.5 !py-1 text-xs" href={`${API_BASE}/api/python/notebooks/${n.file}`} download={n.file}>
                  <Download className="h-3.5 w-3.5" aria-hidden /> Download
                </a>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="card p-5 text-sm" aria-label="How the exercises work">
        <h2 className="text-lg font-semibold">How the exercises work</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Each notebook has a <b>Your turn</b> cell with <span className="font-mono">something = None</span>. Replace <span className="font-mono">None</span> with your code.</li>
          <li>The next cell prints <span className="font-mono">PASS</span> or <span className="font-mono">TRY AGAIN</span> plus a hint. It never raises an error, so <b>Run all</b> always finishes.</li>
          <li>Stuck on notebook 03? The worked solution is <span className="font-mono">python_practice/solutions/</span>.</li>
        </ul>
      </section>
    </PageShell>
  );
}
