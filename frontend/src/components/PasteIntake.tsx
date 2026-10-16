"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { errMsg } from "@/components/panels/kit";
import { postJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";

type Read = {
  client: string; title: string; field: { key: string; label: string; href: string } | null; due: string | null;
  quote: { service: string; hours: number[]; rate: number; low: number; high: number; suggested: number; note: string } | null; note: string;
};
type Started = { job: { id: number }; field: { href: string } | null };

/** Paste a client's message, check what was read, then start the job. Rules only, no AI. Nothing is sent to the client. */
export function PasteIntake() {
  const router = useRouter();
  const [, setActive] = useActiveJob();
  const [text, setText] = useState("");
  const [r, setR] = useState<Read | null>(null);
  const [client, setClient] = useState("");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [quote, setQuote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ask, setAsk] = useState("Summarize what the client needs, list the questions I should ask, and draft a short reply for me to send.");
  const [out, setOut] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function read() {
    setErr(null); setBusy(true);
    try {
      const x = await postJson<Read>("/api/jobs/intake", { text });
      setR(x); setClient(x.client); setTitle(x.title); setDue(x.due ?? ""); setQuote(x.quote ? String(x.quote.suggested) : "");
    } catch (e) { setErr(errMsg(e, "Couldn't read that.")); } finally { setBusy(false); }
  }
  async function askAgent() {
    setErr(null); setBusy(true); setOut(null);
    try {
      const track = r?.field?.key ?? "itsupport";
      const x = await postJson<{ reply: string }>(`/api/agents/${track}/chat`, { message: ask.slice(0, 1200), history: [], source_text: text.slice(0, 4000) });
      setOut(x.reply);
    } catch (e) { setErr(errMsg(e, "The agent couldn't answer.")); } finally { setBusy(false); }
  }
  async function copyOut() {
    try { await navigator.clipboard.writeText(out ?? ""); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { setErr("Couldn't copy. Select the text and copy it by hand."); }
  }
  async function start() {
    setErr(null); setBusy(true);
    try {
      const s = await postJson<Started>("/api/jobs/quick-start", { title, client, field: r?.field?.key ?? null, due: due || null, quote: Number(quote) || null });
      setActive(s.job.id); setText(""); setR(null);
      if (s.field?.href) router.push(s.field.href);
    } catch (e) { setErr(errMsg(e, "Couldn't start the job.")); } finally { setBusy(false); }
  }

  return (
    <details className="card p-3 text-sm">
      <summary className="cursor-pointer font-semibold">Paste a client message to start a job</summary>
      <div className="mt-2 space-y-2">
        <textarea className="input min-h-24 w-full" aria-label="Client message" placeholder="Paste the email or text. Leave out passwords." value={text} onChange={(e) => { setText(e.target.value); setR(null); }} />
        <button className="btn" disabled={busy || text.trim().length < 5} onClick={read}>Read it</button>
        {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
        {r && (
          <div className="space-y-2 border-t border-line pt-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs">Client<input className="input w-full" value={client} onChange={(e) => setClient(e.target.value)} /></label>
              <label className="text-xs">Job<input className="input w-full" value={title} onChange={(e) => setTitle(e.target.value)} /></label>
              <label className="text-xs">Due<input type="date" className="input w-full" value={due} onChange={(e) => setDue(e.target.value)} /></label>
              <label className="text-xs">Quote (USD)<input type="number" min="0" className="input w-full" value={quote} onChange={(e) => setQuote(e.target.value)} /></label>
            </div>
            <p className="text-xs text-muted">
              Dashboard: {r.field?.label ?? "none matched"}.{r.quote ? ` Draft quote from "${r.quote.service}": $${r.quote.low} to $${r.quote.high} (${r.quote.hours[0]} to ${r.quote.hours[1]} h at $${r.quote.rate}/h).` : " No price match, enter a quote yourself."} {r.note}
            </p>
            <button className="btn" disabled={busy || !client.trim() || !title.trim()} onClick={start}>Start this job</button>
            <div className="space-y-2 border-t border-line pt-2">
              <label className="block text-xs">Ask the {r.field?.label ?? "IT"} agent about this message (a draft you check, nothing is sent)
                <textarea className="input mt-1 w-full" rows={2} value={ask} onChange={(e) => setAsk(e.target.value)} />
              </label>
              <button className="btn" disabled={busy || ask.trim().length < 2} onClick={askAgent}>{busy ? "Working…" : "Get agent output"}</button>
              {out && (
                <div className="space-y-1 rounded border border-line p-2" role="status">
                  <pre className="whitespace-pre-wrap font-sans text-sm">{out}</pre>
                  <button className="btn" onClick={copyOut}>{copied ? "Copied" : "Copy output"}</button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </details>
  );
}
