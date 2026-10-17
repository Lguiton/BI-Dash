"use client";
import { acceptFor, checkFile } from "@/lib/fileCheck";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getJson, postForm, postJson, putJson } from "@/lib/api";

const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");

/** Change the sign-in password, or sign out of every device. */
export function PasswordSettings() {
  const [on, setOn] = useState<boolean | null>(null);
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [again, setAgain] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  useEffect(() => { getJson<{ enabled: boolean }>("/api/auth/status").then((s) => setOn(s.enabled)).catch(() => setOn(false)); }, []);
  async function change(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setOk("");
    if (nw !== again) { setErr("The two new passwords don't match."); return; }
    try { await postJson("/api/auth/change-password", { current: cur, new: nw }); setOk("Password changed. Other devices were signed out."); setCur(""); setNw(""); setAgain(""); } catch (x) { setErr(msg(x)); }
  }
  async function everywhere() {
    setErr(null); setOk("");
    try { await postJson("/api/auth/sign-out-everywhere", {}); setOk("Signed out everywhere. You will be asked to sign in again."); } catch (x) { setErr(msg(x)); }
  }
  return (
    <section className="card space-y-3 p-5" aria-label="Sign-in password">
      <h2 className="text-lg font-semibold">Sign-in password</h2>
      {on === false && <p className="text-sm text-muted">Sign-in is off, which is fine while only this computer can open the dashboard. To turn it on, set BI_AUTH=1 and BI_OWNER_PASSWORD in backend/.env and restart.</p>}
      {on && (
        <form onSubmit={change} className="grid max-w-md gap-2 text-sm">
          {err && <ErrorBanner message={err} />}
          <label className="flex flex-col gap-1">Current password<input className="field" type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required /></label>
          <label className="flex flex-col gap-1">New password (12 characters or more)<input className="field" type="password" autoComplete="new-password" minLength={12} value={nw} onChange={(e) => setNw(e.target.value)} required /></label>
          <label className="flex flex-col gap-1">New password again<input className="field" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required /></label>
          <div className="flex flex-wrap items-center gap-3"><button className="btn btn-primary" type="submit">Change password</button><button className="btn" type="button" onClick={everywhere}>Sign out everywhere</button>{ok && <span role="status" style={{ color: "var(--good)" }}>{ok}</span>}</div>
        </form>
      )}
    </section>
  );
}

type Status = { enabled: boolean; hour: number; last_sent: string | null; email_ready: boolean; latest_hour: number; how: string };
type Prev = { subject: string; body: string };

/** Turn the morning briefing on or off, pick the hour, preview it and send a test. */
export function BriefingSettings() {
  const [st, setSt] = useState<Status | null>(null);
  const [prev, setPrev] = useState<Prev | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  useEffect(() => { getJson<Status>("/api/briefing").then(setSt).catch((e) => setErr(msg(e))); }, []);
  async function save(patch: Partial<Pick<Status, "enabled" | "hour">>) {
    setErr(null); setOk("");
    try { setSt(await putJson<Status>("/api/briefing/config", patch)); setOk("Saved."); } catch (e) { setErr(msg(e)); }
  }
  async function preview() { setErr(null); try { setPrev(await getJson<Prev>("/api/briefing/preview")); } catch (e) { setErr(msg(e)); } }
  async function send() { setErr(null); setOk(""); try { await postJson("/api/briefing/send", {}); setOk("Sent. Check your inbox."); } catch (e) { setErr(msg(e)); } }
  return (
    <section className="card space-y-3 p-5" aria-label="Morning briefing">
      <h2 className="text-lg font-semibold">Morning briefing</h2>
      {err && <ErrorBanner message={err} />}
      {st && (
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2"><input type="checkbox" checked={st.enabled} onChange={(e) => save({ enabled: e.target.checked })} />Email me a briefing each day</label>
            <label className="flex items-center gap-2">Send at<select className="field" value={st.hour} onChange={(e) => save({ hour: Number(e.target.value) })}>{Array.from({ length: 21 }, (_, h) => <option key={h} value={h}>{`${h % 12 || 12}:00 ${h < 12 ? "am" : "pm"}`}</option>)}</select></label>
            {st.last_sent && <span className="text-muted">Last sent {st.last_sent}</span>}
          </div>
          {!st.email_ready && <p className="text-muted">Email isn&apos;t set up yet (BI_SMTP_HOST and BI_REPORT_TO in backend/.env), so the briefing can be previewed here but not sent.</p>}
          <p className="text-xs text-muted">{st.how}</p>
          <div className="flex flex-wrap items-center gap-3"><button className="btn" onClick={preview}>Preview today&apos;s briefing</button><button className="btn" disabled={!st.email_ready} onClick={send}>Send one now</button>{ok && <span role="status" style={{ color: "var(--good)" }}>{ok}</span>}</div>
          {prev && <pre className="whitespace-pre-wrap rounded-lg p-3 text-xs" style={{ background: "var(--panel2, rgba(127,127,127,.1))" }} aria-label="Briefing preview">{prev.subject + "\n\n" + prev.body}</pre>}
        </div>
      )}
    </section>
  );
}

