"use client";
import Link from "next/link";
import { GraduationCap } from "lucide-react";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import type { Progress } from "@/lib/types";

/** Main-dashboard widget: where you are in each career track, and the next step to take. Quietly hides if the API is down. */
export function StudyWidget() {
  const [p, setP] = useState<Progress | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Progress>("/api/progress", ctl.signal).then(setP).catch(() => { /* the dashboard shows its own API error */ });
    return () => ctl.abort();
  }, []);
  if (!p) return null;
  const c = p.continue;
  return (
    <section className="card p-5" aria-label="Study progress">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
          <GraduationCap className="h-4 w-4 text-accent" aria-hidden /> Your study tracks
          <span className="rounded-full bg-panel2 px-2 py-0.5 text-xs font-normal normal-case text-muted">{p.overall_pct}% overall</span>
        </h2>
        {c && (
          <Link href={`/tracks/${c.track}`} className="btn btn-primary text-xs">
            Continue: {c.step.label.length > 40 ? c.step.label.slice(0, 38) + "…" : c.step.label}
          </Link>
        )}
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {p.tracks.map((t) => (
          <li key={t.id}>
            <Link href={`/tracks/${t.id}`} className="block rounded-lg bg-panel2 p-3 text-sm hover:brightness-95">
              <div className="flex items-center justify-between font-medium">{t.name}<span className="text-xs text-muted">{t.done}/{t.total}</span></div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--line)" }} role="progressbar"
                   aria-valuenow={t.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${t.name} progress`}>
                <div className="h-full rounded-full" style={{ width: `${t.pct}%`, background: "var(--accent)" }} />
              </div>
              <div className="mt-1.5 truncate text-xs text-muted">{t.next ? `Next: ${t.next.label}` : "Track complete 🎉"}</div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
