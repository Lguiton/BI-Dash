"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson, postJsonH } from "@/lib/api";
import { Badge, Section, Stat, Table, Tabs, errMsg } from "./kit";

interface Param { name: string; label: string; kind: string; options?: string[]; labels?: Record<string, string>; secret?: boolean; required?: boolean }
interface Action { id: string; cat: string; title: string; what: string; risk: "low" | "medium" | "high"; read: boolean; params: Param[]; admin: boolean; typed: boolean; revert_after: number | null; restore_point: boolean; note: string; scan: boolean; undoable: boolean }
interface Catalog { categories: { id: string; label: string }[]; actions: Action[] }
interface Status { enabled: boolean; workspace: string; live: boolean; pin_set: boolean; armed_seconds: number; shell: boolean; platform: string; arm_minutes: number }
interface Finding { severity: string; title: string; detail: string; advice: string; evidence: string[]; source?: string }
interface Analysis { findings: Finding[]; counts: Record<string, number>; caveat: string; skipped?: string[] }
interface Job { id: string; status: string; output: string; simulated: boolean; title: string; analysis?: Analysis; rows?: unknown[]; change_id?: number; revert_in?: number; restore_point?: string }
interface Change { id: number; at: string; action: string; title: string; risk: string; params: Record<string, string>; status: string; output: string; undone_at: string | null; undoable: boolean; revert_in: number | null; kept: number }
interface Preview { script: string; capture: string | null; restore: string | null; note: string }
interface SettingsState { settings: Record<string, Record<string, unknown>>; custom_rows: number; snapshots: { id: number; at: string; label: string; count: number }[] }

const TABS = [
  { id: "security", label: "Security scans" }, { id: "maintenance", label: "Maintenance" }, { id: "settings", label: "Settings and services" },
  { id: "network", label: "Network" }, { id: "accounts", label: "Accounts and software" }, { id: "history", label: "History and undo" }, { id: "reset", label: "Reset app settings" },
];
const riskTone = (r: string): "ok" | "warn" | "bad" => (r === "high" ? "bad" : r === "medium" ? "warn" : "ok");
const sevTone = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "high" ? "bad" : s === "medium" ? "warn" : "muted");
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function ComputerPanel() {
  const [tab, setTab] = useState("security");
  const [st, setSt] = useState<Status | null>(null);
  const [cat, setCat] = useState<Catalog | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => { getJson<Status>("/api/system/status").then(setSt).catch((e) => setErr(errMsg(e, "Couldn't reach the app."))); }, []);
  useEffect(() => {
    getJson<Status>("/api/system/status").then((s) => { setSt(s); if (s.enabled) getJson<Catalog>("/api/system/actions").then(setCat).catch((e) => setErr(errMsg(e, "Couldn't load the actions."))); }).catch((e) => setErr(errMsg(e, "Couldn't reach the app.")));
    const t = setInterval(() => { refresh(); setTick((n) => n + 1); }, 4000);
    return () => clearInterval(t);
  }, [refresh]);
  const armed = !!token && (st?.armed_seconds ?? 0) > 0;

  if (!st) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading...</p>;
  if (!st.enabled) {
    return (
      <Section title="Computer control isn't turned on in this copy">
        <p className="text-sm">This is a personal-edition feature, off by default. To turn it on for <b>this</b> computer only, create an empty file named <code>computer_control.enabled</code> in the project folder (next to the <code>backend</code> and <code>frontend</code> folders), then restart the app.</p>
        <pre className="mt-2 overflow-x-auto rounded bg-panel2 p-2 text-xs">touch computer_control.enabled</pre>
        <p className="mt-2 text-xs text-muted">The personal bundle for your other computer skips this file, so it stays off there.</p>
      </Section>
    );
  }
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Banner st={st} />
      <ArmCard st={st} token={token} armed={armed} setToken={setToken} refresh={refresh} onErr={setErr} />
      <Pending token={token} tick={tick} onErr={setErr} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Computer control" />
      {tab === "security" && <ScanAll st={st} token={token} armed={armed} onErr={setErr} />}
      {cat && cat.categories.some((c) => c.id === tab) && (
        <div className="space-y-3">
          {cat.actions.filter((a) => a.cat === tab).map((a) => <ActionCard key={a.id} a={a} st={st} token={token} armed={armed} />)}
        </div>
      )}
      {tab === "history" && <History st={st} token={token} armed={armed} tick={tick} />}
      {tab === "reset" && <ResetCard />}
    </div>
  );
}

