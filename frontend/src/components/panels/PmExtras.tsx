"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, patchJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

interface CalItem { id: number; title: string; status: string; kind: string; starts: boolean; ends: boolean; overdue: boolean }
interface Day { date: string; items: CalItem[]; sprints: { id: number; name: string }[] }
interface Cal { month: string; label: string; lead_blanks: number; today: string; days: Day[]; unscheduled: number; note: string }

const shift = (m: string, d: number) => { const [y, mo] = m.split("-").map(Number); const t = new Date(y, mo - 1 + d, 1); return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}`; };

export function CalendarTab() {
  const [month, setMonth] = useState<string>("");
  const [cal, setCal] = useState<Cal | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Cal>(`/api/pm/calendar${month ? `?month=${month}` : ""}`, ctl.signal).then((c) => { setCal(c); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the calendar.")); });
    return () => ctl.abort();
  }, [month]);
  if (!cal) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      <div className="flex items-center gap-2">
        <button className="btn" aria-label="Previous month" onClick={() => setMonth(shift(cal.month, -1))}>←</button>
        <h3 className="text-sm font-semibold">{cal.label}</h3>
        <button className="btn" aria-label="Next month" onClick={() => setMonth(shift(cal.month, 1))}>→</button>
        <button className="btn" onClick={() => setMonth("")}>Today</button>
        {cal.unscheduled > 0 && <span className="ml-auto text-xs text-muted">{cal.unscheduled} item(s) have no start date</span>}
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[640px] grid-cols-7 gap-px rounded-lg border border-line bg-line text-xs" role="grid" aria-label={`Calendar for ${cal.label}`}>
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} role="columnheader" className="bg-panel2 p-1 text-center font-semibold">{d}</div>)}
          {Array.from({ length: cal.lead_blanks }).map((_, i) => <div key={`b${i}`} className="min-h-20 bg-panel" />)}
          {cal.days.map((d) => (
            <div key={d.date} role="gridcell" className={`min-h-20 space-y-0.5 bg-panel p-1 ${d.date === cal.today ? "ring-2 ring-inset ring-[var(--accent)]" : ""}`}>
              <div className="flex justify-between text-muted"><span>{Number(d.date.slice(8))}</span>{d.sprints[0] && <span className="truncate" title={d.sprints.map((s) => s.name).join(", ")}>{d.sprints[0].name}</span>}</div>
              {d.items.slice(0, 3).map((it) => (
                <div key={it.id} title={`${it.title} (${it.status})`} className={`truncate rounded px-1 ${it.overdue ? "bg-red-500/20" : it.status === "done" ? "bg-emerald-500/20" : "bg-[var(--accent)]/20"}`}>{it.starts ? "" : "… "}{it.title}</div>
              ))}
              {d.items.length > 3 && <div className="text-muted">+{d.items.length - 3} more</div>}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted">Red = planned end passed and not done. Green = done. {cal.note}</p>
    </div>
  );
}

interface Rule { id: number; name: string; trigger: string; days: number; action: string; value: string; enabled: boolean | number }
interface Rules { rules: Rule[]; triggers: Record<string, string>; actions: Record<string, string>; statuses: string[]; note: string }
interface Change { item_id: number; title: string; rule: string; change: string }

export function RulesTab({ onChanged }: { onChanged: () => void }) {
  const [d, setD] = useState<Rules | null>(null);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("overdue");
  const [days, setDays] = useState(5);
  const [action, setAction] = useState("set_priority");
  const [value, setValue] = useState("1");
  const [changes, setChanges] = useState<{ applied: boolean; changes: Change[]; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Rules>("/api/pm/rules", ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the rules.")); });
    return () => ctl.abort();
  }, [ver]);
  const act = useCallback(async (f: () => Promise<unknown>, m: string) => { setErr(null); try { await f(); setVer((v) => v + 1); } catch (e) { setErr(errMsg(e, m)); } }, []);
  if (!d) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const defaultFor = (a: string) => (a === "set_priority" ? "1" : a === "move_status" ? d.statuses[0] : "");
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Simple if-this-then-that rules on your own board. {d.note} They only touch items in this app; there are no connections to other apps.</p>
      <Section title="New rule">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Name"><input className="field w-40" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="When"><select className="field" value={trigger} onChange={(e) => setTrigger(e.target.value)}>{Object.entries(d.triggers).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          {trigger === "stuck" && <Field label="Days"><input className="field w-16" type="number" min={1} value={days} onChange={(e) => setDays(Number(e.target.value))} /></Field>}
          <Field label="Then"><select className="field" value={action} onChange={(e) => { setAction(e.target.value); setValue(defaultFor(e.target.value)); }}>{Object.entries(d.actions).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          {action === "set_priority" && <Field label="Priority"><select className="field" value={value} onChange={(e) => setValue(e.target.value)}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></Field>}
          {action === "move_status" && <Field label="Status"><select className="field" value={value} onChange={(e) => setValue(e.target.value)}>{d.statuses.map((s) => <option key={s}>{s}</option>)}</select></Field>}
          {action === "add_note" && <Field label="Note"><input className="field w-56 max-w-full" value={value} onChange={(e) => setValue(e.target.value)} /></Field>}
          <button className="btn btn-primary" disabled={!name.trim()} onClick={() => act(async () => { await postJson("/api/pm/rules", { name, trigger, action, value, days: trigger === "stuck" ? days : 0 }); setName(""); }, "Couldn't add that rule.")}>Add rule</button>
        </div>
      </Section>
      <Section title="Your rules">
        {d.rules.length === 0 ? <p className="text-sm text-muted">No rules yet.</p> :
          <ul className="space-y-1 text-sm">{d.rules.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2"><label className="flex items-center gap-1"><input type="checkbox" checked={Boolean(r.enabled)} onChange={(e) => act(() => patchJson(`/api/pm/rules/${r.id}`, { enabled: e.target.checked }), "Couldn't change that.")} /><b>{r.name}</b></label>
              <span className="min-w-0 flex-1 text-xs text-muted">when {d.triggers[r.trigger]?.toLowerCase()}{r.trigger === "stuck" ? ` (${r.days}+ days)` : ""} → {d.actions[r.action]?.toLowerCase()}: {r.value}</span>
              <button className="btn" aria-label={`Delete rule ${r.name}`} onClick={() => act(() => deleteJson(`/api/pm/rules/${r.id}`), "Couldn't delete.")}>Delete</button></li>
          ))}</ul>}
        <div className="mt-3 flex gap-2">
          <button className="btn" onClick={() => act(async () => setChanges(await postJson("/api/pm/rules/run", {})), "Couldn't preview.")}>Preview changes</button>
          <button className="btn btn-primary" onClick={() => act(async () => { setChanges(await postJson("/api/pm/rules/run", { apply: true })); onChanged(); }, "Couldn't run the rules.")}>Run rules</button>
        </div>
        {changes && (
          <div className="mt-3 text-sm"><Badge tone={changes.applied ? "ok" : "muted"}>{changes.applied ? "applied" : "preview"}</Badge> {changes.note}
            {changes.changes.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs">{changes.changes.map((c, i) => <li key={i}>#{c.item_id} {c.title}: {c.change} <span className="text-muted">({c.rule})</span></li>)}</ul>}</div>
        )}
      </Section>
    </div>
  );
}
