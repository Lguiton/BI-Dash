"use client";
import { acceptFor, checkFile } from "@/lib/fileCheck";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postForm, postJson } from "@/lib/api";

type Stage = { key: string; agent: string; title: string; status: string; summary: string; seconds: number; details: Record<string, unknown> };
type Run = { id: string; file: string; name: string; created: string; mode: string; status: string; stages: Stage[]; supervisor: string[]; created_objects: { tables: string[]; packs: string[]; rules: number[] } };
type Hist = { id: string; file: string; name: string; created: string; status: string; mode: string; stages_done: number; stages: number };
type AgentMap = { stages: { key: string; agent: string; does: string; uses: string }[]; not_included: { agent: string; why: string }[] };
type Link_ = { label: string; href: string };
type Sug = { track: string; name: string; does: string; why: string[]; href: string };

const BADGE: Record<string, string> = { ok: "var(--good)", warn: "var(--warn, #b45309)", failed: "var(--bad)", stopped: "var(--bad)", skipped: "var(--muted)", pending: "var(--muted)", not_run: "var(--muted)" };
const LABEL: Record<string, string> = { ok: "Done", warn: "Done, with a warning", failed: "Failed", stopped: "Stopped", skipped: "Skipped", pending: "Waiting", not_run: "Not run" };

