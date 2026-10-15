"use client";
import { PageShell } from "@/components/PageShell";
import { ChecklistLibrary } from "@/components/Checklists";

export default function ChecklistsPage() {
  return (
    <PageShell title="Triage checklists" subtitle="Step-by-step lists for a slow database, a messy network rack and a huge data file. Print one, or tick it off on a job.">
      <ChecklistLibrary />
    </PageShell>
  );
}
