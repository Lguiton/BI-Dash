"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";
import { getJson, putJson } from "@/lib/api";
import type { CoOverview } from "@/lib/types";

export default function CompanyPage() {
  const [d, setD] = useState<CoOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [brief, setBrief] = useState({ company: "", goal: "", notes: "" });
  const [saved, setSaved] = useState(false);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<CoOverview>("/api/company", ctl.signal).then((r) => { setD(r); setBrief(r.brief); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the engagement plan.")); });
    return () => ctl.abort();
  }, [ver]);
  const tick = async (id: string, done: boolean) => { try { setD(await putJson<CoOverview>(`/api/company/deliverables/${id}`, { done })); } catch (e) { setErr(errMsg(e, "Couldn't save.")); } };
  const saveBrief = async () => { try { await putJson("/api/company/brief", brief); setSaved(true); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, "Couldn't save the brief.")); } };
  return (
    <PageShell title="Company engagement" subtitle="Hired to do every discipline for one company: the plan, the order, and where each piece gets done.">
      {err && <ErrorBanner message={err} />}
      {!d && !err && <p className="text-sm text-muted">Loading…</p>}
      {d && (
        <>
          <section className="card space-y-3 p-5" aria-label="Progress">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">{d.brief.company || "Your engagement"} · {d.done}/{d.total} deliverables ({d.pct}%) <Badge>{d.workspace}</Badge></h2>
              {d.next && <Link href={d.next.href} className="btn btn-primary">Next up: {d.next.title}</Link>}
            </div>
            <div className="h-2 rounded bg-panel2" role="progressbar" aria-valuenow={d.pct} aria-valuemin={0} aria-valuemax={100} aria-label="Engagement progress"><div className="h-2 rounded bg-accent" style={{ width: `${d.pct}%` }} /></div>
            <p className="text-xs text-muted">{d.note}</p>
          </section>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Disciplines">
            {d.disciplines.map((x) => (
              <Link key={x.id} href={x.href} className="card block space-y-1 p-4 hover:bg-panel2">
                <div className="text-sm font-semibold">{x.name}</div>
                <div className="text-xs text-muted">{x.does}</div>
                <div className="pt-1 text-xs">Deliverables {x.done}/{x.total} · Learning {x.learning_done}/{x.learning_total}</div>
              </Link>
            ))}
          </div>

          <Section title="Engagement brief" note="Per workspace. Practice is your rehearsal; Real is the actual job.">
            <div className="grid gap-2 sm:grid-cols-3">
              <Field label="Company"><input className="field" value={brief.company} onChange={(e) => { setBrief({ ...brief, company: e.target.value }); setSaved(false); }} /></Field>
              <Field label="Goal (one sentence)"><input className="field" value={brief.goal} onChange={(e) => { setBrief({ ...brief, goal: e.target.value }); setSaved(false); }} /></Field>
              <Field label="Notes"><input className="field" value={brief.notes} onChange={(e) => { setBrief({ ...brief, notes: e.target.value }); setSaved(false); }} /></Field>
            </div>
            <button className="btn btn-primary mt-3" onClick={saveBrief}>{saved ? "Saved" : "Save brief"}</button>
          </Section>

          {d.phases.map((p, i) => (
            <section key={p.id} className="card space-y-3 p-5" aria-label={p.name}>
              <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-base font-semibold">{i + 1}. {p.name}</h2><span className="text-xs text-muted">{p.done}/{p.total} done</span></div>
              <p className="text-sm text-muted">{p.about}</p>
              <ul className="space-y-2">
                {p.deliverables.map((x) => {
                  const disc = d.disciplines.find((y) => y.id === x.discipline);
                  return (
                    <li key={x.id} className="flex items-start gap-3 rounded-md border border-line p-3">
                      <input type="checkbox" className="mt-1" checked={x.done} disabled={x.detected} aria-label={`${x.title}${x.detected ? " (detected from your data)" : ""}`} onChange={(e) => tick(x.id, e.target.checked)} />
                      <div className="min-w-0 flex-1 text-sm">
                        <div className="flex flex-wrap items-center gap-2"><Link href={x.href} className="font-medium underline decoration-dotted">{x.title}</Link><Badge>{disc?.name ?? x.discipline}</Badge>{x.detected && <Badge tone="ok">detected</Badge>}</div>
                        <div className="text-xs text-muted">{x.why}{x.detail ? ` · ${x.detail}` : ""}</div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </>
      )}
    </PageShell>
  );
}
