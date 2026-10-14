"use client";
import { useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Finding = { line: number | null; severity: "error" | "warning" | "info"; code: string; message: string; hint: string };
type Check = { language: string; findings: Finding[]; counts: Record<string, number>; clean: boolean; says: string; note: string; caution: string };
type DiffLine = { kind: "hunk" | "add" | "del" | "same"; text: string };
type Fix = { fixed: string; changed: boolean; changes: string[]; diff: DiffLine[]; before: Record<string, number>; after: Record<string, number>; after_findings: Finding[]; says: string; note: string };

const LANGS = ["auto", "python", "javascript", "html", "json", "sql"];
// The preview page may run scripts but has no network, no storage and no access to this dashboard.
const PREVIEW_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src data:";

function previewDoc(code: string, lang: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}">`;
  if (lang === "javascript") {
    const safe = code.replace(/<\/script/gi, "<\\/script");
    return `<!doctype html><html><head>${meta}<style>body{font:14px system-ui;margin:12px}pre{white-space:pre-wrap}</style></head><body><pre id="log"></pre><script>
var L=document.getElementById('log');['log','info','warn','error'].forEach(function(k){console[k]=function(){L.textContent+=Array.prototype.map.call(arguments,function(a){try{return typeof a==='object'?JSON.stringify(a):String(a)}catch(e){return String(a)}}).join(' ')+'\\n'}});
window.onerror=function(m,s,l){L.textContent+='Error: '+m+' (line '+l+')\\n'};
</script><script>${safe}</script></body></html>`;
  }
  return `<!doctype html><html><head>${meta}</head><body>${code}</body></html>`;
}

