"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { getJson } from "@/lib/api";
import { ChevronDown, DatabaseBackup, FlaskConical, Briefcase, Home, Activity, ArrowLeftRight, BarChart3, Building2, Settings2, Table2, Plug, BrainCircuit, Compass, Database, Network, ShieldCheck, Target, Terminal, Workflow, FileSearch, GitBranch, Gauge, LibraryBig, Shapes, ScrollText, Boxes, Sigma, Bot, Sparkles } from "lucide-react";

type Item = { href: string; label: string; Icon: typeof Database };
// The top bar holds working tools only. Everything meant for learning lives inside Tracks (see LEARN in app/tracks/page.tsx).
const MAIN: Item[] = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/bi", label: "Dashboard", Icon: BarChart3 },
  { href: "/company", label: "Company", Icon: Building2 },
  { href: "/packs", label: "Business dashboards", Icon: Boxes },
  { href: "/intake", label: "Data Intake", Icon: Workflow },
  { href: "/data", label: "My data", Icon: Table2 },
  { href: "/kpis", label: "KPIs", Icon: Target },
  { href: "/clients", label: "Clients", Icon: Briefcase },
  { href: "/services", label: "Services", Icon: Briefcase },
  { href: "/quality", label: "Data quality", Icon: ShieldCheck },
];
const LABS: Item[] = [
  { href: "/toolbox", label: "Data Toolbox", Icon: Table2 },
  { href: "/lab", label: "SQL Lab", Icon: Database },
  { href: "/analysis", label: "Analysis Lab", Icon: Sigma },
  { href: "/studio", label: "Model Studio", Icon: BrainCircuit },
  { href: "/nlp-dl", label: "NLP & Deep Learning", Icon: BrainCircuit },
  { href: "/design", label: "Systems Design", Icon: Boxes },
  { href: "/workflow", label: "Workflow builder", Icon: GitBranch },
  { href: "/diagrams", label: "Diagram studio", Icon: Shapes },
  { href: "/hub", label: "Dataset hub", Icon: Boxes },
  { href: "/knowledge", label: "Knowledge search", Icon: FileSearch },
];
const MANAGE: Item[] = [
  { href: "/sources", label: "Sources", Icon: Plug },
  { href: "/pipelines", label: "Pipelines", Icon: LibraryBig },
  { href: "/compare", label: "Practice vs Real", Icon: ArrowLeftRight },
  { href: "/ops", label: "Ops monitor", Icon: Gauge },
  { href: "/logs", label: "Log explorer", Icon: ScrollText },
  { href: "/settings", label: "Settings & backups", Icon: Settings2 },
  { href: "/activity", label: "Activity log", Icon: Activity },
];

// The fields you work in. Each opens that field's tools.
const FIELDS: { href: string; label: string; Icon: typeof Database; match: (path: string, role: string | null, f: string | null) => boolean }[] = [
  { href: "/toolbox?role=analyst", label: "Data Analyst", Icon: BarChart3, match: (p, r) => p === "/toolbox" && r === "analyst" },
  { href: "/toolbox?role=bi", label: "BI", Icon: Target, match: (p, r) => p === "/toolbox" && r === "bi" },
  { href: "/toolbox?role=science", label: "Data Science", Icon: BrainCircuit, match: (p, r) => p === "/toolbox" && r === "science" },
  { href: "/toolbox?role=eng", label: "Data Engineering", Icon: Database, match: (p, r) => p === "/toolbox" && r === "eng" },
  { href: "/tracks/security?view=tools", label: "Cybersecurity", Icon: ShieldCheck, match: (p) => p.startsWith("/tracks/security") },
  { href: "/tracks/network?view=tools", label: "Network", Icon: Network, match: (p) => p.startsWith("/tracks/network") },
  { href: "/tracks/itsupport?view=tools", label: "IT repair", Icon: Settings2, match: (p) => p.startsWith("/tracks/itsupport") },
  { href: "/toolbox?role=cpe", label: "Computer engineering", Icon: Terminal, match: (p, r) => (p === "/toolbox" && r === "cpe") || p.startsWith("/tracks/cpe") },
  { href: "/toolbox?role=ai", label: "AI engineering", Icon: Bot, match: (p, r) => (p === "/toolbox" && r === "ai") || p.startsWith("/tracks/ai") },
  { href: "/toolbox?role=ml", label: "ML, NLP and DL", Icon: Sparkles, match: (p, r) => (p === "/toolbox" && r === "ml") || p.startsWith("/tracks/ml") },
  { href: "/toolbox?role=pm", label: "Project management", Icon: Compass, match: (p, r) => (p === "/toolbox" && r === "pm") || p.startsWith("/tracks/pm") },
  { href: "/toolbox?role=fs", label: "Full stack", Icon: GitBranch, match: (p, r) => (p === "/toolbox" && r === "fs") || p.startsWith("/tracks/fullstack") },
  { href: "/toolbox?role=sec", label: "DevSecOps", Icon: ShieldCheck, match: (p, r) => p === "/toolbox" && r === "sec" },
  { href: "/fields?f=health", label: "Health data", Icon: Activity, match: (p, _r, f) => p === "/fields" && (f === "health" || !f) },
  { href: "/fields?f=science", label: "Science and research", Icon: FlaskConical, match: (p, _r, f) => p === "/fields" && f === "science" },
  { href: "/fields?f=cloud", label: "Cloud and design", Icon: Shapes, match: (p, _r, f) => p === "/fields" && f === "cloud" },
];

