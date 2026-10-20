"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { WorkTeam } from "@/components/WorkTeam";
import { WorkRoom } from "@/components/WorkRoom";
import { StartBox } from "@/components/StartBox";
import { getJson } from "@/lib/api";
import { useActiveJob } from "@/lib/activeJob";

type OpenJob = { id: number; title: string; client: string; field: { key: string; name?: string } | null };

/** "Agents do the job" for a real dashboard: pick an open job, then the field's agent (or the three-AI team) drafts the work. Drafts only: nothing is sent, closed or marked done. */
export function JobAgentCard({ track }: { track: string }) {
  const [active, setActive] = useActiveJob();
  const [jobs, setJobs] = useState<OpenJob[] | null>(null);
  const [sample, setSample] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<{ jobs: OpenJob[]; sample?: boolean }>("/api/clients/open-jobs").then((r) => { if (live) { setJobs(r.jobs); setSample(!!r.sample); } }).catch(() => { if (live) setJobs([]); });
    return () => { live = false; };
  }, []);
  const mine = (jobs ?? []).filter((j) => j.field?.key === track);
  const rest = (jobs ?? []).filter((j) => j.field?.key !== track);
  const current = (jobs ?? []).find((j) => j.id === active) ?? null;
  return (
    <section className="card space-y-3 p-4" aria-label="Agents do the job">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Agents do the job</h2>
        <span className="text-xs text-muted">Paste an issue or pick a job. The agents do the steps while you work your checklist. Nothing is sent to a client.</span>
      </div>
      <StartBox onStarted={(id) => { setActive(id); setJobs(null); getJson<{ jobs: OpenJob[] }>("/api/clients/open-jobs").then((r) => setJobs(r.jobs)).catch(() => setJobs([])); }} />
      {jobs === null && <p className="text-sm text-muted">Loading jobs…</p>}
      {jobs !== null && jobs.length === 0 && (
        <p className="text-sm">No open jobs yet. <Link href="/intake" className="underline">Paste a client request to start one</Link>, or use Start job on <Link href="/" className="underline">Home</Link>.</p>
      )}
      {jobs !== null && jobs.length > 0 && (
        <label className="block text-xs">Job
          <select className="input mt-1 w-full" value={current ? String(current.id) : ""} onChange={(e) => setActive(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Choose a job…</option>
            {mine.length > 0 && <optgroup label="This field">{mine.map((j) => <option key={j.id} value={j.id}>{j.client}: {j.title}</option>)}</optgroup>}
            {rest.length > 0 && <optgroup label={mine.length ? "Other fields" : "Open jobs"}>{rest.map((j) => <option key={j.id} value={j.id}>{j.client}: {j.title}</option>)}</optgroup>}
          </select>
        </label>
      )}
      {sample && <p className="text-xs text-muted">Practice workspace: nothing here is real.</p>}
      {current && (
        <div className="space-y-3">
          <WorkRoom key={`wr${current.id}`} jobId={current.id} />
          <WorkTeam key={`jt${current.id}`} jobId={current.id} advice={["itsupport", "network", "security"].includes(track)} />
          <p className="text-xs"><Link href={`/job?id=${current.id}`} className="underline">Open the full job page</Link> for steps, timer and closing.</p>
        </div>
      )}
    </section>
  );
}
