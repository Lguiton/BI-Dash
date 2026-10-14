"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getJson } from "@/lib/api";
import { ALL_FIELDS, FIELD_GROUPS } from "@/lib/fieldMenu";
import { useMode, useMyFields } from "@/lib/mode";
import { ChevronDown, DatabaseBackup, FlaskConical, Briefcase, Home, Activity, ArrowLeftRight, BarChart3, Building2, Settings2, Table2, Plug, BrainCircuit, Compass, Database, ShieldCheck, Target, Terminal, Workflow, FileSearch, GitBranch, Gauge, LibraryBig, Shapes, ScrollText, Boxes, Sigma, Layers, BookOpen, GraduationCap, ClipboardCheck, HelpCircle, Wrench, Receipt } from "lucide-react";

type Icon = typeof Database;
type Item = { href: string; label: string; Icon: Icon };
type Group = { label?: string; items: Item[] };

// Work mode: only what is used to earn money. Learning pages live in Learn mode.
const DATA: Group[] = [{ items: [
  { href: "/data", label: "My data", Icon: Table2 },
  { href: "/intake", label: "Data Intake", Icon: Workflow },
  { href: "/quality", label: "Data quality", Icon: ShieldCheck },
] }];
const DASHBOARDS: Group[] = [{ items: [
  { href: "/bi", label: "Dashboard", Icon: BarChart3 },
  { href: "/packs", label: "Business dashboards", Icon: Boxes },
  { href: "/kpis", label: "KPIs", Icon: Target },
  { href: "/company", label: "Company", Icon: Building2 },
] }];
const MORE: Group[] = [
  { label: "Build and connect", items: [
    { href: "/sources", label: "Sources", Icon: Plug },
    { href: "/pipelines", label: "Pipelines", Icon: LibraryBig },
    { href: "/workflow", label: "Workflow builder", Icon: GitBranch },
    { href: "/hub", label: "Dataset hub", Icon: Layers },
    { href: "/knowledge", label: "Knowledge search", Icon: FileSearch },
  ] },
  { label: "Watch", items: [
    { href: "/ops", label: "Ops monitor", Icon: Gauge },
    { href: "/logs", label: "Log explorer", Icon: ScrollText },
    { href: "/activity", label: "Activity log", Icon: Activity },
  ] },
  { label: "Settings", items: [{ href: "/settings", label: "Settings", Icon: Settings2 }] },
];
// Learn mode: study and practice.
const LABS: Group[] = [
  { label: "Labs", items: [
    { href: "/lab", label: "SQL Lab", Icon: Database },
    { href: "/analysis", label: "Analysis Lab", Icon: Sigma },
    { href: "/studio", label: "Model Studio", Icon: BrainCircuit },
    { href: "/nlp-dl", label: "NLP & Deep Learning", Icon: BrainCircuit },
    { href: "/design", label: "Systems Design", Icon: Boxes },
    { href: "/diagrams", label: "Diagram studio", Icon: Shapes },
    { href: "/compare", label: "Practice vs Real", Icon: ArrowLeftRight },
  ] },
  { label: "Practice", items: [
    { href: "/python", label: "Python practice", Icon: Terminal },
    { href: "/ml", label: "ML practice lab", Icon: FlaskConical },
    { href: "/mlhand", label: "Learn ML by hand", Icon: Sigma },
    { href: "/ai", label: "AI practice lab", Icon: BrainCircuit },
    { href: "/apache", label: "Apache practice", Icon: Wrench },
    { href: "/pipeline", label: "Learn pipelines", Icon: LibraryBig },
    { href: "/scd", label: "Learn history tracking", Icon: Receipt },
    { href: "/schema", label: "Learn star schemas", Icon: Shapes },
    { href: "/toolmap", label: "Tool map", Icon: Compass },
    { href: "/portfolio", label: "Portfolio builder", Icon: Briefcase },
  ] },
];

