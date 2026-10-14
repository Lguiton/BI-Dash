"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section } from "@/components/panels/kit";

type Comp = { id: string; label: string; layer: string; why: string };
type Edge = { from: string; to: string; label: string };
type Cost = { server_size: string; server_count: number; lines: Record<string, number>; total: number };
type Cap = { arithmetic: string[]; verdict: string; budget: string | null; cost: Cost; cost_at_10x: Cost; assumptions: string[]; caution: string; peak_rps: number; storage_gb: number };
type Design = { summary: string; components: Comp[]; edges: Edge[]; tables: Record<string, string[]>; ddl: string; api: string[]; sequence: { from: string; to: string; message: string }[]; capacity: Cap; next_steps: string[]; caution: string };
type Card = { topic: string; choice: string; why: string; gives_up: string; revisit_when: string };
type Finding = { severity: string; title: string; detail: string; fix: string };
type Opts = { kinds: Record<string, string>; needs: string[]; uptime: string[]; cases: Record<string, string> };
type Practice = { title: string; prompt: string; numbers: Record<string, number>; checklist?: { id: string; label: string; why: string }[] };
type Grade = { score: number; hits: { label: string }[]; misses: { label: string; why: string }[]; says: string; caution: string };

const LAYERS = ["client", "app", "data", "external"];
const NUM: [string, string][] = [["users", "Total users"], ["active_pct", "% active per day"], ["actions_per_user_day", "Actions per active user per day"], ["peak_factor", "Peak vs average (times)"], ["record_kb", "Size of one record (KB)"], ["new_records_per_day", "New records per day"], ["retention_months", "Keep data (months)"], ["team", "People building it"], ["budget_month", "Monthly budget $ (0 = none)"]];

function Diagram({ comps, edges }: { comps: Comp[]; edges: Edge[] }) {
  const W = 720, rowH = 84, pos: Record<string, { x: number; y: number }> = {};
  const rows = LAYERS.map((l) => comps.filter((c) => c.layer === l)).filter((r) => r.length);
  rows.forEach((r, ri) => r.forEach((c, i) => { pos[c.id] = { x: ((i + 1) * W) / (r.length + 1), y: 34 + ri * rowH }; }));
  return (
    <svg viewBox={`0 0 ${W} ${rows.length * rowH}`} role="img" aria-label="Architecture diagram" className="w-full rounded-md border border-line bg-panel2">
      {edges.filter((e) => pos[e.from] && pos[e.to]).map((e, i) => {
        const a = pos[e.from], b = pos[e.to];
        return <g key={i}><line x1={a.x} y1={a.y + 16} x2={b.x} y2={b.y - 16} stroke="currentColor" strokeOpacity="0.4" /><text x={(a.x + b.x) / 2 + 4} y={(a.y + b.y) / 2} fontSize="9" fill="currentColor" opacity="0.6">{e.label}</text></g>;
      })}
      {comps.map((c) => <g key={c.id}><rect x={pos[c.id].x - 62} y={pos[c.id].y - 16} width="124" height="32" rx="6" fill="none" stroke="currentColor" /><text x={pos[c.id].x} y={pos[c.id].y + 4} textAnchor="middle" fontSize="11" fill="currentColor">{c.label}</text><title>{c.why}</title></g>)}
    </svg>
  );
}

function Sequence({ steps }: { steps: Design["sequence"] }) {
  const actors = Array.from(new Set(steps.flatMap((s) => [s.from, s.to])));
  const W = 720, x = (a: string) => ((actors.indexOf(a) + 0.5) * W) / actors.length, H = 50 + steps.length * 40;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Sequence diagram" className="w-full rounded-md border border-line bg-panel2">
      {actors.map((a) => <g key={a}><text x={x(a)} y="20" textAnchor="middle" fontSize="11" fill="currentColor">{a}</text><line x1={x(a)} y1="28" x2={x(a)} y2={H - 8} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="3 3" /></g>)}
      {steps.map((s, i) => <g key={i}><line x1={x(s.from)} y1={56 + i * 40} x2={x(s.to)} y2={56 + i * 40} stroke="currentColor" markerEnd="url(#ar)" /><text x={(x(s.from) + x(s.to)) / 2} y={50 + i * 40} textAnchor="middle" fontSize="10" fill="currentColor">{i + 1}. {s.message}</text></g>)}
      <defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="currentColor" /></marker></defs>
    </svg>
  );
}

