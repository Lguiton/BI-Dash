"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { ErrorBanner } from "@/components/ErrorBanner";
import { WorkLog } from "@/components/WorkLog";
import { PrepDraft } from "@/components/PrepDraft";
import { JobMaterials } from "@/components/JobMaterials";
import { EivantaNote } from "@/components/EivantaNote";
import { JobVideos } from "@/components/HowTo";
import { JobChecklists } from "@/components/Checklists";
import { ClientNotes } from "@/components/ClientNotes";
import { API_BASE, apiFetch, getJson, postJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Badge, Section } from "@/components/panels/kit";

type Time = { id: number; date: string; hours: number; note: string; billable: boolean; invoice: string | null };
type Over = {
  job: { id: number; title: string; status: string; quote: number; due: string | null; created: string; notes?: string };
  client: { id: number; name: string } | null;
  rate: number; hours: number; unbilled_hours: number; unbilled_amount: number; sample: boolean;
  time: Time[]; invoices: { id: number; number: string; status: string; total: number }[];
  work_items: { id: number; title: string; status_label: string }[];
  ready_to_close?: boolean;
  fixes: { id: number; title: string; area: string; result: string; created_at: string }[]; fixes_note: string;
};
type Bill = "time" | "quote" | "none";
const usd = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function JobView({ id }: { id: number }) {
  const [o, setO] = useState<Over | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [bill, setBill] = useState<Bill>("time");
  const [confirm, setConfirm] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJson<Over>(`/api/jobs/${id}`).then((r) => { if (live) { setO(r); setErr(null); } }).catch((e) => { if (live) setErr(e instanceof Error ? e.message : "Could not load the job"); });
    return () => { live = false; };
  }, [id, tick]);

  async function close() {
    try {
      const r = await postJson<{ invoice: { number: string } | null; note: string; items_closed: number; timer_hours_added: number }>(`/api/jobs/${id}/close`, { bill });
      setMsg([r.invoice ? `Job closed. Invoice ${r.invoice.number} created.` : "Job closed.", r.note, r.timer_hours_added ? `${r.timer_hours_added} h from a running timer was added first.` : "", r.items_closed ? `${r.items_closed} work item(s) marked done.` : ""].filter(Boolean).join(" "));
      setConfirm(false); setTick((t) => t + 1);
    } catch (e) { setErr(e instanceof Error ? e.message : "Close failed"); setConfirm(false); }
  }
  async function accept() {
    try { await postJson(`/api/clients/jobs/${id}/accept`, {}); setMsg("Quote accepted. The job is now active."); setTick((t) => t + 1); } catch (e) { setErr(e instanceof Error ? e.message : "Could not accept"); }
  }
  async function summary() {
    try {
      const r = await apiFetch(`${API_BASE}/api/jobs/${id}/summary`);
      if (!r.ok) throw new Error("Could not build the summary");
      const url = URL.createObjectURL(new Blob([await r.text()], { type: "text/html" }));
      window.open(url, "_blank", "noopener");
    } catch (e) { setErr(e instanceof Error ? e.message : "Summary failed"); }
  }

  if (err && !o) return <ErrorBanner message={err} />;
  if (!o) return <p className="text-sm text-muted">Loading…</p>;
  const done = o.job.status === "done";
  return (
    <div className="grid gap-6">
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="card p-3 text-sm">{msg}</p>}
      {o.sample && <p className="text-xs text-muted">Practice workspace: nothing here is real.</p>}
      <Section title={`${o.job.title}${o.client ? ` for ${o.client.name}` : ""}`}>
        <p className="text-sm text-muted">
          <Badge tone={done ? "ok" : "warn"}>{o.job.status}</Badge> started {o.job.created}{o.job.due ? ` · due ${o.job.due}` : ""} · {o.hours} h recorded · rate {usd(o.rate)}/h{o.job.quote ? ` · quote ${usd(o.job.quote)}` : ""}
        </p>
        <p className="mt-1 text-sm">Not yet billed: <strong>{o.unbilled_hours} h = {usd(o.unbilled_amount)}</strong></p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button className="btn" onClick={summary}>Client summary</button>
          <button className="btn" onClick={() => downloadFile(`/api/jobs/${id}/summary.pdf`, `job-summary-${id}.pdf`).catch((e) => setErr(e instanceof Error ? e.message : "Download failed"))}>Client summary (PDF)</button>
          {(o.job.status === "quoted" || o.job.status === "lead") && <button className="btn btn-primary" onClick={accept}>Quote accepted: start the job</button>}
          {o.client && <Link href="/clients" className="text-xs underline">Open clients</Link>}
        </div>
      </Section>

      {o.ready_to_close && <p role="status" className="card p-3 text-sm">Every work item on this job is done. Time to close it and invoice. Scroll down to <strong>Close job</strong>.</p>}

      <JobMaterials jobId={id} />
      <WorkLog jobId={id} />
      <JobChecklists jobId={id} />
      <JobVideos jobId={id} />
      {o.client && <ClientNotes key={o.client.id} clientId={o.client.id} />}

      <Section title="Hours">
        {o.time.length === 0 ? <p className="text-sm text-muted">No hours yet. Start a timer on a work item above, or add hours on the Clients page.</p> : (
          <ul className="space-y-0.5 text-sm">{o.time.map((t) => <li key={t.id}>{t.date}: {t.hours} h {t.note && <span className="text-muted">({t.note})</span>} {t.invoice ? <Badge tone="ok">{t.invoice}</Badge> : t.billable ? <Badge tone="warn">to bill</Badge> : <Badge tone="muted">not billable</Badge>}</li>)}</ul>
        )}
      </Section>

      <Section title="Fixes for this client">
        {o.fixes.length === 0 ? <p className="text-sm text-muted">{o.fixes_note || "No client on this job."} None found.</p> : (
          <ul className="space-y-0.5 text-sm">{o.fixes.map((f) => <li key={f.id}>{f.title} <span className="text-muted">· {f.area} · {f.result}</span></li>)}</ul>
        )}
      </Section>

      {o.invoices.length > 0 && (
        <Section title="Invoices">
          <ul className="space-y-0.5 text-sm">{o.invoices.map((i) => <li key={i.id}>{i.number} ({i.status}): {usd(i.total)}</li>)}</ul>
        </Section>
      )}

      <EivantaNote jobId={id} />

      <Section title="Close job">
        <PrepDraft draftKey={`job:${id}`} path={`/api/auto/prep/job/${id}`} label="Draft the closing note (AI)" />
        {done ? <p className="text-sm text-muted">This job is closed.</p> : (
          <div className="space-y-2 text-sm">
            <fieldset className="space-y-1">
              <legend className="text-xs text-muted">What to invoice</legend>
              <label className="flex items-center gap-2"><input type="radio" name="bill" checked={bill === "time"} onChange={() => setBill("time")} /> The unbilled hours ({usd(o.unbilled_amount)})</label>
              <label className="flex items-center gap-2"><input type="radio" name="bill" checked={bill === "quote"} onChange={() => setBill("quote")} /> The quoted price{o.job.quote ? ` (${usd(o.job.quote)})` : " (none set)"}</label>
              <label className="flex items-center gap-2"><input type="radio" name="bill" checked={bill === "none"} onChange={() => setBill("none")} /> Nothing, just close it</label>
            </fieldset>
            {!confirm ? <button className="btn" onClick={() => setConfirm(true)}>Close job…</button> : (
              <div className="flex flex-wrap items-center gap-2">
                <span>Stops any running timer, marks work items done{bill !== "none" ? ", and creates a draft invoice" : ""}.</span>
                <button className="btn" onClick={close}>Yes, close it</button>
                <button className="btn" onClick={() => setConfirm(false)}>Cancel</button>
              </div>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}

function Inner() {
  const sp = useSearchParams();
  const id = Number(sp.get("id"));
  if (!id) return <p className="text-sm">No job chosen. <Link href="/clients" className="underline">Pick one from Clients</Link>.</p>;
  return <JobView id={id} />;
}

export default function JobPage() {
  return (
    <PageShell title="Job" subtitle="Everything for one job in one place, with a client-ready write-up when you close it.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense>
    </PageShell>
  );
}
