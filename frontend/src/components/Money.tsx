"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { Badge, Field, Section, Stat, Table, errMsg } from "@/components/panels/kit";

const money = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Re-runs a loader whenever `tick` changes. The state is set only after the request returns (no sync setState in the effect body). */
function useLoad<T>(path: string, tick: number, onErr: (m: string) => void): T | null {
  const [v, setV] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    getJson<T>(path).then((r) => { if (live) setV(r); }).catch((e) => { if (live) onErr(errMsg(e, "Could not load.")); });
    return () => { live = false; };
  }, [path, tick, onErr]);
  return v;
}

type Row = { id: number; number: string; client: string; email: string; total: number; due: string; days_late: number; bucket: string; last_reminded: string | null };
type Rec = { sample: boolean; owed: number; late: number; rows: Row[]; buckets: { id: string; label: string; count: number; total: number }[]; drafts: { id: number; number: string; client: string; total: number; age_days: number }[]; draft_total: number; thank_you: { id: number; number: string; client: string; total: number; paid_date: string }[]; review_url_set: boolean; note: string };
type Draft = { subject: string; body: string; to: string; tone?: string; note: string };

function DraftBox({ d, onSent, sentLabel, onClose }: { d: Draft; onSent: () => void; sentLabel: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(`Subject: ${d.subject}\n\n${d.body}`); setCopied(true); } catch { setCopied(false); }
  }
  return (
    <div className="mt-2 space-y-2 rounded border border-line bg-panel2 p-3 text-sm">
      <p className="text-xs text-muted">To: {d.to || "(no email saved for this client)"}{d.tone ? ` · tone: ${d.tone}` : ""}</p>
      <p><strong>{d.subject}</strong></p>
      <pre className="whitespace-pre-wrap font-sans" tabIndex={0}>{d.body}</pre>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        <button className="btn" onClick={onSent}>{sentLabel}</button>
        <button className="btn" onClick={onClose}>Close</button>
        <span className="text-xs text-muted">{d.note}</span>
      </div>
    </div>
  );
}

