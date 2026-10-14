"use client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Row = { id: string; title: string; status: string; value: string | null; note: string; why: string; fix: string };
type Res = { score_pct: number | null; counts: Record<string, number>; rows: Row[]; start_with: { title: string; fix: string }[]; fix_id: string; limit: string };

export function UnixAudit({ onFix }: { onFix: (id: string) => void }) {
  const [os, setOs] = useState("macos");
  const [script, setScript] = useState("");
  const [text, setText] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const tone = (s: string) => (s === "pass" ? "ok" : s === "fail" ? "bad" : s === "warn" ? "warn" : "muted") as "ok" | "bad" | "warn" | "muted";
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="macOS and Linux hardening audit" note="The app never touches a computer. It writes a read-only script; you run it on a machine you own, paste the output, and it grades each line. A short baseline, not a CIS benchmark.">
        <div className="flex flex-wrap items-end gap-2"><Field label="System"><select aria-label="System type" className="input" value={os} onChange={(e) => { setOs(e.target.value); setScript(""); setRes(null); }}><option value="macos">macOS</option><option value="linux">Linux</option></select></Field>
          <button className="btn" onClick={async () => { setErr(null); try { setScript((await getJson<{ script: string }>(`/api/security/unix/script?os=${os}`)).script); } catch (e) { setErr(errMsg(e, "Could not make the script.")); } }}>Show the script</button>
          {script && <button className="btn" onClick={() => navigator.clipboard?.writeText(script)}>Copy</button>}</div>
        {script && <pre aria-label="Audit script" className="mt-2 max-h-60 overflow-auto rounded bg-panel2 p-2 text-xs">{script}</pre>}
        <Field label="Paste the output here"><textarea aria-label="Script output" className="input mt-3 min-h-28 font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} /></Field>
        <button className="btn mt-2" disabled={!text.trim()} onClick={async () => { setErr(null); try { setRes(await postJson<Res>("/api/security/unix/grade", { os, text })); } catch (e) { setErr(errMsg(e, "Could not grade the output.")); } }}>Grade it</button>
      </Section>
      {res && (
        <Section title={`Result${res.score_pct !== null ? `: ${res.score_pct}% of weighted checks passed` : ""}`} note={res.limit}>
          <table className="w-full text-sm"><tbody>{res.rows.map((r) => <tr key={r.id}><td><Badge tone={tone(r.status)}>{r.status}</Badge></td><td>{r.title}<div className="text-xs text-muted">{r.note}</div></td><td className="text-xs">{(r.status === "fail" || r.status === "warn") && r.fix}</td></tr>)}</tbody></table>
          <button className="btn mt-2" onClick={() => onFix(res.fix_id)}>How to fix these</button>
        </Section>
      )}
    </div>
  );
}