const money = (n: number) => `$${n.toFixed(0)}`;

export default function DesignPage() {
  const [opts, setOpts] = useState<Opts | null>(null);
  const [f, setF] = useState<Record<string, string>>({ name: "Repair shop booking", kind: "booking", uptime: "99.5", users: "300", active_pct: "10", actions_per_user_day: "8", peak_factor: "8", record_kb: "2", new_records_per_day: "40", retention_months: "60", team: "1", budget_month: "0", entities: "" });
  const [needs, setNeeds] = useState<string[]>(["auth", "email"]);
  const [d, setD] = useState<Design | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [rev, setRev] = useState<Finding[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pk, setPk] = useState("booking");
  const [pc, setPc] = useState<Practice | null>(null);
  const [ans, setAns] = useState("");
  const [gr, setGr] = useState<Grade | null>(null);

  useEffect(() => { getJson<Opts>("/api/sysdesign/options").then(setOpts).catch((e) => setErr(String(e.message ?? e))); }, []);
  useEffect(() => { getJson<Practice>(`/api/sysdesign/practice?kind=${pk}`).then(setPc).catch(() => setPc(null)); }, [pk]);
  const set = (k: string, v: string) => setF((o) => ({ ...o, [k]: v }));
  const spec = () => ({ ...f, needs, ...Object.fromEntries(Object.keys(f).filter((k) => !["name", "kind", "uptime", "entities"].includes(k)).map((k) => [k, f[k] === "" ? undefined : Number(f[k])])) });

  async function go() {
    setErr(null); setBusy(true);
    try {
      const s = spec();
      const [dd, tr, rv] = await Promise.all([postJson<Design>("/api/sysdesign/design", s), postJson<{ cards: Card[] }>("/api/sysdesign/tradeoffs", s), postJson<{ findings: Finding[] }>("/api/sysdesign/review", s)]);
      setD(dd); setCards(tr.cards); setRev(rv.findings);
    } catch (e) { setErr(e instanceof Error ? e.message : "Something went wrong."); } finally { setBusy(false); }
  }
  async function grade() {
    setErr(null);
    try { setGr(await postJson<Grade>("/api/sysdesign/practice/grade", { kind: pk, answer: ans })); } catch (e) { setErr(e instanceof Error ? e.message : "Something went wrong."); }
  }
  const tone = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "muted") as "bad" | "warn" | "muted";

  return (
    <PageShell title="Systems Design" subtitle="Describe a system in plain numbers. Get a first design, a cost estimate with the arithmetic shown, the trade-offs, and a review of where it could fail.">
      {err && <ErrorBanner message={err} />}
      <Section title="Describe your system" note="Everything here is rule-based and runs on this computer. Estimates come from your numbers, not from measuring anything.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Name"><input aria-label="System name" className="input" value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Kind of system"><select aria-label="Kind of system" className="input" value={f.kind} onChange={(e) => set("kind", e.target.value)}>{opts && Object.entries(opts.kinds).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Uptime target (%)"><select aria-label="Uptime target" className="input" value={f.uptime} onChange={(e) => set("uptime", e.target.value)}>{(opts?.uptime ?? ["99.5"]).map((u) => <option key={u}>{u}</option>)}</select></Field>
          {NUM.map(([k, l]) => <Field key={k} label={l}><input aria-label={l} className="input" inputMode="decimal" value={f[k]} onChange={(e) => set(k, e.target.value)} /></Field>)}
          {f.kind === "custom" && <Field label="Main things it stores (comma list)"><input aria-label="Entities" className="input" value={f.entities} onChange={(e) => set("entities", e.target.value)} placeholder="jobs, parts, invoices" /></Field>}
        </div>
        <fieldset className="mt-3 flex flex-wrap gap-3 text-sm"><legend className="mb-1 text-xs text-muted">It also needs</legend>
          {(opts?.needs ?? []).map((n) => <label key={n} className="flex items-center gap-1"><input type="checkbox" checked={needs.includes(n)} onChange={(e) => setNeeds((o) => (e.target.checked ? [...o, n] : o.filter((x) => x !== n)))} />{n}</label>)}
        </fieldset>
        <button className="btn mt-3" disabled={busy} onClick={go}>{busy ? "Designing…" : "Design it"}</button>
      </Section>

      {d && (
        <>
          <Section title="The design" note={d.caution}>
            <p className="mb-3 text-sm">{d.summary}</p>
            <Diagram comps={d.components} edges={d.edges} />
            <ul className="mt-3 grid gap-1 text-sm sm:grid-cols-2">{d.components.map((c) => <li key={c.id}><b>{c.label}:</b> <span className="text-muted">{c.why}</span></li>)}</ul>
          </Section>
          <Section title="Main flow"><Sequence steps={d.sequence} /></Section>
          <Section title="Tables and API">
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="mb-1 flex items-center gap-2 text-xs text-muted">SQL <button className="btn" onClick={() => navigator.clipboard?.writeText(d.ddl)}>Copy</button></div><pre aria-label="Table SQL" className="max-h-72 overflow-auto rounded bg-panel2 p-2 text-xs">{d.ddl}</pre></div>
              <div><div className="mb-1 text-xs text-muted">API calls</div><pre aria-label="API calls" className="max-h-72 overflow-auto rounded bg-panel2 p-2 text-xs">{d.api.join("\n")}</pre></div>
            </div>
            <p className="mt-2 text-xs text-muted">Next: {d.next_steps.join(" ")}</p>
          </Section>
          <Section title="Capacity and cost" note={d.capacity.caution}>
            <p className="mb-2 text-sm font-medium">{d.capacity.verdict} {d.capacity.budget}</p>
            <ol className="mb-3 list-decimal pl-5 text-sm">{d.capacity.arithmetic.map((a, i) => <li key={i}>{a}</li>)}</ol>
            <div className="grid gap-3 md:grid-cols-2">
              {([["Now", d.capacity.cost], ["At 10 times the load", d.capacity.cost_at_10x]] as [string, Cost][]).map(([t, c]) => (
                <div key={t} className="rounded border border-line p-3 text-sm"><div className="font-medium">{t}: about {money(c.total)}/month</div><div className="text-xs text-muted">{c.server_count} x {c.server_size.replace("vps_", "")} server</div>
                  <ul className="mt-1 text-xs">{Object.entries(c.lines).map(([k, v]) => <li key={k}>{k}: {money(v)}</li>)}</ul></div>
              ))}
            </div>
            <ul className="mt-2 list-disc pl-5 text-xs text-muted">{d.capacity.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
          </Section>
          <Section title="Trade-offs">
            <div className="grid gap-3 md:grid-cols-2">{cards.map((c) => <div key={c.topic} className="rounded border border-line p-3 text-sm"><div className="font-medium">{c.topic}: {c.choice}</div><p className="text-muted">{c.why}</p><p><b>Gives up:</b> {c.gives_up}</p><p className="text-xs text-muted">Revisit when: {c.revisit_when}</p></div>)}</div>
          </Section>
          <Section title="Design review" note="Reviews only the design you described, not a real system.">
            <ul className="grid gap-2 text-sm">{rev.map((r, i) => <li key={i}><Badge tone={tone(r.severity)}>{r.severity}</Badge> <b>{r.title}.</b> {r.detail} <span className="text-muted">Fix: {r.fix}</span></li>)}</ul>
          </Section>
        </>
      )}

      <Section title="Practice: design it yourself" note="Write your design in plain sentences. Grading checks for the key ideas by keyword. It can't judge your reasoning.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Case"><select aria-label="Practice case" className="input" value={pk} onChange={(e) => { setPk(e.target.value); setGr(null); }}>{opts && Object.entries(opts.cases).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field></div>
        {pc && <p className="mt-2 text-sm"><b>{pc.title}.</b> {pc.prompt}</p>}
        <textarea aria-label="Your design" className="input mt-2 min-h-32 w-full text-sm" value={ans} onChange={(e) => setAns(e.target.value)} placeholder="Describe the parts, how data flows, and your numbers…" />
        <button className="btn mt-2" onClick={grade}>Grade my design</button>
        {gr && (
          <div className="mt-3 text-sm"><p className="font-medium">{gr.score}%. {gr.says}</p>
            {gr.misses.length > 0 && <ul className="mt-1 list-disc pl-5">{gr.misses.map((m) => <li key={m.label}>{m.label}. <span className="text-muted">{m.why}</span></li>)}</ul>}
            <p className="mt-1 text-xs text-muted">{gr.caution}</p></div>
        )}
      </Section>
    </PageShell>
  );
}
