"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, apiFetch, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Client = { id: number; name: string };
type F = { name: string; label: string; choices?: string[]; bool?: boolean; placeholder?: string };
type Row = Record<string, string | number | boolean | null> & { id: number };

const KINDS: Record<string, { title: string; fields: F[]; cols: string[]; note: string }> = {
  backups: { title: "Backup restore tests", note: "Log each time you restored something from a backup as a test. A system with no recent passing test is flagged.", cols: ["system", "date", "result", "every_days", "note"],
    fields: [{ name: "system", label: "Backup or system", placeholder: "Office NAS" }, { name: "result", label: "Result", choices: ["ok", "fail"] }, { name: "date", label: "Date (YYYY-MM-DD)", placeholder: "today" }, { name: "every_days", label: "Test every (days)", placeholder: "30" }, { name: "note", label: "Note" }] },
  accounts: { title: "Account inventory", note: "Key accounts, who owns them, and how they are protected. Do not type passwords or recovery codes here, only whether they are stored.", cols: ["name", "kind", "owner", "mfa", "recovery_stored", "shared", "last_review"],
    fields: [{ name: "name", label: "Account" }, { name: "kind", label: "Kind", choices: ["email", "money", "cloud", "social", "website", "other"] }, { name: "owner", label: "Owner" }, { name: "mfa", label: "Two-step sign-in", choices: ["app", "key", "sms", "none", "unknown"] },
             { name: "recovery_stored", label: "Recovery codes stored safely", bool: true }, { name: "shared", label: "Shared login", bool: true }, { name: "last_review", label: "Last review (YYYY-MM-DD)" }] },
  devices: { title: "Device inventory", note: "Devices and their operating system. End-of-support dates come from a short built-in list or the date you type; confirm on the vendor's page.", cols: ["name", "kind", "os", "os_version", "eol_date", "last_seen"],
    fields: [{ name: "name", label: "Device" }, { name: "kind", label: "Kind", choices: ["pc", "laptop", "phone", "server", "router", "camera", "printer", "other"] }, { name: "os", label: "Operating system", placeholder: "Windows 10 Pro" }, { name: "os_version", label: "Version" }, { name: "eol_date", label: "End of support (YYYY-MM-DD, optional)" }, { name: "last_seen", label: "Last seen (YYYY-MM-DD)" }] },
  timeline: { title: "Incident timeline", note: "Record what happened and what you did, as it happens. Export it as a page for an insurer, lawyer or the client.", cols: ["at", "kind", "what", "who", "incident"],
    fields: [{ name: "kind", label: "Type", choices: ["detected", "action", "contact", "evidence", "recovery", "note"] }, { name: "what", label: "What happened or was done" }, { name: "at", label: "When (YYYY-MM-DDTHH:MM, blank = now)" }, { name: "who", label: "Who" }, { name: "incident", label: "Incident name" }] },
};
type Cmp = { says: string; fixed: { title: string; severity: string }[]; new: { title: string; severity: string }[]; still_open: { title: string; severity: string }[]; got_worse: { title: string }[]; caution: string; from: { date: string; band: string }; to: { date: string; band: string } };
type Status = { systems?: { system: string; status: string; last_test: string; next_due: string; last_success: string | null }[]; flags?: { account: string; severity: string; reasons: string[] }[]; devices?: { name: string; status: string; eol: string | null; days_to_eol: number | null; eol_source: string | null }[]; note?: string; caution?: string };