function Banner({ st }: { st: Status }) {
  return st.live ? (
    <div role="alert" className="rounded border p-3 text-sm" style={{ borderColor: "var(--bad)", background: "var(--panel-2)" }}>
      <b>Real workspace: actions run on this computer.</b> Nothing happens until you arm it with your PIN, and each change records how to undo it.
      {!st.shell && <span className="ml-1 text-xs" style={{ color: "var(--bad)" }}>PowerShell wasn&apos;t found here ({st.platform}), so actions can&apos;t run.</span>}
    </div>
  ) : (
    <div className="rounded border border-line bg-panel2 p-3 text-sm"><b>Practice workspace: simulation only.</b> Every button shows exactly what would run and uses made-up example results. Nothing touches your computer. Switch to Real in the top bar to act for real.</div>
  );
}

function ArmCard({ st, token, armed, setToken, refresh, onErr }: { st: Status; token: string | null; armed: boolean; setToken: (t: string | null) => void; refresh: () => void; onErr: (e: string | null) => void }) {
  const [pin, setPin] = useState("");
  const [cur, setCur] = useState("");
  const [changing, setChanging] = useState(false);
  const act = async (fn: () => Promise<unknown>, m: string) => { onErr(null); try { await fn(); } catch (e) { onErr(errMsg(e, m)); } };
  return (
    <Section title="Lock" note="The PIN guards the Real workspace. It is stored as a salted hash on this computer. Arming lasts 15 minutes and lives only in this browser tab.">
      {!st.pin_set ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs text-muted">Choose a PIN (6 or more characters)<input type="password" className="field" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="new-password" /></label>
          <button className="btn btn-primary" disabled={pin.length < 6} onClick={() => act(async () => { await postJson("/api/system/pin", { pin }); setPin(""); refresh(); }, "Couldn't set the PIN.")}>Set PIN</button>
        </div>
      ) : armed ? (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Badge tone="warn">armed</Badge><span>{mmss(st.armed_seconds)} left</span>
          <button className="btn" onClick={() => act(async () => { await postJson("/api/system/disarm", {}); setToken(null); refresh(); }, "Couldn't lock.")}>Lock now</button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1 text-xs text-muted">PIN<input type="password" className="field" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="current-password" onKeyDown={(e) => { if (e.key === "Enter" && pin) e.currentTarget.form?.requestSubmit(); }} /></label>
            <button className="btn btn-primary" disabled={!pin} onClick={() => act(async () => { const r = await postJson<{ token: string }>("/api/system/arm", { pin }); setToken(r.token); setPin(""); refresh(); }, "Couldn't arm.")}>Arm for {st.arm_minutes} minutes</button>
            <button className="btn" onClick={() => setChanging(!changing)}>{changing ? "Cancel" : "Change PIN"}</button>
          </div>
          {changing && (
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-xs text-muted">Current PIN<input type="password" className="field" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
              <label className="flex flex-col gap-1 text-xs text-muted">New PIN<input type="password" className="field" value={pin} onChange={(e) => setPin(e.target.value)} /></label>
              <button className="btn" disabled={pin.length < 6 || !cur} onClick={() => act(async () => { await postJson("/api/system/pin", { pin, current: cur }); setPin(""); setCur(""); setChanging(false); }, "Couldn't change the PIN.")}>Save new PIN</button>
            </div>
          )}
          {!st.live && <p className="text-xs text-muted">Practice doesn&apos;t need arming; only Real does.</p>}
        </div>
      )}
      {token && !armed && <p className="mt-2 text-xs text-muted">The arming window ended. Enter your PIN to arm again.</p>}
    </Section>
  );
}

function Pending({ token, tick, onErr }: { token: string | null; tick: number; onErr: (e: string | null) => void }) {
  const [rows, setRows] = useState<Change[]>([]);
  const load = useCallback(() => { getJson<{ changes: Change[] }>("/api/system/changes").then((r) => setRows(r.changes.filter((c) => c.revert_in != null))).catch(() => setRows([])); }, []);
  useEffect(() => { load(); }, [load, tick]);
  if (!rows.length) return null;
  return (
    <div role="alert" className="space-y-2 rounded border p-3" style={{ borderColor: "var(--accent)", background: "var(--panel-2)" }}>
      <div className="text-sm font-semibold">Keep these changes?</div>
      {rows.map((c) => (
        <div key={c.id} className="flex flex-wrap items-center gap-2 text-sm">
          <span>{c.title}</span><Badge tone="warn">reverts in {mmss(c.revert_in ?? 0)}</Badge>
          <button className="btn btn-primary" onClick={async () => { try { await postJson(`/api/system/changes/${c.id}/keep`, {}); load(); } catch (e) { onErr(errMsg(e, "Couldn't keep it.")); } }}>Keep</button>
          <button className="btn" disabled={!token} onClick={async () => { try { await postJsonH(`/api/system/changes/${c.id}/undo`, {}, token ? { "X-Control-Token": token } : {}); load(); } catch (e) { onErr(errMsg(e, "Couldn't undo.")); } }}>Undo now</button>
        </div>
      ))}
      <p className="text-xs text-muted">If you do nothing, the computer is put back automatically when the timer ends. If the app is closed first, it is put back the next time the app runs.</p>
    </div>
  );
}

