"use client";
import { useCallback, useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson, putJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";
import type { DbaBench, DbaHealth, GovAccess, GovCatalog, GovControls, GovLineage, GovPii } from "@/lib/types";
import { DrillSection } from "./OpsPanels";
import { Badge, Field, Section, Stat, Table, Tabs, bytes, errMsg, num } from "./kit";

const tone = (l: string) => (l === "high" || l === "critical" ? "bad" : l === "medium" || l === "warn" || l === "warning" ? "warn" : "muted");

export function DbaPanel() {
  const c = useChartColors();
  const [h, setH] = useState<DbaHealth | null>(null);
  const [b, setB] = useState<DbaBench | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ver, setVer] = useState(0);
  const load = useCallback(async () => { setVer((v) => v + 1); }, []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<DbaHealth>("/api/dba/health", ctl.signal).then((r) => { setH(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load database health.")); });
    return () => ctl.abort();
  }, [ver]);
  const run = async (fn: () => Promise<unknown>, done: (r: unknown) => string) => {
    setBusy(true); setMsg(null);
    try { const r = await fn(); setMsg(done(r)); await load(); } catch (e) { setErr(errMsg(e, "That failed.")); } finally { setBusy(false); }
  };
  if (!h) return <>{err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>}</>;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {msg && <p role="status" className="card p-3 text-sm">{msg}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Database size" value={bytes(h.file.size_bytes)} sub={`${h.engine} · WAL ${bytes(h.file.wal_bytes)}`} />
        <Stat label="Free blocks" value={`${h.blocks.free_pct}%`} sub={`${h.blocks.free}/${h.blocks.total} blocks reclaimable`} />
        <Stat label="Backups" value={String(h.backup.count)} sub={h.backup.age_hours == null ? "none yet" : `latest ${num(h.backup.age_hours, 1)} h ago`} />
        <Stat label="Tables / views" value={`${h.tables.length} / ${h.views}`} sub={h.access} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="btn" disabled={busy} onClick={() => run(() => postJson("/api/dba/checkpoint", {}), () => "Checkpoint done: the write-ahead log was merged into the database file.")}>Run CHECKPOINT</button>
        <button className="btn" disabled={busy} onClick={() => run(() => postJson<{ ok: boolean; detail?: string; message?: string }>("/api/dba/verify-backup", {}), (r) => { const x = r as { ok?: boolean; detail?: string; message?: string }; return `Backup check ${x.ok ? "passed" : "FAILED"}: ${x.detail ?? x.message ?? ""}`; })}>Verify latest backup</button>
        <button className="btn" disabled={busy} onClick={() => run(async () => setB(await getJson<DbaBench>("/api/dba/benchmarks")), () => "Benchmarks finished.")}>Run query benchmarks</button>
      </div>
      <Section title="Findings (what to do next)">
        {h.findings.length === 0 ? <p className="text-sm text-muted">Nothing to flag.</p> : <ul className="space-y-2 text-sm">{h.findings.map((f, i) => <li key={i}><Badge tone={tone(f.level)}>{f.level}</Badge> {f.text} <span className="text-muted">→ {f.action}</span></li>)}</ul>}
      </Section>
      <DrillSection onDone={load} />
      <Section title="Integrity checks">
        <Table head={["Check", "Result", "Detail", "Fix"]} rows={h.integrity.map((i) => [i.name, <Badge key="r" tone={i.ok ? "ok" : "bad"}>{i.ok ? "pass" : "fail"}</Badge>, i.detail, i.fix ?? ""])} />
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Size growth" note="One snapshot per hour while the app runs; growth needs time to show.">
          {h.growth.length < 2 ? <p className="text-sm text-muted">Collecting snapshots. Check back later.</p> : (
            <div className="h-48" role="img" aria-label="Database size over time"><ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <LineChart data={h.growth}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="at" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5, 16)} /><YAxis stroke={c.axis} fontSize={11} width={48} tickFormatter={(v: number) => bytes(v)} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} formatter={(v) => bytes(Number(v))} /><Line dataKey="size_bytes" stroke={c.revenue} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>)}
        </Section>
        <Section title="Memory by component"><Table head={["Component", "Size"]} rows={h.memory.filter((m) => m.bytes > 0).map((m) => [m.tag, bytes(m.bytes)])} /></Section>
      </div>
      <Section title="Tables"><Table caption="Tables" head={["Table", "Rows", "Columns", "Primary key", "Indexes"]} rows={h.tables.map((t) => [t.name, t.rows.toLocaleString(), t.columns, t.has_pk ? <Badge key="p" tone="ok">yes</Badge> : <Badge key="p" tone="warn">no</Badge>, t.indexes])} /></Section>
      <Section title="Constraints"><Table head={["Table", "Type", "Columns"]} rows={h.constraints.map((k) => [k.table, k.type, k.columns.join(", ")])} /></Section>
      {b && <Section title="Query benchmarks" note={b.reading}>
        <Table head={["Query", "Median ms", "Runs", "Scans", "Note"]} rows={b.queries.map((q) => [<span key="n" title={q.sql}>{q.name}</span>, <span key="m" className={q.slow ? "text-amber-600" : ""}>{num(q.median_ms, 2)}</span>, q.runs_ms.map((x) => num(x, 1)).join(" · "), q.scans, q.note])} />
        <details className="mt-2 text-xs"><summary className="cursor-pointer">Query plans</summary>{b.queries.map((q) => <div key={q.name} className="mt-2"><b>{q.name}</b><pre className="overflow-auto rounded bg-panel2 p-2" tabIndex={0}>{q.plan}</pre></div>)}</details>
      </Section>}
      <Section title="Engine settings"><Table head={["Setting", "Value"]} rows={h.settings.map((s) => [s.name, s.value])} /></Section>
    </div>
  );
}

