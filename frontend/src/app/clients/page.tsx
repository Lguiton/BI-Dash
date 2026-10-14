"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { API_BASE, apiFetch, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat } from "@/components/panels/kit";

type Client = { id: number; name: string; contact: string; email: string; notes: string; archived: boolean; jobs?: number };
type Job = { id: number; title: string; status: string; quote: number; hours: number; due: string | null; rate: number | null };
type Time = { id: number; job_id: number; date: string; hours: number; note: string; billable: boolean; invoice_id: number | null };
type Inv = { id: number; number: string; issued: string; due: string; status: string; total: number; lines: { desc: string; qty: number; rate: number }[] };
type Fu = { id: number; due: string; note: string; done: boolean; client?: string };
type View = { client: Client; jobs: Job[]; time: Time[]; invoices: Inv[]; followups: Fu[]; packs: { id: number; made: string; files: string[] }[]; unbilled: Time[] };
type Over = { sample: boolean; clients: number; jobs_active: number; pipeline: number; outstanding: number; overdue: (Inv & { client: string; days_late: number })[]; paid_this_month: number; unbilled_hours: number; unbilled_amount: number; followups_due: Fu[]; settings: { rate: number; terms_days: number; business: string; pay_to: string }; note: string };
type PackInfo = { id: string; title: string; rows: number | null };
type Model = { id: string; label: string; verdict: string };

const money = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const STATUS = ["lead", "quoted", "active", "done", "lost"];

