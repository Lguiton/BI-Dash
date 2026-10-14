"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Markdown } from "@/components/Markdown";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

interface Work { id: string; role: string; label: string; kind?: string; kind_label?: string; question: string; source: string; created_at: string; provider: string; model: string; markdown: string; complete: boolean; tools_used: { tool: string; error: boolean; what: string }[]; tokens: { in: number; out: number } }
interface Src { id: string; label: string }

const SAMPLE_Q: Record<string, string> = {
  analyst: "e.g. Why is cost over budget, and what should we do about it?",
  scientist: "e.g. Is the weekend revenue premium real, and does it matter?",
  bi: "e.g. Give leadership a monthly BI summary.",
};

/** The AI does the whole job for the role. You keep your own notes beside it and compare. Nothing here changes your data. */
export function AiWorkPanel({ role, title }: { role: "analyst" | "scientist" | "bi"; title: string }) {
  const [items, setItems] = useState<Work[]>([]);
  const [sources, setSources] = useState<Src[]>([]);
  const [source, setSource] = useState("operations");
  const [types, setTypes] = useState<{ id: string; label: string }[]>([{ id: "complete", label: "Complete analysis (the role's full outline)" }]);
  const [kind, setKind] = useState("complete");
  const [prov, setProv] = useState("auto");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<string>("");
  const [mine, setMine] = useState("");
  const load = () => getJson<{ items: Work[] }>(`/api/agents/${role}/work`).then((d) => { setItems(d.items); setSel((s) => s || d.items[0]?.id || ""); }).catch((e) => setErr(errMsg(e, "Couldn't load earlier AI work.")));
  useEffect(() => {
    getJson<{ items: Work[] }>(`/api/agents/${role}/work`).then((d) => { setItems(d.items); setSel(d.items[0]?.id ?? ""); }).catch((e) => setErr(errMsg(e, "Couldn't load earlier AI work.")));
    getJson<{ types: { id: string; label: string }[] }>("/api/agents/work/types").then((d) => setTypes(d.types)).catch(() => undefined);
    getJson<{ sources: Src[] }>("/api/stats/sources").then((d) => setSources(d.sources)).catch(() => undefined);
  }, [role]);
  const go = async () => {
    setBusy(true); setErr(null);
    try { const w = await postJson<Work>(`/api/agents/${role}/complete`, { question, source, kind, provider: prov }); setSel(w.id); await load(); } catch (e) { setErr(errMsg(e, "The AI couldn't finish.")); } finally { setBusy(false); }
  };
  const del = async (id: string) => { try { await deleteJson(`/api/agents/work/${id}`); setSel(""); await load(); } catch (e) { setErr(errMsg(e, "Couldn't delete that.")); } };
  const cur = items.find((x) => x.id === sel);
  return (
    <div className="space-y-4">
      <Section title={`AI mode: full ${title} work`}>
        <p className="text-sm">One button and the AI does the whole job as a {title}: checks the data, runs the numbers, writes the findings and the story, and lists every number it relied on and where it came from. Pick a type of analysis (descriptive, diagnostic, predictive, prescriptive and more) to see each kind done, or run the complete outline, then put it beside your own version. Where you agree you can be more confident; where you differ, one of you found something worth a second look.</p>
        <p className="mt-1 text-xs text-muted">It can take a minute or two. It reads your data with the same read-only, privacy-checked tools as the chat and changes nothing. Whatever it reads is sent to your AI provider, as with the chat. Verify the numbers before relying on them.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field label="Type of analysis"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>{types.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select></Field>
          <Field label="Data to analyse"><select className="field" value={source} onChange={(e) => setSource(e.target.value)}>{(sources.length ? sources : [{ id: "operations", label: "operations" }]).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></Field>
          <Field label="AI model"><select className="field" value={prov} onChange={(e) => setProv(e.target.value)}><option value="auto">Claude (default when its key is set)</option><option value="anthropic">Claude only</option><option value="openai">OpenAI</option><option value="google">Gemini</option></select></Field>
          <div className="sm:col-span-3"><Field label="Question or brief (optional)"><input className="field" maxLength={600} placeholder={SAMPLE_Q[role]} value={question} onChange={(e) => setQuestion(e.target.value)} /></Field></div>
        </div>
        <button className="btn btn-primary mt-3" disabled={busy} onClick={go}>{busy ? "Working through the whole job…" : "Do the full job for me"}</button>
      </Section>
      {err && <ErrorBanner message={err} />}
      {items.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 text-sm"><span className="text-muted">Earlier runs:</span>
          {items.map((x) => <button key={x.id} className={`btn text-xs ${x.id === sel ? "btn-primary" : ""}`} onClick={() => setSel(x.id)}>{x.created_at.slice(5, 16)} · {(x.kind_label ?? "Complete").split(":")[0].split(" (")[0]}</button>)}</div>
      )}
      {cur && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="card min-w-0 space-y-2 p-4" aria-label="The AI's work">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">The AI&apos;s work</h3>
              <div className="flex flex-wrap gap-2 text-xs"><Badge tone={cur.complete ? "ok" : "warn"}>{cur.complete ? "finished" : "stopped early"}</Badge><Badge>{cur.kind_label ?? "Complete analysis"}</Badge><Badge>{cur.provider}: {cur.model}</Badge><Badge>{cur.tools_used.length} tool calls</Badge></div>
            </div>
            <Markdown text={cur.markdown} />
            <details className="text-xs text-muted"><summary className="cursor-pointer">What it ran</summary>
              <ol className="mt-1 list-decimal space-y-0.5 pl-5">{cur.tools_used.map((t, i) => <li key={i}><code>{t.tool}</code>{t.error ? " (failed)" : ""}{t.what ? <>: <code className="break-all">{t.what}</code></> : ""}</li>)}</ol></details>
            <div className="flex gap-2"><button className="btn text-xs" onClick={() => navigator.clipboard?.writeText(cur.markdown)}>Copy</button><button className="btn text-xs" onClick={() => del(cur.id)}>Delete this run</button></div>
          </section>
          <section className="card min-w-0 space-y-2 p-4" aria-label="Your work">
            <h3 className="text-sm font-semibold">Your work</h3>
            <p className="text-xs text-muted">Paste or type your findings here to read them beside the AI&apos;s. This box is for comparing on screen; it is not saved. Compare: the key numbers, the main driver, the recommendation, and what each of you flagged as a limit.</p>
            <textarea className="field min-h-[24rem] w-full" aria-label="Your findings" value={mine} onChange={(e) => setMine(e.target.value)} placeholder="Your numbers, your finding, your recommendation…" />
          </section>
        </div>
      )}
      {!cur && !busy && <p className="text-sm text-muted">No AI runs yet for this role.</p>}
    </div>
  );
}
