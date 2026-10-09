"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BarChart3, BrainCircuit, ChevronDown, Compass, Database, FlaskConical, GraduationCap, History, Network, ShieldCheck, Sparkles, Target, Terminal, Workflow } from "lucide-react";

const MAIN = [
  { href: "/", label: "Dashboard", Icon: BarChart3 },
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
  { href: "/schema", label: "Star schema", Icon: Network },
  { href: "/scd", label: "SCD lab", Icon: History },
  { href: "/quiz", label: "Quiz", Icon: GraduationCap },
];

export function NavBar() {
  const path = usePathname();
  // Remember the path the menu was opened on: navigating elsewhere closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path;
  const box = useRef<HTMLDivElement>(null);
  const inLabs = LABS.some((l) => l.href === path);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpenAt(null); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpenAt(null); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <nav aria-label="Primary" className="flex flex-wrap gap-1">
      {MAIN.map(({ href, label, Icon }) => {
        const active = path === href;
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`btn ${active ? "btn-primary" : ""}`}>
            <Icon className="h-4 w-4" aria-hidden /> {label}
          </Link>
        );
      })}
      <div className="relative" ref={box}>
        <button type="button" className={`btn ${inLabs ? "btn-primary" : ""}`} aria-expanded={open} aria-haspopup="true"
                onClick={() => setOpenAt(open ? null : path)}>
          <FlaskConical className="h-4 w-4" aria-hidden /> Labs <ChevronDown className="h-3.5 w-3.5" aria-hidden />
        </button>
        {open && (
          <ul className="card absolute right-0 z-20 mt-1 w-48 space-y-0.5 p-1 shadow-lg">
            {LABS.map(({ href, label, Icon }) => (
              <li key={href}>
                <Link href={href} aria-current={path === href ? "page" : undefined}
                      className={`flex items-center gap-2 rounded-md px-2.5 py-2 text-sm hover:bg-panel2 ${path === href ? "bg-panel2 font-semibold" : ""}`}>
                  <Icon className="h-4 w-4" aria-hidden /> {label}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </nav>
  );
}
