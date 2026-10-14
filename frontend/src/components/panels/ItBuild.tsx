"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Field, Section, Stat, Table, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const kb = (n: number) => (n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`);

export function InventoryImport({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState("");
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const go = () => { setErr(null); postJson<R>("/api/it-agent/import", { text }).then((r) => { setRes(r); onDone(); }).catch((e) => { setRes(null); setErr(errMsg(e, "That did not import.")); }); };
  return (
    <Section title="Import from the inventory agent" note="Run the small agent script on each computer you own or administer (it reads the computer's name, system, memory, disks and serial number; it collects no files, apps or user data and sends nothing). Paste its output here: one report, a list, or one per line.">
      <div className="flex flex-wrap items-center gap-2"><a className="btn" href="/api/it-agent/script" download="inventory_agent.py">Download the agent script</a><span className="text-xs text-muted">Run: python inventory_agent.py --out pc01.json</span></div>
      <textarea className="field mt-2 h-28 w-full font-mono text-xs" aria-label="Agent reports" value={text} onChange={(e) => setText(e.target.value)} placeholder='{"schema": 1, "hostname": "PC-01", ...}' />
      <div className="mt-2"><button className="btn btn-primary" disabled={!text.trim()} onClick={go}>Import</button></div>
      {err && <ErrorBanner message={err} />}
      {res && <div className="mt-2 space-y-1 text-sm"><p>Added: {res.created.join(", ") || "none"}. Updated: {res.updated.join(", ") || "none"}.</p>{res.skipped.length > 0 && <ul className="list-disc pl-5 text-amber-600">{res.skipped.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>}<p className="text-xs text-muted">{res.note}</p></div>}
    </Section>
  );
}

export function BackupLab() {
  const [st, setSt] = useState<R | null>(null);
  const [out, setOut] = useState<{ title: string; data: R } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<R | null>(null);
  const [keep, setKeep] = useState("2");
  useEffect(() => { getJson<R>("/api/backuplab").then(setSt).catch((e) => setErr(errMsg(e, "Could not load the practice area."))); getJson<R>("/api/backuplab/reference").then(setInfo).catch(() => setInfo(null)); }, []);
  const call = (title: string, path: string, body?: R) => {
    setErr(null);
    postJson<R>(path, body ?? {}).then((r) => {
      if (r.snapshots && r.files) setSt({ files: r.files, snapshots: r.snapshots, ready: r.ready });
      setOut(title === "Practice area" ? null : { title, data: r.result ?? r });
    }).catch((e) => setErr(errMsg(e, "That did not work.")));
  };
  const refresh = () => getJson<R>("/api/backuplab").then(setSt).catch(() => undefined);
  const edit = (a: string) => postJson<R>("/api/backuplab/edit", { action: a }).then((r) => { setSt(r); setOut(null); }).catch((e) => setErr(errMsg(e, "That did not work.")));
  const last = st?.snapshots?.[st.snapshots.length - 1];
  return (
    <Section title="Backup practice area" note="A private sample folder to practise on. Take a backup, change the files, take another (only the changes are stored), then run a restore drill and see what you would lose. You can also damage a stored file to see a check catch it. Nothing outside the practice area is touched.">
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Backup practice steps">
        <button className="btn" onClick={() => call("Practice area", "/api/backuplab/reset")}>Reset practice folder</button>
        <button className="btn btn-primary" disabled={!st?.ready} onClick={() => call("Backup result", "/api/backuplab/snapshot", { label: "practice" })}>Take a backup</button>
        <button className="btn" disabled={!st?.ready} onClick={() => edit("modify")}>Edit a file</button>
        <button className="btn" disabled={!st?.ready} onClick={() => edit("add")}>Add a file</button>
        <button className="btn" disabled={!st?.ready} onClick={() => edit("delete")}>Delete a file</button>
        <button className="btn" disabled={!last} onClick={() => call("Check of the backup", "/api/backuplab/verify")}>Verify backup</button>
        <button className="btn" disabled={!last} onClick={() => edit("corrupt").then(refresh)}>Damage a stored file</button>
      </div>
      {err && <ErrorBanner message={err} />}
      {st && (
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <Table caption="Practice folder (live files)" head={["File", "Size"]} rows={st.files.map((f: R) => [f.name, kb(f.bytes)])} />
          <Table caption="Backups taken" head={["Snapshot", "Files", "Size", "Actions"]} rows={st.snapshots.map((s: R) => [s.id, s.files, kb(s.bytes),
            <span key={s.id} className="flex gap-1"><button className="btn !py-0.5 text-xs" onClick={() => call("Restore drill", "/api/backuplab/drill", { id: s.id })}>Drill</button><button className="btn !py-0.5 text-xs" onClick={() => call("Restore", "/api/backuplab/restore", { id: s.id })}>Restore</button></span>])} />
        </div>
      )}
      {st && st.snapshots.length > 1 && <div className="mt-2 flex items-end gap-2"><Field label="Keep newest"><input className="field !w-20" type="number" min={1} value={keep} onChange={(e) => setKeep(e.target.value)} aria-label="Snapshots to keep" /></Field><button className="btn" onClick={() => call("Prune", "/api/backuplab/prune", { keep: Number(keep) })}>Remove older backups</button></div>}
      {out && (
        <div className="mt-3 space-y-2 text-sm" role="status">
          <h4 className="font-semibold">{out.title}</h4>
          {out.data.reading && <p>{out.data.reading}</p>}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(out.data).filter(([, v]) => v === null || typeof v !== "object").filter(([k]) => !["reading", "lesson"].includes(k)).slice(0, 8).map(([k, v]) => <Stat key={k} label={k.replace(/_/g, " ")} value={String(v)} />)}
          </div>
          {["added", "changed", "removed", "changed_since", "deleted_since", "new_since", "failed", "corrupt", "missing", "files"].map((k) => Array.isArray(out.data[k]) && out.data[k].length > 0 && typeof out.data[k][0] === "string" ? <p key={k}><b>{k.replace(/_/g, " ")}:</b> {out.data[k].join(", ")}</p> : null)}
          {out.data.lesson && <p className="text-xs text-muted">{out.data.lesson}</p>}
        </div>
      )}
      <details className="mt-3 text-sm"><summary className="cursor-pointer">Use it on your real folders</summary>
        <p className="mt-1">The same engine is a command-line tool: <code>python scripts/backup_tool.py backup &lt;folder&gt; &lt;backup folder&gt;</code>, then <code>verify</code>, <code>drill</code> and <code>restore</code>. Keep the backup on a different disk and copy it off-site (3-2-1). For important data also consider restic, Borg or Veeam.</p></details>
      {info && <>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes common in backup advice</summary><ul className="list-disc pl-5">{info.slips.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary><ul className="list-disc pl-5">{info.not_built.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      </>}
    </Section>
  );
}
