"use client";
import { CheckCircle2, Circle, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

interface Item { id: string; title: string; done: boolean; href: string; detail: string }
interface Status { workspace: string; items: Item[]; done: number; total: number; complete: boolean }

const KEY = "bi_setup_hidden";

/** First-run checklist. Each tick is computed from what really exists in this workspace, never stored as a manual tick. */
export function SetupChecklist({ refreshKey = 0 }: { refreshKey?: number }) {
  const [s, setS] = useState<Status | null>(null);
  const [hidden, setHidden] = useState(true);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading the saved choice once on mount is intentional
    try { setHidden(localStorage.getItem(KEY) === "1"); } catch { setHidden(false); }
  }, []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Status>("/api/setup", ctl.signal).then(setS).catch(() => { /* optional card */ });
    return () => ctl.abort();
  }, [refreshKey]);
  if (!s || s.complete || hidden) return null;
  return (
    <section className="card p-4" aria-label="Getting started">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide">Getting started · {s.done} of {s.total} done</h2>
        <button className="btn !px-2 !py-1 text-xs" onClick={() => { setHidden(true); try { localStorage.setItem(KEY, "1"); } catch { /* fine */ } }} aria-label="Hide the checklist">
          <X className="h-3.5 w-3.5" aria-hidden /> Hide
        </button>
      </div>
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-panel2" role="progressbar" aria-valuenow={s.done} aria-valuemin={0} aria-valuemax={s.total}>
        <div className="h-full bg-[var(--accent)]" style={{ width: `${(s.done / s.total) * 100}%` }} />
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {s.items.map((i) => (
          <li key={i.id}>
            <Link href={i.href} className="flex items-start gap-2 rounded-md p-2 text-sm hover:bg-panel2">
              {i.done ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-label="done" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-label="not done" />}
              <span className="min-w-0"><span className={`block font-medium ${i.done ? "text-muted line-through" : ""}`}>{i.title}</span><span className="block truncate text-xs text-muted">{i.detail}</span></span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
