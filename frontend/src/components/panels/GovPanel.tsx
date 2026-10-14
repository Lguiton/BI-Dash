"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const lines = (t: string) => String(t).split("\n").map((x) => x.trim()).filter(Boolean);
const tone = (t: string): "ok" | "warn" | "bad" => (t === "high" ? "bad" : t === "medium" ? "warn" : "ok");
const json = (t: string, what: string) => { try { return JSON.parse(t); } catch { throw new Error(`${what} isn't valid JSON.`); } };

const TOOLS: ToolSpec[] = [
  { id: "shadow", label: "Shadow AI check", endpoint: "/api/aigov/shadow", note: "List the AI things you actually see in use (names in logs, keys, tool lists). Compared with the registry.",
    fields: [{ k: "names", label: "Seen in use (one per line)", type: "area", rows: 5 }], build: (v) => ({ names: lines(v.names) }), sample: (s) => ({ names: s.observed }) },
  { id: "policy", label: "Policy simulator", endpoint: "/api/aigov/policy", note: "Rules: effect, role, action, data class, kind (use * for any). Deny beats approve beats allow. Requests: role, action, data class, kind.",
    fields: [{ k: "rules", label: "Rules", type: "area", rows: 5 }, { k: "requests", label: "Requests", type: "area", rows: 5 }, { k: "default", label: "When nothing matches", type: "select", options: ["deny", "approve", "allow"], def: "deny" }],
    build: (v) => ({ rules: v.rules, requests: v.requests, default: v.default }), sample: (s) => ({ rules: s.rules, requests: s.requests }) },
  { id: "spend", label: "Spend attribution", endpoint: "/api/aigov/spend", note: "Paste usage as CSV (user, team, app, model, input_tokens, output_tokens, task) and a price per million tokens. See who spends what, check budgets and test a cheaper model for simple tasks.",
    fields: [{ k: "usage", label: "Usage CSV", type: "area", rows: 7 }, { k: "prices", label: "Prices per million tokens (JSON)", type: "area", rows: 4 }, { k: "budgets", label: "Team budgets (JSON, optional)", def: '{"platform": 3, "support": 5}' }, { k: "cheap", label: "Cheaper model for simple tasks (optional)", def: "small-model" }],
    build: (v) => ({ usage: v.usage, prices: json(v.prices, "Prices"), budgets: v.budgets ? json(v.budgets, "Budgets") : null, cheap_model: v.cheap }), sample: (s) => ({ usage: s.usage, prices: s.prices }) },
];

export function GovPanel() {
  const [id, setId] = useState("registry");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/aigov/sample").then(setSamples).catch(() => setSamples(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id);
  return (
    <Section title="AI governance lab" note="Paperwork and arithmetic over what you enter. Nothing calls a model or a gateway, and nothing is enforced: a real gateway and your login system do that. Not legal advice.">
      <Tabs tabs={[{ id: "registry", label: "AI asset registry" }, { id: "tier", label: "Risk tier" }, ...TOOLS.map((t) => ({ id: t.id, label: t.label })), { id: "ref", label: "Reference" }]} value={id} onChange={setId} label="AI governance" />
      {id === "registry" && <Registry />}
      {id === "tier" && <Tier />}
      {spec && <ToolView key={id} spec={spec} samples={samples} />}
      {id === "ref" && <Reference />}
    </Section>
  );
}

const EMPTY = { name: "", kind: "agent", owner: "", purpose: "", provider: "internal", data_class: "internal", pii: false, actions: [] as string[], autonomy: "suggest", human_oversight: false, approved: false, traced: false, last_review: "" };

