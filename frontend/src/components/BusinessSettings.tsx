"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, putJson } from "@/lib/api";
import { errMsg } from "@/components/panels/kit";

type Biz = { rate: number; terms_days: number; business: string; pay_to: string };
type Cat = { groups: { id: string; name: string; rate: number }[]; note: string };

/** What appears on your invoices and the hourly rate behind every quote. */
export function BusinessProfile() {
  const [b, setB] = useState<Biz | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  useEffect(() => {
    let live = true;
    getJson<Biz>("/api/clients/settings").then((r) => { if (live) setB(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load your business details.")); });
    return () => { live = false; };
  }, []);
  async function save() {
    if (!b) return;
    setErr(null); setOk("");
    try { setB(await putJson<Biz>("/api/clients/settings", b)); setOk("Saved."); } catch (e) { setErr(errMsg(e, "Could not save.")); }
  }
  return (
    <section className="card space-y-3 p-5" aria-label="Business details">
      <h2 className="text-lg font-semibold">Business details</h2>
      <p className="text-sm text-muted">Shown on invoices. The default rate is used for time on jobs that have no rate of their own.</p>
      {err && <ErrorBanner message={err} />}
      {b && (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-xs text-muted">Business name<input className="field" maxLength={80} value={b.business} onChange={(e) => setB({ ...b, business: e.target.value })} aria-label="Business name" /></label>
          <label className="grid gap-1 text-xs text-muted">How clients pay you<input className="field" maxLength={200} value={b.pay_to} onChange={(e) => setB({ ...b, pay_to: e.target.value })} aria-label="How clients pay you" /></label>
          <label className="grid gap-1 text-xs text-muted">Default hourly rate ($)<input className="field" type="number" min={0} max={10000} value={b.rate} onChange={(e) => setB({ ...b, rate: Number(e.target.value) })} aria-label="Default hourly rate" /></label>
          <label className="grid gap-1 text-xs text-muted">Payment terms (days until due)<input className="field" type="number" min={0} max={365} value={b.terms_days} onChange={(e) => setB({ ...b, terms_days: Number(e.target.value) })} aria-label="Payment terms in days" /></label>
        </div>
      )}
      <div className="flex items-center gap-3"><button className="btn btn-primary" onClick={save} disabled={!b}>Save</button>{ok && <span role="status" className="text-sm text-emerald-600">{ok}</span>}</div>
    </section>
  );
}

/** Hourly rate for each kind of service. The Services page and every quote use these. */
export function ServiceRates() {
  const [cat, setCat] = useState<Cat | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  useEffect(() => {
    let live = true;
    getJson<Cat>("/api/service-list").then((r) => { if (live) setCat(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the service rates.")); });
    return () => { live = false; };
  }, []);
  async function setRate(g: string, v: number) {
    setErr(null); setOk("");
    try { setCat(await putJson<Cat>("/api/service-list/rates", { [g]: v })); setOk("Rate saved."); } catch (e) { setErr(errMsg(e, "Could not save that rate.")); }
  }
  return (
    <section className="card space-y-3 p-5" aria-label="Service rates">
      <h2 className="text-lg font-semibold">Service hourly rates</h2>
      <p className="text-sm text-muted">Starting values come from the Henderson and Las Vegas price research (set a little under the local market). Change any of them to suit you. Quotes and the Services page update straight away. <Link href="/services" className="underline">Open Services and the price list</Link></p>
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cat?.groups.map((g) => (
          <label key={g.id} className="grid gap-1 text-xs text-muted">{g.name}
            <input className="field" type="number" min={0} max={2000} defaultValue={g.rate} aria-label={`${g.name} hourly rate`} onBlur={(e) => { const v = Number(e.target.value); if (v !== g.rate) void setRate(g.id, v); }} />
          </label>
        ))}
      </div>
      {ok && <p role="status" className="text-sm text-emerald-600">{ok}</p>}
    </section>
  );
}
