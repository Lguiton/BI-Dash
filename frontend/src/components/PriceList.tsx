"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import { errMsg } from "@/components/panels/kit";

type Price = { date: string; note: string; groups: { group: string; rows: { service: string; gets: string; market: string; price: string }[] }[] };

/** The Henderson and Las Vegas price list you can print and hand to a client. Lives in Settings, Business and services. */
export function PriceList() {
  const [pl, setPl] = useState<Price | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { let live = true; getJson<Price>("/api/service-list/price-list").then((p) => { if (live) setPl(p); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the price list.")); }); return () => { live = false; }; }, []);
  return (
    <>
      {err && <ErrorBanner message={err} />}
      {pl && (
        <section className="space-y-4" aria-label="Price list">
          <div className="card space-y-1 p-4 text-sm">
            <p>Researched {pl.date}. <strong>Your price</strong> is set about 10-20% under the local market range.</p>
            <p className="text-xs text-muted">{pl.note}</p>
            <div className="flex gap-2"><button className="btn w-fit" onClick={() => window.print()}>Print</button>
              <button className="btn w-fit" onClick={() => downloadFile("/api/service-list/price-list/pdf", "price-list.pdf").catch((e) => setErr(errMsg(e, "Download failed.")))}>Download PDF</button></div>
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
    </>
  );
}
