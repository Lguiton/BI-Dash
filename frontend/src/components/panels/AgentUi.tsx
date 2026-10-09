"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Search, Send } from "lucide-react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getJson, postJson, putJson } from "@/lib/api";
import type { AgentAction, AgentInfo, AgentMsg, AgentProposal } from "@/lib/types";
import { Badge, errMsg } from "./kit";

interface ChatResp { reply: string; provider: string; model: string; route: { kind: string } | null; proposals: AgentProposal[]; actions: AgentAction[]; tools_used: { tool: string }[]; stopped_early: boolean }

const DIRECT_EXAMPLES: Record<string, string[]> = {
  pm: ["Draft 5 backlog items for a customer-reporting feature", "Add the top 3 risks you see in my plan", "Which item should I do first?", "Take me to the schedule tab"],
  sysanalyst: ["Draft 6 requirements for a billing portal", "Which of my requirements have no test?", "How many servers do I need at 40 arrivals/hour?", "Open the feasibility tab"],
  engineering: ["Suggest an owner and class for each table", "Should I run a checkpoint now?", "Which governance gaps should I fix first?", "Take me to the PII scan"],
  analyst: ["Suggest 3 KPIs with targets", "Which entity is most over budget?", "Write SQL for weekly margin", "Open the KPI builder"],
  scientist: ["Is my weekend result real?", "What confounders could explain it?", "Which test fits two groups with unequal spread?"],
  ml: ["What baseline should I beat?", "Compare my last runs", "Why is my train score better than test?"],
  ai: ["Which privacy mode fits my real data?", "Why did this question go to that model?", "Write an eval for my data agent"],
  fullstack: ["Review the SQL safety of a generated router", "What should I test for a POST endpoint?", "Take me to the scaffold tab"],
};

/** Conversation state lives above the views so it survives switching between Manual, Tools and Agent. */
export function useAgentChat(track: string) {
  const [messages, setMessages] = useState<AgentMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const ref = useRef<AgentMsg[]>([]);
  ref.current = messages;
  const send = useCallback(async (text: string, stepId?: string) => {
    const t = text.trim();
    if (t.length < 2) return;
    const history = ref.current.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: t }]);
    setBusy(true);
    try {
      const r = await postJson<ChatResp>(`/api/agents/${track}/chat`, { message: t, history, step_id: stepId ?? null });
      const used = r.tools_used.length ? ` · used ${r.tools_used.map((x) => x.tool).join(", ")}` : "";
      setMessages((m) => [...m, { role: "agent", content: r.reply, proposals: r.proposals, actions: r.actions, meta: `${r.route?.kind ? `${r.route.kind} → ` : ""}${r.provider}${used}` }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "agent", content: e instanceof ApiError ? e.message : "The agent couldn't answer.", error: true }]);
    } finally { setBusy(false); }
  }, [track]);
  return { messages, busy, send, clear: () => setMessages([]) };
}

/** The always-visible search bar: ask a question or tell the agent what to do. */
export function CommandBar({ name, busy, onSend }: { name: string; busy: boolean; onSend: (text: string) => void }) {
  const [q, setQ] = useState("");
  const go = () => { if (q.trim().length >= 2 && !busy) { onSend(q); setQ(""); } };
  return (
    <form role="search" aria-label={`Ask or instruct the ${name}`} className="card flex items-center gap-2 p-2" onSubmit={(e) => { e.preventDefault(); go(); }}>
      <Search className="ml-2 h-4 w-4 shrink-0 text-muted" aria-hidden />
      <input className="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm outline-none" value={q} maxLength={1200} onChange={(e) => setQ(e.target.value)}
             placeholder={`Ask the ${name} a question, or tell it what to do…`} aria-label={`Message the ${name}`} />
      <button className="btn btn-primary" type="submit" disabled={busy || q.trim().length < 2}><Send className="h-4 w-4" aria-hidden /> {busy ? "Thinking…" : "Send"}</button>
    </form>
  );
}

