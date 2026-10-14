"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson, postJson } from "@/lib/api";

type Svc = { id: string; group: string; name: string; deliverable: string; hours: number[]; model: string; tool: string; needs: string; rate: number; low: number; high: number };
type Cat = { groups: { id: string; name: string; rate: number }[]; services: Svc[]; note: string };
type Price = { date: string; note: string; groups: { group: string; rows: { service: string; gets: string; market: string; price: string }[] }[] };
type Quote = { client: string; lines: { id: string; name: string; qty: number; model: string; hours: number[]; low: number; high: number }[]; subtotal: number[]; discount_pct: number; total: number[]; note: string };
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
const usd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const per = (m: string) => (m === "monthly" ? " / month" : m === "hourly" ? " / session" : "");

export default function ServicesPage() {
  const [cat, setCat] = useState<Cat | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pick, setPick] = useState<Record<string, number>>({});
  const [client, setClient] = useState("");
  const [disc, setDisc] = useState(0);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [group, setGroup] = useState("");
  const [view, setView] = useState<"catalog" | "prices">("catalog");
  const [pl, setPl] = useState<Price | null>(null);
  useEffect(() => { getJson<Cat>("/api/service-list").then(setCat).catch((e) => setErr(msg(e))); getJson<Price>("/api/service-list/price-list").then(setPl).catch((e) => setErr(msg(e))); }, []);
  const shown = useMemo(() => (cat?.services ?? []).filter((s) => !group || s.group === group), [cat, group]);
  async function makeQuote() {
    setErr(null);
    try { setQuote(await postJson<Quote>("/api/service-list/quote", { lines: Object.entries(pick).map(([id, qty]) => ({ id, qty })), client, discount_pct: disc })); } catch (e) { setErr(msg(e)); }
  }
  const count = Object.keys(pick).length;
  return (
    <PageShell title="Services" subtitle="What you can sell across analytics, data science, computer and network engineering and IT repair, with a quick quote builder.">
      {err && <ErrorBanner message={err} />}
      <div role="tablist" aria-label="Services view" className="flex flex-wrap gap-2">
        <button role="tab" aria-selected={view === "catalog"} className={`btn ${view === "catalog" ? "btn-primary" : ""}`} onClick={() => setView("catalog")}>Service catalog and quotes</button>
        <button role="tab" aria-selected={view === "prices"} className={`btn ${view === "prices" ? "btn-primary" : ""}`} onClick={() => setView("prices")}>Henderson and Las Vegas price list</button>
      </div>
      {view === "prices" && pl && (
        <section className="space-y-4" aria-label="Price list">
          <div className="card space-y-1 p-4 text-sm">
            <p>Researched {pl.date}. <strong>Your price</strong> is set about 10-20% under the local market range.</p>
            <p className="text-xs text-muted">{pl.note}</p>
            <button className="btn w-fit" onClick={() => window.print()}>Print</button>
          </div>
          {pl.groups.map((g) => (
            <div key={g.group} className="card overflow-x-auto p-4">
              <h2 className="mb-2 text-sm font-semibold">{g.group}</h2>
              <table className="w-full text-sm">
                <caption className="sr-only">{g.group}</caption>
                <thead><tr><th className="th">Service</th><th className="th">What the client gets</th><th className="th">Market</th><th className="th">Your price</th></tr></thead>
                <tbody>{g.rows.map((r) => <tr key={r.service} className="border-t border-line"><td className="td font-medium">{r.service}</td><td className="td">{r.gets}</td><td className="td text-muted">{r.market}</td><td className="td font-semibold">{r.price}</td></tr>)}</tbody>
              </table>
            </div>
          ))}
        </section>
      )}
      {view === "catalog" && cat && (
        <>
          <p className="text-xs text-muted">Hourly rates are set in <Link href="/settings?tab=business" className="underline">Settings, Business and services</Link>. {cat.note}</p>
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Service groups">
            <button role="tab" aria-selected={!group} className={`btn ${!group ? "btn-primary" : ""}`} onClick={() => setGroup("")}>All</button>
            {cat.groups.map((g) => <button key={g.id} role="tab" aria-selected={group === g.id} className={`btn ${group === g.id ? "btn-primary" : ""}`} onClick={() => setGroup(g.id)}>{g.name}</button>)}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {shown.map((s) => (
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
          <section className="card space-y-2 p-4" aria-label="Quote builder">
            <h2 className="text-sm font-semibold">Quote builder ({count} selected)</h2>
            <div className="flex flex-wrap items-end gap-3 text-xs">
              <label className="flex flex-col gap-1">Client<input className="field" maxLength={80} value={client} onChange={(e) => setClient(e.target.value)} /></label>
              <label className="flex flex-col gap-1">Discount %<input className="field w-20" type="number" min={0} max={50} value={disc} onChange={(e) => setDisc(Number(e.target.value))} /></label>
              <button className="btn btn-primary" disabled={!count} onClick={makeQuote}>Make quote</button>
              <button className="btn" onClick={() => window.print()} disabled={!quote}>Print</button>
            </div>
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
    </PageShell>
  );
}
