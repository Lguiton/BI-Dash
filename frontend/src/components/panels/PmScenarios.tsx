"use client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Table, errMsg, useIsPractice } from "./kit";

type Item = { id: number; title: string; status: string };
type Change = { kind: string; item_id?: number; days?: number; pct?: number; title?: string; duration_days?: number };
type SchedRes = { says: string; changes: string[]; before: { days: number; finish: string; critical: string[]; cost: number }; after: { days: number; finish: string; critical: string[]; cost: number }; delta_days: number; newly_critical: string[]; caution: string };
type SimRes = { says: string; plan_days: number; p10_days: number; p50_days: number; p80_days: number; p90_days: number; finish: Record<string, string>; chance_by_deadline_pct: number | null; histogram: { edges: number[]; counts: number[] }; most_often_critical: { title: string; share_pct: number }[]; ranges_used: string; caution: string };
type ProdRes = { says: string; changes: string[]; ranking: { id: number; title: string; rice_before: number; rice_after: number; rank_before: number; rank_after: number; moved: number }[]; capacity_before: number; capacity_after: number; ships_before: string[]; ships_after: string[]; caution: string };
type Case = { id: string; title: string; brief: string; kind: string; tasks?: { id: number; title: string; days: number; after: number[]; cost: number }[]; features?: { id: number; title: string; reach: number; impact: number; confidence: number; effort: number }[]; questions: { q: string; answer?: string }[]; answers_hidden: boolean };

const KIND_HELP: Record<string, string> = { slip: "One task takes longer", estimate_error: "All estimates are off by a %", capacity_loss: "Lose a % of capacity", add_work: "Add a new task", remove: "Cut a task", cost_overrun: "Costs run over by a %" };