function Menu({ label, Icon, groups, path, active, footer, wide }: { label: string; Icon: Icon; groups: Group[]; path: string; active?: boolean; footer?: { href: string; label: string }; wide?: boolean }) {
  // Remember the path the menu was opened on: navigating elsewhere closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path;
  const box = useRef<HTMLDivElement>(null);
  const inside = active ?? groups.some((g) => g.items.some((l) => l.href === path));

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
        <div className={`card absolute left-0 z-20 mt-1 max-h-[75vh] overflow-y-auto p-1 shadow-lg ${wide ? "w-64" : "w-56"}`}>
          {groups.map((g, gi) => (
            <div key={g.label ?? gi} role="group" aria-label={g.label ?? label}>
              {g.label && <div className="px-2.5 pb-0.5 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{g.label}</div>}
              <ul className="space-y-0.5">
                {g.items.map(({ href, label: l, Icon: I }) => (
                  <li key={href}>
                    <Link href={href} aria-current={path === href ? "page" : undefined} className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-sm hover:bg-panel2 ${path === href ? "bg-panel2 font-semibold" : ""}`}>
                      <I className="h-4 w-4" aria-hidden /> {l}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {footer && <Link href={footer.href} className="mt-1 block border-t border-line px-2.5 py-2 text-xs underline">{footer.label}</Link>}
        </div>
      )}
    </div>
  );
}

function Plain({ href, label, Icon, active }: Item & { active: boolean }) {
  return (
    <Link href={href} aria-current={active ? "page" : undefined} className={`btn ${active ? "btn-primary" : ""}`}>
      <Icon className="h-4 w-4" aria-hidden /> {label}
    </Link>
  );
}

function FieldsMenu({ path }: { path: string }) {
  const [mine] = useMyFields();
  const keep = (id: string) => mine.length === 0 || mine.includes(id);
  const groups: Group[] = [
    { items: [{ href: "/fields", label: "All fields (main screen)", Icon: Compass }] },
    ...FIELD_GROUPS.map((g) => ({ label: g.label, items: g.items.filter((i) => keep(i.id)).map((i) => ({ href: i.href, label: i.label, Icon: Compass })) })).filter((g) => g.items.length > 0),
  ];
  const active = path === "/fields" || ALL_FIELDS.some((i) => i.match(path));
  return <Menu label={mine.length ? `Fields (${mine.length})` : "Fields"} Icon={Compass} groups={groups} path={path} active={active} wide footer={{ href: "/settings#my-fields", label: mine.length ? "Change my fields" : "Show only my fields…" }} />;
}

export function NavBar() {
  const path = usePathname();
  const [mode] = useMode();
  const [cc, setCc] = useState(false);
  useEffect(() => { getJson<{ enabled: boolean }>("/api/system/status").then((s) => setCc(!!s.enabled)).catch(() => setCc(false)); }, []);
  const inTracks = path.startsWith("/tracks") && !ALL_FIELDS.some((f) => f.match(path) && path.startsWith("/tracks/"));
  const more: Group[] = cc ? [...MORE.slice(0, 2), { label: "Settings", items: [...MORE[2].items, { href: "/computer", label: "Computer control", Icon: Terminal }] }] : MORE;

  return (
    <nav aria-label="Primary" className="grid gap-2">
      <div className="flex flex-wrap gap-1">
        <Plain href="/" label="Home" Icon={Home} active={path === "/"} />
        {mode === "work" ? (
          <>
            <Plain href="/clients" label="Clients" Icon={Briefcase} active={path === "/clients"} />
            <Plain href="/services" label="Services" Icon={Receipt} active={path === "/services"} />
            <Menu label="Data" Icon={Table2} groups={DATA} path={path} />
            <Menu label="Dashboards" Icon={BarChart3} groups={DASHBOARDS} path={path} />
            <FieldsMenu path={path} />
            <Menu label="More" Icon={DatabaseBackup} groups={more} path={path} />
          </>
        ) : (
          <>
            <Plain href="/tracks" label="Tracks" Icon={Compass} active={inTracks || path === "/tracks"} />
            <Plain href="/quiz" label="Quiz" Icon={HelpCircle} active={path === "/quiz"} />
            <Plain href="/review" label="Review" Icon={ClipboardCheck} active={path === "/review"} />
            <Plain href="/glossary" label="Glossary" Icon={BookOpen} active={path === "/glossary"} />
            <Menu label="Labs and practice" Icon={FlaskConical} groups={LABS} path={path} />
            <FieldsMenu path={path} />
            <Plain href="/toolbox?role=howto" label="How-to guides" Icon={GraduationCap} active={false} />
          </>
        )}
      </div>
    </nav>
  );
}
