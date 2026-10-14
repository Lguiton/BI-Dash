"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Building2 } from "lucide-react";
import { getJson } from "@/lib/api";
import type { CoOverview } from "@/lib/types";

/** Compact "where am I in the whole job" card for the home page. */
export function CompanyCard() {
  const [d, setD] = useState<CoOverview | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<CoOverview>("/api/company", ctl.signal).then(setD).catch(() => { /* the full page shows errors */ });
    return () => ctl.abort();
  }, []);
  if (!d) return null;
  return (
    <section className="card space-y-2 p-4" aria-label="Company engagement">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><Building2 className="h-4 w-4" aria-hidden /> Company engagement{d.brief.company ? `: ${d.brief.company}` : ""} · {d.done}/{d.total} ({d.pct}%)</h2>
        <div className="flex gap-2">{d.next && <Link href={d.next.href} className="btn text-xs">Next: {d.next.title}</Link>}<Link href="/company" className="btn btn-primary text-xs">Open plan</Link></div>
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {d.disciplines.map((x) => <Link key={x.id} href={x.href} className="rounded-full bg-panel2 px-3 py-1 hover:underline">{x.name.split(" (")[0]} {x.done}/{x.total}</Link>)}
      </div>
    </section>
  );
}
