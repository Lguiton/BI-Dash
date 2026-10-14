"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, Table, Tabs, errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";

interface HubRow { table: string; label: string; source: string; rows: number; columns: number; updated_at: string | null; tags: string[]; has_note: boolean }
interface ColInfo { name: string; type: string; kind: string; nulls: number; distinct_count: number; min?: number; max?: number; mean?: number; median?: number; top?: { value: string; n: number }[] }
interface Summary { table: string; rows: number; columns: ColInfo[]; checks: { level: string; title: string; why: string }[]; grade: string; ideas: string[]; note: string; tags: string[] }
interface Rule { id: number; table: string; kind: string; params: Record<string, unknown>; text: string }
interface Suggestion { kind: string; params: Record<string, unknown>; text: string; why: string }
interface RunRes { table: string; rules: number; failed: number; passed: number; results: { id: number; text: string; passed: boolean; failing: number; total: number; unit: string; sample: Record<string, unknown>[] }[]; at: string }
interface Hist { id: number; at: string; table_name: string; total: number; failed: number; trigger: string }

const tone = (l: string): "ok" | "warn" | "bad" | "muted" => (l === "bad" || l === "fail" ? "bad" : l === "warn" ? "warn" : l === "ok" ? "ok" : "muted");

export default function HubPage() {
  const [rows, setRows] = useState<HubRow[] | null>(null);
  const [sel, setSel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ tables: HubRow[] }>("/api/hub", ctl.signal).then((d) => { setRows(d.tables); setSel((s) => s || d.tables[0]?.table || ""); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load your tables.")); });
    return () => ctl.abort();
  }, [ver]);
  return (
    <PageShell title="Dataset hub" subtitle="Everything you've imported, with a health check, notes, tags and quality rules. Our own small take on a data catalogue.">
      {err && <ErrorBanner message={err} />}
      {!rows && !err && <p className="text-sm text-muted">Loading…</p>}
      {rows && rows.length === 0 && <section className="card p-5 text-sm">You haven&apos;t imported a table yet. Add one in <Link className="underline" href="/data">My data</Link>, or build one with the <Link className="underline" href="/workflow">Workflow builder</Link>.</section>}
      {rows && rows.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)]">
          <Section title="Your tables">
            <ul className="space-y-1">{rows.map((r) => (
              <li key={r.table}><button className={`btn w-full justify-between ${sel === r.table ? "btn-primary" : ""}`} onClick={() => setSel(r.table)} aria-pressed={sel === r.table}>
                <span className="truncate">{r.label}</span><span className="text-xs opacity-80">{r.rows.toLocaleString()} rows</span></button></li>
            ))}</ul>
          </Section>
          {sel && <TableDetail key={sel} table={sel} onChange={() => setVer((v) => v + 1)} />}
        </div>
      )}
    </PageShell>
  );
}

function TableDetail({ table, onChange }: { table: string; onChange: () => void }) {
  const [tab, setTab] = useState("health");
  const [s, setS] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [tags, setTags] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Summary>(`/api/hub/${encodeURIComponent(table)}`, ctl.signal).then((d) => { setS(d); setNote(d.note); setTags(d.tags.join(", ")); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't read that table.")); });
    return () => ctl.abort();
  }, [table]);
  const saveNotes = async () => {
    setErr(null); setSaved(false);
    try { await putJson(`/api/hub/${encodeURIComponent(table)}/notes`, { note, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }); setSaved(true); onChange(); } catch (e) { setErr(errMsg(e, "Couldn't save the notes.")); }
  };
  if (!s) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="min-w-0 space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold">{s.table}</h2><Badge tone={s.grade.startsWith("good") ? "ok" : s.grade.includes("notes") ? "warn" : "bad"}>{s.grade}</Badge><span className="text-sm text-muted">{s.rows.toLocaleString()} rows, {s.columns.length} columns</span></div>
      <Tabs tabs={[{ id: "health", label: "Health" }, { id: "columns", label: "Columns" }, { id: "notes", label: "Notes & tags" }, { id: "rules", label: "Quality rules" }]} value={tab} onChange={setTab} label="Table views" />
      {tab === "health" && (
        <>
          <Section title="Checks">
            {s.checks.length === 0 ? <p className="text-sm text-muted">Nothing worth flagging.</p> :
              <ul className="space-y-2">{s.checks.map((c, i) => <li key={i} className="rounded border border-line p-2 text-sm"><div className="flex items-center gap-2"><Badge tone={tone(c.level)}>{c.level}</Badge><span>{c.title}</span></div><p className="mt-1 text-xs text-muted">{c.why}</p></li>)}</ul>}
          </Section>
          <Section title="Ideas to try next"><ul className="list-disc space-y-1 pl-5 text-sm">{s.ideas.map((i) => <li key={i}>{i}</li>)}</ul></Section>
        </>
      )}
      {tab === "columns" && (
        <Section title="Columns" note="Blanks and distinct counts are computed on the full table.">
          <Table head={["Column", "Type", "Blank", "Distinct", "Range / top values"]} caption="Columns" rows={s.columns.map((c) => [c.name, c.type, c.nulls.toLocaleString(), c.distinct_count.toLocaleString(),
            c.kind === "number" ? `${c.min} to ${c.max} (mean ${c.mean != null ? Math.round(c.mean * 100) / 100 : "—"})` : (c.top ?? []).map((t) => `${t.value} (${t.n})`).join(", ")])} />
        </Section>
      )}
      {tab === "notes" && (
        <Section title="Notes and tags" note="Saved with the workspace. Handy for where the data came from and what to watch for.">
          <textarea className="field w-full" rows={4} aria-label="Notes" value={note} onChange={(e) => { setNote(e.target.value); setSaved(false); }} />
          <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Tags (comma separated)"><input className="field w-64 max-w-full" value={tags} onChange={(e) => { setTags(e.target.value); setSaved(false); }} /></Field>
            <button className="btn btn-primary" onClick={saveNotes}>Save</button>{saved && <span role="status" className="text-xs text-emerald-600">Saved</span>}</div>
        </Section>
      )}
      {tab === "rules" && <Rules table={table} />}
    </div>
  );
}

