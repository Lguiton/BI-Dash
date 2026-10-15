"use client";
import { PageShell } from "@/components/PageShell";
import { LeadTracker } from "@/components/Leads";

export default function LeadsPage() {
  return (
    <PageShell title="Leads" subtitle="Where each lead came from, what you quoted and whether you won it, so you can see which sources are worth your time.">
      <LeadTracker />
    </PageShell>
  );
}
