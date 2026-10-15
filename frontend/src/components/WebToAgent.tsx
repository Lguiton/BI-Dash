"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { postJson } from "@/lib/api";
import { FIX } from "@/components/toolbox/FieldFix";

const AGENTS: [string, string][] = [
  ["itsupport", "IT Specialist"], ["security", "Cybersecurity"], ["network", "Network"], ["analyst", "Data Analyst / BI"], ["scientist", "Data Science / Stats"],
  ["ml", "ML, NLP, deep learning"], ["engineering", "Data Engineering"], ["ai", "AI Engineering"], ["fullstack", "Full Stack / DevOps"], ["pm", "Project and Product"],
  ["sysanalyst", "Systems Analyst"], ["cpe", "Computer Engineering"],
];
const FIX_AREA: Record<string, "it" | "security" | "network"> = { itsupport: "it", security: "security", network: "network" };
const MAX_TEXT = 4000;
const MAX_ASK = 1100;

/** Picks the agent that matches the dashboard you are on. */
export function agentForPath(path: string): string {
  const f = path.match(/^\/field\/([a-z-]+)/);
  if (f && FIX[f[1]]) return FIX[f[1]].specs[0].agent;
  const t = path.match(/^\/tracks\/([a-z]+)/);
  if (t && AGENTS.some(([id]) => id === t[1])) return t[1];
  return "itsupport";
}

type Reply = { reply: string; provider: string; past_work?: { title: string }[] };

/** Send text you copied from a web page to an agent. The text is labelled as an outside source, secrets are blanked, and you see exactly what goes. */
export function WebToAgent({ url, selection }: { url: string; selection: string }) {
  const path = usePathname();
  const [agent, setAgent] = useState(() => agentForPath(path));
  const [text, setText] = useState("");
  const [ask, setAsk] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<Reply | null>(null);
  const [title, setTitle] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setErr(null); setRes(null); setSaved(null);
    try {
      const r = await postJson<Reply>(`/api/agents/${agent}/chat`, { message: ask.trim().slice(0, 1200), source_text: text.trim() || undefined, source_url: url || undefined });
      setRes(r);
      setTitle(ask.trim().slice(0, 100));
    } catch (e) { setErr(e instanceof Error ? e.message : "The agent couldn't answer."); } finally { setBusy(false); }
  };
  const area = FIX_AREA[agent];
  const save = async () => {
    if (!res || !area) return;
    setErr(null);
    const steps = res.reply.split("\n").map((l) => l.replace(/^[\s>*#\-\d.)]+/, "").trim()).filter((l) => l.length > 2).slice(0, 40);
    let host = "";
    try { host = new URL(url).hostname; } catch { /* no source address */ }
    try {
      await postJson("/api/fixlog", { area, title: title.trim() || "Fix from the web", symptoms: ask.trim(), steps, result: "not_fixed", tags: ["from web"], tools: host ? `Source: ${host}` : "", cause: "" });
      setSaved("Saved to the fix log as 'Not fixed yet'. Open the fix log tab to mark it fixed once you have confirmed it works.");
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); }
  };
  return (
    <div className="space-y-2 border-t border-line p-2 text-xs" aria-label="Send to agent">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">Agent
          <select className="field max-w-48" aria-label="Agent" value={agent} onChange={(e) => setAgent(e.target.value)}>{AGENTS.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select>
        </label>
        <button className="btn" disabled={!selection} onClick={() => setText(selection.slice(0, MAX_TEXT))}>Use my selection{selection ? ` (${Math.min(selection.length, MAX_TEXT)} chars)` : ""}</button>
        <span className="text-muted">{url ? `Source: ${url.replace(/^https:\/\//, "").slice(0, 50)}` : "No page open"}</span>
      </div>
      <textarea className="field h-20 w-full" aria-label="Text from the page" placeholder="Text from the page (select it in Reader view, or paste it). Only the part that matters." value={text} maxLength={MAX_TEXT} onChange={(e) => setText(e.target.value)} />
      <div className="flex gap-1">
        <input className="field min-w-0 flex-1" aria-label="Your case and question" placeholder="Your case and what you want, e.g. Dell laptop, black screen after update: give me the steps" value={ask} maxLength={MAX_ASK} onChange={(e) => setAsk(e.target.value)} />
        <button className="btn btn-primary" disabled={busy || ask.trim().length < 2} onClick={send}>{busy ? "Asking…" : "Send to agent"}</button>
      </div>
      <p className="text-muted">What is sent: your question plus this text ({text.length}/{MAX_TEXT} characters), labelled as an outside source the agent must not obey and should check. Passwords and keys are blanked. It goes to your AI provider, so leave out client details.</p>
      {err && <p role="alert" className="text-red-600">{err}</p>}
      {res && (
        <div className="space-y-1">
          <p className="text-muted">{res.provider}{res.past_work?.length ? ` · started from your past fix: ${res.past_work.map((p) => p.title).join("; ")}` : ""}</p>
          <pre aria-label="Agent reply" className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 font-sans text-sm">{res.reply}</pre>
          <p className="text-muted">Check the steps before you run them. A web page can be wrong or out of date.</p>
          {area && !saved && (
            <div className="flex gap-1"><input className="field min-w-0 flex-1" aria-label="Fix log title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /><button className="btn" onClick={save}>Save to fix log</button></div>
          )}
          {saved && <p className="text-emerald-600">{saved}</p>}
        </div>
      )}
    </div>
  );
}
