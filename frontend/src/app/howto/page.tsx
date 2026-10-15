"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { HowToLibrary } from "@/components/HowTo";

function Body() {
  const sp = useSearchParams();
  const v = Number(sp.get("v"));
  return <HowToLibrary initialId={Number.isInteger(v) && v > 0 ? v : null} />;
}

export default function HowToPage() {
  return (
    <PageShell title="How-to videos" subtitle="Links to videos that show a job being done, sorted by field. A link opens in a new tab; nothing is downloaded.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Body /></Suspense>
    </PageShell>
  );
}
