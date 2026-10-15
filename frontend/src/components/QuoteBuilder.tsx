"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getJson, postJson } from "@/lib/api";
import { downloadPost } from "@/lib/download";

type Svc = { id: string; group: string; name: string; deliverable: string; hours: number[]; model: string; tool: string; needs: string; rate: number; low: number; high: number };
type Cat = { groups: { id: string; name: string; rate: number }[]; services: Svc[]; note: string };
type Quote = { client: string; lines: { id: string; name: string; qty: number; model: string; hours: number[]; low: number; high: number }[]; subtotal: number[]; discount_pct: number; total: number[]; note: string };
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
const usd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const per = (m: string) => (m === "monthly" ? " / month" : m === "hourly" ? " / session" : "");

/** Everything you can sell, sorted by field, with the quote builder. Lives in Settings, Quotes and prices. */
export function QuoteBuilder() {
  const [cat, setCat] = useState<Cat | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [client, setClient] = useState("");
  const [disc, setDisc] = useState(0);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [group, setGroup] = useState("");
  const [clients, setClients] = useState<{ id: number; name: string }[]>([]);
  const [pricePick, setPricePick] = useState("mid");
  const [saved, setSaved] = useState<{ job_id: number; price: number } | null>(null);
  useEffect(() => { getJson<{ clients: { id: number; name: string }[] }>("/api/clients").then((r) => setClients(r.clients)).catch(() => {}); }, []);
  async function saveJob() {
    setErr(null);
    const name = client.trim();
    const hit = clients.find((c) => c.name.toLowerCase() === name.toLowerCase());
    try {
      const r = await postJson<{ job: { id: number }; price: number }>("/api/clients/jobs/from-quote", { lines: Object.entries(pick).map(([id, qty]) => ({ id, qty })), discount_pct: disc, pick: pricePick, ...(hit ? { client_id: hit.id } : { client_name: name }) });
      setSaved({ job_id: r.job.id, price: r.price });
      getJson<{ clients: { id: number; name: string }[] }>("/api/clients").then((x) => setClients(x.clients)).catch(() => {});
    } catch (e) { setErr(msg(e)); }
  }
  useEffect(() => { getJson<Cat>("/api/service-list").then(setCat).catch((e) => setErr(msg(e))); }, []);
  async function makeQuote() {
    setErr(null);
    try { setQuote(await postJson<Quote>("/api/service-list/quote", { lines: Object.entries(pick).map(([id, qty]) => ({ id, qty })), client, discount_pct: disc })); } catch (e) { setErr(msg(e)); }
  }
  const count = Object.keys(pick).length;
  const byField = useMemo(() => (cat?.groups ?? []).filter((g) => !group || g.id === group).map((g) => ({ g, items: (cat?.services ?? []).filter((x) => x.group === g.id) })).filter((x) => x.items.length), [cat, group]);
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {cat && (
        <>
          <p className="text-xs text-muted">Pick the services for a job by field, then build a quote. Hourly rates are under Business and services. {cat.note}</p>
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Fields">
            <button role="tab" aria-selected={!group} className={`btn ${!group ? "btn-primary" : ""}`} onClick={() => setGroup("")}>All fields</button>
            {cat.groups.map((g) => <button key={g.id} role="tab" aria-selected={group === g.id} className={`btn ${group === g.id ? "btn-primary" : ""}`} onClick={() => setGroup(g.id)}>{g.name}</button>)}
          </div>
          {byField.map(({ g, items }) => (
            <section key={g.id} className="space-y-2" aria-label={g.name}>
              <h2 className="text-sm font-semibold">{g.name} <span className="font-normal text-muted">· {items.length} services · {usd(g.rate)}/hour</span></h2>
              <div className="grid gap-3 md:grid-cols-2">
                {items.map((s) => (
                  <article key={s.id} className="card space-y-1 p-4 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold">{s.name}</h3>
                      <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={s.id in pick} onChange={(e) => setPick((p) => { const n = { ...p }; if (e.target.checked) n[s.id] = 1; else delete n[s.id]; return n; })} />Quote</label>
                    </div>
                    <p>{s.deliverable}</p>
                    <p className="text-xs text-muted">Typical {s.hours[0]} to {s.hours[1]} hours · {usd(s.low)} to {usd(s.high)}{per(s.model)} at {usd(s.rate)}/hour</p>
                    <p className="text-xs text-muted">Helps: {s.tool}{s.needs ? ` · You need: ${s.needs}` : ""}</p>
                  </article>
                ))}
              </div>
            </section>
          ))}
          <section className="card space-y-2 p-4" aria-label="Quote builder">
            <h2 className="text-sm font-semibold">Quote builder ({count} selected)</h2>
            <div className="flex flex-wrap items-end gap-3 text-xs">
              <label className="flex flex-col gap-1">Client<input className="field" list="quote-clients" maxLength={80} value={client} onChange={(e) => setClient(e.target.value)} /><datalist id="quote-clients">{clients.map((c) => <option key={c.id} value={c.name} />)}</datalist></label>
              <label className="flex flex-col gap-1">Discount %<input className="field w-20" type="number" min={0} max={50} value={disc} onChange={(e) => setDisc(Number(e.target.value))} /></label>
              <button className="btn btn-primary" disabled={!count} onClick={makeQuote}>Make quote</button>
              <label className="flex flex-col gap-1">Job price<select className="field" value={pricePick} onChange={(e) => setPricePick(e.target.value)}><option value="mid">Middle of the range</option><option value="low">Low end</option><option value="high">High end</option></select></label>
              <button className="btn" disabled={!quote || !client.trim()} title={client.trim() ? "Creates the job in Clients with this price, status quoted" : "Type the client's name first"} onClick={saveJob}>Save as quoted job</button>
              <button className="btn" onClick={() => window.print()} disabled={!quote}>Print</button>
              <button className="btn" disabled={!quote} onClick={() => downloadPost("/api/service-list/quote/pdf", { lines: Object.entries(pick).map(([id, qty]) => ({ id, qty })), client, discount_pct: disc }, "quote.pdf").catch((e) => setErr(msg(e)))}>Download PDF</button>
            </div>
            {saved && <p role="status" className="text-sm">Saved as a quoted job at ${saved.price.toLocaleString("en-US", { maximumFractionDigits: 0 })}. <Link className="underline" href={`/job?id=${saved.job_id}`}>Open the job</Link>. When the client says yes, press &ldquo;Quote accepted&rdquo; there; when the work is done, close the job to invoice it.</p>}
            {quote && (
              <div className="space-y-1 text-sm">
                <h3 className="font-semibold">Quote{quote.client ? ` for ${quote.client}` : ""}</h3>
                <ul className="list-disc pl-5">{quote.lines.map((l) => <li key={l.id}>{l.name}{l.qty > 1 ? ` × ${l.qty}` : ""}: {usd(l.low)} to {usd(l.high)}{per(l.model)}</li>)}</ul>
                <p>Subtotal {usd(quote.subtotal[0])} to {usd(quote.subtotal[1])}{quote.discount_pct ? `, after ${quote.discount_pct}% off: ` : ". Total: "}<strong>{usd(quote.total[0])} to {usd(quote.total[1])}</strong></p>
                <p className="text-xs text-muted">{quote.note}</p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
