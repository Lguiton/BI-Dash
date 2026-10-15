"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, putJson } from "@/lib/api";

type Today = {
  sample: boolean; count: number; note: string;
  followups: { id: number; client: string; note: string; due: string }[];
  overdue_invoices: { id: number; number: string; client: string; total: number; days_late: number; draft: string }[];
  jobs_due: { id: number; title: string; client: string; due: string | null; late: boolean }[];
  work_due: { id: number; title: string; due: string; overdue: boolean }[];
  timer: { id: number; title: string; elapsed: number; warn: boolean } | null;
  ready_to_close: { id: number; title: string; client: string }[];
  backup: { message: string; where: string } | null;
};
type Prep = { enabled: boolean; daily_cap: number; auto_new_items: boolean; used_today: number; remaining: number; hard_max: number; ai_mode: string; note: string };
const usd = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Everything that needs you right now, in one list. Reminders are drafts you copy and send yourself; nothing here sends anything. */
export function TodayPanel({ footer }: { footer?: string }) {
  const [t, setT] = useState<Today | null>(null);
  const [prep, setPrep] = useState<Prep | null>(null);
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [showDraft, setShowDraft] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [cap, setCap] = useState("");

  useEffect(() => {
    let live = true;
    getJson<Today>("/api/auto/today").then((r) => { if (live) setT(r); }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load today's list.")); });
    getJson<Prep>("/api/auto/prep").then((r) => { if (live) { setPrep(r); setCap(String(r.daily_cap)); } }).catch(() => {});
    return () => { live = false; };
  }, [tick]);

  async function savePrep(body: Record<string, unknown>) {
    setErr(null);
    try { setPrep(await putJson<Prep>("/api/auto/prep", body)); setTick((x) => x + 1); } catch (e) { setErr(errMsg(e, "That setting didn't save.")); }
  }
  async function copy(id: number, text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(id); setTimeout(() => setCopied(null), 2000); } catch { setErr("Couldn't copy. Select the text and copy it by hand."); }
  }
  const mins = (s: number) => `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;

  return (
    <section className="card space-y-2 p-4" aria-label="Today">
      <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Today{t ? ` (${t.count})` : ""}</h2>{t?.sample && <Badge tone="warn">Sample data</Badge>}</div>
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      {!t && !err && <p className="text-sm text-muted">Loading…</p>}
      {t && t.count === 0 && <p className="text-sm">Nothing is late and nothing needs you right now.</p>}
      {t && (
        <ul className="space-y-1.5 text-sm">
          {t.timer?.warn && <li><Badge tone="warn">timer</Badge> A timer has been running on &quot;{t.timer.title}&quot; for {mins(t.timer.elapsed)}. Still working? <Link href="/" className="underline">Check the work log</Link>.</li>}
          {t.overdue_invoices.map((i) => (
            <li key={`inv${i.id}`}>
              <Badge tone="bad">late</Badge> Invoice {i.number} for {i.client}: {usd(i.total)}, {i.days_late} day{i.days_late === 1 ? "" : "s"} late.{" "}
              <button className="underline" onClick={() => setShowDraft(showDraft === i.id ? null : i.id)}>{showDraft === i.id ? "Hide reminder" : "Reminder ready"}</button>
              {showDraft === i.id && (
                <div className="mt-1 space-y-1">
                  <pre className="whitespace-pre-wrap rounded bg-panel2 p-2 text-xs">{i.draft}</pre>
                  <button className="btn" onClick={() => copy(i.id, i.draft)}>{copied === i.id ? "Copied" : "Copy reminder"}</button>
                </div>
              )}
            </li>
          ))}
          {t.followups.map((f) => <li key={`fu${f.id}`}><Badge tone="warn">follow up</Badge> {f.client}: {f.note || "check in"} (due {f.due}) <Link href="/clients" className="underline">Clients</Link></li>)}
          {t.jobs_due.map((j) => <li key={`jd${j.id}`}><Badge tone={j.late ? "bad" : "warn"}>{j.late ? "late job" : "due soon"}</Badge> <Link href={`/job?id=${j.id}`} className="underline">{j.title}</Link> for {j.client}{j.due ? ` (due ${j.due})` : ""}</li>)}
          {t.work_due.map((w) => <li key={`wd${w.id}`}><Badge tone={w.overdue ? "bad" : "warn"}>{w.overdue ? "overdue" : "due today"}</Badge> {w.title} ({w.due})</li>)}
          {t.ready_to_close.map((j) => <li key={`rc${j.id}`}><Badge tone="ok">ready</Badge> All steps are done on <Link href={`/job?id=${j.id}`} className="underline">{j.title}</Link> for {j.client}. Close it and invoice.</li>)}
          {t.backup && <li><Badge tone="warn">backup</Badge> {t.backup.message} <Link href={t.backup.where} className="underline">Settings</Link></li>}
        </ul>
      )}
      {footer && <p className="text-xs text-muted">{footer}</p>}
      {prep && (
        <details className="border-t border-line pt-2 text-xs">
          <summary className="cursor-pointer text-muted">AI prep drafts: {prep.enabled ? `on, ${prep.used_today} of ${prep.daily_cap} used today` : "off"}</summary>
          <div className="mt-2 space-y-2">
            <p className="text-muted">{prep.note} Uses OpenAI only. It never sends a client name, and it stops at the daily cap.</p>
            <label className="flex items-center gap-2"><input type="checkbox" checked={prep.enabled} onChange={(e) => savePrep({ enabled: e.target.checked })} /> Turn on prep drafts (a button on each work item)</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={prep.auto_new_items} disabled={!prep.enabled || prep.ai_mode !== "full"} onChange={(e) => savePrep({ auto_new_items: e.target.checked })} /> Also draft new work items automatically (needs AI mode &quot;full&quot;; now: {prep.ai_mode})</label>
            <div className="flex items-center gap-2">
              <label htmlFor="prep-cap">Daily cap (1 to {prep.hard_max})</label>
              <input id="prep-cap" className="input w-20" inputMode="numeric" value={cap} onChange={(e) => setCap(e.target.value)} />
              <button className="btn" onClick={() => savePrep({ daily_cap: Number(cap) })}>Save cap</button>
            </div>
          </div>
        </details>
      )}
    </section>
  );
}
