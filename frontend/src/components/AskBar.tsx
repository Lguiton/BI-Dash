"use client";
import Link from "next/link";
import { Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, getJson } from "@/lib/api";

type Dest = { href: string; title: string; what: string; kind: string; score: number; why: string };
type Routed = { results: Dest[]; primary: Dest | null; tip: string | null };

/** "Type what you need": sends a plain sentence to the best dashboard, lab or agent. Opens it straight away when the match is clear, otherwise lists the choices. */
export function AskBar({ autofocus = false }: { autofocus?: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [choices, setChoices] = useState<Dest[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = q.trim();
    if (!text) return;
    setBusy(true); setMsg(null); setChoices(null);
    try {
      const r = await getJson<Routed>(`/api/concierge?q=${encodeURIComponent(text)}`);
      if (!r.primary) { setMsg(r.tip ?? "Nothing matched. Try different words."); return; }
      const second = r.results[1];
      if (!second || r.primary.score >= second.score * 1.25) { router.push(r.primary.href); setQ(""); }
      else setChoices(r.results);
    } catch (err) { setMsg(err instanceof ApiError ? err.message : "Couldn't reach the backend."); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-2" role="search" aria-label="Route your request">
      <form onSubmit={submit} className="flex gap-2">
        <input className="field w-full" aria-label="Type what you need" placeholder="Type what you need… e.g. sort my tickets by category, fix a cracked screen, quote a network install" maxLength={300}
               value={q} onChange={(e) => setQ(e.target.value)} autoFocus={autofocus} />
        <button type="submit" className="btn btn-primary shrink-0" disabled={busy || !q.trim()}><Send className="h-4 w-4" aria-hidden /> {busy ? "Routing…" : "Go"}</button>
      </form>
      {msg && <p role="status" className="text-sm text-muted">{msg}</p>}
      {choices && (
        <ul className="card divide-y divide-line" aria-label="Where to go">
          {choices.map((d) => (
            <li key={d.href}>
              <Link href={d.href} onClick={() => { setChoices(null); setQ(""); }} className="flex items-baseline justify-between gap-3 px-3 py-2 text-sm hover:bg-panel2">
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
