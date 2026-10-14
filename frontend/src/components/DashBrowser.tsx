"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, deleteJson, getJson } from "@/lib/api";

type Browse = { columns: string[]; rows: { id: number; values: (string | number | null)[] }[]; total: number; matched: number; limit: number; offset: number };
const PAGE = 25;
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");

function DataTab({ pid, onChange }: { pid: string; onChange?: () => void }) {
  const [d, setD] = useState<Browse | null>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("record_date");
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const [off, setOff] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    getJson<Browse>(`/api/biz-packs/${pid}/browse?q=${encodeURIComponent(q)}&sort=${encodeURIComponent(sort)}&dir=${dir}&limit=${PAGE}&offset=${off}`)
      .then((r) => { setD(r); setErr(null); }).catch((e) => setErr(msg(e)));
  }, [pid, q, sort, dir, off]);
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load]);
  const head = (c: string) => { if (c === sort) setDir(dir === "asc" ? "desc" : "asc"); else { setSort(c); setDir("asc"); } setOff(0); };
  async function del(id: number) {
    if (!window.confirm("Delete this row? This can't be undone.")) return;
    try { await deleteJson(`/api/biz-packs/${pid}/rows/${id}`); load(); onChange?.(); } catch (e) { setErr(msg(e)); }
  }
  return (
    <div className="space-y-2">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2">
        <input className="input" placeholder="Search every column…" value={q} onChange={(e) => { setQ(e.target.value); setOff(0); }} aria-label="Search rows" />
        {d && <span className="text-xs opacity-70">{d.matched.toLocaleString()} of {d.total.toLocaleString()} rows</span>}
      </div>
      {d && d.total === 0 && <p className="text-sm opacity-70">No rows yet. Load sample data, import a CSV, or use quick add.</p>}
      {d && d.total > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr>{d.columns.map((c) => (
              <th key={c} className="cursor-pointer whitespace-nowrap px-2 py-1 text-left" onClick={() => head(c)} aria-sort={c === sort ? (dir === "asc" ? "ascending" : "descending") : "none"}>
                {c.replace(/_/g, " ")}{c === sort ? (dir === "asc" ? " ▲" : " ▼") : ""}
              </th>))}<th /></tr></thead>
            <tbody>{d.rows.map((r) => (
              <tr key={r.id} className="border-t border-current/10">
                {r.values.map((v, i) => <td key={i} className="whitespace-nowrap px-2 py-1">{typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v}</td>)}
                <td className="px-2"><button className="text-xs underline opacity-70" onClick={() => del(r.id)} aria-label="Delete row">delete</button></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
      {d && d.matched > PAGE && (
        <div className="flex items-center gap-2 text-sm">
          <button className="btn" disabled={off === 0} onClick={() => setOff(Math.max(0, off - PAGE))}>Previous</button>
          <span>{off + 1}–{Math.min(off + PAGE, d.matched)}</span>
          <button className="btn" disabled={off + PAGE >= d.matched} onClick={() => setOff(off + PAGE)}>Next</button>
        </div>
      )}
    </div>
  );
}

function WebTab({ pid }: { pid: string }) {
  const key = `bi-web-${pid}`;
  const [url, setUrl] = useState("");
  const [shown, setShown] = useState("");
  const [saved, setSaved] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch { return []; } });
  const [err, setErr] = useState<string | null>(null);
  const store = (l: string[]) => { setSaved(l); try { localStorage.setItem(key, JSON.stringify(l)); } catch { /* storage unavailable */ } };
  function go(u: string) {
    let t = u.trim();
    if (!t) return;
    if (!/^https?:\/\//i.test(t)) t = "https://" + t;
    try { const p = new URL(t); if (!/^https?:$/.test(p.protocol)) throw new Error(); setErr(null); setUrl(p.href); setShown(p.href); }
    catch { setErr("That doesn't look like a web address."); }
  }
  return (
    <div className="space-y-2">
      {err && <ErrorBanner message={err} />}
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); go(url); }}>
        <input className="input min-w-64 flex-1" placeholder="Paste a web address, e.g. support.microsoft.com" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Web address" />
        <button className="btn" type="submit">Go</button>
        {shown && <a className="btn" href={shown} target="_blank" rel="noopener noreferrer">Open in new tab</a>}
        {shown && !saved.includes(shown) && <button className="btn" type="button" onClick={() => store([...saved, shown].slice(-12))}>Save link</button>}
      </form>
      {saved.length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs">{saved.map((s) => (
          <span key={s} className="rounded border border-current/20 px-2 py-1"><button className="underline" onClick={() => { setUrl(s); go(s); }}>{s.replace(/^https?:\/\//, "")}</button>
            <button className="ml-2 opacity-60" aria-label={`Remove ${s}`} onClick={() => store(saved.filter((x) => x !== s))}>×</button></span>))}</div>
      )}
      {shown ? (
        <iframe title="Web page" src={shown} className="h-[520px] w-full rounded border border-current/20 bg-white" sandbox="allow-scripts allow-forms allow-popups allow-same-origin" referrerPolicy="no-referrer" />
      ) : <p className="text-sm opacity-70">Look things up next to your numbers. Saved links stay with this dashboard on this device.</p>}
      <p className="text-xs opacity-70">Some sites (banks, Google, LinkedIn, most logins) refuse to be shown inside another page. If it stays blank, use “Open in new tab”.</p>
    </div>
  );
}

/** One data browser and one web pane per dashboard. */
export function DashBrowser({ pid, onChange }: { pid: string; onChange?: () => void }) {
  const [tab, setTab] = useState<"data" | "web">("data");
  return (
    <section className="card space-y-2 p-4" aria-label="Browser">
      <div role="tablist" className="flex gap-2">
        {(["data", "web"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={`btn ${tab === t ? "font-semibold underline" : ""}`} onClick={() => setTab(t)}>{t === "data" ? "Browse data" : "Web"}</button>))}
      </div>
      {tab === "data" ? <DataTab pid={pid} onChange={onChange} /> : <WebTab pid={pid} />}
    </section>
  );
}
