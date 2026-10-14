"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg, num } from "./kit";
import { ColSelect, Lesson, Sentences, Warn, first, groupish, pct, useRun, type Base, type Col } from "./analysisKit";

const LEVEL_TONE: Record<string, "ok" | "warn" | "bad"> = { ok: "ok", warn: "warn", bad: "bad" };

// ---------------------------------------------------------------- always-visible reminder + input check
interface Chk { rows: number; verdict: "green" | "amber" | "red"; message: string; checks: { check: string; level: string; detail: string }[]; reminders: string[] }
export function BeforeYouAct({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [sel, setSel] = useState<string[]>(nums.slice(0, 2).map((c) => c.name));
  const [date, setDate] = useState(first(cols, "date"));
  const [group, setGroup] = useState(groupish(cols)[0]?.name ?? "");
  const [open, setOpen] = useState(false);
  const r = useRun<Chk>();
  const color = r.data?.verdict === "green" ? "var(--good-bg)" : r.data?.verdict === "red" ? "var(--bad-bg)" : "var(--warn-bg)";
  return (
    <div className="space-y-2 rounded border border-line bg-panel2 p-3 text-xs">
      <p><b>Before you act.</b> A recommendation is only as good as its inputs, so check the data first. It is a draft to test and keep watching, not an order: this page never changes anything by itself, and the decision stays with you.</p>
      <button className="btn" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide the input check" : "Check my data is fit to act on"}</button>
      {open && (
        <div className="space-y-3">
          <fieldset className="text-xs text-muted"><legend className="mb-1">Columns the advice relies on</legend>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">{cols.filter((c) => c.kind !== "date").map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={sel.includes(c.name)} onChange={() => setSel(sel.includes(c.name) ? sel.filter((x) => x !== c.name) : [...sel, c.name])} />{c.name}</label>)}</div></fieldset>
          <div className="grid gap-2 sm:grid-cols-2"><ColSelect label="Date column (to check freshness)" value={date} onChange={setDate} cols={cols} kinds={["date"]} none="Skip" /><ColSelect label="Group column (to check group sizes)" value={group} onChange={setGroup} cols={cols} kinds={["text", "bool"]} none="Skip" /></div>
          <button className="btn btn-primary" disabled={r.busy || sel.length === 0} onClick={() => r.run("/api/stats/input-check", { ...base, columns: sel, date_col: date || null, group_col: group || null })}>{r.busy ? "Checking…" : "Run the check"}</button>
          {r.err && <ErrorBanner message={r.err} />}
          {r.data && (
            <div className="space-y-2">
              <p className="rounded px-3 py-2 text-sm" style={{ background: color }}><b>{r.data.verdict === "green" ? "Looks sound." : r.data.verdict === "amber" ? "Usable with care." : "Not ready."}</b> {r.data.message}</p>
              <Table head={["Check", "Result", "Detail"]} rows={r.data.checks.map((c) => [c.check, <Badge key="b" tone={LEVEL_TONE[c.level]}>{c.level === "ok" ? "ok" : c.level === "warn" ? "caution" : "problem"}</Badge>, c.detail])} />
              <ul className="list-disc space-y-1 pl-5 text-muted">{r.data.reminders.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- decision brief: the four types in order
interface Brief { metric: string; sections: { kind: string; title: string; lines: string[]; detail: { opportunities?: { group: string; estimated_gain: number }[]; drivers?: { column: string; detail: string }[] } }[]; notes: string[]; lesson: string }
const KIND_LABEL: Record<string, string> = { descriptive: "1. Descriptive", diagnostic: "2. Diagnostic", predictive: "3. Predictive", prescriptive: "4. Prescriptive" };
export function BriefTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [metric, setMetric] = useState(nums[0]?.name ?? "");
  const [group, setGroup] = useState(groupish(cols)[0]?.name ?? "");
  const [date, setDate] = useState(first(cols, "date"));
  const [hib, setHib] = useState(true);
  const r = useRun<Brief>();
  if (nums.length === 0) return <p className="text-sm text-muted">This needs a number column to analyze.</p>;
  return (
    <div className="space-y-4">
      <Section title="Decision brief: all four steps in one page" note="Prescriptive analytics builds on the other three: what happened, why, what is likely next, then what to do.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <ColSelect label="Number to improve" value={metric} onChange={setMetric} cols={nums} />
          <ColSelect label="Compare these groups" value={group} onChange={setGroup} cols={cols} kinds={["text", "bool"]} none="No groups" />
          <ColSelect label="Date column" value={date} onChange={setDate} cols={cols} kinds={["date"]} none="No dates" />
          <Field label="Better means"><select className="field" value={hib ? "high" : "low"} onChange={(e) => setHib(e.target.value === "high")}><option value="high">higher</option><option value="low">lower</option></select></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !metric} onClick={() => r.run("/api/stats/brief", { ...base, metric, group_col: group || null, date_col: date || null, higher_is_better: hib })}>{r.busy ? "Working…" : "Build the brief"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} />
          <div className="grid gap-3 md:grid-cols-2">
            {r.data.sections.map((s, i) => (
              <section key={i} className="card min-w-0 p-4">
                <div className="mb-1 text-xs uppercase tracking-wide text-muted">{KIND_LABEL[s.kind] ?? s.kind}</div>
                <h3 className="mb-2 text-sm font-semibold">{s.title}</h3>
                <Sentences items={s.lines} />
              </section>
            ))}
          </div>
          {r.data.notes.length > 0 && <Warn items={r.data.notes} />}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- goal seek
interface Goal { y: string; target: number; current: number; gap: number; r2: number; options: { lever: string; effect_per_unit: number; reliable: boolean; current_average: number; change_needed: number; needed_value: number; change_pct: number | null; inside_observed_range: boolean; observed_range: [number, number] }[]; plan: { pct_each: number; levers: { lever: string; from: number; to: number }[]; all_inside_range: boolean } | null; sentences: string[]; warnings: string[]; lesson: string }
export function GoalTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [y, setY] = useState(nums[0]?.name ?? "");
  const [levers, setLevers] = useState<string[]>(nums.slice(1, 3).map((c) => c.name));
  const [target, setTarget] = useState("");
  const r = useRun<Goal>();
  if (nums.length < 2) return <p className="text-sm text-muted">This needs a number to reach and at least one number you could change.</p>;
  const lv = levers.filter((c) => c !== y);
  return (
    <div className="space-y-4">
      <Section title="What would it take to reach a target?" note="Runs a regression backwards: how far each lever must move, others held fixed, for the average to reach your target.">
        <div className="grid gap-3 md:grid-cols-3">
          <ColSelect label="Number to move (average)" value={y} onChange={(v) => { setY(v); r.reset(); }} cols={nums} />
          <Field label="Target for its average"><input className="field" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
          <fieldset className="min-w-0 text-xs text-muted"><legend className="mb-1">Levers you can change</legend>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">{nums.filter((c) => c.name !== y).map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={levers.includes(c.name)} onChange={() => setLevers(levers.includes(c.name) ? levers.filter((x) => x !== c.name) : [...levers, c.name])} />{c.name}</label>)}</div></fieldset>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || lv.length === 0 || target.trim() === "" || Number.isNaN(Number(target))} onClick={() => r.run("/api/stats/goal", { ...base, y, target: Number(target), levers: lv })}>{r.busy ? "Working…" : "Find the plan"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} /><Warn items={r.data.warnings} /><Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label={`Average ${r.data.y} now`} value={num(r.data.current, 2)} /><Stat label="Target" value={num(r.data.target, 2)} /><Stat label="Gap" value={`${r.data.gap > 0 ? "+" : ""}${num(r.data.gap, 2)}`} /><Stat label="How well inputs explain it" value={pct(r.data.r2, 0)} sub="R²" />
          </div>
          <Section title="One lever at a time" note="Best options first (reliable and within what you've actually seen).">
            <Table head={["Lever", "Effect of +1", "Now", "Needed", "Change", "Reliable link?", "Within your data?"]}
              rows={r.data.options.map((o) => [o.lever, num(o.effect_per_unit, 4), num(o.current_average, 2), num(o.needed_value, 2), o.change_pct == null ? "—" : `${o.change_pct > 0 ? "+" : ""}${o.change_pct}%`, <Badge key="r" tone={o.reliable ? "ok" : "muted"}>{o.reliable ? "yes" : "unclear"}</Badge>, <Badge key="i" tone={o.inside_observed_range ? "ok" : "warn"}>{o.inside_observed_range ? `yes (${num(o.observed_range[0], 1)} to ${num(o.observed_range[1], 1)})` : "no: extrapolating"}</Badge>])} />
          </Section>
          {r.data.plan && (
            <Section title={`Or move every reliable lever by ${r.data.plan.pct_each > 0 ? "+" : ""}${r.data.plan.pct_each}%`} note={r.data.plan.all_inside_range ? "All of these stay inside values you have seen." : "Some of these go beyond values you have seen."}>
              <Table head={["Lever", "From", "To"]} rows={r.data.plan.levers.map((l) => [l.lever, num(l.from, 2), num(l.to, 2)])} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- allocation optimizer
interface Alloc { budget: number; current_total: number; spent: number; return_now: number; return_new: number; gain: number; gain_pct: number | null; allocation: { group: string; rows: number; return_per_unit: number; current: number; recommended: number; change: number; change_pct: number; return_now: number; return_new: number; thin: boolean }[]; sentences: string[]; warnings: string[]; lesson: string }
export function AllocTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [group, setGroup] = useState(groupish(cols)[0]?.name ?? "");
  const [ret, setRet] = useState(nums.find((c) => /rev|sales|amount|profit/i.test(c.name))?.name ?? nums[0]?.name ?? "");
  const [eff, setEff] = useState(nums.find((c) => /cost|spend|budget|hours|units/i.test(c.name) && c.name !== ret)?.name ?? nums.find((c) => c.name !== ret)?.name ?? "");
  const [budget, setBudget] = useState("");
  const [lo, setLo] = useState("0.5");
  const [hi, setHi] = useState("1.5");
  const r = useRun<Alloc>();
  if (nums.length < 2 || !cols.some((c) => c.kind === "text" || c.kind === "bool")) return <p className="text-sm text-muted">This needs a category column (the options), a return column (revenue) and an effort column (cost, spend, hours).</p>;
  return (
    <div className="space-y-4">
      <Section title="Best way to split a budget" note="Optimization: maximize total return across groups with a fixed budget, keeping each group between a minimum and maximum share of what it has now.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <ColSelect label="Options to split across" value={group} onChange={setGroup} cols={cols} kinds={["text", "bool"]} />
          <ColSelect label="Return (what you gain)" value={ret} onChange={setRet} cols={cols} kinds={["number"]} />
          <ColSelect label="Effort (what you spend)" value={eff} onChange={setEff} cols={cols} kinds={["number"]} />
          <Field label="Budget (blank = what you spend now)"><input className="field" inputMode="decimal" value={budget} onChange={(e) => setBudget(e.target.value)} /></Field>
          <Field label="No group below (× current)"><input className="field" inputMode="decimal" value={lo} onChange={(e) => setLo(e.target.value)} /></Field>
          <Field label="No group above (× current)"><input className="field" inputMode="decimal" value={hi} onChange={(e) => setHi(e.target.value)} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !group || !ret || !eff} onClick={() => r.run("/api/stats/allocate", { ...base, group_col: group, return_col: ret, effort_col: eff, budget: budget.trim() === "" ? null : Number(budget), min_mult: Number(lo), max_mult: Number(hi) })}>{r.busy ? "Optimizing…" : "Find the best split"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} /><Warn items={r.data.warnings} /><Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Budget" value={num(r.data.budget, 0)} sub={`spent ${num(r.data.spent, 0)}`} /><Stat label="Return now" value={num(r.data.return_now, 0)} /><Stat label="Return, best split" value={num(r.data.return_new, 0)} />
            <Stat label="Estimated gain" value={`${r.data.gain > 0 ? "+" : ""}${num(r.data.gain, 0)}`} sub={r.data.gain_pct == null ? undefined : `${r.data.gain_pct > 0 ? "+" : ""}${r.data.gain_pct}%`} />
          </div>
          <Section title="Recommended split" note="Return per unit comes from each group's past results. Shift in small steps and measure.">
            <Table head={["Option", "Rows", "Return per unit", "Now", "Recommended", "Change", ""]}
              rows={r.data.allocation.map((a) => [a.group, a.rows.toLocaleString(), num(a.return_per_unit, 3), num(a.current, 0), <b key="r">{num(a.recommended, 0)}</b>,
                <span key="c" style={{ color: a.change > 0 ? "var(--good)" : a.change < 0 ? "var(--bad)" : undefined }}>{a.change > 0 ? "+" : ""}{num(a.change, 0)} ({a.change_pct > 0 ? "+" : ""}{a.change_pct}%)</span>, a.thin ? <Badge key="t" tone="warn">few rows</Badge> : ""])} />
          </Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- monitor the result
interface Tracked { id: string; title: string; action: string; source: string; metric: string; baseline: number; baseline_from: string; baseline_to: string; start: string; target: number | null; status: string; message: string; current: number | null; rows_since: number; change_pct?: number | null; progress_pct?: number; unusual?: boolean }
const STATUS_TONE: Record<string, "ok" | "warn" | "bad" | "muted"> = { "on target": "ok", "moving the right way": "ok", "moving the wrong way": "bad", "no clear effect": "warn", changed: "warn", waiting: "muted", "no clear change": "muted", unavailable: "bad" };
export function TrackTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [items, setItems] = useState<Tracked[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetric] = useState(nums[0]?.name ?? "");
  const [date, setDate] = useState(first(cols, "date"));
  const [title, setTitle] = useState("");
  const [action, setAction] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<{ items: Tracked[] }>("/api/stats/track").then((d) => setItems(d.items)).catch((e) => setErr(errMsg(e, "Couldn't load tracked decisions."))); }, []);
  const reload = () => getJson<{ items: Tracked[] }>("/api/stats/track").then((d) => setItems(d.items)).catch((e) => setErr(errMsg(e, "Couldn't load tracked decisions.")));
  const add = async () => {
    setBusy(true); setErr(null);
    try { await postJson("/api/stats/track", { ...base, title, action, metric, date_col: date, target: target.trim() === "" ? null : Number(target) }); setTitle(""); setAction(""); setTarget(""); await reload(); } catch (e) { setErr(errMsg(e, "Couldn't save that.")); } finally { setBusy(false); }
  };
  const remove = async (id: string) => { setErr(null); try { await deleteJson(`/api/stats/track/${id}`); await reload(); } catch (e) { setErr(errMsg(e, "Couldn't delete that.")); } };
  if (nums.length === 0 || !cols.some((c) => c.kind === "date")) return <p className="text-sm text-muted">Tracking needs a number column and a date column.</p>;
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Conditions change and surprises happen, so keep watching. Record what you decided; the page remembers the average from the last 30 days of data as the baseline, then compares it with the data that arrives after.</p>
      {err && <ErrorBanner message={err} />}
      <Section title="Track a decision">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="What did you decide?"><input className="field" maxLength={140} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Raise West prices 5%" /></Field>
          <ColSelect label="Number to watch" value={metric} onChange={setMetric} cols={cols} kinds={["number"]} />
          <ColSelect label="Date column" value={date} onChange={setDate} cols={cols} kinds={["date"]} />
          <Field label="Target for its average (optional)"><input className="field" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
        </div>
        <div className="mt-2"><Field label="What will you do? (optional)"><input className="field" maxLength={500} value={action} onChange={(e) => setAction(e.target.value)} /></Field></div>
        <button className="btn btn-primary mt-3" disabled={busy || !title.trim() || !metric || !date} onClick={add}>{busy ? "Saving…" : "Start tracking"}</button>
        <p className="mt-2 text-xs text-muted">Uses the data source and filters selected above. Load newer data in My data, then come back to see the effect.</p>
      </Section>
      <Section title="Tracked decisions">
        {!items ? <p className="text-sm text-muted">Loading…</p> : items.length === 0 ? <p className="text-sm text-muted">Nothing tracked yet.</p> : (
          <ul className="divide-y divide-line">
            {items.map((t) => (
              <li key={t.id} className="space-y-1 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2"><b>{t.title}</b><Badge tone={STATUS_TONE[t.status] ?? "muted"}>{t.status}</Badge><Badge>{t.metric}</Badge>
                  <button className="btn ml-auto" aria-label={`Stop tracking ${t.title}`} onClick={() => remove(t.id)}>Remove</button></div>
                {t.action && <p className="text-muted">{t.action}</p>}
                <p>{t.message}</p>
                <p className="text-xs text-muted">Baseline {num(t.baseline, 2)} ({t.baseline_from} to {t.baseline_to}); watching data from {t.start}; {t.rows_since.toLocaleString()} row(s) since.{t.target != null ? ` Target ${num(t.target, 2)}${t.progress_pct != null ? `, progress ${t.progress_pct}%` : ""}.` : ""}</p>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