function Menu({ label, Icon, items, path }: { label: string; Icon: typeof Database; items: Item[]; path: string }) {
  // Remember the path the menu was opened on: navigating elsewhere closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path;
  const box = useRef<HTMLDivElement>(null);
  const inside = items.some((l) => l.href === path);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpenAt(null); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpenAt(null); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <div className="relative" ref={box}>
      <button type="button" className={`btn ${inside ? "btn-primary" : ""}`} aria-expanded={open} aria-haspopup="true" onClick={() => setOpenAt(open ? null : path)}>
        <Icon className="h-4 w-4" aria-hidden /> {label} <ChevronDown className="h-3.5 w-3.5" aria-hidden />
      </button>
      {open && (
        <ul className="card absolute left-0 z-20 mt-1 w-52 space-y-0.5 p-1 shadow-lg">
          {items.map(({ href, label: l, Icon: I }) => (
            <li key={href}>
              <Link href={href} aria-current={path === href ? "page" : undefined} className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-sm hover:bg-panel2 ${path === href ? "bg-panel2 font-semibold" : ""}`}>
                <I className="h-4 w-4" aria-hidden /> {l}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FieldsRow({ path }: { path: string }) {
  const sp = useSearchParams();
  const role = sp.get("role");
  const fld = sp.get("f");
  return (
    <div role="group" aria-label="Fields" className="flex flex-wrap items-center gap-1">
      <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-muted">Fields</span>
      {FIELDS.map(({ href, label, Icon, match }) => {
        const active = match(path, role, fld);
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`btn ${active ? "btn-primary" : ""}`}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        );
      })}
    </div>
  );
}

export function NavBar() {
  const path = usePathname();
  const [cc, setCc] = useState(false);
  useEffect(() => { getJson<{ enabled: boolean }>("/api/system/status").then((s) => setCc(!!s.enabled)).catch(() => setCc(false)); }, []);
  const inTracks = path.startsWith("/tracks") && !FIELDS.some((f) => f.match(path, null, null) && path.startsWith("/tracks/"));

  return (
    <nav aria-label="Primary" className="grid gap-2">
      <Suspense fallback={null}><FieldsRow path={path} /></Suspense>
      <div className="flex flex-wrap gap-1">
        {MAIN.map(({ href, label, Icon }) => (
          <Link key={href} href={href} aria-current={path === href ? "page" : undefined} className={`btn ${path === href ? "btn-primary" : ""}`}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        ))}
        <Menu label="Labs" Icon={FlaskConical} items={LABS} path={path} />
        <Menu label="Manage" Icon={DatabaseBackup} items={cc ? [...MANAGE, { href: "/computer", label: "Computer control", Icon: Terminal }] : MANAGE} path={path} />
        <Link href="/tracks" aria-current={inTracks ? "page" : undefined} className={`btn ${inTracks ? "btn-primary" : ""}`}><Compass className="h-4 w-4" aria-hidden /> Tracks</Link>
      </div>
    </nav>
  );
}
