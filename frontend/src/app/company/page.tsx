"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";
import { getJson, postJson, putJson } from "@/lib/api";
import { downloadFile } from "@/lib/download";
import type { CoOverview, CoSnapshot } from "@/lib/types";

export default function CompanyPage() {
  const [d, setD] = useState<CoOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [brief, setBrief] = useState({ company: "", goal: "", notes: "" });
  const [saved, setSaved] = useState(false);
  const [ver, setVer] = useState(0);
  const [snaps, setSnaps] = useState<CoSnapshot[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const [draft, setDraft] = useState({ note: "", due: "" });
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ snapshots: CoSnapshot[] }>("/api/company/snapshots", ctl.signal).then((r) => setSnaps(r.snapshots)).catch(() => { /* snapshots are optional */ });
    return () => ctl.abort();
  }, [ver]);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<CoOverview>("/api/company", ctl.signal).then((r) => { setD(r); setBrief(r.brief); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the engagement plan.")); });
    return () => ctl.abort();
  }, [ver]);
  const tick = async (id: string, done: boolean) => { try { setD(await putJson<CoOverview>(`/api/company/deliverables/${id}`, { done })); } catch (e) { setErr(errMsg(e, "Couldn't save.")); } };
  const saveBrief = async () => { try { await putJson("/api/company/brief", brief); setSaved(true); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, "Couldn't save the brief.")); } };
  const saveMeta = async (id: string) => { try { setD(await putJson<CoOverview>(`/api/company/deliverables/${id}/meta`, draft)); setEdit(null); } catch (e) { setErr(errMsg(e, "Couldn't save the note.")); } };
  const snap = async (ai: boolean) => {
    setBusy(ai ? "ai" : "snap"); setErr(null);
    try { await postJson(ai ? "/api/company/snapshots/ai-brief" : "/api/company/snapshots", {}); setVer((v) => v + 1); }
    catch (e) { setErr(errMsg(e, "Couldn't take the snapshot.")); }
    finally { setBusy(null); }
  };
  const exportAs = async (f: "xlsx" | "pdf") => { setBusy(f); setErr(null); try { await downloadFile(`/api/company/export?format=${f}`, `company_plan.${f}`); } catch (e) { setErr(errMsg(e, "Export failed.")); } finally { setBusy(null); } };
  return (
    <PageShell title="Company engagement" subtitle="Hired to do every discipline for one company: the plan, the order, and where each piece gets done.">
      {err && <ErrorBanner message={err} />}
      {!d && !err && <p className="text-sm text-muted">Loading…</p>}
      {d && (
        <>
          <section className="card space-y-3 p-5" aria-label="Progress">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">{d.brief.company || "Your engagement"} · {d.done}/{d.total} deliverables ({d.pct}%) <Badge>{d.workspace}</Badge>{d.overdue > 0 && <> <Badge tone="bad">{d.overdue} overdue</Badge></>}{d.due_soon > 0 && <> <Badge tone="warn">{d.due_soon} due this week</Badge></>}</h2>
              <div className="flex flex-wrap gap-2">
                <button className="btn text-xs" disabled={busy !== null} onClick={() => exportAs("xlsx")}>{busy === "xlsx" ? "Building…" : "Export Excel"}</button>
                <button className="btn text-xs" disabled={busy !== null} onClick={() => exportAs("pdf")}>{busy === "pdf" ? "Building…" : "Export PDF"}</button>
                {d.next && <Link href={d.next.href} className="btn btn-primary">Next up: {d.next.title}</Link>}
              </div>
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

          <Section title="Weekly snapshots and brief" note="A snapshot saves where the plan stands so next week can say what moved. The backend takes one automatically each week while it is running. The AI brief sends only counts and deliverable titles, never your records.">
            <div className="flex flex-wrap gap-2">
              <button className="btn" disabled={busy !== null} onClick={() => snap(false)}>{busy === "snap" ? "Saving…" : "Take a snapshot now"}</button>
              <button className="btn" disabled={busy !== null} onClick={() => snap(true)}>{busy === "ai" ? "Writing…" : "Write the brief with AI"}</button>
            </div>
            {snaps.length === 0 ? <p className="mt-3 text-sm text-muted">No snapshots yet.</p> : (
              <ul className="mt-3 space-y-2">
                {snaps.slice(0, 6).map((x, i) => (
                  <li key={x.at + i} className="rounded-md border border-line p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted"><span>{x.at} UTC</span><Badge>{x.kind}</Badge><Badge>{x.done}/{x.total} ({x.pct}%)</Badge>{x.ai && <Badge tone="ok">AI-written</Badge>}</div>
                    <p className="mt-1">{x.brief}</p>
                  </li>
                ))}
              </ul>
            )}
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
                        <div className="flex flex-wrap items-center gap-2">{x.overdue && <Badge tone="bad">overdue</Badge>}{x.due_soon && <Badge tone="warn">due soon</Badge>}{x.due && <Badge>due {x.due}</Badge>}</div>
                        <div className="text-xs text-muted">{x.why}{x.detail ? ` · ${x.detail}` : ""}</div>
                        {x.note && <div className="mt-1 text-xs"><b>Note:</b> {x.note}</div>}
                        {edit === x.id ? (
                          <div className="mt-2 flex flex-wrap items-end gap-2">
                            <Field label="Due date"><input type="date" className="field" value={draft.due} onChange={(e) => setDraft({ ...draft, due: e.target.value })} /></Field>
                            <Field label="Note"><input className="field" maxLength={600} value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} /></Field>
                            <button className="btn btn-primary text-xs" onClick={() => saveMeta(x.id)}>Save</button>
                            <button className="btn text-xs" onClick={() => setEdit(null)}>Cancel</button>
                          </div>
                        ) : <button className="btn mt-1 !py-0.5 text-xs" onClick={() => { setEdit(x.id); setDraft({ note: x.note, due: x.due }); }}>{x.note || x.due ? "Edit note and date" : "Add note or due date"}</button>}
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