function Rules({ table }: { table: string }) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [sug, setSug] = useState<Suggestion[]>([]);
  const [run, setRun] = useState<RunRes | null>(null);
  const [hist, setHist] = useState<Hist[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([getJson<{ rules: Rule[] }>("/api/dq/rules", ctl.signal), getJson<{ runs: Hist[] }>(`/api/dq/history?table=${encodeURIComponent(table)}`, ctl.signal), getJson<{ suggestions: Suggestion[] }>(`/api/dq/suggest?table=${encodeURIComponent(table)}`, ctl.signal)])
      .then(([r, h, s]) => { setRules(r.rules.filter((x) => x.table === table)); setHist(h.runs); setSug(s.suggestions); })
      .catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the rules.")); });
    return () => ctl.abort();
  }, [table, ver]);
  const act = async (f: () => Promise<unknown>, m: string) => { setErr(null); try { await f(); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, m)); } };
  const have = new Set(rules.map((r) => r.text));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Rules on this table" note="Rules are checked when you press Run (or by a pipeline). A failing rule shows up in the alerts on the dashboard.">
        {rules.length === 0 ? <p className="text-sm text-muted">No rules yet. Add some from the suggestions below.</p> :
          <ul className="space-y-1 text-sm">{rules.map((r) => <li key={r.id} className="flex items-center gap-2"><span className="min-w-0 flex-1">{r.text}</span><button className="btn" aria-label={`Delete rule ${r.text}`} onClick={() => act(() => deleteJson(`/api/dq/rules/${r.id}`), "Couldn't delete.")}>Delete</button></li>)}</ul>}
        <button className="btn btn-primary mt-3" disabled={rules.length === 0} onClick={() => act(async () => setRun(await postJson<RunRes>(`/api/dq/run?table=${encodeURIComponent(table)}`, {})), "The run failed.")}>Run rules now</button>
      </Section>
      {run && (
        <Section title={`${run.passed} passed, ${run.failed} failed`}>
          <ul className="space-y-2 text-sm">{run.results.map((r) => (
            <li key={r.id} className="rounded border border-line p-2"><div className="flex items-center gap-2"><Badge tone={r.passed ? "ok" : "bad"}>{r.passed ? "pass" : "fail"}</Badge><span>{r.text}</span>{!r.passed && <span className="text-xs text-muted">{r.failing.toLocaleString()} of {r.total.toLocaleString()} {r.unit}</span>}</div>
              {!r.passed && r.sample.length > 0 && <pre className="mt-1 overflow-x-auto rounded bg-panel2 p-2 text-xs">{r.sample.map((x) => JSON.stringify(x)).join("\n")}</pre>}</li>
          ))}</ul>
        </Section>
      )}
      <Section title="Suggested rules" note="Written from today's data. Check each makes business sense before you keep it.">
        <ul className="space-y-1 text-sm">{sug.filter((s) => !have.has(s.text)).map((s) => (
          <li key={s.text} className="flex items-center gap-2"><span className="min-w-0 flex-1">{s.text} <span className="text-xs text-muted">{s.why}</span></span>
            <button className="btn" onClick={() => act(() => postJson("/api/dq/rules", { table, kind: s.kind, params: s.params }), "Couldn't add that rule.")}>Add</button></li>
        ))}</ul>
      </Section>
      {hist.length > 0 && <Section title="Run history"><Table head={["When (UTC)", "Rules", "Failed", "Trigger"]} caption="Quality run history" rows={hist.map((h) => [h.at, String(h.total), String(h.failed), h.trigger])} /></Section>}
    </div>
  );
}
