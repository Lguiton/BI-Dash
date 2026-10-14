"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, deleteJson, getJson, postJson } from "@/lib/api";
import { BizAssistant } from "@/components/BizAssistant";
import { DashBrowser } from "@/components/DashBrowser";
import { CustomBuilder, ExplainButton, FileImport, QuickAdd, ReportBox } from "@/components/PackExtras";
import { downloadFile } from "@/lib/download";

type PackInfo = { id: string; industry: string; dept: string; title: string; about: string; rows: number | null; columns: string[]; custom?: boolean };
type PKpi = { label: string; unit: string; direction: string; value: number | null; previous: number | null; change_pct: number | null; good: boolean | null };
type Dash = {
  id: string; title: string; industry: string; dept: string; days: number; as_of: string; records: number; kpis: PKpi[];
  trend_label: string; trend: { day: string; value: number | null }[]; breakdowns: { dim: string; rows: { name: string; value: number | null }[] }[];
};

type Ov = {
  days: number; packs: number; available: number; improving: number; worsening: number;
  attention: { pack: string; industry: string; dept: string; kpi: string; unit: string; value: number | null; change_pct: number | null }[];
  cards: { id: string; industry: string; dept: string; title: string; records: number; as_of: string; kpis: PKpi[]; trend_label: string; trend: { day: string; value: number | null }[] }[];
};

const WINDOWS = [{ v: 7, l: "7 days" }, { v: 30, l: "30 days" }, { v: 90, l: "90 days" }, { v: 0, l: "All" }];

