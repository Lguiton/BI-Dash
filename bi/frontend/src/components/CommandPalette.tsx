"use client";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { SearchHit } from "@/lib/types";

/** Ctrl+K (or Cmd+K): jump to any page, career, manual step, plan deliverable, glossary term or KPI. */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [sel, setSel] = useState(0);
  const [failed, setFailed] = useState(false);
  const [actions, setActions] = useState<{ id: string; label: string; detail: string }[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [running, setRunning] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-palette", onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("open-palette", onOpen); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const ctl = new AbortController();
    getJson<{ actions: { id: string; label: string; detail: string }[] }>("/api/actions", ctl.signal).then((r) => setActions(r.actions)).catch(() => { /* actions are optional */ });
    return () => ctl.abort();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    const ctl = new AbortController();
    const t = setTimeout(() => {
      getJson<{ results: SearchHit[] }>(`/api/search?q=${encodeURIComponent(q)}&limit=10`, ctl.signal)
        .then((r) => { setHits(r.results); setSel(0); setFailed(false); })
        .catch(() => { if (!ctl.signal.aborted) setFailed(true); });
    }, q ? 150 : 0);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [q, open]);

  if (!open) return null;
  const shown = q.trim() ? actions.filter((a) => `${a.label} ${a.detail}`.toLowerCase().includes(q.trim().toLowerCase())) : actions;
  const runAction = async (id: string) => {
    setRunning(true); setResult(null);
    try { const r = await postJson<{ message: string }>(`/api/actions/${id}/run`, { confirm: true }); setResult({ ok: true, text: r.message }); }
    catch (e) { setResult({ ok: false, text: e instanceof ApiError ? e.message : "That didn't work." }); }
    finally { setRunning(false); setPending(null); }
  };
  const go = (h: SearchHit) => { setOpen(false); setQ(""); router.push(h.href); };
  const onKeys = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter" && hits[sel]) { e.preventDefault(); go(hits[sel]); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[12vh]" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <div role="dialog" aria-modal="true" aria-label="Search the dashboard" className="card flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden shadow-xl" onKeyDown={onKeys}>
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 text-muted" aria-hidden />
          <input ref={input} className="w-full bg-transparent py-3 text-sm outline-none" placeholder="Search pages, careers, manual steps, KPIs, terms…" value={q} maxLength={100} onChange={(e) => setQ(e.target.value)}
                 role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={hits[sel] ? `hit-${sel}` : undefined} aria-label="Search" />
          <kbd className="rounded border border-line px-1.5 text-xs text-muted">Esc</kbd>
        </div>
        <ul id="palette-list" role="listbox" className="max-h-[40vh] shrink-0 overflow-auto p-1">
          {failed && <li className="px-3 py-3 text-sm text-red-600">Search needs the backend running.</li>}
          {!failed && hits.length === 0 && <li className="px-3 py-3 text-sm text-muted">{q ? "Nothing matches that." : "Start typing."}</li>}
          {hits.map((h, i) => (
            <li key={`${h.href}-${h.title}-${i}`} id={`hit-${i}`} role="option" aria-selected={i === sel}>
              <button type="button" className={`flex w-full items-baseline justify-between gap-3 rounded-md px-3 py-2 text-left text-sm ${i === sel ? "bg-panel2" : ""}`} onMouseEnter={() => setSel(i)} onClick={() => go(h)}>
                <span className="min-w-0"><span className="block truncate font-medium">{h.title}</span>{h.sub && <span className="block truncate text-xs text-muted">{h.sub}</span>}</span>
                <span className="shrink-0 rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{h.kind}</span>
              </button>
            </li>
          ))}
        </ul>
        {shown.length > 0 && (
          <div className="overflow-auto border-t border-line p-1" role="group" aria-label="Actions">
            <p className="px-3 pb-1 pt-2 text-xs uppercase tracking-wide text-muted">Actions (safe, nothing is deleted)</p>
            {shown.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md px-3 py-1.5 text-sm">
                <span className="min-w-0"><span className="block font-medium">{a.label}</span><span className="block text-xs text-muted">{a.detail}</span></span>
                {pending === a.id ? (
                  <span className="inline-flex items-center gap-2 text-xs">Run it?
                    <button type="button" className="btn btn-primary !px-2 !py-1 text-xs" disabled={running} onClick={() => runAction(a.id)}>{running ? "Running…" : "Yes, run"}</button>
                    <button type="button" className="btn !px-2 !py-1 text-xs" onClick={() => setPending(null)}>Cancel</button>
                  </span>
                ) : <button type="button" className="btn !px-2 !py-1 text-xs" onClick={() => { setResult(null); setPending(a.id); }}>Run…</button>}
              </div>
            ))}
            {result && <p role={result.ok ? "status" : "alert"} className="px-3 pb-2 text-xs" style={{ color: result.ok ? "var(--good)" : "var(--bad)" }}>{result.text}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export function SearchButton() {
  return (
    <button type="button" className="btn" onClick={() => window.dispatchEvent(new Event("open-palette"))} aria-label="Search (Ctrl+K)" title="Search (Ctrl+K)">
      <Search className="h-4 w-4" aria-hidden /> Search <kbd className="hidden rounded border border-line px-1 text-[10px] text-muted sm:inline">Ctrl K</kbd>
    </button>
  );
}