export function CodeWorkbench() {
  const [code, setCode] = useState("");
  const [lang, setLang] = useState("auto");
  const [res, setRes] = useState<Check | null>(null);
  const [fix, setFix] = useState<Fix | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [out, setOut] = useState<{ t: "out" | "err" | "status"; s: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [jup, setJup] = useState<{ running: boolean; url: string; how?: string } | null>(null);
  const worker = useRef<Worker | null>(null);

  const eff = res?.language ?? (lang === "auto" ? "" : lang);
  async function run<T>(name: string, fn: () => Promise<T>): Promise<T | undefined> {
    setErr(null); setBusy(name);
    try { return await fn(); } catch (e) { setErr(errMsg(e, "Something went wrong.")); } finally { setBusy(""); }
  }
  const check = () => run("check", async () => { setFix(null); setRes(await postJson<Check>("/api/code/check", { code, language: lang })); });
  const doFix = (mode: "safe" | "ai") => run(mode, async () => { setFix(await postJson<Fix>("/api/code/fix", { code, language: lang, mode })); });
  const toNotebook = () => run("nb", async () => {
    const nb = await postJson<object>("/api/code/notebook", { code, language: lang });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(nb, null, 1)], { type: "application/json" }));
    a.download = "workbench.ipynb"; a.click(); URL.revokeObjectURL(a.href);
    setJup(await getJson<{ running: boolean; url: string; how?: string }>("/api/code/jupyter"));
  });
  function runPython() {
    worker.current?.terminate();
    setOut([]); setRunning(true);
    const w = new Worker("/pyrunner.mjs", { type: "module" });
    worker.current = w;
    const t = setTimeout(() => { stop(); setOut((o) => [...o, { t: "err", s: "Stopped: it ran longer than 20 seconds." }]); }, 20000);
    w.onmessage = (e) => {
      const m = e.data;
      if (m.type === "done") { clearTimeout(t); setRunning(false); w.terminate(); worker.current = null; }
      else setOut((o) => [...o, { t: m.type, s: m.text }]);
    };
    w.onerror = () => { clearTimeout(t); setOut((o) => [...o, { t: "err", s: "The Python runner could not start." }]); setRunning(false); };
    w.postMessage({ code });
  }
  function stop() { worker.current?.terminate(); worker.current = null; setRunning(false); }
  const isWeb = eff === "html" || eff === "javascript" || (lang === "auto" && /<\w+/.test(code));
  const isPy = eff === "python" || (lang === "auto" && !isWeb && !!code.trim() && eff !== "sql" && eff !== "json");
  const tone = (s: string) => (s === "error" ? "bad" : s === "warning" ? "warn" : "muted") as "bad" | "warn" | "muted";

  return (
    <div className="grid gap-4">
      <Section title="Code Workbench" note="Paste code to check it, fix it, preview it or run it. Nothing is saved or written to your files, and your code stays on this computer.">
        <div className="grid gap-2">
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Language"><select aria-label="Code language" className="input" value={lang} onChange={(e) => { setLang(e.target.value); setRes(null); }}>{LANGS.map((l) => <option key={l}>{l}</option>)}</select></Field>
            <button className="btn" disabled={!code.trim() || !!busy} onClick={check}>{busy === "check" ? "Checking…" : "Check"}</button>
            <button className="btn" disabled={!code.trim() || !!busy} onClick={() => doFix("safe")}>Safe fixes</button>
            <button className="btn" disabled={!code.trim() || !!busy} onClick={() => doFix("ai")}>{busy === "ai" ? "Asking…" : "Fix with AI (review first)"}</button>
            {isWeb && <button className="btn" disabled={!code.trim()} onClick={() => setPreview(previewDoc(code, eff === "javascript" || (lang === "auto" && !/<\w+/.test(code)) ? "javascript" : "html"))}>Preview</button>}
            {isPy && <button className="btn" disabled={!code.trim() || running} onClick={runPython}>Run Python</button>}
            {running && <button className="btn" onClick={stop}>Stop</button>}
            <button className="btn" disabled={!code.trim() || !!busy} onClick={toNotebook}>Send to Jupyter (.ipynb)</button>
          </div>
          <textarea aria-label="Code to check" className="input min-h-64 w-full font-mono text-xs" spellCheck={false} value={code} onChange={(e) => { setCode(e.target.value); setRes(null); setFix(null); }} placeholder="Paste Python, JavaScript, HTML, JSON or SQL here…" />
        </div>
        {err && <ErrorBanner message={err} />}
      </Section>

      {res && (
        <Section title={`Check: ${res.language}`} note={res.caution}>
          <p className="mb-2 text-sm">{res.says} {res.note}</p>
          <ul className="grid gap-1 text-sm">
            {res.findings.map((f, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-2"><Badge tone={tone(f.severity)}>{f.severity}</Badge><span className="font-mono text-xs">line {f.line ?? "?"}</span><span>{f.message}</span>{f.hint && <span className="text-xs text-muted">{f.hint}</span>}</li>
            ))}
          </ul>
        </Section>
      )}

      {fix && (
        <Section title="Suggested fix (not applied)" note={fix.note}>
          <p className="mb-2 text-sm">{fix.says}</p>
          <ul className="mb-2 list-disc pl-5 text-sm">{fix.changes.map((c, i) => <li key={i}>{c}</li>)}</ul>
          {fix.changed ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="mb-1 text-xs text-muted">Differences</div>
                <pre aria-label="Differences" className="max-h-80 overflow-auto rounded bg-panel2 p-2 text-xs">{fix.diff.map((d, i) => <div key={i} className={d.kind === "add" ? "bg-emerald-500/20" : d.kind === "del" ? "bg-red-500/20" : d.kind === "hunk" ? "text-muted" : ""}>{d.kind === "add" ? "+ " : d.kind === "del" ? "- " : "  "}{d.text}</div>)}</pre></div>
              <div><div className="mb-1 flex items-center gap-2 text-xs text-muted">Fixed code <button className="btn" onClick={() => navigator.clipboard?.writeText(fix.fixed)}>Copy</button> <button className="btn" onClick={() => { setCode(fix.fixed); setFix(null); setRes(null); }}>Use this in the box</button></div>
                <pre aria-label="Fixed code" className="max-h-80 overflow-auto rounded bg-panel2 p-2 text-xs">{fix.fixed}</pre></div>
            </div>
          ) : <p className="text-sm text-muted">Nothing to change.</p>}
          {fix.after_findings.length > 0 && <p className="mt-2 text-xs text-muted">Still flagged after the fix: {fix.after_findings.map((f) => `line ${f.line}: ${f.message}`).join(" · ")}</p>}
        </Section>
      )}

      {preview !== null && (
        <Section title="Preview" note="Runs in a locked box: no internet, no storage, and it cannot see this dashboard or your files.">
          <iframe title="Code preview" sandbox="allow-scripts" srcDoc={preview} className="h-80 w-full rounded border border-border bg-white" />
          <button className="btn mt-2" onClick={() => setPreview(null)}>Close preview</button>
        </Section>
      )}

      {out.length > 0 && (
        <Section title="Python output" note="Runs inside your browser with Python's standard library only, with no internet. For pandas and data work, send it to Jupyter.">
          <pre aria-label="Python output" className="max-h-80 overflow-auto rounded bg-panel2 p-2 text-xs">{out.map((o, i) => <div key={i} className={o.t === "err" ? "text-red-600" : o.t === "status" ? "text-muted" : ""}>{o.s}</div>)}</pre>
        </Section>
      )}

      {jup && (
        <Section title="Jupyter">
          <p className="text-sm">The notebook downloaded as <b>workbench.ipynb</b>. {jup.running ? <>Jupyter is running on this computer: <a className="underline" href={jup.url} target="_blank" rel="noopener noreferrer">open Jupyter</a>, then Upload the file.</> : <>Jupyter isn&apos;t running. {jup.how}</>}</p>
        </Section>
      )}
    </div>
  );
}