function fmt(unit: string, v: number | null): string {
  if (v === null) return "n/a";
  if (unit === "usd") return `$${v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 100 ? 2 : 0 })}`;
  if (unit === "pct") return `${v.toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
  return v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 100 ? 1 : 0 });
}
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");

export default function PacksPage() {
  const [packs, setPacks] = useState<PackInfo[]>([]);
  const [industry, setIndustry] = useState("");
  const [pid, setPid] = useState("");
  const [days, setDays] = useState(30);
  const [dash, setDash] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [replace, setReplace] = useState(true);
  const [ver, setVer] = useState(0);
  const [view, setView] = useState<"all" | "one">("all");
  const [ov, setOv] = useState<Ov | null>(null);
  const [isReal, setIsReal] = useState(false);

  useEffect(() => {
    getJson<{ packs: PackInfo[] }>("/api/biz-packs").then((r) => {
      setPacks(r.packs);
      const want = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("pid") : null;
      const hit = want ? r.packs.find((p) => p.id === want) : undefined;
      setIndustry((i) => (hit && !i ? hit.industry : i) || r.packs[0]?.industry || "");
      setPid((p) => (hit && !p ? hit.id : p) || r.packs[0]?.id || "");
      if (hit) setView((v) => (v === "all" ? "one" : v));
    }).catch((e) => setError(msg(e)));
  }, [ver]);

  useEffect(() => {
    if (view !== "all") return;
    let live = true;
    getJson<Ov>(`/api/biz-packs/overview?days=${days}`).then((o) => { if (live) setOv(o); }).catch((e) => { if (live) setError(msg(e)); });
    return () => { live = false; };
  }, [view, days, ver]);

  useEffect(() => {
    getJson<{ active: string }>("/api/workspaces").then((w) => setIsReal(w.active === "real")).catch(() => {});
  }, []);

  const cur = packs.find((p) => p.id === pid);
  const loaded = cur?.rows != null;
  useEffect(() => {
    if (!pid || !loaded) return;
    let live = true;
    getJson<Dash>(`/api/biz-packs/${pid}/dashboard?days=${days}`).then((d) => { if (live) { setDash(d); setError(null); } }).catch((e) => { if (live) setError(msg(e)); });
    return () => { live = false; };
  }, [pid, days, loaded, ver]);

  const industries = useMemo(() => [...new Set(packs.map((p) => p.industry))], [packs]);
  const depts = packs.filter((p) => p.industry === industry);

  const act = useCallback(async (fn: () => Promise<string>) => {
    setBusy(true); setError(null); setNote("");
    try { setNote(await fn()); setVer((v) => v + 1); } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  }, []);

  function pickIndustry(i: string) {
    setIndustry(i); setDash(null); setNote("");
    const first = packs.find((p) => p.industry === i);
    if (first) setPid(first.id);
  }

  return (
    <PageShell title="Business dashboards" subtitle="Pick an industry and a department. Load sample data to see it, or import your own CSV.">
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2" role="tablist" aria-label="View">
          <button role="tab" aria-selected={view === "all"} className={`btn ${view === "all" ? "btn-primary" : ""}`} onClick={() => setView("all")}>Command center</button>
          <button role="tab" aria-selected={view === "one"} className={`btn ${view === "one" ? "btn-primary" : ""}`} onClick={() => setView("one")}>One dashboard</button>
        </div>
        <div className="flex gap-1" role="group" aria-label="Overview window">
          {WINDOWS.map((w) => <button key={w.v} className={`btn text-xs ${w.v === days ? "btn-primary" : ""}`} aria-pressed={w.v === days} onClick={() => setDays(w.v)}>{w.l}</button>)}
        </div>
      </div>
      {view === "all" && (
        <section className="space-y-4" aria-label="Command center">
          {ov && ov.packs === 0 && isReal && (
            <div className="card p-4 text-sm">Nothing loaded yet. This is the Real workspace, so open a department under One dashboard and import your CSV. Sample data lives in Practice.</div>
          )}
          {ov && ov.packs === 0 && !isReal && (
            <div className="card space-y-2 p-4">
              <p className="text-sm">Nothing loaded yet. Load sample data for every industry and department to see the whole picture.</p>
              <button className="btn btn-primary" disabled={busy} onClick={() => act(async () => { const r = await postJson<{ installed: number }>("/api/biz-packs/samples", {}); return `Loaded ${r.installed} dashboards.`; })}>Load sample data for all</button>
            </div>
          )}
          {note && <p role="status" className="text-sm" style={{ color: "var(--good)" }}>{note}</p>}
          {ov && ov.packs > 0 && (
            <>
              <div className="grid gap-3 sm:grid-cols-4">
                <div className="card p-4"><div className="text-xs text-muted">Dashboards live</div><div className="mt-1 text-2xl font-bold">{ov.packs} <span className="text-sm font-normal text-muted">of {ov.available}</span></div></div>
                <div className="card p-4"><div className="text-xs text-muted">Numbers improving</div><div className="mt-1 text-2xl font-bold" style={{ color: "var(--good)" }}>{ov.improving}</div></div>
                <div className="card p-4"><div className="text-xs text-muted">Numbers worsening</div><div className="mt-1 text-2xl font-bold" style={{ color: "var(--bad)" }}>{ov.worsening}</div></div>
                <div className="card p-4"><div className="text-xs text-muted">Need attention (10%+ the wrong way)</div><div className="mt-1 text-2xl font-bold">{ov.attention.length}</div></div>
              </div>
              {ov.attention.length > 0 && (
                <section className="card p-4">
                  <h2 className="mb-2 text-sm font-semibold">Needs attention</h2>
                  <ul className="divide-y text-sm" style={{ borderColor: "var(--border)" }}>
                    {ov.attention.map((a) => (
                      <li key={a.pack + a.kpi}>
                        <button className="flex w-full items-center justify-between gap-3 py-2 text-left hover:opacity-80" onClick={() => { setIndustry(a.industry); setPid(a.pack); setDash(null); setView("one"); }}>
                          <span><span className="font-medium">{a.kpi}</span> <span className="text-muted">· {a.industry}, {a.dept}</span></span>
                          <span className="whitespace-nowrap" style={{ color: "var(--bad)" }}>{fmt(a.unit, a.value)} ({a.change_pct && a.change_pct > 0 ? "+" : ""}{a.change_pct}%)</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {[...new Set(ov.cards.map((c) => c.industry))].map((ind) => (
                <div key={ind} className="space-y-2">
                  <h2 className="text-sm font-semibold">{ind}</h2>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {ov.cards.filter((c) => c.industry === ind).map((c) => (
                      <button key={c.id} className="card space-y-2 p-4 text-left hover:opacity-90" aria-label={`Open ${c.dept} dashboard for ${c.industry}`} onClick={() => { setIndustry(c.industry); setPid(c.id); setDash(null); setView("one"); }}>
                        <div className="text-sm font-semibold">{c.dept}<span className="font-normal text-muted"> · {c.title}</span></div>
                        <div className="grid grid-cols-3 gap-2">
                          {c.kpis.map((k) => (
                            <div key={k.label}><div className="truncate text-[11px] text-muted">{k.label}</div><div className="text-base font-bold">{fmt(k.unit, k.value)}</div>
                              <div className="text-[11px]" style={{ color: k.good === null ? "var(--muted)" : k.good ? "var(--good)" : "var(--bad)" }}>{k.change_pct === null ? "n/a" : `${k.change_pct > 0 ? "+" : ""}${k.change_pct}%`}</div></div>
                          ))}
                        </div>
                        <div className="h-12"><ResponsiveContainer width="100%" height="100%"><LineChart data={c.trend}><Line type="monotone" dataKey="value" stroke="var(--accent)" dot={false} strokeWidth={1.5} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </section>
      )}
      {view === "one" && (<>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Industry">
        {industries.map((i) => (
          <button key={i} role="tab" aria-selected={i === industry} className={`btn ${i === industry ? "btn-primary" : ""}`} onClick={() => pickIndustry(i)}>{i}</button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Department">
        {depts.map((p) => (
          <button key={p.id} role="tab" aria-selected={p.id === pid} className={`btn text-sm ${p.id === pid ? "btn-primary" : ""}`} onClick={() => { setPid(p.id); setDash(null); setNote(""); }}>
            {p.dept}{p.rows != null ? "" : " (no data)"}
          </button>
        ))}
      </div>
      <details className="card p-4">
        <summary className="cursor-pointer text-sm font-medium">Build a new dashboard from any file</summary>
        <div className="mt-2"><CustomBuilder onDone={(id) => { setNote("Dashboard built."); setVer((v) => v + 1); setIndustry("Custom"); setPid(id); setDash(null); }} /></div>
      </details>
      {cur && (
        <section className="card space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><h2 className="font-semibold">{cur.title}</h2><p className="text-sm text-muted">{cur.about}</p></div>
            <div className="flex flex-wrap gap-2">
              {!isReal && <button className="btn" disabled={busy} onClick={() => act(async () => { const r = await postJson<{ rows: number }>(`/api/biz-packs/${pid}/sample`, {}); return `Sample data loaded (${r.rows} rows).`; })}>{loaded ? "Reset to sample data" : "Load sample data"}</button>}
              <button className="btn" onClick={() => downloadFile(`/api/biz-packs/${pid}/template.csv`, `${pid}.csv`).catch((e) => setError(msg(e)))}>CSV template</button>
              {loaded && <button className="btn" disabled={busy} onClick={() => act(async () => { await deleteJson(`/api/biz-packs/${pid}/data`); setDash(null); return "Data removed."; })}>Remove data</button>}
            </div>
          </div>
          {note && <p role="status" className="text-sm" style={{ color: "var(--good)" }}>{note}</p>}
          <details>
            <summary className="cursor-pointer text-sm font-medium">Import your own data</summary>
            <p className="mt-2 text-xs text-muted">Columns needed: {cur.columns.join(", ")}. Dates as YYYY-MM-DD.</p>
            <div className="mt-2"><FileImport pid={pid} onDone={(m) => { setNote(m); setVer((v) => v + 1); }} /></div>
            <p className="mt-3 text-xs text-muted">Or paste CSV text:</p>
            <textarea className="field mt-2 h-28 w-full font-mono text-xs" aria-label="CSV text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste CSV here, or choose a file" />
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-1"><input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />Replace existing rows</label>
              <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => act(async () => {
                const r = await postJson<{ imported: number; skipped_notes: string[] }>(`/api/biz-packs/${pid}/import`, { csv: text, replace });
                setText(""); return `Imported ${r.imported} rows.${r.skipped_notes.length ? " Skipped: " + r.skipped_notes.join("; ") : ""}`;
              })}>Import</button>
            </div>
          </details>
          <details>
            <summary className="cursor-pointer text-sm font-medium">Quick add one record</summary>
            <div className="mt-2"><QuickAdd pid={pid} onDone={() => setVer((v) => v + 1)} /></div>
          </details>
          {cur.custom && <button className="btn text-xs" disabled={busy} onClick={() => act(async () => { if (!window.confirm("Delete this dashboard and its data?")) return ""; await deleteJson(`/api/biz-packs/${pid}/custom`); setPid(""); setDash(null); return "Dashboard deleted."; })}>Delete this custom dashboard</button>}
        </section>
      )}
      {loaded && dash && dash.id === pid && (
        <>
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm text-muted">{dash.records.toLocaleString()} records, latest {dash.as_of}</p>

          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {dash.kpis.map((k) => (
              <div key={k.label} className="card p-4">
                <div className="text-xs text-muted">{k.label}</div>
                <div className="mt-1 text-2xl font-bold">{fmt(k.unit, k.value)}</div>
                <div className="mt-1 text-xs" style={{ color: k.good === null ? "var(--muted)" : k.good ? "var(--good)" : "var(--bad)" }}>
                  {k.change_pct === null ? (days ? "no prior period" : "all data") : `${k.change_pct > 0 ? "+" : ""}${k.change_pct}% vs previous ${days} days`}
                </div>
                <ExplainButton pid={dash.id} kpi={k.label} days={days} />
              </div>
            ))}
          </div>
          <section className="card p-4">
            <h3 className="mb-2 text-sm font-semibold">{dash.trend_label} by day</h3>
            <div className="h-64"><ResponsiveContainer width="100%" height="100%">
              <LineChart data={dash.trend}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="day" fontSize={11} minTickGap={30} /><YAxis fontSize={11} width={56} /><Tooltip /><Line type="monotone" dataKey="value" stroke="var(--accent)" dot={false} strokeWidth={2} /></LineChart>
            </ResponsiveContainer></div>
          </section>
          <div className="grid gap-3 lg:grid-cols-3">
            {dash.breakdowns.map((b) => (
              <section key={b.dim} className="card p-4">
                <h3 className="mb-2 text-sm font-semibold">{dash.trend_label} by {b.dim.replace(/_/g, " ")}</h3>
                <div className="h-56"><ResponsiveContainer width="100%" height="100%">
                  <BarChart data={b.rows} layout="vertical" margin={{ left: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis type="number" fontSize={11} /><YAxis type="category" dataKey="name" fontSize={11} width={84} /><Tooltip /><Bar dataKey="value" fill="var(--accent)" /></BarChart>
                </ResponsiveContainer></div>
              </section>
            ))}
          </div>
        </>
      )}
      {cur && loaded && <BizAssistant key={pid} pid={pid} columns={cur.columns} />}
      {cur && loaded && <ReportBox pid={pid} days={days} />}
      {cur && <DashBrowser key={"b" + pid} pid={pid} onChange={() => setVer((v) => v + 1)} />}
      {cur && !loaded && <p className="text-sm text-muted">No data yet for {cur.dept}. Load the sample to see how it looks, or import yours.</p>}
      </>)}
    </PageShell>
  );
}
