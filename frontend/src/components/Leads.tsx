"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg } from "@/components/panels/kit";

type Lead = { id: number; name: string; source: string; contact: string; what: string; value: number; status: string; next_step: string; next_date: string | null; note: string; due: boolean; client_id: number | null; job_id: number | null; created: string };
type List = { leads: Lead[]; statuses: string[]; sources: string[]; sample: boolean };
type Stats = { sources: { source: string; leads: number; quoted: number; won: number; lost: number; open: number; won_value: number; open_value: number; win_rate: number | null }[]; message: string; totals: { leads: number; open: number; open_value: number; won_value: number } };
const money = (n: number) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function LeadTracker() {
  const [list, setList] = useState<List | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [f, setF] = useState({ name: "", source: "referral", contact: "", what: "", value: "", next_step: "", next_date: "" });
  const [won, setWon] = useState<{ client_id: number; job_id: number } | null>(null);
  useEffect(() => {
    let live = true;
    Promise.all([getJson<List>("/api/leads"), getJson<Stats>("/api/leads/stats")]).then(([l, s]) => { if (live) { setList(l); setStats(s); } }).catch((e) => { if (live) setErr(errMsg(e, "Could not load leads.")); });
    return () => { live = false; };
  }, [tick]);
  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't work.")); } };
  const open = list?.leads.filter((l) => l.status !== "won" && l.status !== "lost") ?? [];
  const closed = list?.leads.filter((l) => l.status === "won" || l.status === "lost") ?? [];
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {list?.sample && <p role="note" className="rounded border border-amber-500 bg-amber-500/10 p-2 text-sm">Practice workspace: sample data. Switch to Real for your own leads.</p>}
      {won && <p role="status" className="card p-3 text-sm">Won. A client and a job were created. <Link className="underline" href={`/job?id=${won.job_id}`}>Open the job</Link>.</p>}
      {stats && <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Leads" value={String(stats.totals.leads)} /><Stat label="Still open" value={String(stats.totals.open)} sub={money(stats.totals.open_value)} /><Stat label="Won value" value={money(stats.totals.won_value)} /></div>}
      <Section title="Add a lead" note="A lead is someone who has not hired you yet. Winning one makes the client and a job for you.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Name"><input aria-label="Lead name" className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Where from"><select aria-label="Lead source" className="input" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>{(list?.sources ?? ["referral"]).map((s) => <option key={s}>{s}</option>)}</select></Field>
          <Field label="Phone or email"><input aria-label="Lead contact" className="input" value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} /></Field>
          <Field label="What they need"><input aria-label="What they need" className="input w-56" value={f.what} onChange={(e) => setF({ ...f, what: e.target.value })} /></Field>
          <Field label="Likely value $"><input aria-label="Likely value" className="input w-24" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
          <Field label="Next step"><input aria-label="Next step" className="input w-44" value={f.next_step} onChange={(e) => setF({ ...f, next_step: e.target.value })} /></Field>
          <Field label="By (YYYY-MM-DD)"><input aria-label="Next step date" className="input w-36" value={f.next_date} onChange={(e) => setF({ ...f, next_date: e.target.value })} /></Field>
          <button className="btn btn-primary" disabled={!f.name.trim()} onClick={() => act(async () => { await postJson("/api/leads", { ...f, value: f.value || 0, next_date: f.next_date || null }); setF({ ...f, name: "", contact: "", what: "", value: "", next_step: "", next_date: "" }); })}>Add lead</button>
        </div>
      </Section>
      <Section title={`Open leads (${open.length})`}>
        {open.length === 0 ? <p className="text-sm text-muted">No open leads.</p> : (
          <ul className="divide-y divide-line">
            {open.map((l) => (
              <li key={l.id} className="space-y-1 py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span><strong>{l.name}</strong> <Badge>{l.source}</Badge> {l.what && <span className="text-muted">· {l.what}</span>} {l.value > 0 && <span>· {money(l.value)}</span>} {l.due && <Badge tone="warn">next step due</Badge>}</span>
                  <span className="flex flex-wrap gap-2">
                    <select aria-label={`Status of ${l.name}`} className="input" value={l.status} onChange={(e) => act(() => putJson(`/api/leads/${l.id}`, { status: e.target.value }))}>{["new", "contacted", "quoted", "lost"].map((s) => <option key={s}>{s}</option>)}</select>
                    <button className="btn btn-primary" onClick={() => act(async () => setWon(await postJson<{ client_id: number; job_id: number }>(`/api/leads/${l.id}/win`, {})))}>Won it</button>
                    <button className="btn" aria-label={`Delete lead ${l.name}`} onClick={() => act(() => deleteJson(`/api/leads/${l.id}`))}>Delete</button>
                  </span>
                </div>
                {(l.next_step || l.contact) && <p className="text-xs text-muted">{l.contact}{l.contact && l.next_step ? " · " : ""}{l.next_step}{l.next_date ? ` (by ${l.next_date})` : ""}</p>}
              </li>
            ))}
          </ul>
        )}
      </Section>
      {stats && (
        <Section title="Which sources pay" note={stats.message}>
          <Table head={["Source", "Leads", "Quoted", "Won", "Lost", "Win rate", "Won value", "Still open"]} rows={stats.sources.map((s) => [s.source, s.leads, s.quoted, s.won, s.lost, s.win_rate == null ? "—" : `${s.win_rate}%`, money(s.won_value), `${s.open} (${money(s.open_value)})`])} caption="Leads by source" />
        </Section>
      )}
      {closed.length > 0 && <Section title={`Finished (${closed.length})`}><ul className="text-sm">{closed.map((l) => <li key={l.id}>{l.name} · {l.source} · <Badge tone={l.status === "won" ? "ok" : "bad"}>{l.status}</Badge>{l.job_id ? <> · <Link className="underline" href={`/job?id=${l.job_id}`}>job</Link></> : ""}</li>)}</ul></Section>}
    </div>
  );
}
