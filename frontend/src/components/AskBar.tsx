"use client";
import Link from "next/link";
import { Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getJson, postJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";

type Dest = { href: string; title: string; what: string; kind: string; score: number; why: string };
type Fld = { key: string; label: string; href: string };
type Routed = { results: Dest[]; primary: Dest | null; tip: string | null };

/** A dashboard opens with what you typed already in its own ask box, so nothing has to be copied across. */
const withAsk = (href: string, text: string) => (href.startsWith("/tracks/") && text.trim() ? `${href}${href.includes("?") ? "&" : "?"}ask=${encodeURIComponent(text.trim())}` : href);

/** "Type what you need": sends a plain sentence to the best dashboard, lab or agent. Opens it straight away when the match is clear, otherwise lists the choices. */
export function AskBar({ autofocus = false }: { autofocus?: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [choices, setChoices] = useState<Dest[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [, setActive] = useActiveJob();
  const [jobForm, setJobForm] = useState(false);
  const [clientName, setClientName] = useState("");
  const [field, setField] = useState("");
  const [clientList, setClientList] = useState<string[]>([]);
  const [fields, setFields] = useState<Fld[]>([]);

  useEffect(() => {
    if (!jobForm) return;
    let live = true;
    getJson<{ clients: { name: string; archived?: boolean }[] }>("/api/clients").then((r) => { if (live) setClientList(r.clients.filter((c) => !c.archived).map((c) => c.name)); }).catch(() => {});
    getJson<{ fields: Fld[] }>("/api/jobs/fields/list").then((r) => { if (live) setFields(r.fields); }).catch(() => {});
    getJson<{ field: Fld | null }>(`/api/jobs/fields/guess?title=${encodeURIComponent(q.trim())}`).then((r) => { if (live) setField(r.field?.key ?? ""); }).catch(() => {});
    return () => { live = false; };
    // the guess is made once, when the form opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobForm]);

  const wasTyped = (v: string) => { setQ(v); setChoices(null); };

  const startJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const r = await postJson<{ job: { id: number }; field: Fld | null }>("/api/jobs/quick-start", { title: q.trim(), client: clientName, field: field || null });
      setActive(r.job.id); setJobForm(false); setQ(""); setClientName("");
      router.push(r.field ? r.field.href : "/");
    } catch (err) { setMsg(err instanceof ApiError ? err.message : "Couldn't start the job."); }
    finally { setBusy(false); }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = q.trim();
    if (!text) return;
    setBusy(true); setMsg(null); setChoices(null);
    try {
      const r = await getJson<Routed>(`/api/concierge?q=${encodeURIComponent(text)}`);
      if (!r.primary) { setMsg(r.tip ?? "Nothing matched. Try different words."); return; }
      setChoices(r.results);
    } catch (err) { setMsg(err instanceof ApiError ? err.message : "Couldn't reach the backend."); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-2" role="search" aria-label="Route your request">
      <form onSubmit={submit} className="flex gap-2">
        <input className="field w-full" aria-label="Type what you need" placeholder="Type what you need… e.g. sort my tickets by category, fix a cracked screen, quote a network install" maxLength={300}
               value={q} onChange={(e) => wasTyped(e.target.value)} autoFocus={autofocus} />
        <button type="submit" className="btn btn-primary shrink-0" disabled={busy || !q.trim()}><Send className="h-4 w-4" aria-hidden /> {busy ? "Routing…" : "Go"}</button>
        <button type="button" className="btn shrink-0" disabled={busy || !q.trim()} aria-expanded={jobForm} title="Turn what you typed into a job and open its field dashboard" onClick={() => { setJobForm((v) => !v); setMsg(null); setChoices(null); }}>Start as job</button>
      </form>
      {jobForm && (
        <form onSubmit={startJob} className="card flex flex-wrap items-end gap-2 p-3" aria-label="Start a job">
          <p className="w-full text-sm"><strong>{q.trim() || "Job"}</strong></p>
          <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-muted">Client
            <input className="input" list="askbar-clients" placeholder="Pick or type a new client" value={clientName} onChange={(e) => setClientName(e.target.value)} required />
            <datalist id="askbar-clients">{clientList.map((n) => <option key={n} value={n} />)}</datalist>
          </label>
          <label className="flex w-52 flex-col gap-1 text-xs text-muted">Field
            <select className="input" value={field} onChange={(e) => setField(e.target.value)}>
              <option value="">Not sure yet</option>
              {fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || !clientName.trim() || !q.trim()}>Start job</button>
          <button type="button" className="btn" onClick={() => setJobForm(false)}>Cancel</button>
        </form>
      )}
      {msg && <p role="status" className="text-sm text-muted">{msg}</p>}
      {choices && (
        <p className="text-xs text-muted">Suggested first. Pick where to go, or{" "}
          <button type="button" className="underline" onClick={() => { setJobForm(true); setMsg(null); }}>start it as a job and pick its field</button>.</p>
      )}
      {choices && (
        <ul className="card divide-y divide-line" aria-label="Where to go">
          {choices.map((d) => (
            <li key={d.href}>
              <Link href={withAsk(d.href, q)} onClick={() => { setChoices(null); setQ(""); }} className="flex items-baseline justify-between gap-3 px-3 py-2 text-sm hover:bg-panel2">
                <span className="min-w-0"><span className="block font-medium">{d.title}</span><span className="block text-xs text-muted">{d.what} · {d.why}</span></span>
                <span className="shrink-0 rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{d.kind}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