export function ScenariosTab({ items }: { items: Item[] }) {
  const practice = useIsPractice();
  const [err, setErr] = useState<string | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [kind, setKind] = useState("slip");
  const [itemId, setItemId] = useState<number | "">("");
  const [amt, setAmt] = useState("5");
  const [sched, setSched] = useState<SchedRes | null>(null);
  const [opt, setOpt] = useState("20");
  const [pes, setPes] = useState("50");
  const [deadline, setDeadline] = useState("");
  const [sim, setSim] = useState<SimRes | null>(null);
  const [cap, setCap] = useState("");
  const [capPct, setCapPct] = useState("0");
  const [effItem, setEffItem] = useState<number | "">("");
  const [effMult, setEffMult] = useState("2");
  const [prod, setProd] = useState<ProdRes | null>(null);
  const [caseKind, setCaseKind] = useState("website");
  const [seed, setSeed] = useState("1");
  const [cs, setCs] = useState<Case | null>(null);
  const [loaded, setLoaded] = useState<string | null>(null);

  const guard = async (fn: () => Promise<void>) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, "That didn't run.")); } };
  const need = kind === "slip" || kind === "remove";
  const pctKind = kind === "estimate_error" || kind === "capacity_loss" || kind === "cost_overrun";
  const addChange = () => {
    const n = Number(amt);
    if (need && itemId === "") { setErr("Pick the task first."); return; }
    setErr(null);
    const c: Change = kind === "slip" ? { kind, item_id: Number(itemId), days: n } : kind === "remove" ? { kind, item_id: Number(itemId) } : kind === "add_work" ? { kind, title: "New task", duration_days: n, ...(itemId === "" ? {} : { deps: [Number(itemId)] } as object) } : { kind, pct: n };
    setChanges([...changes, c]);
  };
  const describe = (c: Change) => `${KIND_HELP[c.kind]}${c.item_id ? ` (#${c.item_id} ${items.find((i) => i.id === c.item_id)?.title ?? ""})` : ""}${c.days !== undefined ? `: ${c.days} days` : ""}${c.pct !== undefined ? `: ${c.pct}%` : ""}${c.duration_days !== undefined ? `: ${c.duration_days} days` : ""}`;
  const maxC = sim ? Math.max(...sim.histogram.counts, 1) : 1;

  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <p className="card p-3 text-sm text-muted">What-ifs run on a copy. Your board is never changed. Ask the Project & Product agent in plain words and it runs the same scenarios.</p>

      <Section title="1. Schedule what-if" note="Same critical-path maths as the Schedule tab, run twice: as it is, and with your changes.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Change"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(KIND_HELP).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          {(need || kind === "add_work") && <Field label={kind === "add_work" ? "After task (optional)" : "Task"}><select className="field" value={itemId} onChange={(e) => setItemId(e.target.value ? Number(e.target.value) : "")}><option value="">{kind === "add_work" ? "Nothing" : "Choose…"}</option>{items.map((i) => <option key={i.id} value={i.id}>#{i.id} {i.title}</option>)}</select></Field>}
          {kind !== "remove" && <Field label={pctKind ? "Percent" : "Days"}><input className="field w-24" type="number" value={amt} onChange={(e) => setAmt(e.target.value)} /></Field>}
          <button className="btn" onClick={addChange}>Add change</button>
          <button className="btn btn-primary" disabled={!changes.length} onClick={() => guard(async () => setSched(await postJson<SchedRes>("/api/pm/scenarios/schedule", { changes })))}>Run what-if</button>
          {changes.length > 0 && <button className="btn" onClick={() => { setChanges([]); setSched(null); }}>Clear</button>}
        </div>
        {changes.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm">{changes.map((c, i) => <li key={i}>{describe(c)}</li>)}</ul>}
        {sched && (
          <div className="mt-3 space-y-2 text-sm">
            <p className="font-medium">{sched.says}</p>
            <div className="grid gap-2 md:grid-cols-2">
              <div className="rounded-md border border-line p-2"><div className="text-xs text-muted">Before</div>{sched.before.days} days · finish {sched.before.finish}<div className="text-xs text-muted">Critical: {sched.before.critical.join(" → ") || "none"}</div></div>
              <div className="rounded-md border border-line p-2"><div className="text-xs text-muted">After</div>{sched.after.days} days · finish {sched.after.finish}<div className="text-xs text-muted">Critical: {sched.after.critical.join(" → ") || "none"}</div></div>
            </div>
            <p className="text-xs text-muted">{sched.caution}</p>
          </div>
        )}
      </Section>

      <Section title="2. How likely is the date? (1,000 simulated schedules)" note="Each unfinished task is drawn from a range around its estimate. The answer is a spread, not one date.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Could go faster by %"><input className="field w-24" type="number" value={opt} onChange={(e) => setOpt(e.target.value)} /></Field>
          <Field label="Could run slower by %"><input className="field w-24" type="number" value={pes} onChange={(e) => setPes(e.target.value)} /></Field>
          <Field label="Deadline (optional)"><input className="field" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => guard(async () => setSim(await postJson<SimRes>("/api/pm/scenarios/simulate", { optimistic_pct: Number(opt), pessimistic_pct: Number(pes), deadline: deadline || null, changes: changes.length ? changes : null })))}>Simulate{changes.length ? " with the changes above" : ""}</button>
        </div>
        {sim && (
          <div className="mt-3 space-y-2 text-sm">
            <p className="font-medium">{sim.says}</p>
            <div className="flex flex-wrap gap-2"><Badge>Plan {sim.plan_days} days</Badge><Badge>50%: {sim.p50_days} days ({sim.finish.p50})</Badge><Badge tone="warn">80%: {sim.p80_days} days ({sim.finish.p80})</Badge><Badge tone="bad">90%: {sim.p90_days} days ({sim.finish.p90})</Badge>{sim.chance_by_deadline_pct !== null && <Badge tone={sim.chance_by_deadline_pct >= 80 ? "ok" : "bad"}>By deadline: {sim.chance_by_deadline_pct}%</Badge>}</div>
            <div className="flex h-24 items-end gap-0.5" role="img" aria-label="How many of the 1,000 runs finished in each range of days">
              {sim.histogram.counts.map((c, i) => <div key={i} title={`${sim.histogram.edges[i]}–${sim.histogram.edges[i + 1]} days: ${c} runs`} className="flex-1 rounded-t bg-[var(--accent)]" style={{ height: `${Math.max(2, (c / maxC) * 100)}%` }} />)}
            </div>
            <p className="text-xs text-muted">From {sim.histogram.edges[0]} to {sim.histogram.edges[sim.histogram.edges.length - 1]} days. Most often on the critical path: {sim.most_often_critical.map((m) => `${m.title} (${m.share_pct}%)`).join(", ") || "none"}. {sim.ranges_used}. {sim.caution}</p>
          </div>
        )}
      </Section>

      <Section title="3. Product what-if (RICE ranking and capacity)" note="Change an effort estimate or the team's capacity and see what moves.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Item whose effort changes"><select className="field" value={effItem} onChange={(e) => setEffItem(e.target.value ? Number(e.target.value) : "")}><option value="">None</option>{items.map((i) => <option key={i.id} value={i.id}>#{i.id} {i.title}</option>)}</select></Field>
          <Field label="Effort times"><input className="field w-20" type="number" step="0.1" value={effMult} onChange={(e) => setEffMult(e.target.value)} /></Field>
          <Field label="Capacity (effort)"><input className="field w-24" type="number" value={cap} onChange={(e) => setCap(e.target.value)} placeholder="half of all" /></Field>
          <Field label="Capacity change %"><input className="field w-24" type="number" value={capPct} onChange={(e) => setCapPct(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => guard(async () => setProd(await postJson<ProdRes>("/api/pm/scenarios/product", { changes: effItem === "" ? [] : [{ item_id: effItem, field: "effort", multiplier: Number(effMult) }], capacity: cap ? Number(cap) : null, capacity_pct: Number(capPct) })))}>Run</button>
        </div>
        {prod && (
          <div className="mt-3 space-y-2 text-sm">
            <p className="font-medium">{prod.says}</p>
            <Table head={["Item", "RICE before", "RICE after", "Rank", "Moved"]} rows={prod.ranking.map((r) => [r.title, r.rice_before, r.rice_after, `${r.rank_before} → ${r.rank_after}`, r.moved === 0 ? "–" : r.moved > 0 ? `up ${r.moved}` : `down ${-r.moved}`])} />
            <p className="text-xs text-muted">{prod.caution}</p>
          </div>
        )}
      </Section>

      <Section title="4. Practice cases (answers hidden until you ask)" note="Work it out on paper first, then check. The answers come from the same engine as the tabs.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Case"><select className="field" value={caseKind} onChange={(e) => setCaseKind(e.target.value)}><option value="website">Website relaunch</option><option value="app_mvp">Mobile app MVP</option><option value="repair_shop">Opening a repair counter</option><option value="product_roadmap">Product roadmap choices</option></select></Field>
          <Field label="Variation"><input className="field w-20" type="number" min={1} max={999} value={seed} onChange={(e) => setSeed(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => guard(async () => { setLoaded(null); setCs(await getJson<Case>(`/api/pm/scenarios/practice?kind=${caseKind}&seed=${seed}`)); })}>New case</button>
          {cs && cs.answers_hidden && <button className="btn" onClick={() => guard(async () => setCs(await getJson<Case>(`/api/pm/scenarios/practice?kind=${cs.kind}&seed=${seed}&reveal=true`)))}>Show answers</button>}
          {cs && practice && cs.kind !== "product_roadmap" && <button className="btn" onClick={() => guard(async () => { const r = await postJson<{ loaded: number }>("/api/pm/scenarios/practice/load", { kind: cs.kind, seed: Number(seed) }); setLoaded(`Loaded ${r.loaded} tasks onto the board. Refresh the other tabs to explore them.`); })}>Load onto my board</button>}
        </div>
        {loaded && <p role="status" className="mt-2 text-sm">{loaded}</p>}
        {cs && (
          <div className="mt-3 space-y-2 text-sm">
            <h4 className="font-semibold">{cs.title}</h4><p>{cs.brief}</p>
            {cs.tasks && <Table head={["#", "Task", "Days", "After", "Cost"]} rows={cs.tasks.map((t) => [t.id, t.title, t.days, t.after.join(", ") || "–", t.cost.toLocaleString()])} />}
            {cs.features && <Table head={["#", "Feature", "Reach", "Impact", "Confidence", "Effort"]} rows={cs.features.map((f) => [f.id, f.title, f.reach, f.impact, f.confidence, f.effort])} />}
            <ol className="list-decimal space-y-2 pl-5">{cs.questions.map((q, i) => <li key={i}>{q.q}{q.answer && <p className="mt-1 rounded-md bg-panel2 p-2"><strong>Answer:</strong> {q.answer}</p>}</li>)}</ol>
          </div>
        )}
      </Section>
    </div>
  );
}
