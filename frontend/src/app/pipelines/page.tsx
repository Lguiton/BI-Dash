"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, Table, errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, postJson } from "@/lib/api";

interface Task { id: string; kind: string; depends_on: string[]; retries: number; ref: string | number | null; table?: string; fail_on_rule_failure?: boolean }
interface Pipe { id: number; name: string; tasks: Task[]; every_minutes: number; enabled: boolean; last_run_at: string | null; last_ok: boolean | null }
interface TaskRes { id: string; status: string; attempts: number; seconds: number; message: string }
interface RunRes { id: number; name: string; ok: boolean; seconds: number; results: TaskRes[] }
interface Hist { id: number; at: string; ok: boolean; seconds: number; trigger: string; detail: TaskRes[] }
interface Opt { id: number; name: string }

const EVERY: [number, string][] = [[0, "Only when I press Run"], [15, "Every 15 minutes"], [60, "Every hour"], [360, "Every 6 hours"], [1440, "Every day"]];

export default function PipelinesPage() {
  const [pipes, setPipes] = useState<Pipe[]>([]);
  const [kinds, setKinds] = useState<{ id: string; label: string }[]>([]);
  const [wfs, setWfs] = useState<Opt[]>([]);
  const [srcs, setSrcs] = useState<Opt[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  const [last, setLast] = useState<RunRes | null>(null);
  const [hist, setHist] = useState<{ id: number; runs: Hist[] } | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [every, setEvery] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([getJson<{ pipelines: Pipe[]; kinds: { id: string; label: string }[] }>("/api/pipelines", ctl.signal), getJson<{ workflows: Opt[] }>("/api/workflows", ctl.signal), getJson<{ sources: Opt[] }>("/api/sources", ctl.signal).catch(() => ({ sources: [] as Opt[] }))])
      .then(([p, w, s]) => { setPipes(p.pipelines); setKinds(p.kinds); setWfs(w.workflows); setSrcs(s.sources); })
      .catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load pipelines.")); });
    return () => ctl.abort();
  }, [ver]);

  const act = async (f: () => Promise<unknown>, m: string) => { setErr(null); try { await f(); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, m)); } };
  const addTask = (kind: string) => setTasks([...tasks, { id: `${kind}_${tasks.length + 1}`, kind, depends_on: tasks.length ? [tasks[tasks.length - 1].id] : [], retries: 0, ref: kind === "backup" ? null : kind === "workflow" ? wfs[0]?.id ?? null : kind === "source" ? srcs[0]?.id ?? null : "", table: "" }]);
  const upd = (i: number, p: Partial<Task>) => setTasks(tasks.map((t, n) => (n === i ? { ...t, ...p } : t)));
  const run = (p: Pipe) => act(async () => { setBusy(p.id); try { setLast(await postJson<RunRes>(`/api/pipelines/${p.id}/run`, {})); } finally { setBusy(null); } }, "The run failed.");
  const showHist = async (p: Pipe) => { try { setHist({ id: p.id, runs: (await getJson<{ runs: Hist[] }>(`/api/pipelines/${p.id}/history`)).runs }); } catch (e) { setErr(errMsg(e, "Couldn't load the history.")); } };

  return (
    <PageShell title="Pipelines" subtitle="Chain tasks with dependencies, retries and a schedule: our own small take on Airflow or Prefect.">
      {err && <ErrorBanner message={err} />}
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Honest limits: pipelines run inside this app, one at a time, and scheduled runs happen only while the backend is running. A failed task skips the tasks that depend on it.</p>
      <Section title="New pipeline">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Schedule"><select className="field" value={every} onChange={(e) => setEvery(Number(e.target.value))}>{EVERY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">{kinds.map((k) => <button key={k.id} className="btn" onClick={() => addTask(k.id)}>+ {k.label}</button>)}</div>
        <ol className="mt-3 space-y-2">{tasks.map((t, i) => (
          <li key={i} className="flex flex-wrap items-end gap-2 rounded border border-line p-2 text-sm">
            <Field label="Task id"><input className="field w-28" value={t.id} onChange={(e) => upd(i, { id: e.target.value })} /></Field>
            <Badge>{t.kind}</Badge>
            {t.kind === "workflow" && (<><Field label="Workflow"><select className="field" value={String(t.ref ?? "")} onChange={(e) => upd(i, { ref: Number(e.target.value) })}>{wfs.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></Field><Field label="Fill table"><input className="field w-32" value={t.table ?? ""} onChange={(e) => upd(i, { table: e.target.value })} /></Field></>)}
            {t.kind === "dq" && <Field label="Table with rules"><input className="field w-32" value={String(t.ref ?? "")} onChange={(e) => upd(i, { ref: e.target.value })} /></Field>}
            {t.kind === "source" && <Field label="Source"><select className="field" value={String(t.ref ?? "")} onChange={(e) => upd(i, { ref: Number(e.target.value) })}>{srcs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>}
            <Field label="After"><select className="field" value={t.depends_on[0] ?? ""} onChange={(e) => upd(i, { depends_on: e.target.value ? [e.target.value] : [] })}><option value="">(nothing)</option>{tasks.filter((_, n) => n !== i).map((o) => <option key={o.id}>{o.id}</option>)}</select></Field>
            <Field label="Retries"><input className="field w-16" type="number" min={0} max={3} value={t.retries} onChange={(e) => upd(i, { retries: Number(e.target.value) })} /></Field>
            <button className="btn" onClick={() => setTasks(tasks.filter((_, n) => n !== i))}>Remove</button>
          </li>
        ))}</ol>
        <button className="btn btn-primary mt-3" disabled={!name.trim() || tasks.length === 0}
          onClick={() => act(async () => { await postJson("/api/pipelines", { name, tasks: tasks.map((t) => ({ ...t, depends_on: t.depends_on.filter(Boolean) })), every_minutes: every, enabled: true }); setName(""); setTasks([]); }, "Couldn't save that pipeline.")}>Save pipeline</button>
      </Section>
      {pipes.map((p) => (
        <section key={p.id} className="card space-y-2 p-4">
          <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{p.name}</h3>
            {p.last_ok !== null && <Badge tone={p.last_ok ? "ok" : "bad"}>{p.last_ok ? "last run ok" : "last run failed"}</Badge>}
            <span className="text-xs text-muted">{p.tasks.length} task(s) · {EVERY.find(([v]) => v === p.every_minutes)?.[1] ?? `every ${p.every_minutes} min`}{p.last_run_at ? ` · last ${p.last_run_at}` : ""}</span>
            <span className="ml-auto flex gap-2">
              <button className="btn btn-primary" disabled={busy === p.id} onClick={() => run(p)}>{busy === p.id ? "Running…" : "Run now"}</button>
              <button className="btn" onClick={() => showHist(p)}>History</button>
              <button className="btn" aria-label={`Delete ${p.name}`} onClick={() => act(() => deleteJson(`/api/pipelines/${p.id}`), "Couldn't delete.")}>Delete</button></span></div>
          <p className="text-xs text-muted">{p.tasks.map((t) => `${t.id} (${t.kind})${t.depends_on.length ? ` after ${t.depends_on.join(", ")}` : ""}`).join("  →  ")}</p>
          {last?.id === p.id && <TaskTable res={last.results} title={`Latest run: ${last.ok ? "ok" : "failed"} in ${last.seconds}s`} />}
          {hist?.id === p.id && (hist.runs.length === 0 ? <p className="text-sm text-muted">No runs yet.</p> : <Table head={["When (UTC)", "Result", "Seconds", "Trigger"]} caption="Run history" rows={hist.runs.map((r) => [r.at, r.ok ? "ok" : "failed", String(r.seconds), r.trigger])} />)}
        </section>
      ))}
    </PageShell>
  );
}

function TaskTable({ res, title }: { res: TaskRes[]; title: string }) {
  return <div><p className="mb-1 text-xs font-semibold">{title}</p><Table head={["Task", "Status", "Tries", "Seconds", "Message"]} caption={title} rows={res.map((r) => [r.id, r.status, String(r.attempts), String(r.seconds), r.message])} /></div>;
}