function Findings({ a }: { a: Analysis }) {
  return (
    <div className="mt-3 space-y-2">
      <p className="text-sm">{a.counts.high} high, {a.counts.medium} medium, {a.counts.low} low, {a.counts.info} for information.</p>
      {a.findings.length === 0 ? <p className="text-sm text-muted">Nothing stood out.</p> : (
        <ul className="space-y-2">
          {a.findings.map((f, i) => (
            <li key={i} className="rounded border border-line p-2 text-sm">
              <div><Badge tone={sevTone(f.severity)}>{f.severity}</Badge> <span className="font-medium">{f.title}</span></div>
              {f.detail && <p className="break-words text-xs text-muted">{f.detail}</p>}
              <p className="text-xs">{f.advice}</p>
              {f.evidence.length > 0 && <details className="text-xs text-muted"><summary className="cursor-pointer">Details</summary><ul className="mt-1 space-y-0.5">{f.evidence.map((e, j) => <li key={j} className="break-all">{e}</li>)}</ul></details>}
            </li>
          ))}
        </ul>
      )}
      {a.skipped && a.skipped.length > 0 && <p className="text-xs text-muted">Skipped: {a.skipped.join("; ")}</p>}
      <p className="text-xs text-muted">{a.caveat}</p>
    </div>
  );
}

function usePoll(): { job: Job | null; start: (j: Job) => void; clear: () => void } {
  const [job, setJob] = useState<Job | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stop = () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  useEffect(() => stop, []);
  const start = (j: Job) => {
    stop(); setJob(j);
    if (j.status !== "running") return;
    timer.current = setInterval(() => { getJson<Job>(`/api/system/jobs/${j.id}`).then((n) => { setJob(n); if (n.status !== "running") stop(); }).catch(() => stop()); }, 1500);
  };
  return { job, start, clear: () => { stop(); setJob(null); } };
}

function ScanAll({ st, token, armed, onErr }: { st: Status; token: string | null; armed: boolean; onErr: (e: string | null) => void }) {
  const { job, start } = usePoll();
  const can = !st.live || armed;
  return (
    <Section title="Full security scan" note="Runs seven read-only scans (protection status, accounts, remote-access tools, camera and microphone use, startup items, network connections, running programs). Some parts need administrator rights; anything that can't run is listed as skipped. This is not an antivirus.">
      <button className="btn btn-primary" disabled={!can} onClick={async () => { onErr(null); try { start(await postJsonH<Job>("/api/system/scan-all", {}, token ? { "X-Control-Token": token } : {})); } catch (e) { onErr(errMsg(e, "Couldn't start the scan.")); } }}>
        {st.live ? "Run full scan" : "Show a sample scan"}
      </button>
      {!can && <span className="ml-2 text-xs text-muted">Arm with your PIN first.</span>}
      {job?.status === "running" && <p className="mt-2 text-sm text-muted">{job.output || "Working..."}</p>}
      {job?.simulated && <p className="mt-2 text-xs text-muted">{job.output}</p>}
      {job?.analysis && <Findings a={job.analysis} />}
    </Section>
  );
}