export default function IntakePage() {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [preview, setPreview] = useState(true);
  const [protect, setProtect] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [hist, setHist] = useState<Hist[]>([]);
  const [sug, setSug] = useState<{ rid: string; items: Sug[] } | null>(null);
  const [agents, setAgents] = useState<AgentMap | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const stop = useRef(false);

  const m = (e: unknown, d: string) => (e instanceof ApiError ? e.message : d);
  const loadHist = () => getJson<{ runs: Hist[] }>("/api/intake").then((r) => setHist(r.runs)).catch(() => {});
  useEffect(() => { void loadHist(); getJson<AgentMap>("/api/intake/agents").then(setAgents).catch(() => {}); return () => { stop.current = true; }; }, []);

  const drive = async (r: Run) => {
    setRun(r);
    stop.current = false;
    while (r.status === "running" && !stop.current) {
      r = await postJson<Run>(`/api/intake/${r.id}/next`, {});
      setRun(r);
    }
    void loadHist();
  };
  const begin = async () => {
    if (!file) return;
    setBusy(true); setErr(null); setRun(null);
    try {
      const f = new FormData();
      f.append("file", file); f.append("name", name); f.append("target", target); f.append("preview", String(preview)); f.append("protect_pii", String(protect));
      await drive(await postForm<Run>("/api/intake/start", f));
    } catch (e) { setErr(m(e, "The run failed.")); } finally { setBusy(false); }
  };
  const apply = async () => {
    if (!run) return; setBusy(true); setErr(null);
    try { await drive(await postJson<Run>(`/api/intake/${run.id}/apply`, {})); } catch (e) { setErr(m(e, "Couldn't start the full run.")); } finally { setBusy(false); }
  };
  const undo = async () => {
    if (!run) return; setBusy(true); setErr(null);
    try { setRun(await postJson<Run>(`/api/intake/${run.id}/undo`, {})); void loadHist(); } catch (e) { setErr(m(e, "Couldn't undo.")); } finally { setBusy(false); }
  };
  const open = async (id: string) => { setErr(null); try { setRun(await getJson<Run>(`/api/intake/${id}`)); } catch (e) { setErr(m(e, "Couldn't open that run.")); } };

  const finished = !!run?.stages.find((s) => s.key === "report" && s.status !== "pending");
  const runId = run?.id;
  useEffect(() => {
    if (!finished || !runId) return;
    let live = true;
    getJson<{ suggestions: Sug[] }>(`/api/intake/${runId}/suggest`).then((r) => { if (live) setSug({ rid: runId, items: r.suggestions }); }).catch(() => {});
    return () => { live = false; };
  }, [finished, runId]);
  const rep = run?.stages.find((s) => s.key === "report")?.details as { needs_you?: string[]; links?: Link_[] } | undefined;
  const plan = run?.stages.find((s) => s.key === "preview_plan")?.details as { plan?: string[] } | undefined;

  return (
    <PageShell title="Data Intake" subtitle="Upload a file. A supervisor runs it past the security, engineering, analyst, science, ML and BI agents in order, stopping if a gate fails. Nothing is overwritten.">
      <section className="card space-y-3 p-4" aria-label="Upload">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-sm">File (CSV, Excel, JSON, XML, text or log, Parquet, HTML, PDF with a table)
            <input className="field" type="file" accept={acceptFor("data")} aria-label="File" onChange={(e) => { const f = e.target.files?.[0] ?? null; const bad = f ? checkFile(f, "data") : null; setErr(bad); if (bad) e.target.value = ""; setFile(bad ? null : f); }} /></label>
          <label className="flex flex-col gap-1 text-sm">Name for this data<input className="field" value={name} maxLength={50} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q3 sales" /></label>
          <label className="flex flex-col gap-1 text-sm">Column to predict (optional)<input className="field" value={target} maxLength={80} onChange={(e) => setTarget(e.target.value)} placeholder="leave blank to skip modelling" /></label>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} /> Test first (writes nothing, shows the plan)</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={protect} onChange={(e) => setProtect(e.target.checked)} /> Hide personal-data columns from the AI agents</label>
          <button className="btn btn-primary" disabled={!file || busy} onClick={begin}>{busy ? "Working…" : preview ? "Test run" : "Run everything"}</button>
        </div>
      </section>
      {err && <ErrorBanner message={err} />}

      {run && (
        <section className="space-y-3" aria-label="Run">
          <div className="card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">{run.file} · {run.mode === "preview" ? "test run" : "full run"} · {run.status.replace("_", " ")}</h2>
              <span className="flex gap-2">
                {run.status === "preview_done" && <button className="btn btn-primary" disabled={busy} onClick={apply}>Run for real</button>}
                {run.status === "done" && <button className="btn" disabled={busy} onClick={undo}>Undo this run</button>}
              </span>
            </div>
            <ol className="mt-3 space-y-2">
              {run.stages.map((s, i) => (
                <li key={s.key} className="rounded-md border border-line p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium">{i + 1}. {s.agent}</span>
                    <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ color: BADGE[s.status] ?? "inherit", border: `1px solid ${BADGE[s.status] ?? "var(--line)"}` }}>{LABEL[s.status] ?? s.status}{s.seconds ? ` · ${s.seconds}s` : ""}</span>
                  </div>
                  <p className="text-xs text-muted">{s.title}</p>
                  {s.summary && <p className="mt-1 text-sm">{s.summary}</p>}
                  {s.status !== "pending" && s.status !== "not_run" && Object.keys(s.details).length > 0 && (
                    <details className="mt-1 text-xs"><summary className="cursor-pointer text-muted">Details</summary><pre className="mt-1 max-h-60 overflow-auto rounded-md bg-panel2 p-2">{JSON.stringify(s.details, null, 2)}</pre></details>
                  )}
                </li>
              ))}
            </ol>
            {busy && run.status === "running" && <p role="status" className="mt-2 text-sm text-muted">The next agent is working…</p>}
          </div>
          {plan?.plan && <div className="card space-y-1 p-4 text-sm"><h3 className="font-semibold">What a full run would do</h3><ul className="list-disc pl-5">{plan.plan.map((p) => <li key={p}>{p}</li>)}</ul></div>}
          {rep && (
            <div className="card space-y-2 p-4 text-sm">
              <h3 className="font-semibold">What needs you</h3>
              {rep.needs_you && rep.needs_you.length > 0 ? <ul className="list-disc pl-5">{rep.needs_you.map((n) => <li key={n}>{n}</li>)}</ul> : <p>Nothing.</p>}
              <div className="flex flex-wrap gap-2">{rep.links?.map((l) => <Link key={l.href + l.label} className="btn" href={l.href}>{l.label}</Link>)}</div>
            </div>
          )}
          {finished && sug && sug.rid === run?.id && sug.items.length > 0 && (
            <div className="card space-y-2 p-4 text-sm" aria-label="Work on it in a dashboard">
              <h3 className="font-semibold">Where do you want to work on this file?</h3>
              <p className="text-xs text-muted">Best fits first, from the columns and file name. Pick one: it opens that dashboard with your file loaded and its agent ready to start.</p>
              <ul className="grid gap-2 sm:grid-cols-2">
                {sug.items.map((x) => (
                  <li key={x.track} className="rounded border border-line p-3">
                    <Link href={x.href} className="btn btn-primary">Open in {x.name}</Link>
                    <div className="mt-1 text-xs">{x.does}</div>
                    <div className="text-xs text-muted">Why: {x.why.join("; ")}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="card space-y-1 p-4 text-sm"><h3 className="font-semibold">Supervisor notes</h3><ul className="list-disc pl-5 text-muted">{run.supervisor.map((n, i) => <li key={i}>{n}</li>)}</ul></div>
        </section>
      )}

      {agents && (
        <section className="card space-y-2 p-4 text-sm" aria-label="Who does what">
          <h3 className="font-semibold">Who does what</h3>
          <table className="w-full text-left"><thead><tr><th className="border-b border-line px-2 py-1">Agent</th><th className="border-b border-line px-2 py-1">Job</th><th className="border-b border-line px-2 py-1">Dashboards it uses</th></tr></thead>
            <tbody>{agents.stages.map((a) => <tr key={a.key}><td className="border-b border-line px-2 py-1 font-medium">{a.agent}</td><td className="border-b border-line px-2 py-1">{a.does}</td><td className="border-b border-line px-2 py-1 text-muted">{a.uses}</td></tr>)}</tbody></table>
          <p className="text-xs text-muted">Not in the data workflow: {agents.not_included.map((n) => `${n.agent} (${n.why})`).join(" · ")}</p>
        </section>
      )}

      {hist.length > 0 && (
        <section className="card p-4 text-sm" aria-label="Earlier runs">
          <h3 className="mb-2 font-semibold">Earlier runs</h3>
          <ul className="space-y-1">{hist.map((h) => <li key={h.id} className="flex flex-wrap items-center justify-between gap-2"><span>{h.name} ({h.file}) · {h.mode === "preview" ? "test" : "full"} · {h.status.replace("_", " ")} · {h.created}</span><button className="btn !px-2 !py-1 text-xs" onClick={() => open(h.id)}>Open</button></li>)}</ul>
        </section>
      )}
    </PageShell>
  );
}
