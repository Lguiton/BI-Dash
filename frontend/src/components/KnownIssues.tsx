"use client";
import { useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

type Kev = { cve: string; vendor: string; product: string; name: string; added: string; what: string; action: string; due: string; ransomware: boolean };
type KevRes = { query: string; total: number; shown: number; catalog_total: number; results: Kev[]; saved_on: string; warning: string; note: string };
type Rel = { cycle: string; label: string; released: string; eol: string; latest: string; lts: boolean; status: "ended" | "soon" | "supported"; says: string };
type EolRes = { product: string; releases: Rel[]; saved_on: string; warning: string; note: string };
const PRODUCTS = ["windows", "windows-server", "macos", "ios", "android", "ubuntu", "debian", "office", "python", "nodejs", "php", "mysql", "postgresql", "wordpress", "firefox"];
const tone = (s: Rel["status"]) => (s === "ended" ? "bad" : s === "soon" ? "warn" : "ok");

function Support() {
  const [product, setProduct] = useState("");
  const [cycle, setCycle] = useState("");
  const [res, setRes] = useState<EolRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { setRes(await getJson<EolRes>(`/api/known-issues/eol?product=${encodeURIComponent(product.trim())}&cycle=${encodeURIComponent(cycle.trim())}`)); }
    catch (x) { setErr(errMsg(x, "Couldn't look that up.")); setRes(null); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Is this still supported? (endoflife.date)</h3>
      <form onSubmit={go} className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-44 flex-col gap-1 text-xs text-muted">Product
          <input className="input" list="ki-products" placeholder="windows, ubuntu, macos…" value={product} onChange={(e) => setProduct(e.target.value)} required />
          <datalist id="ki-products">{PRODUCTS.map((p) => <option key={p} value={p} />)}</datalist>
        </label>
        <label className="flex w-40 flex-col gap-1 text-xs text-muted">Version (optional)
          <input className="input" placeholder="e.g. 10 or 22.04" value={cycle} onChange={(e) => setCycle(e.target.value)} />
        </label>
        <button className="btn btn-primary" disabled={busy || !product.trim()}>{busy ? "Looking…" : "Check support dates"}</button>
      </form>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      {res && (
        <div className="space-y-1">
          {res.warning && <p role="status" className="text-xs text-amber-600">{res.warning}</p>}
          {res.releases.length === 0 && <p className="text-sm text-muted">No version matched. Clear the version box to see them all.</p>}
          <ul className="space-y-1 text-sm">
            {res.releases.map((r) => (
              <li key={r.cycle} className="flex flex-wrap items-center justify-between gap-2 rounded border border-line px-2 py-1">
                <span><strong>{r.label}</strong>{r.lts && <span className="ml-2 text-xs text-muted">LTS</span>}{r.latest && <span className="ml-2 text-xs text-muted">latest {r.latest}</span>}</span>
                <Badge tone={tone(r.status)}>{r.says}</Badge>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">{res.note} Copy saved {res.saved_on}.</p>
        </div>
      )}
    </div>
  );
}

function Exploited() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<KevRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { setRes(await getJson<KevRes>(`/api/known-issues/kev?q=${encodeURIComponent(q.trim())}&limit=25`)); }
    catch (x) { setErr(errMsg(x, "Couldn't load the list.")); setRes(null); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Flaws attackers are using now (CISA list)</h3>
      <form onSubmit={go} className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-56 flex-1 flex-col gap-1 text-xs text-muted">Vendor, product or CVE (blank shows the newest)
          <input className="input" placeholder="e.g. windows, cisco, CVE-2026-1234" value={q} onChange={(e) => setQ(e.target.value)} maxLength={120} />
        </label>
        <button className="btn btn-primary" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
      </form>
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      {res && (
        <div className="space-y-1">
          {res.warning && <p role="status" className="text-xs text-amber-600">{res.warning}</p>}
          <p className="text-xs text-muted">{res.total} match{res.total === 1 ? "" : "es"}{res.total > res.shown ? `, showing the newest ${res.shown}` : ""} of {res.catalog_total} listed.</p>
          <ul className="space-y-1 text-sm">
            {res.results.map((r) => (
              <li key={r.cve} className="rounded border border-line px-2 py-1">
                <div className="flex flex-wrap items-center justify-between gap-2"><span><strong>{r.cve}</strong> · {r.vendor} {r.product}</span><span className="text-xs text-muted">added {r.added}{r.ransomware ? " · used in ransomware" : ""}</span></div>
                <div>{r.name}</div>
                <div className="text-xs text-muted">{r.action}{r.due ? ` (government due date ${r.due})` : ""}</div>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">{res.note} Copy saved {res.saved_on}.</p>
        </div>
      )}
    </div>
  );
}

/** Two free public lookups for IT repair and security jobs: when software stops getting updates, and which flaws are being exploited. */
export function KnownIssues({ first }: { first: "support" | "exploited" }) {
  return (
    <section className="card space-y-4 p-4" aria-label="Known issues and support dates">
      <div><h2 className="text-sm font-semibold">Known issues and support dates</h2><p className="text-xs text-muted">Free public data, no key. Check the vendor&apos;s page before telling a client.</p></div>
      {first === "support" ? <><Support /><hr className="border-line" /><Exploited /></> : <><Exploited /><hr className="border-line" /><Support /></>}
    </section>
  );
}