type Laptop = { laptop: boolean; encrypted: boolean; locks: boolean; findmy: boolean; windows_signin: boolean; text: Record<string, { label: string; how: string }> };

/** Travelling with a laptop: safety checklist, a backup copy outside the laptop, and moving your data between computers. */
export function LaptopSettings() {
  const [lp, setLp] = useState<Laptop | null>(null);
  const [folder, setFolder] = useState("");
  const [last, setLast] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  const [file, setFile] = useState<File | null>(null);
  useEffect(() => {
    getJson<Laptop>("/api/health-check/laptop").then(setLp).catch((e) => setErr(msg(e)));
    getJson<{ folder: string; last: string }>("/api/backups/copy-folder").then((c) => { setFolder(c.folder); setLast(c.last); }).catch(() => {});
  }, []);
  async function tick(patch: Partial<Laptop>) { setErr(null); try { setLp(await putJson<Laptop>("/api/health-check/laptop", patch)); } catch (e) { setErr(msg(e)); } }
  async function saveFolder() {
    setErr(null); setOk("");
    try { const c = await putJson<{ folder: string; last: string }>("/api/backups/copy-folder", { folder }); setLast(c.last); setOk(c.folder ? "Saved. Every new backup is also copied there." : "Copy folder cleared."); } catch (e) { setErr(msg(e)); }
  }
  async function upload() {
    if (!file) return;
    setErr(null); setOk("");
    try { const b = new FormData(); b.append("file", file); await postForm("/api/backups/upload", b); setOk("Backup added to your list. Restore it from the Backups list on this page."); setFile(null); } catch (e) { setErr(msg(e)); }
  }
  const keys = ["encrypted", "locks", "findmy", "windows_signin"] as const;
  return (
    <section className="card space-y-4 p-5" aria-label="Laptop and travel">
      <h2 className="text-lg font-semibold">Laptop and travel</h2>
      {err && <ErrorBanner message={err} />}
      {ok && <p role="status" className="text-sm" style={{ color: "var(--good)" }}>{ok}</p>}
      {lp && (
        <div className="space-y-2 text-sm">
          <label className="flex items-center gap-2 font-medium"><input type="checkbox" checked={lp.laptop} onChange={(e) => tick({ laptop: e.target.checked })} />This dashboard runs on a laptop I travel with</label>
          {lp.laptop && (
            <ul className="space-y-1 pl-1">{keys.map((k) => (
              <li key={k}><label className="flex items-start gap-2"><input className="mt-1" type="checkbox" checked={lp[k]} onChange={(e) => tick({ [k]: e.target.checked })} /><span>{lp.text[k].label}. <span className="text-xs text-muted">{lp.text[k].how}</span></span></label></li>
            ))}</ul>
          )}
          <p className="text-xs text-muted">Ticking these only records what you confirmed; the health check on the Activity page reminds you about anything left unticked.</p>
        </div>
      )}
      <div className="space-y-1 text-sm">
        <h3 className="font-medium">Copy every backup to another place</h3>
        <div className="flex flex-wrap items-center gap-2">
          <input className="field min-w-72 flex-1" placeholder="e.g. D:\Backups or C:\Users\you\OneDrive\BI-backups" aria-label="Backup copy folder" value={folder} onChange={(e) => setFolder(e.target.value)} />
          <button className="btn" onClick={saveFolder}>Save folder</button>
        </div>
        <p className="text-xs text-muted">A USB drive, or a OneDrive or Google Drive folder, so losing the laptop doesn&apos;t lose the business. The newest 14 copies are kept.{last ? ` Last copy: ${last}.` : ""}</p>
      </div>
      <div className="space-y-1 text-sm">
        <h3 className="font-medium">Move data from another computer</h3>
        <div className="flex flex-wrap items-center gap-2"><input type="file" accept={acceptFor("backup")} aria-label="Backup file to bring in" onChange={(e) => { const f = e.target.files?.[0] ?? null; const bad = f ? checkFile(f, "backup") : null; setErr(bad); if (bad) e.target.value = ""; setFile(bad ? null : f); }} /><button className="btn" disabled={!file} onClick={upload}>Add this backup</button></div>
        <p className="text-xs text-muted">On the old computer, download a backup from the Backups list below, then add it here and restore it. Your settings and sign-in stay on each computer.</p>
      </div>
    </section>
  );
}
