"use client";
import Link from "next/link";
import { PageShell } from "@/components/PageShell";
import { LogsTab } from "@/components/panels/SecPanel";

export default function LogsPage() {
  return (
    <PageShell title="Log explorer" subtitle="Paste or upload a log file, search it, and see what the detection rules found. A small take on Splunk or Kibana for one file at a time.">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Reads one file you give it and stores nothing. Not a log indexer: it can&apos;t follow live logs or search months of data. For the full security workflow see the <Link className="underline" href="/tracks/security?view=tools">Cybersecurity track</Link>; systems analysts can use it to trace a bottleneck or error burst.</p>
      <LogsTab />
    </PageShell>
  );
}
