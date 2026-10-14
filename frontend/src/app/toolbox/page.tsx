"use client";
import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { HowTo } from "@/components/toolbox/HowTo";
import { legacyFieldHref } from "@/lib/fieldMenu";
import { useMode } from "@/lib/mode";

// This page now holds only the how-to guides (Learn mode). Old toolbox links forward to the field's own dashboard.
function Inner() {
  const p = useSearchParams();
  const router = useRouter();
  const [mode] = useMode();
  const field = legacyFieldHref(p.get("role"), null, p.get("pack"));
  const target = field ?? (mode === "work" ? "/fields" : null);
  useEffect(() => { if (target) router.replace(target); }, [target, router]);
  if (target) return <p className="text-sm text-muted">Opening…</p>;
  return <HowTo openId={p.get("guide") ?? undefined} />;
}

export default function ToolboxPage() {
  return (
    <PageShell title="How-to guides" subtitle="Search how to do or fix anything. Each field's own dashboard has its tools.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense>
    </PageShell>
  );
}
