"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PwaSetup } from "@/components/PwaSetup";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";

type Pack = { id: string; industry: string; dept: string; title: string; rows: number | null };
type Briefing = { subject: string; items: number; sections: { title: string; items: string[] }[] };
type Health = { score: number; grade: string; needs_attention: { name: string; detail: string }[] };

const PLACES = [
  { href: "/bi", label: "Main dashboard", note: "Your uploaded data: trend, entities, insights" },
  { href: "/packs", label: "Business dashboards", note: "Industry and department views, reports, imports" },
  { href: "/company", label: "Company", note: "Plan, goals and company health" },
  { href: "/kpis", label: "KPIs", note: "Targets and how you are doing" },
  { href: "/tracks", label: "Tracks", note: "Analyst, data science, IT, engineering tools" },
  { href: "/services", label: "Services", note: "What you can sell, with a quote builder" },
  { href: "/intake", label: "Data Intake", note: "Upload a file; the agents process it end to end" },
  { href: "/data", label: "My data", note: "Tables, charts and imports" },
];

export default function HomePage() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [pick, setPick] = useState("");
  const [brief, setBrief] = useState<Briefing | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const m = (e: unknown) => (e instanceof ApiError ? e.message : "Couldn't load part of the home screen.");
    getJson<{ packs: Pack[] }>("/api/biz-packs").then((r) => setPacks(r.packs)).catch((e) => setErr(m(e)));
    getJson<Briefing>("/api/briefing/preview").then(setBrief).catch(() => setBrief(null));
    getJson<Health>("/api/health-check").then(setHealth).catch(() => setHealth(null));
  }, []);

  const industries = [...new Set(packs.map((p) => p.industry))];
  return (
    <PageShell title="Home" subtitle="Everything in one place: today's briefing, your system health and a shortcut to any dashboard.">
      {err && <ErrorBanner message={err} />}
      <section className="card space-y-2 p-4" aria-label="Dashboards">
        <h2 className="text-sm font-semibold">Dashboards</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input min-w-72" aria-label="Choose a dashboard" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Choose a dashboard…</option>
            <optgroup label="Main"><option value="/bi">Main dashboard (your uploaded data)</option><option value="/company">Company</option><option value="/kpis">KPIs</option></optgroup>
            {industries.map((i) => (
              <optgroup key={i} label={i}>{packs.filter((p) => p.industry === i).map((p) => <option key={p.id} value={`/packs?pid=${p.id}`}>{p.dept}: {p.title}{p.rows == null ? " (no data yet)" : ""}</option>)}</optgroup>
            ))}
          </select>
          <Link href={pick || "#"} aria-disabled={!pick} className={`btn btn-primary ${pick ? "" : "pointer-events-none opacity-50"}`}>Open</Link>
        </div>
      </section>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="card space-y-2 p-4" aria-label="Today's briefing">
          <h2 className="text-sm font-semibold">Today&apos;s briefing</h2>
          {!brief && <p className="text-sm text-muted">Loading…</p>}
          {brief && brief.items === 0 && <p className="text-sm">Nothing needs attention today.</p>}
          {brief?.sections.map((s) => (
            <div key={s.title}><h3 className="text-xs font-semibold uppercase text-muted">{s.title}</h3><ul className="list-disc pl-5 text-sm">{s.items.map((i) => <li key={i}>{i}</li>)}</ul></div>
          ))}
          <Link href="/settings" className="text-xs underline">Briefing settings</Link>
        </section>
        <section className="card space-y-2 p-4" aria-label="System health">
          <h2 className="text-sm font-semibold">System health</h2>
          {health ? (<>
            <p className="text-2xl font-bold">{health.score}<span className="text-sm font-normal text-muted"> / 100 · {health.grade}</span></p>
            {health.needs_attention.length === 0 ? <p className="text-sm">Everything checks out.</p> : <ul className="list-disc pl-5 text-sm">{health.needs_attention.map((n) => <li key={n.name}><strong>{n.name}.</strong> {n.detail}</li>)}</ul>}
          </>) : <p className="text-sm text-muted">Loading…</p>}
          <Link href="/activity" className="text-xs underline">Open the activity log</Link>
        </section>
      </div>
      <div><PwaSetup showButton /></div>
      <section aria-label="Places" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {PLACES.map((p) => <Link key={p.href} href={p.href} className="card p-4 hover:bg-panel2"><div className="font-semibold">{p.label}</div><div className="text-xs text-muted">{p.note}</div></Link>)}
      </section>
    </PageShell>
  );
}