function Registry() {
  const [d, setD] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [f, setF] = useState<R>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => { getJson<R>("/api/aigov/assets").then(setD).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  useEffect(() => { load(); getJson<R>("/api/aigov/reference").then(setRef).catch(() => undefined); }, [load]);
  const save = () => { setErr(null); postJson<R>("/api/aigov/assets", f).then(() => { setF(EMPTY); load(); }).catch((e) => setErr(errMsg(e, "Could not save."))); };
  const del = (id: string) => { deleteJson<R>(`/api/aigov/assets/${id}`).then(load).catch((e) => setErr(errMsg(e, "Could not delete."))); };
  const sel = (k: string, label: string, opts: string[]) => <Field label={label}><select className="field" aria-label={label} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}>{opts.map((x) => <option key={x}>{x}</option>)}</select></Field>;
  const chk = (k: string, label: string) => <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} />{label}</label>;
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <Field label="Name"><input className="field" aria-label="Asset name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        {sel("kind", "Kind", ref?.kinds ?? ["agent"])}
        <Field label="Owner"><input className="field" aria-label="Owner" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} /></Field>
        {sel("provider", "Provider", ["internal", "external"])}
        {sel("data_class", "Most sensitive data", ref?.data_classes ?? ["internal"])}
        {sel("autonomy", "Autonomy", ref?.autonomy ?? ["suggest"])}
        <Field label="Last review (YYYY-MM-DD)"><input className="field" aria-label="Last review" value={f.last_review} onChange={(e) => setF({ ...f, last_review: e.target.value })} /></Field>
        <div className="sm:col-span-2"><Field label="Purpose"><input className="field" aria-label="Purpose" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} /></Field></div>
      </div>
      <div className="flex flex-wrap gap-3">
        {(ref?.actions ?? []).map((a: string) => <label key={a} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={f.actions.includes(a)} onChange={(e) => setF({ ...f, actions: e.target.checked ? [...f.actions, a] : f.actions.filter((x: string) => x !== a) })} />can {a.replace("_", " ")}</label>)}
        {chk("pii", "Handles personal data")}{chk("human_oversight", "Human oversight")}{chk("approved", "Approved")}{chk("traced", "Actions traced")}
      </div>
      <button className="btn" onClick={save}>Register asset</button>
      {d && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Assets" value={String(d.count)} /><Stat label="High risk" value={String(d.tiers.high)} /><Stat label="Medium" value={String(d.tiers.medium)} /><Stat label="With issues" value={String(d.with_issues)} /></div>
          {d.assets.length > 0 && <Table caption="Registered AI assets" head={["Name", "Kind", "Owner", "Risk", "Issues", ""]} rows={d.assets.map((a: R) => [a.name, a.kind, a.owner || "—", <Badge key="t" tone={tone(a.tier)}>{a.tier}</Badge>, a.issues.length ? <ul key="i" className="list-disc pl-4">{a.issues.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : "None", <button key="d" className="btn" aria-label={`Delete ${a.name}`} onClick={() => del(a.id)}>Delete</button>])} />}
        </div>
      )}
    </div>
  );
}

function Tier() {
  const [ref, setRef] = useState<R | null>(null);
  const [a, setA] = useState<Record<string, boolean>>({});
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/aigov/reference").then(setRef).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  const go = () => { setErr(null); postJson<R>("/api/aigov/risk-tier", { answers: a }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Could not classify.")); }); };
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const group = (title: string, items: R) => (
    <fieldset className="rounded border border-line p-3"><legend className="px-1 text-sm font-semibold">{title}</legend>
      {Object.entries(items).map(([k, v]) => <label key={k} className="mb-1 flex items-center gap-2 text-sm"><input type="checkbox" checked={!!a[k]} onChange={(e) => setA({ ...a, [k]: e.target.checked })} />{String(v)}</label>)}
    </fieldset>
  );
  return (
    <div className="space-y-3">
      <p className="text-sm">Tick what your AI use case does. Modelled on the EU AI Act&apos;s four levels as a learning aid.</p>
      {group("Practices usually banned", ref.prohibited_triggers)}{group("High-risk areas", ref.high_risk_triggers)}{group("Transparency", ref.transparency_triggers)}
      <button className="btn" onClick={go}>Classify</button>
      {err && <ErrorBanner message={err} />}
      {res && (
        <div className="space-y-2">
          <Stat label="Tier" value={res.tier} />
          <p className="text-sm"><b>Because:</b> {res.because.join("; ")}</p>
          <div><h4 className="text-sm font-semibold">Controls to put in place</h4><ul className="list-disc pl-5 text-sm">{res.controls.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul></div>
          <p className="text-sm"><b>NIST AI RMF:</b> {res.nist_ai_rmf}</p>
          <p className="text-xs text-muted">{res.limit}</p>
        </div>
      )}
    </div>
  );
}

function Reference() {
  const [d, setD] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/aigov/reference").then(setD).catch(() => setD(null)); }, []);
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  const list = (title: string, items: string[]) => <div><h4 className="text-sm font-semibold">{title}</h4><ul className="list-disc pl-5 text-sm">{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div>;
  return (
    <div className="space-y-3">
      <Table caption="Ideas from the book and where they are here" head={["Idea", "NIST AI RMF", "In this app", "Limit"]} rows={d.crosswalk.map((c: R) => [c.idea, c.nist_ai_rmf, c.in_this_app, c.limit])} />
      {list("What the book leaves out", d.gaps_in_the_book)}
      {list("Mistakes and overclaims in the source", d.slips)}
      {list("Not built (needs a platform)", d.not_built)}
    </div>
  );
}
