"use client";
import { useCallback, useEffect, useState } from "react";
import { ApiError, getJson, postJson, putJson } from "@/lib/api";

interface Row { key: string; label: string; kind: "usd" | "pts" | "n"; this: number | null; last: number | null; change: number | null }
interface Weekly {
  config: { enabled: boolean; weekday: number; last_sent: string }; days: string[]; email_ready: boolean; error: string | null;
  report: { window: { from: string; to: string; previous_from: string; previous_to: string }; rows: Row[]; paragraph: string; note: string } | null;
}
const show = (r: Row, v: number | null) => (v == null ? "n/a" : r.kind === "usd" ? `$${Math.round(v).toLocaleString()}` : r.kind === "pts" ? `${v.toFixed(1)}%` : Math.round(v).toLocaleString());

/** "What changed this week": a rule-based paragraph (no AI) plus an optional weekly email. */
export function WeeklyCard({ refreshKey = 0 }: { refreshKey?: number }) {
  const [w, setW] = useState<Weekly | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback((signal?: AbortSignal) => { getJson<Weekly>("/api/weekly", signal).then(setW).catch(() => { /* optional */ }); }, []);
  useEffect(() => { const ctl = new AbortController(); load(ctl.signal); return () => ctl.abort(); }, [load, refreshKey]);
  if (!w) return null;
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg({ ok: true, text: ok }); load(); } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "That didn't work." }); }
  };
  return (
    <section className="card space-y-3 p-4" aria-label="What changed this week">
      <h2 className="text-sm font-semibold uppercase tracking-wide">What changed this week</h2>
      {w.report ? (
        <>
          <p className="text-sm">{w.report.paragraph}</p>
          <p className="text-xs text-muted">{w.report.window.from} to {w.report.window.to}, compared with {w.report.window.previous_from} to {w.report.window.previous_to}. {w.report.note}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">This week against last week</caption>
              <thead><tr><th className="th">Measure</th><th className="th text-right">This week</th><th className="th text-right">Week before</th><th className="th text-right">Change</th></tr></thead>
              <tbody>{w.report.rows.map((r) => (
                <tr key={r.key} className="border-t border-line"><td className="td">{r.label}</td><td className="td text-right tabular-nums">{show(r, r.this)}</td><td className="td text-right tabular-nums">{show(r, r.last)}</td>
                  <td className="td text-right tabular-nums">{r.change == null ? "n/a" : r.kind === "pts" ? `${r.change > 0 ? "+" : ""}${r.change.toFixed(1)} pts` : `${r.change > 0 ? "+" : ""}${r.change.toFixed(1)}%`}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      ) : <p className="text-sm text-muted">{w.error}</p>}
      <div className="flex flex-wrap items-end gap-3 border-t border-line pt-3 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={w.config.enabled} disabled={!w.email_ready && !w.config.enabled}
          onChange={(e) => act(() => putJson("/api/weekly", { enabled: e.target.checked }), e.target.checked ? "Weekly email is on." : "Weekly email is off.")} /> Email this every</label>
        <select className="field" aria-label="Day of week" value={w.config.weekday} onChange={(e) => act(() => putJson("/api/weekly", { weekday: Number(e.target.value) }), "Day saved.")}>
          {w.days.map((d, i) => <option key={d} value={i}>{d}</option>)}
        </select>
        <button className="btn" disabled={!w.email_ready || !w.report} onClick={() => act(() => postJson("/api/weekly/send", {}), "Sent.")}>Send now</button>
        {!w.email_ready && <span className="text-xs text-muted">Email isn&apos;t set up (see Settings), so scheduling is off.</span>}
        {msg && <span role={msg.ok ? "status" : "alert"} className="text-xs" style={{ color: msg.ok ? "var(--good)" : "var(--bad)" }}>{msg.text}</span>}
      </div>
      <p className="text-xs text-muted">The scheduled email only goes out while the backend is running with the scheduler on, and sends at most once on the chosen day. The text email has no attachment; use the PDF button for a file.</p>
    </section>
  );
}
