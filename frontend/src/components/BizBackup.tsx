"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, errMsg } from "@/components/panels/kit";

type Check = { name: string; ok: boolean; detail: string };
type Item = { name: string; kind: string; size_bytes: number; created_at: string; counts: Record<string, number>; tested: { ok: boolean; at: string } | null };
type Resp = { backups: Item[]; status: { warning: string; copy_folder: string; copy_last: string; count: number } };
type Test = { name: string; ok: boolean; checks: Check[] };

/** Backs up the file that holds clients, jobs, invoices, leads, books and the fix log. Each backup can be put through a restore test. */
export function BizBackup() {
  const [r, setR] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [test, setTest] = useState<Test | null>(null);
  const [sure, setSure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    getJson<Resp>("/api/biz-backup").then((x) => { if (live) setR(x); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load business backups.")); });
    return () => { live = false; };
  }, [tick]);
  async function act(fn: () => Promise<unknown>) { setErr(null); setBusy(true); try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); } }
  return (
    <section className="card space-y-3 p-5" aria-label="Business data backups">
      <h2 className="text-lg font-semibold">Business data backups</h2>
      <p className="text-sm text-muted">Your clients, jobs, invoices, leads, books, fix log and notes live in a separate file from the databases above, so they get their own backup. One is made automatically about once a day while the app runs, and each is tested right away. A copy also goes to your backup folder if you set one.</p>
      {err && <ErrorBanner message={err} />}
      {r?.status.warning && <p role="alert" className="rounded border border-amber-500 bg-amber-500/10 p-2 text-sm">{r.status.warning}</p>}
      {r?.status.copy_folder ? <p className="text-xs text-muted">Copies go to {r.status.copy_folder}. Last copy: {r.status.copy_last || "none yet"}.</p> : <p className="text-xs text-muted">No backup folder is set, so backups stay on this computer. Set one above to also keep a copy on a USB drive or cloud folder.</p>}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={() => act(async () => { const b = await postJson<{ test: Test }>("/api/biz-backup", {}); setTest(b.test); })}>Back up business data now</button>
      </div>
      {test && (
        <div role="status" className="rounded border border-line p-3 text-sm">
          <p className="font-semibold">{test.ok ? "Restore test passed" : "Restore test FAILED"}: {test.name}</p>
          <ul className="mt-1 space-y-0.5">{test.checks.map((c) => <li key={c.name}><Badge tone={c.ok ? "ok" : "bad"}>{c.ok ? "pass" : "fail"}</Badge> {c.name}: <span className="text-muted">{c.detail}</span></li>)}</ul>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Business data backups</caption>
          <thead><tr><th className="th">Made</th><th className="th">Kind</th><th className="th">Inside</th><th className="th">Restore test</th><th className="th" /></tr></thead>
          <tbody>
            {r?.backups.map((b) => (
              <tr key={b.name} className="border-t border-line">
                <td className="td">{b.created_at}</td><td className="td">{b.kind}</td>
                <td className="td text-xs">{b.counts.clients ?? 0} clients, {b.counts.jobs ?? 0} jobs, {b.counts.invoices ?? 0} invoices, {b.counts.leads ?? 0} leads, {b.counts.fixes ?? 0} fixes</td>
                <td className="td">{b.tested ? <Badge tone={b.tested.ok ? "ok" : "bad"}>{b.tested.ok ? "passed" : "failed"} {b.tested.at.slice(0, 10)}</Badge> : <Badge tone="warn">not tested</Badge>}</td>
                <td className="td">
                  {sure === b.name ? (
                    <span className="flex flex-wrap items-center gap-2">Replace today&apos;s business data with this one? A safety backup is made first.
                      <button className="btn" style={{ color: "var(--bad)" }} onClick={() => act(async () => { await postJson(`/api/biz-backup/${b.name}/restore`, { confirm: true }); window.location.reload(); })}>Yes, restore</button>
                      <button className="btn" onClick={() => setSure(null)}>Cancel</button></span>
                  ) : (
                    <span className="flex flex-wrap gap-2">
                      <button className="btn" disabled={busy} onClick={() => act(async () => setTest(await postJson<Test>(`/api/biz-backup/${b.name}/test`, {})))}>Test</button>
                      <button className="btn" onClick={() => setSure(b.name)}>Restore</button>
                      <a className="btn" href={`${API_BASE}/api/biz-backup/${b.name}/download`} download>Download</a>
                      <button className="btn" aria-label={`Delete backup ${b.name}`} onClick={() => act(() => deleteJson(`/api/biz-backup/${b.name}`))}>Delete</button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {r && r.backups.length === 0 && <tr><td className="td text-muted" colSpan={5}>No business-data backups yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">The restore test opens a scratch copy and checks its checksum, its health and its record counts. It never touches your live data. Restoring replaces all business data and study progress with what the backup held.</p>
    </section>
  );
}
