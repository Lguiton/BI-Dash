"use client";
import Link from "next/link";
import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { PageShell } from "@/components/PageShell";
import { FIELD_GROUPS, legacyFieldHref } from "@/lib/fieldMenu";
import { useMyFields } from "@/lib/mode";

function Hub() {
  const sp = useSearchParams();
  const router = useRouter();
  const [mine] = useMyFields();
  const old = legacyFieldHref(null, sp.get("f"), sp.get("pack"));
  useEffect(() => { if (old) router.replace(old); }, [old, router]);
  if (old) return <p className="text-sm text-muted">Opening…</p>;
  const groups = FIELD_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => mine.length === 0 || mine.includes(i.id)) })).filter((g) => g.items.length > 0);
  return (
    <div className="grid gap-6">
      <p className="text-sm text-muted">Pick a field to open its own dashboard. {mine.length ? `Showing the ${mine.length} you chose.` : "Showing every field."} <Link href="/settings#my-fields" className="underline">{mine.length ? "Change my fields" : "Show only my fields"}</Link></p>
      {groups.map((g) => (
        <section key={g.id} aria-label={g.label} className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {g.items.map((i) => (
              <Link key={i.id} href={i.href} className="card group flex flex-col gap-1 p-4 hover:bg-panel2" aria-label={`Open ${i.label}`}>
                <span className="flex items-center justify-between font-semibold">{i.label}<ArrowRight className="h-4 w-4 opacity-60 group-hover:opacity-100" aria-hidden /></span>
                <span className="text-xs text-muted">{i.blurb}</span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export default function FieldsPage() {
  return (
    <PageShell title="Fields" subtitle="Each field has its own dashboard with the tools and services for that kind of work.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Hub /></Suspense>
    </PageShell>
  );
}