export default function ClientsPage() {
  const [ov, setOv] = useState<Over | null>(null);
  const [list, setList] = useState<Client[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [v, setV] = useState<View | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [job, setJob] = useState({ title: "", quote: "", due: "" });
  const [tm, setTm] = useState({ job_id: "", hours: "", note: "" });
  const [fu, setFu] = useState({ note: "", due: "" });
  const [extra, setExtra] = useState({ desc: "", qty: "1", rate: "" });
  const [packs, setPacks] = useState<PackInfo[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [pp, setPp] = useState({ pack_id: "", days: "30", done: "", how_to_use: "", limits: "", next: "" });
  const [pm, setPm] = useState<string[]>([]);
  const [rate, setRate] = useState("");
  const [biz, setBiz] = useState("");

  const fail = (e: unknown) => setErr(e instanceof Error ? e.message : "Something went wrong.");
  const [tick, setTick] = useState(0);
  const reload = useCallback(async () => { setTick((t) => t + 1); }, []);
  useEffect(() => {
    let live = true;
    Promise.all([getJson<Over>("/api/clients/overview"), getJson<{ clients: Client[] }>("/api/clients"), sel ? getJson<View>(`/api/clients/${sel}`) : Promise.resolve(null)])
      .then(([o, l, vw]) => { if (live) { setOv(o); setList(l.clients); setV(vw); } })
      .catch((e) => { if (live) fail(e); });
    return () => { live = false; };
  }, [sel, tick]);
  useEffect(() => {
    getJson<{ packs: PackInfo[] }>("/api/biz-packs").then((r) => setPacks(r.packs.filter((p) => p.rows))).catch(() => {});
    getJson<{ models: Model[] }>("/api/biz-models").then((r) => setModels(r.models)).catch(() => {});
  }, []);
  async function act(fn: () => Promise<unknown>) { setErr(null); try { await fn(); await reload(); } catch (e) { fail(e); } }
  async function put(path: string, body: unknown) { const r = await apiFetch(`${API_BASE}${path}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Failed"); }
  async function del(path: string) { const r = await apiFetch(`${API_BASE}${path}`, { method: "DELETE" }); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Failed"); }
  async function makePack() {
    if (!sel) return; setErr(null);
    try {
      const r = await apiFetch(`${API_BASE}/api/clients/${sel}/pack`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pack_id: pp.pack_id || null, days: Number(pp.days), model_ids: pm, notes: { done: pp.done, how_to_use: pp.how_to_use, limits: pp.limits, next: pp.next } }) });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Could not make the pack.");
      const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = `handoff_${v?.client.name ?? "client"}.zip`; a.click(); URL.revokeObjectURL(a.href); await reload();
    } catch (e) { fail(e); }
  }

  return (
    <PageShell title="Clients" subtitle="Your own freelance work: clients, jobs, hours, invoices, follow-ups, and a handoff pack to give a paying client.">
      {err && <ErrorBanner message={err} />}
      {ov?.sample && <p role="note" className="rounded border border-amber-500 bg-amber-500/10 p-2 text-sm">Practice workspace: everything here is sample data and every invoice and pack is stamped SAMPLE. Switch to the Real workspace for real clients.</p>}
      {ov && (
        <Section title="Overview" note={ov.note}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Active jobs" value={String(ov.jobs_active)} /><Stat label="Pipeline (leads and quotes)" value={money(ov.pipeline)} /><Stat label="Waiting to be paid" value={money(ov.outstanding)} /><Stat label="Paid this month" value={money(ov.paid_this_month)} /><Stat label="Unbilled hours" value={`${ov.unbilled_hours}`} /><Stat label="Unbilled value" value={money(ov.unbilled_amount)} /></div>
          {ov.overdue.length > 0 && <p className="mt-3 text-sm"><Badge tone="bad">overdue</Badge> {ov.overdue.map((i) => `${i.number} ${i.client} ${money(i.total)} (${i.days_late} days late)`).join(" · ")}</p>}
          {ov.followups_due.length > 0 && <p className="mt-2 text-sm"><Badge tone="warn">follow up</Badge> {ov.followups_due.map((f) => `${f.client}: ${f.note} (due ${f.due})`).join(" · ")}</p>}
          <div className="mt-3 flex flex-wrap items-end gap-2"><Field label="Default hourly rate $"><input aria-label="Default hourly rate" className="input" value={rate || String(ov.settings.rate)} onChange={(e) => setRate(e.target.value)} /></Field>
            <Field label="Your business name (on invoices)"><input aria-label="Business name" className="input" value={biz || ov.settings.business} onChange={(e) => setBiz(e.target.value)} /></Field>
            <button className="btn" onClick={() => act(() => put("/api/clients/settings", { rate: Number(rate || ov.settings.rate), business: biz || ov.settings.business }))}>Save</button></div>
        </Section>
      )}

      <Section title="Clients">
        <div className="flex flex-wrap items-end gap-2"><Field label="New client"><input aria-label="New client name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Client or business name" /></Field>
          <button className="btn" disabled={!name.trim()} onClick={() => act(async () => { const c = await postJson<Client>("/api/clients", { name }); setName(""); setSel(c.id); })}>Add client</button></div>
        <ul className="mt-3 flex flex-wrap gap-2">{list.map((c) => <li key={c.id}><button className={`btn ${sel === c.id ? "ring-2" : ""}`} aria-pressed={sel === c.id} onClick={() => setSel(c.id)}>{c.name} <span className="text-xs text-muted">({c.jobs ?? 0} jobs)</span></button></li>)}</ul>
        {list.length === 0 && <p className="mt-2 text-sm text-muted">No clients yet.</p>}
      </Section>

      {v && (
        <>
          <Section title={`${v.client.name}: jobs`}>
            <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th>Job</th><th>Status</th><th className="text-right">Hours</th><th className="text-right">Quote</th><th>Due</th><th /></tr></thead>
              <tbody>{v.jobs.map((j) => <tr key={j.id}><td>{j.title}</td><td><select aria-label={`Status of ${j.title}`} className="input" value={j.status} onChange={(e) => act(() => put(`/api/clients/jobs/${j.id}`, { status: e.target.value }))}>{STATUS.map((s) => <option key={s}>{s}</option>)}</select></td><td className="text-right">{j.hours}</td><td className="text-right">{money(j.quote)}</td><td>{j.due ?? ""}</td><td><button className="btn" aria-label={`Delete job ${j.title}`} onClick={() => act(() => del(`/api/clients/jobs/${j.id}`))}>Delete</button></td></tr>)}</tbody></table>
            <div className="mt-3 flex flex-wrap items-end gap-2"><Field label="Job title"><input aria-label="Job title" className="input" value={job.title} onChange={(e) => setJob({ ...job, title: e.target.value })} /></Field>
              <Field label="Quote $"><input aria-label="Job quote" className="input w-28" value={job.quote} onChange={(e) => setJob({ ...job, quote: e.target.value })} /></Field>
              <Field label="Due (YYYY-MM-DD)"><input aria-label="Job due date" className="input w-36" value={job.due} onChange={(e) => setJob({ ...job, due: e.target.value })} /></Field>
              <button className="btn" disabled={!job.title.trim()} onClick={() => act(async () => { await postJson("/api/clients/jobs/add", { client_id: v.client.id, title: job.title, quote: job.quote || 0, due: job.due || null, status: "active" }); setJob({ title: "", quote: "", due: "" }); })}>Add job</button></div>
          </Section>

          <Section title="Hours">
            <ul className="text-sm">{v.time.slice(-8).reverse().map((t) => <li key={t.id}>{t.date}: {t.hours} h on {v.jobs.find((j) => j.id === t.job_id)?.title} {t.note && `(${t.note})`} {t.invoice_id ? <Badge tone="ok">invoiced</Badge> : t.billable ? <Badge tone="warn">unbilled</Badge> : <Badge>not billable</Badge>}</li>)}</ul>
            <div className="mt-3 flex flex-wrap items-end gap-2"><Field label="Job"><select aria-label="Hours job" className="input" value={tm.job_id} onChange={(e) => setTm({ ...tm, job_id: e.target.value })}><option value="">Choose…</option>{v.jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select></Field>
              <Field label="Hours"><input aria-label="Hours worked" className="input w-24" value={tm.hours} onChange={(e) => setTm({ ...tm, hours: e.target.value })} /></Field>
              <Field label="Note"><input aria-label="Hours note" className="input" value={tm.note} onChange={(e) => setTm({ ...tm, note: e.target.value })} /></Field>
              <button className="btn" disabled={!tm.job_id || !tm.hours} onClick={() => act(async () => { await postJson("/api/clients/time/add", { job_id: Number(tm.job_id), hours: tm.hours, note: tm.note }); setTm({ job_id: tm.job_id, hours: "", note: "" }); })}>Log time</button></div>
          </Section>

          <Section title="Invoices" note="An invoice is built from unbilled billable hours (hours x rate) plus any extra line you add. Marking one void gives the hours back.">
            <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th>Number</th><th>Due</th><th>Status</th><th className="text-right">Total</th><th /></tr></thead>
              <tbody>{v.invoices.map((i) => <tr key={i.id}><td>{i.number}</td><td>{i.due}</td><td><select aria-label={`Status of ${i.number}`} className="input" value={i.status} onChange={(e) => act(() => put(`/api/clients/invoices/${i.id}`, { status: e.target.value }))}>{["draft", "sent", "paid", "void"].map((s) => <option key={s}>{s}</option>)}</select></td><td className="text-right">{money(i.total)}</td><td><a className="underline" href={`${API_BASE}/api/clients/invoices/${i.id}/view`} target="_blank" rel="noopener noreferrer">Open</a></td></tr>)}</tbody></table>
            <p className="mt-2 text-sm">Ready to bill: {v.unbilled.reduce((s, t) => s + t.hours, 0)} hours.</p>
            <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Extra line (optional)"><input aria-label="Extra line description" className="input" value={extra.desc} onChange={(e) => setExtra({ ...extra, desc: e.target.value })} /></Field>
              <Field label="Qty"><input aria-label="Extra line quantity" className="input w-20" value={extra.qty} onChange={(e) => setExtra({ ...extra, qty: e.target.value })} /></Field>
              <Field label="Rate $"><input aria-label="Extra line rate" className="input w-24" value={extra.rate} onChange={(e) => setExtra({ ...extra, rate: e.target.value })} /></Field>
              <button className="btn" onClick={() => act(async () => { await postJson("/api/clients/invoices/create", { client_id: v.client.id, extra: extra.desc ? [{ desc: extra.desc, qty: extra.qty, rate: extra.rate || 0 }] : [] }); setExtra({ desc: "", qty: "1", rate: "" }); })}>Create invoice</button></div>
          </Section>

          <Section title="Follow-ups">
            <ul className="text-sm">{v.followups.map((f) => <li key={f.id} className="flex items-center gap-2"><input type="checkbox" aria-label={`Done: ${f.note}`} checked={f.done} onChange={(e) => act(() => put(`/api/clients/followups/${f.id}`, { done: e.target.checked }))} /><span className={f.done ? "line-through text-muted" : ""}>{f.due}: {f.note}</span><button className="btn" aria-label={`Delete follow-up ${f.note}`} onClick={() => act(() => del(`/api/clients/followups/${f.id}`))}>Delete</button></li>)}</ul>
            <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Follow up on"><input aria-label="Follow-up note" className="input" value={fu.note} onChange={(e) => setFu({ ...fu, note: e.target.value })} /></Field>
              <Field label="By (YYYY-MM-DD)"><input aria-label="Follow-up date" className="input w-36" value={fu.due} onChange={(e) => setFu({ ...fu, due: e.target.value })} /></Field>
              <button className="btn" disabled={!fu.note.trim()} onClick={() => act(async () => { await postJson("/api/clients/followups/add", { client_id: v.client.id, note: fu.note, due: fu.due || null }); setFu({ note: "", due: "" }); })}>Add</button></div>
          </Section>

          <Section title="Handoff pack" note="A zip for the client: the report from one of your business dashboards (if you pick one), a work summary, invoices, model verdicts, and your notes on what was done, how to use it and its limits. Nothing is sent anywhere.">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Report from dashboard"><select aria-label="Report dashboard" className="input" value={pp.pack_id} onChange={(e) => setPp({ ...pp, pack_id: e.target.value })}><option value="">None</option>{packs.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
              <Field label="Report period (days)"><select aria-label="Report period" className="input" value={pp.days} onChange={(e) => setPp({ ...pp, days: e.target.value })}>{["7", "30", "90", "365", "0"].map((d) => <option key={d} value={d}>{d === "0" ? "All data" : d}</option>)}</select></Field>
              {(["done", "how_to_use", "limits", "next"] as const).map((k) => <Field key={k} label={{ done: "What was done", how_to_use: "How to use it", limits: "Limits and assumptions", next: "Suggested next steps" }[k]}><textarea aria-label={k} className="input min-h-20" value={pp[k]} onChange={(e) => setPp({ ...pp, [k]: e.target.value })} /></Field>)}
            </div>
            {models.length > 0 && <fieldset className="mt-2 flex flex-wrap gap-3 text-sm"><legend className="text-xs text-muted">Include model results</legend>{models.map((m) => <label key={m.id} className="flex items-center gap-1"><input type="checkbox" checked={pm.includes(m.id)} onChange={(e) => setPm((o) => (e.target.checked ? [...o, m.id] : o.filter((x) => x !== m.id)))} />{m.label}</label>)}</fieldset>}
            <button className="btn mt-3" onClick={makePack}>Build and download pack</button>
            {v.packs.length > 0 && <p className="mt-2 text-xs text-muted">Made before: {v.packs.map((p) => p.made).join(", ")}</p>}
          </Section>
        </>
      )}
    </PageShell>
  );
}
