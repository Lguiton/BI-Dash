"use client";
import { useEffect, useState } from "react";
import { Globe, X } from "lucide-react";
import { getJson, postJson, putJson } from "@/lib/api";

interface Mark { title: string; url: string }
interface Read { url: string; host: string; title: string; text: string; truncated: boolean; links: { text: string; url: string }[]; note: string }
const KEY = "bi_webdock";

function load(): { open: boolean; url: string; big: boolean } {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? ""); return { open: !!v.open, url: String(v.url ?? ""), big: !!v.big }; } catch { return { open: false, url: "", big: false }; }
}
const norm = (v: string) => { const t = v.trim(); if (!t) return ""; return /^https:\/\//i.test(t) ? t : /^http:\/\//i.test(t) ? "" : `https://${t}`; };

/** A small web browser docked on every page. The live view is an iframe, so it uses YOUR browser's internet; the Reader view goes through the backend. */
export function WebDock() {
  const [s, setS] = useState({ open: false, url: "", big: false });
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"live" | "reader">("live");
  const [marks, setMarks] = useState<Mark[]>([]);
  const [rd, setRd] = useState<Read | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  // Reading localStorage must wait until after hydration, so this one-time setState in an effect is intended.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { const v = load(); setS(v); setInput(v.url); setReady(true); }, []);
  useEffect(() => { if (ready) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* storage may be blocked */ } } }, [s, ready]);
  useEffect(() => {
    if (!s.open || marks.length) return;
    const ctl = new AbortController();
    getJson<{ items: Mark[] }>("/api/web/bookmarks", ctl.signal).then((d) => setMarks(d.items)).catch(() => {});
    return () => ctl.abort();
  }, [s.open, marks.length]);

  const go = async (raw: string, m = mode) => {
    const u = norm(raw);
    setErr(null); setRd(null);
    if (!u) { setErr(raw.trim() ? "Only https:// links are opened here." : null); return; }
    setInput(u); setS((p) => ({ ...p, url: u }));
    if (m === "reader") {
      setBusy(true);
      try { setRd(await postJson<Read>("/api/web/read", { url: u })); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't read that page."); } finally { setBusy(false); }
    }
  };
  const saveMarks = async (items: Mark[]) => { try { setMarks((await putJson<{ items: Mark[] }>("/api/web/bookmarks", { items })).items); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); } };
  const pickMode = (m: "live" | "reader") => { setMode(m); if (s.url) void go(s.url, m); };

  if (!s.open) {
    return <button type="button" className="btn btn-primary fixed bottom-4 right-4 z-30 shadow-lg" onClick={() => setS({ ...s, open: true })} aria-label="Open the web panel"><Globe className="h-4 w-4" aria-hidden /> Web</button>;
  }
  const saved = marks.some((m) => m.url === s.url);
  return (
    <aside aria-label="Web panel" className={`card fixed bottom-4 right-4 z-30 flex flex-col shadow-2xl ${s.big ? "h-[85vh] w-[min(900px,calc(100vw-2rem))]" : "h-[60vh] w-[min(460px,calc(100vw-2rem))]"}`}>
      <div className="flex items-center gap-1 border-b border-line p-2">
        <Globe className="h-4 w-4 shrink-0 text-muted" aria-hidden />
        <form className="flex min-w-0 flex-1 gap-1" onSubmit={(e) => { e.preventDefault(); void go(input); }}>
          <input className="field min-w-0 flex-1" aria-label="Web address" placeholder="Search address, e.g. duckdb.org" value={input} onChange={(e) => setInput(e.target.value)} />
          <button className="btn" type="submit">Go</button>
        </form>
        <button className="btn" aria-label={s.big ? "Make the panel smaller" : "Make the panel bigger"} onClick={() => setS({ ...s, big: !s.big })}>{s.big ? "−" : "+"}</button>
        <button className="btn" aria-label="Close the web panel" onClick={() => setS({ ...s, open: false })}><X className="h-4 w-4" aria-hidden /></button>
      </div>
      <div className="flex flex-wrap items-center gap-1 border-b border-line p-2 text-xs">
        <button className={`btn ${mode === "live" ? "btn-primary" : ""}`} aria-pressed={mode === "live"} onClick={() => pickMode("live")}>Live page</button>
        <button className={`btn ${mode === "reader" ? "btn-primary" : ""}`} aria-pressed={mode === "reader"} onClick={() => pickMode("reader")}>Reader (text)</button>
        <select className="field max-w-40" aria-label="Bookmarks" value="" onChange={(e) => { if (e.target.value) void go(e.target.value); }}>
          <option value="">Bookmarks…</option>{marks.map((m) => <option key={m.url} value={m.url}>{m.title}</option>)}
        </select>
        {s.url && !saved && <button className="btn" onClick={() => saveMarks([...marks, { title: new URL(s.url).hostname.replace(/^www\./, ""), url: s.url }])}>Save</button>}
        {s.url && saved && <button className="btn" onClick={() => saveMarks(marks.filter((m) => m.url !== s.url))}>Unsave</button>}
        {s.url && <a className="btn" href={s.url} target="_blank" rel="noopener noreferrer">New tab ↗</a>}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {err && <p role="alert" className="m-2 rounded-lg p-2 text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>{err}</p>}
        {!s.url && !err && <p className="p-3 text-sm text-muted">Type an address or pick a bookmark. The Live page uses your own browser&apos;s internet. If a site shows a blank frame it doesn&apos;t allow embedding: use Reader or New tab. Don&apos;t sign in to anything important in here.</p>}
        {s.url && mode === "live" && <iframe key={s.url} title="Web page" src={s.url} className="h-full w-full bg-white" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" referrerPolicy="no-referrer" />}
        {mode === "reader" && busy && <p className="p-3 text-sm text-muted">Reading…</p>}
        {mode === "reader" && rd && (
          <div className="space-y-2 p-3 text-sm">
            <h3 className="font-semibold">{rd.title || rd.host}</h3>
            <p className="text-xs text-muted">{rd.note}</p>
            <pre className="whitespace-pre-wrap break-words font-sans text-sm">{rd.text}{rd.truncated ? "\n…(shortened)" : ""}</pre>
            {rd.links.length > 0 && <details><summary className="cursor-pointer text-xs text-muted">Links on the page ({rd.links.length})</summary><ul className="mt-1 space-y-0.5 text-xs">{rd.links.map((l) => <li key={l.url}><button className="underline" onClick={() => void go(l.url)}>{l.text}</button></li>)}</ul></details>}
          </div>
        )}
      </div>
    </aside>
  );
}
