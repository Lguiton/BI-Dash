"use client";
import { useState } from "react";
import { Badge, errMsg } from "./kit";
import { postJson } from "@/lib/api";

const ROLES = [
  "customer service technician", "personal consultant", "financial advisor", "teacher", "travel agent", "therapist", "chef", "project manager", "career coach", "life coach",
  "fashion stylist", "cybersecurity analyst", "nutritionist", "social media manager", "copywriter", "wedding planner", "software developer", "journalist", "real estate agent",
  "photographer", "data analyst", "legal consultant", "graphic designer", "music producer", "sales representative", "negotiation coach", "language translator", "UX/UI designer",
  "mediator", "startup mentor", "sports coach", "parenting coach", "software tester", "content strategist", "talent editor", "business analyst", "travel blogger",
  "network engineer", "IT support technician", "business intelligence analyst", "machine learning engineer", "technical writer", "systems analyst", "freelance consultant",
];
const TASKS = [
  "a social media content plan", "a workout routine", "a meal plan", "a project timeline", "a therapy session outline", "a menu for a restaurant", "a business proposal",
  "a career development plan", "a fashion lookbook", "a cybersecurity risk assessment", "a content marketing strategy", "a wedding invitation design", "a software testing plan",
  "a financial investment portfolio", "a marketing brochure", "a customer satisfaction survey", "a training program for employees", "a product packaging design", "a data analysis report",
  "a legal contract outline", "a graphic design brief for a poster", "a music playlist", "a healthcare treatment plan", "a negotiation strategy", "a website wireframe", "a parenting guide",
  "a civil engineering checklist", "a website content collection plan", "a data visualization dashboard", "a video editing storyboard", "a talent recruiting plan", "a wellness program",
  "a business process improvement plan", "a social work intervention plan", "a construction project proposal", "a machine learning model plan", "a market analysis summary", "a travel blog itinerary",
  "a network troubleshooting checklist", "a client quote with scope and price", "a runbook for a common IT problem", "a KPI definition sheet", "a backup and recovery plan",
];
const FORMATS = [
  "a step-by-step infographic", "a comparison table", "a presentation slide outline", "a mind map", "a reusable template", "a Q&A session", "a checklist", "a problem-solving scenario",
  "a first-draft interface design mockup", "a conversation script", "a demonstration video script", "an interactive quiz", "a data visualization", "a sample code example", "a storytelling narrative",
  "a case study analysis", "a pricing comparison table", "a strategic plan outline", "a storyboard", "a mock client meeting transcript", "a mock therapy session transcript", "a sample workout plan",
  "a mock negotiation transcript", "a sample testing report", "a sample lesson plan", "a design lookbook", "a mock interview", "a before-and-after showcase", "a blueprint or architectural diagram",
  "a marketing campaign analysis report", "a mock mediation script", "a sample healthcare consultation", "a short email I can send", "a one-page summary", "a numbered list of next actions",
  "a JSON object", "a CSV table", "plain language for a non-technical client",
];

/** Role + task + format picker that builds a clear prompt, to copy or run on the AI agent. Nothing is sent unless you press the agent button. */
export function PromptLibrary() {
  const [role, setRole] = useState(ROLES[0]);
  const [task, setTask] = useState(TASKS[0]);
  const [fmt, setFmt] = useState(FORMATS[0]);
  const [extra, setExtra] = useState("");
  const [out, setOut] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const prompt = `Act as ${/^[aeio]/i.test(role) ? "an" : "a"} ${role}. Create ${task}. Show it as ${fmt}.${extra.trim() ? `\n\nDetails: ${extra.trim()}` : ""}\n\nAsk me up to 3 questions first if something important is missing, then give the result.`;

  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setMsg("Copied to the clipboard."); }
    catch {
      const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
      let ok = false; try { ok = document.execCommand("copy"); } catch { ok = false; }
      document.body.removeChild(ta); setMsg(ok ? "Copied to the clipboard." : "Couldn't copy. Select the text and press Ctrl+C.");
    }
    setTimeout(() => setMsg(null), 3000);
  }
  async function ask() {
    setBusy(true); setOut(null); setMsg(null);
    try { setOut((await postJson<{ reply: string }>("/api/agents/ai/chat", { message: prompt.slice(0, 1200), history: [] })).reply); }
    catch (e) { setMsg(errMsg(e, "The agent couldn't answer.")); } finally { setBusy(false); }
  }
  const sel = (label: string, value: string, set: (v: string) => void, list: string[], pre: string) => (
    <label className="block text-xs">{label}
      <select className="input mt-1 w-full" value={value} onChange={(e) => set(e.target.value)}>{list.map((x) => <option key={x} value={x}>{pre}{x}</option>)}</select>
    </label>
  );
  return (
    <details className="card p-4 text-sm" aria-label="Prompt library">
      <summary className="cursor-pointer text-base font-semibold">Prompt library: role, task, format</summary>
      <div className="mt-3 space-y-3">
        <p className="text-xs text-muted">Pick a role, a task and an output format, add your own details, and copy the finished prompt into any AI, or run it on the AI engineering agent. Clear prompts name who the AI is, what to make and how to show it.</p>
        <div className="grid gap-2 md:grid-cols-3">
          {sel("1. Adopt a role", role, setRole, ROLES, "Act as a ")}
          {sel("2. Specify the task", task, setTask, TASKS, "Create ")}
          {sel("3. Output format", fmt, setFmt, FORMATS, "Show as ")}
        </div>
        <label className="block text-xs">4. Your details (optional: who it is for, size, tone, facts; no passwords or private data)
          <textarea className="input mt-1 w-full" rows={2} value={extra} onChange={(e) => setExtra(e.target.value)} />
        </label>
        <div className="space-y-1 rounded border border-line p-2">
          <div className="flex items-center justify-between"><span className="text-xs font-semibold">Your prompt</span><Badge tone="muted">{prompt.length} characters</Badge></div>
          <pre className="whitespace-pre-wrap font-sans text-sm">{prompt}</pre>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={() => void copy(prompt)}>Copy prompt</button>
          <button className="btn" disabled={busy} onClick={ask}>{busy ? "Working…" : "Run on the AI agent"}</button>
          {msg && <span role="status" className="text-xs">{msg}</span>}
        </div>
        {out && (
          <div className="space-y-1 rounded border border-line p-2" role="status">
            <pre className="whitespace-pre-wrap font-sans text-sm">{out}</pre>
            <button className="btn" onClick={() => void copy(out)}>Copy answer</button>
          </div>
        )}
      </div>
    </details>
  );
}
