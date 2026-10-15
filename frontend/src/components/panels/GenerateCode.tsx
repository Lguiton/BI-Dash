"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Markdown } from "@/components/Markdown";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Lang = { id: string; label: string };
type Finding = { line: number | null; severity: "error" | "warning" | "info"; message: string; hint: string };
type Result = {
  language: string; code: string; notes: string; provider: string; model: string; caution: string; masked_in_request: number; secret_in_code: boolean;
  check: { findings: Finding[]; counts: Record<string, number>; says: string; note: string } | null;
  syntax: { checked: boolean; ok: boolean | null; detail: string };
  risks: { line: number; message: string; hint: string }[];
};
const EXT: Record<string, string> = { python: "py", javascript: "js", typescript: "ts", sql: "sql", bash: "sh", powershell: "ps1" };
const EXAMPLE: Record<string, string> = {
  python: "e.g. read every CSV in a folder, add a total column, and save one combined file",
  javascript: "e.g. a function that formats a number as US dollars and a few test calls",
  typescript: "e.g. a typed function that groups an array of invoices by client",
  sql: "e.g. total revenue per month for the last 12 months from a table called invoices",
  bash: "e.g. back up a folder to a dated zip file and keep only the last 7",
  powershell: "e.g. list the 20 largest files in my Downloads folder",
};

function saveText(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

/** Describe what you want, get code to copy. It is checked and risk-scanned, never run. */
export function GenerateCode() {
  const [langs, setLangs] = useState<Lang[]>([]);
  const [lang, setLang] = useState("python");
  const [ask, setAsk] = useState("");
  const [ctx, setCtx] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ languages: Lang[] }>("/api/code/generate/languages", ctl.signal).then((d) => setLangs(d.languages)).catch(() => {});
    return () => ctl.abort();
  }, []);

  const go = async () => {
    setBusy(true); setErr(null); setRes(null); setCopied(false);
    try { setRes(await postJson<Result>("/api/code/generate", { language: lang, request: ask, context: ctx })); }
    catch (e) { setErr(errMsg(e, "Couldn't generate the code.")); }
    finally { setBusy(false); }
  };
  const copy = async () => {
    if (!res) return;
    try { await navigator.clipboard.writeText(res.code); setCopied(true); } catch { setErr("Your browser blocked copying. Select the code and copy it by hand."); }
  };
  const bad = res ? (res.check?.counts.error ?? 0) + (res.syntax.ok === false ? 1 : 0) : 0;
  return (
    <div className="space-y-4">
      <Section title="Generate code" note="Describe what you want and the assistant writes it. The code is checked and scanned for risky steps before you see it. Nothing is ever run for you: you copy it, read it, and try it on sample data.">
        <div className="space-y-3">
          <Field label="Language"><select className="field" aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)}>{(langs.length ? langs : [{ id: "python", label: "Python" }]).map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</select></Field>
          <Field label="What should the code do?"><textarea className="field h-24 w-full" aria-label="What should the code do" placeholder={EXAMPLE[lang]} maxLength={1500} value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
          <details><summary className="cursor-pointer text-sm text-muted">Add your own code, column names or notes (optional)</summary>
            <textarea className="field mt-2 h-24 w-full" aria-label="Extra context" placeholder="Paste table columns, a sample row, or the function you want changed. Leave out real client data." maxLength={4000} value={ctx} onChange={(e) => setCtx(e.target.value)} />
          </details>
          <div className="flex flex-wrap items-center gap-3">
            <button className="btn btn-primary" disabled={busy || ask.trim().length < 10} onClick={go}>{busy ? "Writing…" : "Generate code"}</button>
            <span className="text-xs text-muted">Goes to your AI provider (complex questions go to Claude first). Passwords and keys you type are blanked first.</span>
          </div>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <Section title="Your code" note={`${res.provider} · ${res.model}`}>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {bad === 0 ? <Badge tone="ok">no errors found</Badge> : <Badge tone="bad">{bad} error(s) found: read before using</Badge>}
              {res.risks.length > 0 && <Badge tone="warn">{res.risks.length} risky step(s)</Badge>}
              {res.secret_in_code && <Badge tone="bad">looks like a secret in the code</Badge>}
              <span className="text-xs text-muted">{res.syntax.detail}</span>
            </div>
            {res.risks.length > 0 && (
              <ul className="space-y-1 rounded border border-line bg-panel2 p-3 text-sm" aria-label="Risky steps">
                {res.risks.map((r, i) => <li key={i}><b>Line {r.line}:</b> {r.message} <span className="text-muted">{r.hint}</span></li>)}
              </ul>
            )}
            {res.check && res.check.findings.length > 0 && (
              <ul className="space-y-1 text-sm" aria-label="Review findings">
                {res.check.findings.slice(0, 8).map((f, i) => <li key={i}><Badge tone={f.severity === "error" ? "bad" : f.severity === "warning" ? "warn" : "muted"}>{f.severity}</Badge> {f.line ? `line ${f.line}: ` : ""}{f.message} <span className="text-muted">{f.hint}</span></li>)}
              </ul>
            )}
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                <button className="btn" onClick={copy}>{copied ? "Copied" : "Copy code"}</button>
                <button className="btn" onClick={() => saveText(`generated.${EXT[res.language] ?? "txt"}`, res.code)}>Download file</button>
                <button className="btn" onClick={go} disabled={busy}>Write it again</button>
              </div>
              <pre aria-label="Generated code" className="max-h-96 overflow-auto rounded bg-panel2 p-3 text-xs"><code>{res.code}</code></pre>
            </div>
            {res.notes && <div aria-label="Notes" className="rounded border border-line p-3 text-sm"><Markdown text={res.notes} /></div>}
            <p className="text-xs text-muted">{res.caution}</p>
          </div>
        </Section>
      )}
    </div>
  );
}