const ENDPOINT: Record<string, string> = { item: "/api/pm/items", risk: "/api/pm/risks", okr: "/api/pm/okrs", requirement: "/api/sysanalyst/requirements", kpi: "/api/kpis" };
async function applyProposal(p: AgentProposal): Promise<string> {
  if (p.type === "asset") { await putJson(`/api/governance/assets/${encodeURIComponent(String(p.data.name))}`, p.data); return "Saved to the catalog."; }
  if (p.type === "action") {
    if (p.data.name === "checkpoint") { await postJson("/api/dba/checkpoint", {}); return "Checkpoint done."; }
    const r = await postJson<{ ok?: boolean; detail?: string }>("/api/dba/verify-backup", {}); return `Backup check ${r.ok ? "passed" : "FAILED"}${r.detail ? `: ${r.detail}` : ""}`;
  }
  await postJson(ENDPOINT[p.type], p.data); return "Added.";
}
function Proposal({ p }: { p: AgentProposal }) {
  const [state, setState] = useState<{ s: "idle" | "busy" | "ok" | "err"; msg?: string }>({ s: "idle" });
  const title = String(p.data.title ?? p.data.name ?? p.data.kr ?? p.type);
  const detail = Object.entries(p.data).filter(([k, v]) => v !== "" && v != null && !["title", "name", "status"].includes(k)).map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`).join(" · ");
  return (
    <div className="mt-2 rounded-md border border-line bg-panel2 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2"><Badge>draft {p.type}</Badge><b className="text-sm">{title}</b></div>
      {detail && <div className="mt-1 text-muted">{detail}</div>}
      {p.reason && <div className="mt-1 text-muted">Why: {p.reason}</div>}
      <div className="mt-2 flex items-center gap-2">
        <button className="btn !py-0.5 text-xs" disabled={state.s === "busy" || state.s === "ok"} onClick={async () => {
          setState({ s: "busy" });
          try { setState({ s: "ok", msg: await applyProposal(p) }); } catch (e) { setState({ s: "err", msg: errMsg(e, "That didn't save.") }); }
        }}>{state.s === "ok" ? "Done" : p.type === "action" ? "Run it" : "Add to my workspace"}</button>
        {state.msg && <span role="status" className={state.s === "err" ? "text-red-600" : "text-emerald-600"}>{state.msg}</span>}
      </div>
    </div>
  );
}

export function AgentPanel({ track, chat, onAction }: { track: string; chat: ReturnType<typeof useAgentChat>; onAction: (a: AgentAction) => void }) {
  const [info, setInfo] = useState<AgentInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<AgentInfo>(`/api/agents/${track}`, ctl.signal).then(setInfo).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the agent.")); });
    return () => ctl.abort();
  }, [track]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [chat.messages.length]);
  if (err) return <ErrorBanner message={err} />;
  if (!info) return <p className="text-sm text-muted">Loading…</p>;
  const ready = info.status.ready.length > 0, allowed = info.status.policy.allowed;
  const examples = [...(DIRECT_EXAMPLES[track] ?? []), ...info.suggestions.slice(0, 2)];
  return (
    <div className="space-y-4">
      <section className="card space-y-2 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-base font-semibold"><Bot className="h-5 w-5" aria-hidden /> {info.name}</h2>
          <div className="flex gap-2 text-xs"><Badge tone={allowed ? "ok" : "bad"}>privacy: {info.status.policy.mode}</Badge><Badge tone={ready ? "ok" : "warn"}>{ready ? `provider: ${info.status.ready.join(", ")}` : "no AI key yet"}</Badge></div>
        </div>
        <p className="text-sm text-muted">Focus: {info.focus}.</p>
        <ul className="list-disc space-y-0.5 pl-5 text-sm">{info.can.map((c) => <li key={c}>{c}</li>)}</ul>
        <p className="text-xs text-muted">It can&apos;t change anything by itself: drafts come with an Add button and links open only when you click. Whatever it reads (per your privacy mode) is sent to the AI provider. {!allowed && "AI is off for this workspace: switch it on in Settings."} {allowed && !ready && "Add a key in backend/.env and restart to enable it: the manual works without one."}</p>
      </section>
      <section className="card p-4" aria-label="Examples">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Try asking or directing</h3>
        <div className="flex flex-wrap gap-2">{examples.map((x) => <button key={x} className="btn text-xs" disabled={chat.busy} onClick={() => chat.send(x)}>{x}</button>)}</div>
      </section>
      <section className="card min-w-0 space-y-3 p-4" aria-label="Conversation" aria-live="polite">
        {chat.messages.length === 0 && <p className="text-sm text-muted">No messages yet. Use the search bar above, or press an example.</p>}
        {chat.messages.map((m, i) => (
          <div key={i} className={`max-w-full rounded-lg p-3 text-sm ${m.role === "user" ? "ml-8 bg-panel2" : m.error ? "border border-red-500/40" : "border border-line"}`}>
            <div className="mb-1 text-xs text-muted">{m.role === "user" ? "You" : info.name}{m.meta ? ` · ${m.meta}` : ""}</div>
            <div className="whitespace-pre-wrap break-words">{m.content}</div>
            {m.actions?.map((a, j) => <button key={j} className="btn mt-2 mr-2 text-xs" onClick={() => onAction(a)}>{a.label}</button>)}
            {m.proposals?.map((p, j) => <Proposal key={j} p={p} />)}
          </div>
        ))}
        {chat.busy && <p className="text-sm text-muted">Thinking…</p>}
        <div ref={end} />
        {chat.messages.length > 0 && <button className="btn text-xs" onClick={chat.clear}>Clear conversation</button>}
      </section>
    </div>
  );
}
