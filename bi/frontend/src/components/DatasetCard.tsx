"use client";
import Link from "next/link";
import { CheckCircle2, Database, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { num } from "@/lib/format";
import type { DatasetCareer, DatasetInfo } from "@/lib/types";

export function useDataset(refreshKey = 0) {
  const [d, setD] = useState<DatasetInfo | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<DatasetInfo>("/api/dataset", ctl.signal).then(setD).catch(() => { /* the page shows its own API error */ });
    return () => ctl.abort();
  }, [refreshKey]);
  return d;
}

function Checks({ c }: { c: DatasetCareer }) {
  return (
    <ul className="mt-2 space-y-1 text-xs">
      {c.checks.map((k) => (
        <li key={k.need} className="flex items-start gap-1.5">
          {k.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--c-profit)]" aria-label="met" /> : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--c-cost)]" aria-label="not met" />}
          <span><span className="text-muted">{k.need}:</span> {k.have}</span>
        </li>
      ))}
    </ul>
  );
}

/** Main dashboard: one imported dataset powers every career, and this says whether it is big enough for each one's exercises. */
export function DatasetCard({ refreshKey }: { refreshKey: number }) {
  const d = useDataset(refreshKey);
  if (!d) return null;
  return (
    <details className="card p-5" aria-label="Your data in every track">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <Database className="h-4 w-4 text-accent" aria-hidden /> Your data in every track
        <span className="rounded-full bg-panel2 px-2 py-0.5 text-xs font-normal normal-case text-muted">
          {num(d.rows)} records · {d.entities} entities · {d.days} days · {d.careers.filter((c) => c.ready).length}/{d.careers.length} careers ready
        </span>
      </summary>
      <p className="mt-3 text-xs text-muted">
        Whatever you import here is the same data every career dashboard, lab and notebook reads. Nothing to copy or re-upload per field.
      </p>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {d.careers.map((c) => (
          <li key={c.id} className="rounded-lg bg-panel2 p-3 text-sm">
            <Link href={`/tracks/${c.id}`} className="font-medium hover:underline">{c.name}</Link>
            <div className="text-xs text-muted">{c.uses}</div>
            <Checks c={c} />
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Compact version for a career's own dashboard. */
export function DatasetStrip({ careerId }: { careerId: string }) {
  const d = useDataset();
  const c = d?.careers.find((x) => x.id === careerId);
  if (!d || !c) return null;
  return (
    <div className="card p-4 text-sm" aria-label="Data used by this dashboard">
      <div className="flex flex-wrap items-center gap-2">
        <Database className="h-4 w-4 text-accent" aria-hidden />
        <strong>Using your imported data</strong>
        <span className="text-xs text-muted">{num(d.rows)} records · {d.entities} entities · {d.date_min} to {d.date_max}</span>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-xs ${c.ready ? "bg-panel2 text-[var(--c-profit)]" : "bg-panel2 text-[var(--c-cost)]"}`}>
          {c.ready ? "Ready for this track" : "Needs more data"}
        </span>
      </div>
      <Checks c={c} />
      <p className="mt-2 text-xs text-muted">Import a different CSV on the <Link href="/" className="underline">main dashboard</Link> and this page updates.</p>
    </div>
  );
}
