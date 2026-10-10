"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Activity, ArrowLeftRight, BarChart3, Building2, BookA, DatabaseBackup, Settings2, Table2, Plug, BrainCircuit, ChevronDown, Compass, Database, FlaskConical, GraduationCap, History, Workflow as Pipe, Network, ShieldCheck, Sparkles, Target, Terminal, Workflow, FileSearch, GitBranch, Gauge, LibraryBig, Map, Shapes, ScrollText, Boxes } from "lucide-react";

const MAIN = [
  { href: "/", label: "Dashboard", Icon: BarChart3 },
  { href: "/company", label: "Company", Icon: Building2 },
  { href: "/data", label: "My data", Icon: Table2 },
  { href: "/kpis", label: "KPIs", Icon: Target },
  { href: "/quality", label: "Data quality", Icon: ShieldCheck },
  { href: "/tracks", label: "Tracks", Icon: Compass },
];
const LABS = [
  { href: "/lab", label: "SQL Lab", Icon: Database },
  { href: "/python", label: "Python", Icon: Terminal },
  { href: "/apache", label: "Apache", Icon: Workflow },
  { href: "/ml", label: "ML Lab", Icon: BrainCircuit },
  { href: "/ai", label: "AI Lab", Icon: Sparkles },
  { href: "/pipeline", label: "Pipeline", Icon: Pipe },
  { href: "/schema", label: "Star schema", Icon: Network },
  { href: "/glossary", label: "Glossary", Icon: BookA },
  { href: "/scd", label: "SCD lab", Icon: History },
  { href: "/quiz", label: "Quiz", Icon: GraduationCap },
  { href: "/hub", label: "Dataset hub", Icon: Boxes },
  { href: "/workflow", label: "Workflow builder", Icon: GitBranch },
  { href: "/diagrams", label: "Diagram studio", Icon: Shapes },
  { href: "/knowledge", label: "Knowledge search", Icon: FileSearch },
  { href: "/toolmap", label: "Tool map", Icon: Map },
];

const MANAGE = [
  { href: "/sources", label: "Sources", Icon: Plug },
  { href: "/compare", label: "Practice vs Real", Icon: ArrowLeftRight },
  { href: "/pipelines", label: "Pipelines", Icon: LibraryBig },
  { href: "/ops", label: "Ops monitor", Icon: Gauge },
  { href: "/logs", label: "Log explorer", Icon: ScrollText },
  { href: "/settings", label: "Settings & backups", Icon: Settings2 },
  { href: "/activity", label: "Activity log", Icon: Activity },
];

function Menu({ label, Icon, items, path }: { label: string; Icon: typeof Database; items: typeof LABS; path: string }) {
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
      <button type="button" className={`btn ${inside ? "btn-primary" : ""}`} aria-expanded={open} aria-haspopup="true"
              onClick={() => setOpenAt(open ? null : path)}>
        <Icon className="h-4 w-4" aria-hidden /> {label} <ChevronDown className="h-3.5 w-3.5" aria-hidden />
      </button>
      {open && (
        <ul className="card absolute right-0 z-20 mt-1 w-52 space-y-0.5 p-1 shadow-lg">
          {items.map(({ href, label: l, Icon: I }) => (
            <li key={href}>
              <Link href={href} aria-current={path === href ? "page" : undefined}
                    className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-sm hover:bg-panel2 ${path === href ? "bg-panel2 font-semibold" : ""}`}>
                <I className="h-4 w-4" aria-hidden /> {l}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NavBar() {
  const path = usePathname();
  const inTracks = path.startsWith("/tracks");

  return (
    <nav aria-label="Primary" className="flex flex-wrap gap-1">
      {MAIN.map(({ href, label, Icon }) => {
        const active = href === "/tracks" ? inTracks : path === href;
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`btn ${active ? "btn-primary" : ""}`}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        );
      })}
      <Menu label="Labs" Icon={FlaskConical} items={LABS} path={path} />
      <Menu label="Manage" Icon={DatabaseBackup} items={MANAGE} path={path} />
    </nav>
  );
}