function ActionCard({ a, st, token, armed }: { a: Action; st: Status; token: string | null; armed: boolean }) {
  const [vals, setVals] = useState<Record<string, string>>(() => Object.fromEntries(a.params.map((p) => [p.name, p.kind === "enum" ? (p.options?.[0] ?? "") : ""])));
  const [prev, setPrev] = useState<Preview | null>(null);
  const [asking, setAsking] = useState(false);
  const [word, setWord] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const { job, start } = usePoll();
  const can = !st.live || armed;
  const body = () => Object.fromEntries(Object.entries(vals).filter(([, v]) => v !== ""));
  const doPreview = async () => { setMsg(null); try { setPrev(await postJson<Preview>("/api/system/preview", { action: a.id, params: body() })); } catch (e) { setMsg(errMsg(e, "Couldn't preview.")); } };
  const doRun = async () => {
    setMsg(null); setAsking(false);
    try { start(await postJsonH<Job>("/api/system/run", { action: a.id, params: body(), confirm: word }, token ? { "X-Control-Token": token } : {})); setWord(""); }
    catch (e) { setMsg(errMsg(e, "Couldn't run it.")); }
  };
  return (
    <section className="card min-w-0 space-y-2 p-4" aria-label={a.title}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{a.title}</h3>
        <Badge tone={a.read ? "ok" : riskTone(a.risk)}>{a.read ? "read only" : `${a.risk} risk`}</Badge>
        {a.admin && <Badge>needs administrator</Badge>}
        {a.undoable && <Badge tone="ok">undoable</Badge>}
        {a.revert_after && <Badge tone="warn">auto-reverts</Badge>}
      </div>
      <p className="text-xs text-muted">{a.what}{a.note ? ` ${a.note}` : ""}</p>
      {a.params.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {a.params.map((p) => (
            <label key={p.name} className="flex min-w-0 flex-col gap-1 text-xs text-muted">{p.label}
              {p.kind === "enum" ? (
                <select className="field" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}>{(p.options ?? []).map((o) => <option key={o} value={o}>{p.labels?.[o] ?? o}</option>)}</select>
              ) : (
                <input className="field" type={p.secret ? "password" : "text"} autoComplete="off" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} />
              )}
            </label>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={doPreview}>Preview command</button>
        {!asking ? (
          <button className="btn btn-primary" disabled={!can} onClick={() => (a.read ? doRun() : setAsking(true))}>{st.live ? "Run" : "Simulate"}</button>
        ) : (
          <>
            {st.live && a.typed && <input className="field w-40" aria-label="Type CONFIRM" placeholder="Type CONFIRM" value={word} onChange={(e) => setWord(e.target.value)} />}
            <button className="btn btn-primary" disabled={st.live && a.typed && word.trim().toUpperCase() !== "CONFIRM"} onClick={doRun}>{st.live ? "Yes, change my computer" : "Yes, simulate"}</button>
            <button className="btn" onClick={() => { setAsking(false); setWord(""); }}>Cancel</button>
          </>
        )}
        {!can && <span className="text-xs text-muted">Arm with your PIN first.</span>}
      </div>
      {msg && <p role="alert" className="text-sm" style={{ color: "var(--bad)" }}>{msg}</p>}
      {prev && (
        <details open className="text-xs">
          <summary className="cursor-pointer text-muted">What would run (nothing in here is built from your typing; inputs travel separately)</summary>
          <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2">{prev.script}</pre>
          {prev.capture && <><div className="mt-1 text-muted">Saved first, so Undo works:</div><pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2">{prev.capture}</pre></>}
          {prev.restore && <><div className="mt-1 text-muted">Undo runs:</div><pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2">{prev.restore}</pre></>}
        </details>
      )}
      {job && (
        <div className="space-y-1 text-sm">
          <div>{job.status === "running" ? <Badge tone="warn">running...</Badge> : <Badge tone={job.status === "ok" ? "ok" : "bad"}>{job.simulated ? "simulated" : job.status}</Badge>}
            {job.revert_in ? <span className="ml-2 text-xs text-muted">Will revert in {mmss(job.revert_in)} unless you press Keep above.</span> : null}
            {job.restore_point ? <span className="ml-2 text-xs text-muted">Restore point: {job.restore_point}</span> : null}</div>
          {job.analysis && <Findings a={job.analysis} />}
          {job.output && !job.analysis && <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 text-xs">{job.output}</pre>}
          {job.output && job.analysis && job.simulated && <details className="text-xs text-muted"><summary className="cursor-pointer">Command</summary><pre className="whitespace-pre-wrap">{job.output}</pre></details>}
        </div>
      )}
    </section>
  );
}

function History({ st, token, armed, tick }: { st: Status; token: string | null; armed: boolean; tick: number }) {
  const [rows, setRows] = useState<Change[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);
  const load = useCallback(() => { getJson<{ changes: Change[] }>("/api/system/changes").then((r) => setRows(r.changes)).catch((e) => setErr(errMsg(e, "Couldn't load the history."))); }, []);
  useEffect(() => { load(); }, [load, tick]);
  const H: Record<string, string> = token ? { "X-Control-Token": token } : {};
  const can = st.live && armed;
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      <Section title="Fallback" note="Undo everything puts back every undoable change from the last 24 hours, newest first. Changes that can't be undone (deleted temp files, software removed) are not touched.">
        {!ask ? <button className="btn" disabled={!can} onClick={() => setAsk(true)}>Undo everything (last 24 hours)</button> : (
          <div className="flex flex-wrap items-center gap-2 text-sm">Put back all undoable changes?
            <button className="btn btn-primary" onClick={async () => { setAsk(false); setErr(null); try { const r = await postJsonH<{ undone: number[]; failed: { id: number; why: string }[] }>("/api/system/undo-all", {}, H); setOk(`Undone: ${r.undone.length}. Failed: ${r.failed.length}.${r.failed.length ? " " + r.failed.map((f) => `#${f.id}: ${f.why}`).join("; ") : ""}`); load(); } catch (e) { setErr(errMsg(e, "Couldn't undo.")); } }}>Yes, undo</button>
            <button className="btn" onClick={() => setAsk(false)}>Cancel</button></div>
        )}
        {!can && <span className="ml-2 text-xs text-muted">Needs the Real workspace and your PIN.</span>}
        {ok && <p role="status" className="mt-2 text-sm">{ok}</p>}
      </Section>
      <Section title="Changes made from this app">
        {rows.length === 0 ? <p className="text-sm text-muted">Nothing yet. Read-only scans aren&apos;t listed.</p> : (
          <Table head={["When (UTC)", "Change", "Result", ""]} caption="Changes" rows={rows.map((c) => [
            c.at, <span key="t">{c.title}{Object.keys(c.params).length ? <span className="text-xs text-muted"> ({Object.entries(c.params).map(([k, v]) => `${k}=${v}`).join(", ")})</span> : null}</span>,
            <Badge key="s" tone={c.status === "ok" ? "ok" : c.status === "failed" ? "bad" : "muted"}>{c.undone_at ? "undone" : c.status}</Badge>,
            c.undoable ? <button key="u" className="btn" disabled={!can} onClick={async () => { setErr(null); try { await postJsonH(`/api/system/changes/${c.id}/undo`, {}, H); load(); } catch (e) { setErr(errMsg(e, "Couldn't undo.")); } }}>Undo</button> : "",
          ])} />
        )}
      </Section>
    </div>
  );
}

function ResetCard() {
  const [d, setD] = useState<SettingsState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [ask, setAsk] = useState<string | null>(null);
  const load = useCallback(() => { getJson<SettingsState>("/api/system/settings").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load settings."))); }, []);
  useEffect(() => { load(); }, [load]);
  const act = async (fn: () => Promise<unknown>, okText: string) => { setErr(null); setAsk(null); try { await fn(); setMsg(okText); load(); } catch (e) { setErr(errMsg(e, "That didn't work.")); } };
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="text-sm">{msg}</p>}
      <Section title="Reset the app's own settings" note="Puts AI access, blocked columns, backup options, alert and report options back to their defaults. Your data, backups, progress and the activity log are not touched. A snapshot is saved first, so you can restore it.">
        <p className="mb-2 text-sm text-muted">{d ? `${d.custom_rows} saved setting(s) differ from the defaults.` : "Loading..."}</p>
        <div className="flex flex-wrap gap-2">
          {["practice", "real", "all"].map((s) => (ask === s ? (
            <span key={s} className="flex items-center gap-2 text-sm">Reset {s}?
              <button className="btn btn-primary" onClick={() => act(() => postJson("/api/system/settings/reset", { scope: s }), `Reset ${s} settings. A snapshot was saved first.`)}>Yes, reset</button>
              <button className="btn" onClick={() => setAsk(null)}>Cancel</button></span>
          ) : <button key={s} className="btn" onClick={() => setAsk(s)}>Reset {s === "all" ? "both workspaces" : s}</button>))}
          <button className="btn" onClick={() => act(() => postJson("/api/system/settings/snapshot", {}), "Snapshot saved.")}>Take a snapshot now</button>
        </div>
      </Section>
      <Section title="Snapshots">
        {!d || d.snapshots.length === 0 ? <p className="text-sm text-muted">No snapshots yet. One is saved automatically before every reset or restore.</p> : (
          <Table head={["#", "When (UTC)", "What", "Settings", ""]} caption="Settings snapshots" rows={d.snapshots.map((s) => [String(s.id), s.at, s.label, String(s.count),
            <button key="r" className="btn" onClick={() => act(() => postJson("/api/system/settings/restore", { id: s.id }), `Restored snapshot #${s.id}.`)}>Restore</button>])} />
        )}
      </Section>
      {d && <Stat label="Backup keep (Practice / Real)" value={`${String(d.settings.practice?.backup_keep)} / ${String(d.settings.real?.backup_keep)}`} sub={`Auto backup: ${String(d.settings.practice?.auto_backup)} / ${String(d.settings.real?.auto_backup)}`} />}
    </div>
  );
}
