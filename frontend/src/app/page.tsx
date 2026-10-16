"use client";
import { ClientMessages } from "@/components/ClientMessages";
import { PasteIntake } from "@/components/PasteIntake";
import { TodayStrip } from "@/components/TodayStrip";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { WorkLog } from "@/components/WorkLog";
import { TodayPanel } from "@/components/TodayPanel";
import { MoreToday } from "@/components/MoreToday";
import { AssistantDesk } from "@/components/AssistantDesk";
import { PwaSetup } from "@/components/PwaSetup";
import { PageShell } from "@/components/PageShell";
import { useRouter } from "next/navigation";
import { ApiError, getJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";
import { useMode } from "@/lib/mode";

type Pack = { id: string; industry: string; dept: string; title: string; rows: number | null };
type Briefing = { subject: string; items: number; sections: { title: string; items: string[] }[] };
type Health = { score: number; grade: string; needs_attention: { name: string; detail: string }[] };
type Fu = { id: number; due: string; note: string; client?: string };
type Over = { sample: boolean; clients: number; jobs_active: number; pipeline: number; outstanding: number; overdue: { id: number; number: string; client: string; total: number; days_late: number }[]; paid_this_month: number; unbilled_hours: number; unbilled_amount: number; followups_due: Fu[] };
type OpenJob = { id: number; title: string; status: string; client: string; client_id: number; quote: number; hours: number; due: string | null; late: boolean; field: { key: string; label: string; href: string } | null };

const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;
const QUICK = [
  { href: "/clients", label: "New client", note: "Add a client, a job or an invoice" },
  { href: "/intake", label: "Import data", note: "Drop in a file; it is cleaned and checked" },
  { href: "/packs", label: "Make a dashboard", note: "Industry and department views" },
  { href: "/settings?tab=quotes", label: "Quote a job", note: "Quote builder and price list, by field" },
  { href: "/money", label: "Money", note: "Who owes you, profit per job, expenses and tax set-aside" },
  { href: "/leads", label: "Leads", note: "Where leads come from and which ones you won" },
];
const STUDY = [
  { href: "/tracks", label: "Tracks", note: "Career paths with a learning path each" },
  { href: "/quiz", label: "Practice quiz", note: "Test what you know" },
  { href: "/review", label: "Spaced review", note: "Come back to what you missed" },
  { href: "/glossary", label: "Data glossary", note: "Plain-English definitions" },
  { href: "/lab", label: "SQL Lab", note: "Practice queries" },
  { href: "/analysis", label: "Analysis Lab", note: "Statistics and forecasting practice" },
  { href: "/studio", label: "Model Studio", note: "Build and test models" },
  { href: "/nlp-dl", label: "NLP & Deep Learning", note: "Hands-on text and neural nets" },
  { href: "/design", label: "Systems Design", note: "Design practice" },
  { href: "/toolbox?role=howto", label: "How-to guides", note: "Search how to do or fix anything" },
];

export default function HomePage() {
  const [mode] = useMode();
  return (
    <PageShell title="Home" subtitle={mode === "work" ? "Today's work: jobs, follow-ups, money and quick starts." : "Learn mode: study, practice and how-to guides."}>
      {mode === "work" ? <WorkHome /> : <LearnHome />}
    </PageShell>
  );
}

function LearnHome() {
  return (
    <>
      <section aria-label="Study" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {STUDY.map((p) => <Link key={p.href} href={p.href} className="card p-4 hover:bg-panel2"><div className="font-semibold">{p.label}</div><div className="text-xs text-muted">{p.note}</div></Link>)}
      </section>
      <p className="text-xs text-muted">Switch back to Work mode with the button in the top corner when you are ready for clients.</p>
    </>
  );
}

function WorkHome() {
  const [packs, setPacks] = useState<Pack[]>([]);
  const [pick, setPick] = useState("");
  const [brief, setBrief] = useState<Briefing | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [ov, setOv] = useState<Over | null>(null);
  const [jobs, setJobs] = useState<OpenJob[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const router = useRouter();
  const [activeId, setActive] = useActiveJob();

  useEffect(() => {
    const m = (e: unknown) => (e instanceof ApiError ? e.message : "Couldn't load part of the home screen.");
    getJson<{ packs: Pack[] }>("/api/biz-packs").then((r) => setPacks(r.packs)).catch((e) => setErr(m(e)));
    getJson<Briefing>("/api/briefing/preview").then(setBrief).catch(() => setBrief(null));
    getJson<Health>("/api/health-check").then(setHealth).catch(() => setHealth(null));
    getJson<Over>("/api/clients/overview").then(setOv).catch(() => setOv(null));
    getJson<{ jobs: OpenJob[] }>("/api/clients/open-jobs").then((r) => setJobs(r.jobs)).catch(() => setJobs([]));
  }, []);

  const industries = [...new Set(packs.map((p) => p.industry))];
  return (
    <>
      {err && <ErrorBanner message={err} />}
      <TodayStrip />
      <PasteIntake />
      <ClientMessages />
      <section aria-label="Quick starts" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {QUICK.map((p) => <Link key={p.href} href={p.href} className="card p-4 hover:bg-panel2"><div className="font-semibold">{p.label}</div><div className="text-xs text-muted">{p.note}</div></Link>)}
      </section>

      <AssistantDesk />

      <WorkLog />

      <div className="grid gap-4 md:grid-cols-2">
        <TodayPanel footer={ov ? `${usd(ov.outstanding)} outstanding · ${usd(ov.paid_this_month)} paid this month · ${usd(ov.unbilled_amount)} unbilled (${ov.unbilled_hours} h) · ${usd(ov.pipeline)} in quotes` : undefined} />
        <section className="card space-y-2 p-4" aria-label="Open jobs">
          <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Open jobs{ov ? ` (${jobs?.length ?? 0})` : ""}</h2><Link href="/clients" className="text-xs underline">All clients</Link></div>
          {jobs === null && <p className="text-sm text-muted">Loading…</p>}
          {jobs?.length === 0 && <p className="text-sm">No open jobs. <Link href="/clients" className="underline">Add a client and a job</Link>, or <Link href="/settings?tab=quotes" className="underline">quote one</Link>.</p>}
          <ul className="space-y-1 text-sm">
            {jobs?.slice(0, 8).map((j) => (
              <li key={j.id} className="flex flex-wrap items-center justify-between gap-2">
                <span><Link href={`/job?id=${j.id}`} className="underline"><strong>{j.title}</strong></Link> <span className="text-muted">for {j.client}</span>{j.field && <span className="ml-2 rounded-full bg-panel2 px-2 py-0.5 text-xs text-muted">{j.field.label}</span>}</span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-muted">{j.status}{j.due ? ` · due ${j.due}` : ""}{j.late ? " · late" : ""}{j.quote ? ` · ${usd(j.quote)}` : ""}</span>
                  {activeId === j.id ? <span className="text-xs font-medium text-emerald-600">pinned</span> : <button className="btn" aria-label={`Work on ${j.title}`} onClick={() => { setActive(j.id); router.push(j.field ? j.field.href : `/job?id=${j.id}`); }}>Work on it</button>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <MoreToday />

      <section className="card space-y-2 p-4" aria-label="Dashboards">
        <h2 className="text-sm font-semibold">Open a dashboard</h2>
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
    </>
  );
}
