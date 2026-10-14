"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg } from "./kit";
import { Lesson } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const tone = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "pass" ? "ok" : s === "warn" ? "warn" : s === "fail" ? "bad" : "muted");

export function EndpointTab() {
  const [script, setScript] = useState<string>(""); const [ref, setRef] = useState<R | null>(null);
  const [t, setT] = useState(""); const [res, setRes] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null); const [copied, setCopied] = useState(false);
  useEffect(() => {
    getJson<R>("/api/endpoint/script").then((r) => setScript(r.script)).catch(() => undefined);
    getJson<R>("/api/endpoint/reference").then(setRef).catch(() => undefined);
  }, []);
  const copy = () => { navigator.clipboard?.writeText(script).then(() => setCopied(true)).catch(() => setCopied(false)); };
  const go = () => { setErr(null); postJson<R>("/api/endpoint/grade", { text: t }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Could not grade that.")); }); };
  return (
    <div className="space-y-4">
      <Section title="Windows endpoint hardening audit" note="This app never touches your computer. Step 1: copy the read-only script and run it yourself in PowerShell on a PC you own (as administrator for the fullest results). Step 2: paste what it prints below.">
        <div className="mb-2 flex gap-2"><button className="btn" onClick={copy} disabled={!script}>{copied ? "Copied" : "Copy the read-only script"}</button><button className="btn" onClick={() => setT(ref?.sample ?? "")}>Load sample output</button></div>
        <pre aria-label="Read-only script" className="max-h-48 overflow-auto rounded border border-line bg-panel2 p-3 font-mono text-xs">{script}</pre>
        <Field label="Paste the script's output"><textarea className="field mt-2 font-mono" rows={8} value={t} onChange={(e) => setT(e.target.value)} aria-label="Script output" /></Field>
        <div className="mt-2"><button className="btn btn-primary" onClick={go}>Grade the results</button></div>
        {err && <ErrorBanner message={err} />}
        {res && <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5"><Stat label="Score" value={res.score_pct == null ? "n/a" : `${res.score_pct}%`} /><Stat label="Pass" value={String(res.counts.pass)} /><Stat label="Warn" value={String(res.counts.warn)} /><Stat label="Fail" value={String(res.counts.fail)} /><Stat label="Unknown or missing" value={String(res.counts.unknown + res.counts.missing)} /></div>
          {(res.start_with as R[]).length > 0 && <div><h4 className="text-sm font-semibold">Start with these</h4><ol className="list-decimal space-y-1 pl-5 text-sm">{(res.start_with as R[]).map((x) => <li key={x.id}><strong>{x.title}</strong> ({x.status}). {x.fix}</li>)}</ol><p className="mt-1 text-xs text-muted">Test each change on one machine first, roll it out in phases and keep a way back.</p></div>}
          <Table head={["Check", "Severity", "Result", "Found", "Why it matters"]} rows={(res.rows as R[]).map((r) => [r.title, r.severity === 3 ? "high" : r.severity === 2 ? "medium" : "low", <Badge key="s" tone={tone(r.status)}>{r.status}</Badge>, r.value == null ? "-" : `${r.value}: ${r.note}`, r.why])} caption="Hardening results" />
          <Lesson text={res.lesson} /><p className="text-xs text-muted">{res.limit}</p>
        </div>}
      </Section>
      {ref && <Section title="Rollout process and slips in the source checklist">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{(ref.process as string[]).map((x) => <li key={x}>{x}</li>)}</ol>
        <h4 className="mt-3 text-sm font-semibold">Mistakes and gaps in the source guide</h4>
        <ul className="list-disc space-y-1 pl-5 text-sm">{(ref.slips as string[]).map((x) => <li key={x}>{x}</li>)}</ul>
        <p className="mt-2 text-xs text-muted">Not built: {(ref.not_built as string[]).join(" ")}</p>
      </Section>}
    </div>
  );
}