const GTABS = [{ id: "catalog", label: "Catalog" }, { id: "pii", label: "PII scan" }, { id: "lineage", label: "Lineage" }, { id: "controls", label: "Controls" }, { id: "access", label: "Access" }];
export function GovernancePanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return <div className="space-y-4"><Tabs tabs={GTABS} value={tab} onChange={onTab} label="Governance views" />
    {tab === "catalog" && <Catalog />}{tab === "pii" && <Pii />}{tab === "lineage" && <Lineage />}{tab === "controls" && <Controls />}{tab === "access" && <Access />}</div>;
}
function useLoad<T>(path: string) {
  const [d, setD] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  const load = useCallback(async () => { setVer((v) => v + 1); }, []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<T>(path, ctl.signal).then((r) => { setD(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load.")); });
    return () => ctl.abort();
  }, [path, ver]);
  return { d, err, load, setErr };
}

function Catalog() {
  const { d, err, load, setErr } = useLoad<GovCatalog>("/api/governance/catalog");
  const [edit, setEdit] = useState<string | null>(null);
  const [f, setF] = useState({ owner: "", steward: "", description: "", classification: "", retention_days: "", retention_column: "" });
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  const start = (a: GovCatalog["assets"][number]) => { setEdit(a.name); setF({ owner: a.owner ?? "", steward: a.steward ?? "", description: a.description ?? "", classification: a.classification ?? "", retention_days: a.retention_days == null ? "" : String(a.retention_days), retention_column: a.retention_column ?? "" }); };
  const save = async () => { try { await putJson(`/api/governance/assets/${encodeURIComponent(edit!)}`, f); setEdit(null); await load(); } catch (e) { setErr(errMsg(e, "Couldn't save.")); } };
  const a = d.assets.find((x) => x.name === edit);
  return (
    <div className="space-y-4">
      <Section title="Data catalog" note="Owner = accountable for the data. Steward = looks after its quality day to day. Classification is yours to set; the suggestion comes from the PII scan.">
        <Table caption="Data catalog" head={["Asset", "Rows", "Owner", "Steward", "Class", "Suggested", "Complete", "Dupes", "Retention", ""]}
          rows={d.assets.filter((x) => !x.system).map((x) => [x.name, x.rows.toLocaleString(), x.owner ?? <Badge key="o" tone="warn">none</Badge>, x.steward ?? "—", x.classification ?? <Badge key="c" tone="warn">unclassified</Badge>, x.suggested_classification,
            x.completeness_pct == null ? "—" : `${x.completeness_pct}%`, x.duplicate_rows, x.retention_days == null ? "—" : `${x.retention_days} d${x.retention_eligible_rows ? ` (${x.retention_eligible_rows} past)` : ""}`,
            <button key="e" className="btn !py-0.5 text-xs" onClick={() => start(x)}>Edit</button>])} />
      </Section>
      {a && (
        <Section title={`Edit ${a.name}`}>
          <div className="grid gap-2 sm:grid-cols-3">
            <Field label="Owner"><input className="field" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} /></Field>
            <Field label="Steward"><input className="field" value={f.steward} onChange={(e) => setF({ ...f, steward: e.target.value })} /></Field>
            <Field label="Classification"><select className="field" value={f.classification} onChange={(e) => setF({ ...f, classification: e.target.value })}><option value="">unclassified</option>{d.classes.map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Retention (days)"><input className="field" inputMode="numeric" value={f.retention_days} onChange={(e) => setF({ ...f, retention_days: e.target.value })} /></Field>
            <Field label="Retention date column"><select className="field" value={f.retention_column} onChange={(e) => setF({ ...f, retention_column: e.target.value })}><option value="">—</option>{a.columns.map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
            <Field label="Description"><input className="field" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
          </div>
          <p className="mt-2 text-xs text-muted">{Object.entries(d.classes_help).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
          <div className="mt-3 flex gap-2"><button className="btn btn-primary" onClick={save}>Save</button><button className="btn" onClick={() => setEdit(null)}>Cancel</button></div>
        </Section>
      )}
    </div>
  );
}

function Pii() {
  const { d, err, load, setErr } = useLoad<GovPii>("/api/governance/pii-scan");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Scanning…</p>;
  const protect = async (cols: string[]) => { try { await postJson("/api/governance/protect", { columns: cols }); await load(); } catch (e) { setErr(errMsg(e, "Couldn't protect.")); } };
  const open = d.findings.filter((x) => !x.protected_from_ai).map((x) => x.column);
  return (
    <Section title={`Personal-data scan (${d.unprotected} unprotected)`} note={d.note}>
      {d.findings.length === 0 ? <p className="text-sm">Nothing obvious found.</p> : (
        <>
          <Table caption="PII findings" head={["Table", "Column", "Looks like", "Evidence", "Confidence", "AI access", ""]}
            rows={d.findings.map((x) => [x.table, x.column, x.category, x.evidence, <Badge key="c" tone={tone(x.confidence)}>{x.confidence}</Badge>, x.protected_from_ai ? <Badge key="p" tone="ok">blocked</Badge> : <Badge key="p" tone="warn">visible to AI</Badge>,
              x.protected_from_ai ? "" : <button key="b" className="btn !py-0.5 text-xs" onClick={() => protect([x.column])}>Protect from AI</button>])} />
          {open.length > 1 && <button className="btn mt-3" onClick={() => protect(Array.from(new Set(open)))}>Protect all {open.length}</button>}
        </>
      )}
    </Section>
  );
}

function Lineage() {
  const { d, err } = useLoad<GovLineage>("/api/governance/lineage");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <Section title="Where the data flows" note={d.pipeline}>
        <Table head={["From", "To", "How"]} rows={d.edges.map((e) => [e.from, e.to, e.kind])} />
      </Section>
      <Section title="What reads it"><Table head={["Consumer", "Reads"]} rows={d.consumers.map((c) => [c.name, c.reads])} /></Section>
    </div>
  );
}
function Controls() {
  const { d, err } = useLoad<GovControls>("/api/governance/controls");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <Section title={`Governance controls: ${d.in_place}/${d.total} in place`} note="A self-assessment from facts this app can see. It is not a compliance certification.">
      <ul className="space-y-2 text-sm">{d.controls.map((c) => <li key={c.id}><Badge tone={c.ok ? "ok" : "warn"}>{c.ok ? "in place" : "gap"}</Badge> <b>{c.title}</b> <span className="text-muted">{c.detail}{!c.ok && c.fix ? ` → ${c.fix}` : ""}</span></li>)}</ul>
    </Section>
  );
}
function Access() {
  const { d, err } = useLoad<GovAccess>("/api/governance/access");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="AI privacy mode" value={d.ai.mode} sub={`${d.ai.blocked_columns.length} blocked column(s)`} /><Stat label="Failed actions" value={String(d.failed_total)} sub={`since ${d.since}`} /><Stat label="Data leaving" value={String(d.data_leaving.length)} sub="exports and AI calls" /></div>
      <Section title="Activity by action" note={d.note}><Table head={["Action", "Count", "Failed"]} rows={d.by_action.map((a) => [a.action, a.n, a.failed])} /></Section>
    </div>
  );
}
