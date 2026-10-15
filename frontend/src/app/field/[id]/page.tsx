"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { Badge } from "@/components/panels/kit";
import { getJson } from "@/lib/api";
import { fieldById, FIELD_GROUPS } from "@/lib/fieldMenu";
import { FieldFix } from "@/components/toolbox/FieldFix";
import { AiTools } from "@/components/toolbox/AiTools";
import { AnalystTools } from "@/components/toolbox/AnalystTools";
import { BiTools } from "@/components/toolbox/BiTools";
import { CpeTools } from "@/components/toolbox/CpeTools";
import { EngTools } from "@/components/toolbox/EngTools";
import { FsTools } from "@/components/toolbox/FsTools";
import { MlTools } from "@/components/toolbox/MlTools";
import { WithPacks } from "@/components/toolbox/PackTools";
import { PmTools } from "@/components/toolbox/PmTools";
import { ScienceTools } from "@/components/toolbox/ScienceTools";

type Svc = { id: string; group: string; name: string; low: number; high: number; model: string; rate: number };
const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

function Body({ id, pack }: { id: string; pack?: string }) {
  const P = (core: React.ReactNode, packs: { id: string; label: string }[]) => <WithPacks key={pack ?? "core"} core={core} packs={packs} initial={pack} />;
  switch (id) {
    case "analyst": return <AnalystTools />;
    case "bi": return P(<BiTools />, [{ id: "revops", label: "Revenue operations" }]);
    case "science": return <ScienceTools />;
    case "eng": return <EngTools />;
    case "cpe": return <CpeTools />;
    case "ai": return <AiTools />;
    case "ml": return P(<MlTools />, [{ id: "cv", label: "Computer vision" }]);
    case "pm": return P(<PmTools />, [{ id: "itpm", label: "IT project management" }]);
    case "consulting": return P(null, [{ id: "biz", label: "Business consulting" }]);
    case "devsecops": return P(null, [{ id: "devsecops", label: "DevSecOps" }, { id: "revsec", label: "Revenue-system security" }]);
    case "fs": return P(<FsTools />, [{ id: "devops", label: "DevOps" }]);
    case "cloud": return P(null, [{ id: "cloud", label: "Cloud architecture" }]);
    case "health": return P(null, [{ id: "cds", label: "Clinical data science" }, { id: "hana", label: "Health analytics" }, { id: "hbi", label: "Health BI" }, { id: "hinf", label: "Health informatics" }]);
    case "research": return P(null, [{ id: "stat", label: "Statistics" }, { id: "gen", label: "Genomic data science" }, { id: "sci", label: "Science and research" }]);
    case "marketing": return P(null, [{ id: "mkt", label: "Digital marketing" }, { id: "ux", label: "UI/UX and graphic design" }]);
    default: return null;
  }
}

function Sell({ groups }: { groups: string[] }) {
  const [svcs, setSvcs] = useState<Svc[] | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ services: Svc[] }>("/api/service-list").then((r) => { if (live) setSvcs(r.services.filter((s) => groups.includes(s.group))); }).catch(() => { if (live) setSvcs([]); });
    return () => { live = false; };
  }, [groups]);
  if (!svcs || svcs.length === 0) return null;
  return (
    <section className="card space-y-2 p-4" aria-label="Services you can sell here">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-semibold">Services you can sell in this field</h2><Link href="/settings?tab=quotes" className="text-xs underline">Quotes and prices</Link></div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {svcs.slice(0, 6).map((s) => (
          <li key={s.id} className="rounded border border-line p-2 text-sm"><div className="font-medium">{s.name}</div><div className="text-xs text-muted">{usd(s.low)} to {usd(s.high)}{s.model === "monthly" ? " / month" : ""} at {usd(s.rate)}/hour</div></li>
        ))}
      </ul>
      {svcs.length > 6 && <p className="text-xs text-muted">{svcs.length - 6} more in Services.</p>}
    </section>
  );
}

function Inner() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const field = fieldById(id);
  const group = FIELD_GROUPS.find((g) => g.items.some((i) => i.id === id));
  const trackHref = field && field.href.startsWith("/tracks/") ? field.href : null;
  useEffect(() => { if (trackHref) router.replace(trackHref); }, [trackHref, router]);
  if (!field) return <p className="text-sm">There is no field called &ldquo;{id}&rdquo;. <Link href="/fields" className="underline">Back to all fields</Link>.</p>;
  if (trackHref) return <p className="text-sm text-muted">Opening {field.label}…</p>;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link href="/fields" className="btn">All fields</Link>
        {group && <Badge>{group.label}</Badge>}
        <span className="text-muted">{field.blurb}</span>
      </div>
      <FieldFix key={id} field={id} />
      <Sell groups={field.services} />
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Tools</h2>
      <Body id={id} pack={sp.get("pack") ?? undefined} />
    </div>
  );
}

function Title() {
  const { id } = useParams<{ id: string }>();
  const f = fieldById(id);
  return <PageShell title={f ? f.label : "Field"} subtitle={f ? "Your own dashboard for this field: what you can sell, and its tools." : "That field was not found."}><Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense></PageShell>;
}

export default function FieldPage() {
  return <Suspense fallback={null}><Title /></Suspense>;
}