export function Owed() {
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<{ kind: "rem" | "thx"; id: number; d: Draft } | null>(null);
  const [url, setUrl] = useState("");
  const r = useLoad<Rec>("/api/money/receivables", tick, setErr);
  const bump = () => setTick((t) => t + 1);
  async function draft(kind: "rem" | "thx", id: number) {
    setErr(null);
    try { setOpen({ kind, id, d: await getJson<Draft>(`/api/money/${kind === "rem" ? "reminder" : "thank-you"}/${id}`) }); } catch (e) { setErr(errMsg(e, "Could not draft it.")); }
  }
  async function sent() {
    if (!open) return;
    try { await postJson(`/api/money/${open.kind === "rem" ? "reminder" : "thank-you"}/${open.id}/sent`, {}); setOpen(null); bump(); } catch (e) { setErr(errMsg(e, "Could not save that.")); }
  }
  async function saveUrl() {
    try { await putJson("/api/money/settings", { review_url: url }); setUrl(""); bump(); } catch (e) { setErr(errMsg(e, "Could not save the link.")); }
  }
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {r?.sample && <p role="note" className="rounded border border-amber-500 bg-amber-500/10 p-2 text-sm">Practice workspace: sample data. Switch to Real for your own invoices.</p>}
      {r && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Owed to you" value={money(r.owed)} /><Stat label="Past due" value={money(r.late)} />
            <Stat label="Drafts not sent" value={money(r.draft_total)} sub={`${r.drafts.length} invoice${r.drafts.length === 1 ? "" : "s"}`} />
            <Stat label="Waiting on a thank-you" value={String(r.thank_you.length)} />
          </div>
          <Section title="By how late" note={r.note}>
            <div className="flex flex-wrap gap-2 text-sm">{r.buckets.map((b) => <span key={b.id} className="rounded border border-line px-3 py-1">{b.label}: <strong>{b.count}</strong> · {money(b.total)}</span>)}</div>
          </Section>
          <Section title="Invoices waiting to be paid">
            {r.rows.length === 0 ? <p className="text-sm text-muted">Nothing is waiting. Invoices show here once you mark them sent.</p> : (
              <ul className="divide-y divide-line">
                {r.rows.map((x) => (
                  <li key={x.id} className="py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span><strong>{x.number}</strong> · {x.client} · {money(x.total)} · due {x.due}{" "}
                        {x.days_late > 0 ? <Badge tone={x.days_late > 30 ? "bad" : "warn"}>{x.days_late} days late</Badge> : <Badge>{x.days_late === 0 ? "due today" : `due in ${-x.days_late} days`}</Badge>}
                        {x.last_reminded && <span className="ml-2 text-xs text-muted">reminded {x.last_reminded}</span>}</span>
                      <span className="flex gap-2"><button className="btn" onClick={() => draft("rem", x.id)}>Draft reminder</button></span>
                    </div>
                    {open?.kind === "rem" && open.id === x.id && <DraftBox d={open.d} sentLabel="I sent it" onSent={sent} onClose={() => setOpen(null)} />}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          {r.drafts.length > 0 && (
            <Section title="Draft invoices (never sent)" note="Open Clients, set the invoice to sent once you have given it to the client. Then it counts as owed.">
              <ul className="text-sm">{r.drafts.map((d) => <li key={d.id}>{d.number} · {d.client} · {money(d.total)} <span className="text-muted">· made {d.age_days} days ago</span></li>)}</ul>
            </Section>
          )}
          <Section title="Thank-you and review asks" note="Paid in the last 60 days. The note is a draft: you send it.">
            {!r.review_url_set && (
              <div className="mb-3 flex flex-wrap items-end gap-2"><Field label="Your review link (Google, Nextdoor...)"><input aria-label="Review link" className="input w-80" value={url} placeholder="https://" onChange={(e) => setUrl(e.target.value)} /></Field><button className="btn" disabled={!url.trim()} onClick={saveUrl}>Save link</button></div>
            )}
            {r.thank_you.length === 0 ? <p className="text-sm text-muted">No paid invoices are waiting for a thank-you.</p> : (
              <ul className="divide-y divide-line">
                {r.thank_you.map((x) => (
                  <li key={x.id} className="py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span><strong>{x.number}</strong> · {x.client} · {money(x.total)} · paid {x.paid_date}</span><button className="btn" onClick={() => draft("thx", x.id)}>Draft thank-you</button></div>
                    {open?.kind === "thx" && open.id === x.id && <DraftBox d={open.d} sentLabel="I sent it" onSent={sent} onClose={() => setOpen(null)} />}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </>
      )}
    </div>
  );
}

type PJob = { job_id: number; title: string; client: string; status: string; hours: number; charged: number; paid: number; owed: number; parts: number; net: number; per_hour: number | null; flag: string };
type Profit = { sample: boolean; target_rate: number; jobs: PJob[]; clients: { client: string; hours: number; charged: number; parts: number; net: number; per_hour: number | null }[]; totals: { hours: number; charged: number; parts: number; net: number; per_hour: number | null }; note: string };

export function ProfitView() {
  const [err, setErr] = useState<string | null>(null);
  const p = useLoad<Profit>("/api/money/profit", 0, setErr);
  const ph = (n: number | null) => (n == null ? "—" : `${money(n)}/h`);
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {p && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Charged" value={money(p.totals.charged)} /><Stat label="Parts" value={money(p.totals.parts)} /><Stat label="Net" value={money(p.totals.net)} /><Stat label="Net per hour" value={ph(p.totals.per_hour)} sub={`your rate ${money(p.target_rate)}/h`} />
          </div>
          <Section title="Each job, lowest hourly first" note={p.note}>
            {p.jobs.length === 0 ? <p className="text-sm text-muted">Log hours and invoice a job to see it here.</p> : (
              <Table head={["Job", "Client", "Hours", "Charged", "Parts", "Net", "Per hour", "Paid / owed", "Note"]} rows={p.jobs.map((j) => [j.title, j.client, j.hours, money(j.charged), money(j.parts), money(j.net), ph(j.per_hour), `${money(j.paid)} / ${money(j.owed)}`, j.flag ? <span key="f" className="block min-w-48 whitespace-normal text-xs text-amber-600">{j.flag}</span> : ""])} caption="Profit per job" />
            )}
          </Section>
          {p.clients.length > 1 && (
            <Section title="By client"><Table head={["Client", "Hours", "Charged", "Parts", "Net", "Per hour"]} rows={p.clients.map((c) => [c.client, c.hours, money(c.charged), money(c.parts), money(c.net), ph(c.per_hour)])} caption="Profit per client" /></Section>
          )}
        </>
      )}
    </div>
  );
}

type Books = {
  sample: boolean; year: number; settings: { tax_pct: number; mileage_rate: number; review_url: string }; income: number; expenses_total: number; miles: number; mileage_deduction: number; net: number; set_aside: number;
  categories: { category: string; total: number }[]; quarters: { quarter: number; income: number; expenses: number; mileage: number; net: number; set_aside: number }[]; due_dates: string[]; next_due: string | null;
  paid: { number: string; client: string; paid_date: string; total: number; set_aside: number }[]; expenses: { id: number; date: string; amount: number; category: string; vendor: string; note: string; job_id: number | null }[];
  mileage_log: { id: number; date: string; miles: number; purpose: string }[]; note: string;
};

export function BooksView() {
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [cats, setCats] = useState<string[]>([]);
  const [ex, setEx] = useState({ amount: "", category: "parts", vendor: "", note: "", date: "" });
  const [mi, setMi] = useState({ miles: "", purpose: "", date: "" });
  const [tax, setTax] = useState("");
  const [rate, setRate] = useState("");
  const b = useLoad<Books>(`/api/money/books?year=${year}`, tick, setErr);
  useEffect(() => { getJson<{ categories: string[] }>("/api/money/categories").then((r) => setCats(r.categories)).catch(() => {}); }, []);
  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't work.")); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Year"><input aria-label="Year" type="number" className="input w-24" value={year} min={2000} max={2100} onChange={(e) => setYear(Number(e.target.value) || new Date().getFullYear())} /></Field>
        <button className="btn" onClick={() => downloadFile(`/api/money/books.csv?year=${year}`, `books-${year}.csv`).catch((e) => setErr(errMsg(e, "Download failed.")))}>Download CSV for your tax preparer</button>
      </div>
      {b && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Income (paid)" value={money(b.income)} /><Stat label="Expenses" value={money(b.expenses_total)} /><Stat label="Mileage" value={money(b.mileage_deduction)} sub={`${b.miles} miles`} /><Stat label="Net" value={money(b.net)} /><Stat label={`Set aside (${b.settings.tax_pct}%)`} value={money(b.set_aside)} />
          </div>
          <p className="text-sm">{b.next_due ? <>Next typical estimated-tax date: <strong>{b.next_due}</strong>. </> : "All four typical estimated-tax dates for this year have passed. "}<span className="text-xs text-muted">Dates: {b.due_dates.join(", ")}</span></p>
          <Section title="Settings" note="You choose the set-aside percent and keep the mileage rate current.">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Set aside % of net"><input aria-label="Set-aside percent" className="input w-24" value={tax || String(b.settings.tax_pct)} onChange={(e) => setTax(e.target.value)} /></Field>
              <Field label="Mileage rate $ per mile"><input aria-label="Mileage rate" className="input w-24" value={rate || String(b.settings.mileage_rate)} onChange={(e) => setRate(e.target.value)} /></Field>
              <button className="btn" onClick={() => act(async () => { await putJson("/api/money/settings", { tax_pct: tax || b.settings.tax_pct, mileage_rate: rate || b.settings.mileage_rate }); setTax(""); setRate(""); })}>Save</button>
            </div>
          </Section>
          <Section title="By quarter"><Table head={["Quarter", "Income", "Expenses", "Mileage", "Net", "Set aside"]} rows={b.quarters.map((q) => [`Q${q.quarter}`, money(q.income), money(q.expenses), money(q.mileage), money(q.net), money(q.set_aside)])} caption="Quarterly totals" /></Section>
          <Section title="Add an expense">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Amount $"><input aria-label="Expense amount" className="input w-24" value={ex.amount} onChange={(e) => setEx({ ...ex, amount: e.target.value })} /></Field>
              <Field label="Category"><select aria-label="Expense category" className="input" value={ex.category} onChange={(e) => setEx({ ...ex, category: e.target.value })}>{cats.map((c) => <option key={c}>{c}</option>)}</select></Field>
              <Field label="Vendor"><input aria-label="Vendor" className="input w-40" value={ex.vendor} onChange={(e) => setEx({ ...ex, vendor: e.target.value })} /></Field>
              <Field label="Note"><input aria-label="Expense note" className="input w-48" value={ex.note} onChange={(e) => setEx({ ...ex, note: e.target.value })} /></Field>
              <Field label="Date (blank = today)"><input aria-label="Expense date" className="input w-36" placeholder="YYYY-MM-DD" value={ex.date} onChange={(e) => setEx({ ...ex, date: e.target.value })} /></Field>
              <button className="btn" disabled={!ex.amount} onClick={() => act(async () => { await postJson("/api/money/expenses", { ...ex, date: ex.date || null }); setEx({ amount: "", category: ex.category, vendor: "", note: "", date: "" }); })}>Add</button>
            </div>
            <ul className="mt-3 divide-y divide-line text-sm">{b.expenses.map((e) => <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-1"><span>{e.date} · {money(e.amount)} · {e.category}{e.vendor ? ` · ${e.vendor}` : ""}{e.note ? ` · ${e.note}` : ""}</span><button className="btn" aria-label={`Delete expense ${e.date} ${money(e.amount)}`} onClick={() => act(() => deleteJson(`/api/money/expenses/${e.id}`))}>Delete</button></li>)}</ul>
            {b.expenses.length === 0 && <p className="mt-2 text-sm text-muted">No expenses for {b.year}. Keep the receipts.</p>}
          </Section>
          <Section title="Mileage log">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Miles"><input aria-label="Miles" className="input w-24" value={mi.miles} onChange={(e) => setMi({ ...mi, miles: e.target.value })} /></Field>
              <Field label="Purpose"><input aria-label="Trip purpose" className="input w-64" placeholder="Client visit: Acme Dental" value={mi.purpose} onChange={(e) => setMi({ ...mi, purpose: e.target.value })} /></Field>
              <Field label="Date (blank = today)"><input aria-label="Trip date" className="input w-36" placeholder="YYYY-MM-DD" value={mi.date} onChange={(e) => setMi({ ...mi, date: e.target.value })} /></Field>
              <button className="btn" disabled={!mi.miles} onClick={() => act(async () => { await postJson("/api/money/mileage", { ...mi, date: mi.date || null }); setMi({ miles: "", purpose: "", date: "" }); })}>Add trip</button>
            </div>
            <ul className="mt-3 divide-y divide-line text-sm">{b.mileage_log.map((r) => <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-1"><span>{r.date} · {r.miles} miles{r.purpose ? ` · ${r.purpose}` : ""}</span><button className="btn" aria-label={`Delete trip ${r.date} ${r.miles} miles`} onClick={() => act(() => deleteJson(`/api/money/mileage/${r.id}`))}>Delete</button></li>)}</ul>
          </Section>
          <Section title="Set aside per payment"><Table head={["Invoice", "Client", "Paid", "Amount", "Set aside"]} rows={b.paid.map((p) => [p.number, p.client, p.paid_date, money(p.total), money(p.set_aside)])} caption="Payments received" /></Section>
          <p className="text-xs text-muted">{b.note}</p>
        </>
      )}
    </div>
  );
}
