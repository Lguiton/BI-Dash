"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

type Today = {
  followups: { id: number }[];
  overdue_invoices: { id: number }[];
  jobs_due: { id: number; title: string; late: boolean }[];
  work_due: { id: number }[];
  ready_to_close: { id: number; title: string }[];
  timer: { id: number; title: string; warn: boolean } | null;
};

/** One line at the top of Home: what needs you first, one click each. Reads only; changes nothing. */
export function TodayStrip() {
  const [t, setT] = useState<Today | null>(null);
  useEffect(() => {
    let live = true;
    getJson<Today>("/api/auto/today").then((r) => { if (live) setT(r); }).catch(() => {});
    return () => { live = false; };
  }, []);
  if (!t) return null;
  const next = t.jobs_due[0];
  const chips: { key: string; href: string; text: string; tone: string }[] = [];
  if (next) chips.push({ key: "next", href: `/job?id=${next.id}`, text: `${next.late ? "Late" : "Next"}: ${next.title}`, tone: next.late ? "text-red-600" : "" });
  if (t.overdue_invoices.length) chips.push({ key: "inv", href: "/clients", text: `${t.overdue_invoices.length} unpaid late`, tone: "text-red-600" });
  if (t.followups.length) chips.push({ key: "fu", href: "/clients", text: `${t.followups.length} follow-up${t.followups.length === 1 ? "" : "s"}`, tone: "" });
  if (t.work_due.length) chips.push({ key: "wd", href: "/#work-log", text: `${t.work_due.length} step${t.work_due.length === 1 ? "" : "s"} due`, tone: "" });
  if (t.ready_to_close.length) chips.push({ key: "rc", href: `/job?id=${t.ready_to_close[0].id}`, text: `${t.ready_to_close.length} ready to close`, tone: "text-green-700" });
  if (t.timer) chips.push({ key: "tm", href: `/job?id=${t.timer.id}`, text: `Timer: ${t.timer.title}`, tone: t.timer.warn ? "text-amber-600" : "" });
  return (
    <nav aria-label="Today at a glance" className="card flex flex-wrap items-center gap-2 p-2 text-sm">
      <span className="px-1 text-xs font-semibold text-muted">Today</span>
      {chips.length === 0 && <span className="text-muted">Nothing is late and nothing needs you right now.</span>}
      {chips.map((c) => <Link key={c.key} href={c.href} className={`rounded border border-line px-2 py-0.5 hover:bg-panel2 ${c.tone}`}>{c.text}</Link>)}
    </nav>
  );
}
