"use client";
import Link from "next/link";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { WorkRoom } from "@/components/WorkRoom";
import { StartBox } from "@/components/StartBox";
import { useActiveJob } from "@/lib/activeJob";

function Inner() {
  const sp = useSearchParams();
  const router = useRouter();
  const [, setActive] = useActiveJob();
  const id = Number(sp.get("id"));
  const started = (n: number) => { setActive(n); router.push(`/workroom?id=${n}`); };
  if (!id) return (
    <div className="space-y-4">
      <StartBox onStarted={started} />
      <p className="text-sm">Already have a job? <Link href="/clients" className="underline">Pick it from Clients</Link> and choose Work Room.</p>
    </div>
  );
  return (
    <div className="space-y-4">
      <WorkRoom key={id} jobId={id} />
      <details className="text-sm"><summary className="cursor-pointer underline">Start another job</summary><div className="mt-2"><StartBox onStarted={started} /></div></details>
    </div>
  );
}

export default function WorkRoomPage() {
  return (
    <PageShell title="Work Room" subtitle="Your checklist on one side, the agents' finished work on the other. They do the work, you verify and tick.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense>
    </PageShell>
  );
}