function Records({ kind, cid, onFix }: { kind: string; cid: number; onFix: (id: string) => void }) {
  const spec = KINDS[kind];
  const [rows, setRows] = useState<Row[]>([]);
  const [st, setSt] = useState<Status | null>(null);
  const [f, setF] = useState<Record<string, string | boolean>>({});
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const statusPath = { backups: "backups/status", accounts: "accounts/review", devices: "devices/status" }[kind];
  useEffect(() => {
    let live = true;
    Promise.all([getJson<{ rows: Row[] }>(`/api/sectrack/${kind}/list/${cid}`), statusPath ? getJson<Status>(`/api/sectrack/${cid}/${statusPath}`) : Promise.resolve(null)])
      .then(([r, s]) => { if (live) { setRows(r.rows); setSt(s); } }).catch((e) => { if (live) setErr(errMsg(e, "Could not load.")); });
    return () => { live = false; };
  }, [kind, cid, statusPath, tick]);
  async function add() { setErr(null); try { await postJson(`/api/sectrack/${kind}`, { client_id: cid, ...f }); setF({}); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not add.")); } }
  async function del(id: number) { setErr(null); const r = await apiFetch(`${API_BASE}/api/sectrack/${kind}/${id}`, { method: "DELETE" }); if (!r.ok) setErr("Could not delete."); setTick((t) => t + 1); }
  const tone = (s: string) => (s === "ok" ? "ok" : s === "failed" || s === "expired" || s === "high" ? "bad" : "warn") as "ok" | "bad" | "warn";
  return (
    <Section title={spec.title} note={spec.note}>
      {err && <ErrorBanner message={err} />}
      {st?.systems && <ul className="mb-3 grid gap-1 text-sm">{st.systems.map((s) => <li key={s.system}><Badge tone={tone(s.status)}>{s.status}</Badge> {s.system}: last test {s.last_test}, next due {s.next_due}{s.last_success ? `, last success ${s.last_success}` : ", never passed"}</li>)}{st.systems.some((s) => s.status !== "ok") && <li><button className="btn" onClick={() => onFix("restore-test")}>How to test a restore</button></li>}</ul>}
      {st?.flags && <ul className="mb-3 grid gap-1 text-sm">{st.flags.length === 0 && <li className="text-muted">No account flags.</li>}{st.flags.map((x) => <li key={x.account}><Badge tone={tone(x.severity)}>{x.severity}</Badge> {x.account}: {x.reasons.join("; ")}</li>)}{st.flags.length > 0 && <li><button className="btn" onClick={() => onFix("account-review")}>How to review accounts</button></li>}</ul>}
      {st?.devices && <ul className="mb-3 grid gap-1 text-sm">{st.devices.map((d) => <li key={d.name}><Badge tone={tone(d.status)}>{d.status}</Badge> {d.name}: {d.eol ? `support ends ${d.eol} (${d.eol_source}), ${d.days_to_eol! < 0 ? `${-d.days_to_eol!} days ago` : `in ${d.days_to_eol} days`}` : "end-of-support date unknown"}</li>)}{st.devices.some((d) => d.status === "expired" || d.status === "soon") && <li><button className="btn" onClick={() => onFix("device-eol")}>What to do about old devices</button></li>}{st.note && <li className="text-xs text-muted">{st.note}</li>}</ul>}
      {rows.length > 0 && <div className="mb-3 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted">{spec.cols.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}<th /></tr></thead><tbody>{rows.map((r) => <tr key={r.id}>{spec.cols.map((c) => <td key={c}>{typeof r[c] === "boolean" ? (r[c] ? "yes" : "no") : String(r[c] ?? "").replace("T", " ")}</td>)}<td><button className="btn" aria-label={`Delete ${kind} ${r.id}`} onClick={() => del(r.id)}>Delete</button></td></tr>)}</tbody></table></div>}
      <div className="flex flex-wrap items-end gap-2">
        {spec.fields.map((x) => x.bool ? <label key={x.name} className="flex items-center gap-1 text-xs text-muted"><input type="checkbox" checked={!!f[x.name]} onChange={(e) => setF({ ...f, [x.name]: e.target.checked })} />{x.label}</label>
          : <Field key={x.name} label={x.label}>{x.choices ? <select aria-label={`${spec.title} ${x.label}`} className="input" value={String(f[x.name] ?? "")} onChange={(e) => setF({ ...f, [x.name]: e.target.value })}><option value="">Choose…</option>{x.choices.map((c) => <option key={c}>{c}</option>)}</select>
            : <input aria-label={`${spec.title} ${x.label}`} className="input" placeholder={x.placeholder} value={String(f[x.name] ?? "")} onChange={(e) => setF({ ...f, [x.name]: e.target.value })} />}</Field>)}
        <button className="btn" onClick={add}>Add</button>
        {kind === "timeline" && <a className="btn" href={`${API_BASE}/api/sectrack/${cid}/timeline/html`} target="_blank" rel="noopener noreferrer">Export as a page</a>}
      </div>
    </Section>
  );
}

function Compare({ cid }: { cid: number }) {
  const [hist, setHist] = useState<{ id: number; date: string; band: string }[]>([]);
  const [cmp, setCmp] = useState<Cmp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => { let live = true; getJson<{ reports: { id: number; date: string; band: string }[] }>(`/api/sectrack/${cid}/reports`).then((r) => { if (live) setHist(r.reports); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load.")); }); return () => { live = false; }; }, [cid, tick]);
  async function compare() { setErr(null); try { setCmp(await getJson<Cmp>(`/api/sectrack/${cid}/compare`)); } catch (e) { setErr(errMsg(e, "Could not compare.")); } }
  return (
    <Section title="Checkup history and re-check" note="Save a report for this client from the Checkup report tab (use 'Save for this client'), then compare the newest with the one before it.">
      {err && <ErrorBanner message={err} />}
      <ul className="text-sm">{hist.map((h) => <li key={h.id}>{h.date}: {h.band}</li>)}{hist.length === 0 && <li className="text-muted">No saved reports yet.</li>}</ul>
      <div className="mt-2 flex gap-2"><button className="btn" disabled={hist.length < 2} onClick={compare}>Compare the latest two</button><button className="btn" onClick={() => setTick((t) => t + 1)}>Refresh</button></div>
      {cmp && (
        <div className="mt-3 text-sm"><p className="font-medium">{cmp.says} ({cmp.from.band} to {cmp.to.band})</p>
          {([["Fixed", cmp.fixed, "ok"], ["New", cmp.new, "bad"], ["Still open", cmp.still_open, "warn"]] as const).map(([t, l, tn]) => <div key={t} className="mt-2"><Badge tone={tn}>{t} ({l.length})</Badge><ul className="list-disc pl-5">{l.map((i, k) => <li key={k}>{i.title} <span className="text-xs text-muted">{i.severity}</span></li>)}</ul></div>)}
          <p className="mt-2 text-xs text-muted">{cmp.caution}</p></div>
      )}
    </Section>
  );
}

export function ClientRecords({ onFix }: { onFix: (id: string) => void }) {
  const [list, setList] = useState<Client[]>([]);
  const [cid, setCid] = useState<number | null>(null);
  const [sub, setSub] = useState("compare");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { let live = true; getJson<{ clients: Client[] }>("/api/clients").then((r) => { if (live) setList(r.clients); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load clients.")); }); return () => { live = false; }; }, []);
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Client security records" note="Records live with each client from the Clients page. In Practice they are sample data; in Real they are your clients'.">
        <Field label="Client"><select aria-label="Security records client" className="input" value={cid ?? ""} onChange={(e) => setCid(e.target.value ? Number(e.target.value) : null)}><option value="">Choose a client…</option>{list.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        {list.length === 0 && <p className="mt-2 text-xs text-muted">No clients yet. Add one on the Clients page first.</p>}
        {cid && <div className="mt-3 flex flex-wrap gap-2" role="tablist" aria-label="Record type">{[["compare", "Re-check history"], ["backups", "Backup restores"], ["accounts", "Accounts"], ["devices", "Devices"], ["timeline", "Incident timeline"]].map(([id, l]) => <button key={id} role="tab" aria-selected={sub === id} className={`btn ${sub === id ? "btn-primary" : ""}`} onClick={() => setSub(id)}>{l}</button>)}</div>}
      </Section>
      {cid && sub === "compare" && <Compare key={cid} cid={cid} />}
      {cid && sub !== "compare" && <Records key={`${sub}-${cid}`} kind={sub} cid={cid} onFix={onFix} />}
    </div>
  );
}
