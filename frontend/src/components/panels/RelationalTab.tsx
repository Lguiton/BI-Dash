"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson } from "./analysisKit";

interface Attr { name: string; type?: string; pk?: boolean; required?: boolean; unique?: boolean }
interface Ent { name: string; attributes: Attr[] }
interface Rel { a: string; b: string; kind: string }
interface Ref {
  concepts: { term: string; what: string }[]; topologies: { name: string; what: string; example: string; note: string }[]; distributed: { name: string; what: string; note: string }[];
  roles: { role: string; does: string; tools: string }[]; history: { when: string; what: string }[]; products: { name: string; facts: string[]; free: string }[]; licensing: string;
  practices: { name: string; what: string }[]; slips: string[]; types: string[]; kinds: string[]; example: { entities: Ent[]; relationships: Rel[] }; note: string;
}
interface ErdRes { ddl: string[]; tables: string[]; diagram: string[]; notes: string[]; lesson: string }
interface An { degree: number; cardinality: number; schema: { name: string; type: string }[]; candidate_keys: string[][]; dependencies: { lhs: string; rhs: string }[]; hints: { kind: string; text: string }[]; caution: string; lesson: string; demo: boolean }
interface Dep { holds: boolean; text: string; violations: Record<string, unknown>[]; violation_groups: number }
interface Tbl { table_name: string; label: string; rows_count: number }
const Code = ({ children }: { children: string }) => <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded border border-line bg-panel2 p-2 text-xs">{children}</pre>;
const TABS = [{ id: "erd", label: "ERD to tables" }, { id: "keys", label: "Keys and dependencies" }, { id: "model", label: "Relational model" }, { id: "arch", label: "Architecture and scale" }, { id: "who", label: "Roles and products" }];

export function RelationalTab() {
  const [ref, setRef] = useState<Ref | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("erd");
  const [ents, setEnts] = useState<Ent[]>([]);
  const [rels, setRels] = useState<Rel[]>([]);
  const [audit, setAudit] = useState(false);
  const [erd, setErd] = useState<ErdRes | null>(null);
  const [tables, setTables] = useState<Tbl[]>([]);
  const [src, setSrc] = useState("demo");
  const [an, setAn] = useState<An | null>(null);
  const [kind, setKind] = useState("fd");
  const [lhs, setLhs] = useState("");
  const [rhs, setRhs] = useState("");
  const [dep, setDep] = useState<Dep | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    getJson<Ref>("/api/relational").then((r) => { setRef(r); setEnts(r.example.entities); setRels(r.example.relationships); }).catch((e) => setErr(errMsg(e, "Couldn't load the lab.")));
    getJson<{ tables: Tbl[] }>("/api/data/tables").then((d) => setTables(d.tables)).catch(() => setTables([]));
  }, []);
  const build = () => { setErr(null); postJson<ErdRes>("/api/relational/erd", { entities: ents, relationships: rels, audit_columns: audit }).then(setErd).catch((e) => { setErd(null); setErr(errMsg(e, "Check the design.")); }); };
  const body = () => (src === "demo" ? { demo: true } : { table: src });
  const look = () => { setBusy(true); setErr(null); setDep(null); postJson<An>("/api/relational/analyze", body()).then((r) => { setAn(r); setLhs(r.schema[0]?.name ?? ""); setRhs(r.schema[1]?.name ?? ""); }).catch((e) => { setAn(null); setErr(errMsg(e, "Couldn't analyze that.")); }).finally(() => setBusy(false)); };
  const test = () => { setErr(null); postJson<Dep>("/api/relational/dependency", { ...body(), kind, lhs: [lhs], rhs: [rhs] }).then(setDep).catch((e) => { setDep(null); setErr(errMsg(e, "Couldn't test that.")); }); };
  const setEnt = (i: number, f: (e: Ent) => Ent) => setEnts(ents.map((x, j) => (j === i ? f(x) : x)));
  if (!ref) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <Lesson text={ref.note} />
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setErr(null); }} label="Relational design" />
      {err && <ErrorBanner message={err} />}
      {tab === "erd" && (
        <div className="space-y-3">
          <Section title="1. Entities and attributes" note="Entities become tables and attributes become columns. Mark one attribute as the primary key, or one is added for you. The sample is author and book.">
            <div className="space-y-3">{ents.map((e, i) => (
              <div key={i} className="rounded border border-line p-2">
                <div className="flex flex-wrap items-end gap-2"><Field label="Entity (table)"><input className="field" value={e.name} onChange={(x) => setEnt(i, (o) => ({ ...o, name: x.target.value }))} /></Field>
                  <button className="btn" onClick={() => setEnts(ents.filter((_, j) => j !== i))}>Remove entity</button></div>
                <div className="mt-2 space-y-1">{e.attributes.map((a, k) => (
                  <div key={k} className="grid grid-cols-2 items-center gap-2 sm:grid-cols-6">
                    <input className="field" aria-label="Attribute" value={a.name} onChange={(x) => setEnt(i, (o) => ({ ...o, attributes: o.attributes.map((y, m) => (m === k ? { ...y, name: x.target.value } : y)) }))} />
                    <select className="field" aria-label="Type" value={a.type ?? "text"} onChange={(x) => setEnt(i, (o) => ({ ...o, attributes: o.attributes.map((y, m) => (m === k ? { ...y, type: x.target.value } : y)) }))}>{ref.types.map((t) => <option key={t}>{t}</option>)}</select>
                    {(["pk", "required", "unique"] as const).map((f) => <label key={f} className="text-xs"><input type="checkbox" checked={!!a[f]} onChange={(x) => setEnt(i, (o) => ({ ...o, attributes: o.attributes.map((y, m) => (m === k ? { ...y, [f]: x.target.checked } : y)) }))} /> {f === "pk" ? "Primary key" : f === "required" ? "Required" : "Unique"}</label>)}
                    <button className="btn" onClick={() => setEnt(i, (o) => ({ ...o, attributes: o.attributes.filter((_, m) => m !== k) }))}>Remove</button></div>))}</div>
                <button className="btn mt-2" onClick={() => setEnt(i, (o) => ({ ...o, attributes: [...o.attributes, { name: "", type: "text" }] }))}>Add attribute</button>
              </div>))}</div>
            <button className="btn mt-2" onClick={() => setEnts([...ents, { name: "", attributes: [{ name: "", type: "text" }] }])}>Add entity</button>
          </Section>
          <Section title="2. Relationships" note="1:N means one A has many B (the foreign key goes in B). M:N becomes its own link table. 1:1 puts a unique foreign key in B.">
            <div className="space-y-1">{rels.map((r, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <select className="field" aria-label="From entity" value={r.a} onChange={(x) => setRels(rels.map((y, j) => (j === i ? { ...y, a: x.target.value } : y)))}><option value="">A…</option>{ents.map((e) => <option key={e.name}>{e.name}</option>)}</select>
                <select className="field" aria-label="Kind" value={r.kind} onChange={(x) => setRels(rels.map((y, j) => (j === i ? { ...y, kind: x.target.value } : y)))}>{ref.kinds.map((k) => <option key={k}>{k}</option>)}</select>
                <select className="field" aria-label="To entity" value={r.b} onChange={(x) => setRels(rels.map((y, j) => (j === i ? { ...y, b: x.target.value } : y)))}><option value="">B…</option>{ents.map((e) => <option key={e.name}>{e.name}</option>)}</select>
                <button className="btn" onClick={() => setRels(rels.filter((_, j) => j !== i))}>Remove</button></div>))}</div>
            <div className="mt-2 flex flex-wrap items-center gap-3"><button className="btn" onClick={() => setRels([...rels, { a: "", b: "", kind: "1:N" }])}>Add relationship</button>
              <label className="text-sm"><input type="checkbox" checked={audit} onChange={(e) => setAudit(e.target.checked)} /> Add a &ldquo;last modified&rdquo; column</label>
              <button className="btn btn-primary" onClick={build}>Make the tables</button></div>
          </Section>
          {erd && <Section title="3. Result (tested: every statement ran)">
            {erd.diagram.length > 0 && <Code>{erd.diagram.join("\n")}</Code>}
            <Code>{erd.ddl.join("\n\n")}</Code>
            <ul className="mt-2 list-disc pl-5 text-sm">{erd.notes.map((n, i) => <li key={i}>{n}</li>)}</ul><p className="mt-2 text-xs text-muted">{erd.lesson} Run the SQL in your own database; this tab never changes your data.</p>
          </Section>}
          <Section title="Design habits that keep a database healthy"><Table head={["Habit", "What it means"]} rows={ref.practices.map((p) => [p.name, p.what])} /></Section>
        </div>
      )}
      {tab === "keys" && (
        <div className="space-y-3">
          <Section title="Find keys and dependencies in a table" note="Pick the built-in example (the course's employee and project table) or one of your imported tables.">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Table"><select className="field" value={src} onChange={(e) => { setSrc(e.target.value); setAn(null); setDep(null); }}><option value="demo">Built-in example: employee projects</option>{tables.map((t) => <option key={t.table_name} value={t.table_name}>{t.label} ({t.rows_count.toLocaleString()} rows)</option>)}</select></Field>
              <button className="btn btn-primary" disabled={busy} onClick={look}>{busy ? "Looking…" : "Analyze"}</button></div>
          </Section>
          {an && <>
            <div className="grid gap-3 sm:grid-cols-3"><Stat label="Degree (columns)" value={String(an.degree)} /><Stat label="Cardinality (rows)" value={an.cardinality.toLocaleString()} /><Stat label="Candidate keys" value={String(an.candidate_keys.length)} /></div>
            <Section title="Candidate keys">{an.candidate_keys.length ? <ul className="list-disc pl-5 text-sm">{an.candidate_keys.map((k, i) => <li key={i}>{k.join(" + ")}</li>)}</ul> : <p className="text-sm">None found.</p>}</Section>
            <Section title="Rules that hold in this data (A → B)">{an.dependencies.length ? <Table head={["If you know", "you know"]} rows={an.dependencies.map((d) => [d.lhs, d.rhs])} /> : <p className="text-sm">No single-column rules found.</p>}</Section>
            {an.hints.length > 0 && <Section title="What it suggests">{an.hints.map((h, i) => <p key={i} className="mb-1 text-sm"><Badge tone="warn">{h.kind}</Badge> {h.text}</p>)}</Section>}
            <Lesson text={`${an.lesson} ${an.caution}`} />
            <Section title="Test a rule yourself">
              <div className="flex flex-wrap items-end gap-3">
                <Field label="Kind"><select className="field" value={kind} onChange={(e) => { setKind(e.target.value); setDep(null); }}><option value="fd">Functional: A → B</option><option value="mvd">Multi-valued: A →→ B</option></select></Field>
                <Field label="A"><select className="field" value={lhs} onChange={(e) => setLhs(e.target.value)}>{an.schema.map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
                <Field label="B"><select className="field" value={rhs} onChange={(e) => setRhs(e.target.value)}>{an.schema.map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
                <button className="btn" onClick={test}>Test</button></div>
              {dep && <div className="mt-2"><p className="text-sm" role="status"><Badge tone={dep.holds ? "ok" : "bad"}>{dep.holds ? "holds" : "does not hold"}</Badge> {dep.text}</p>
                {dep.violations.length > 0 && <Table head={Object.keys(dep.violations[0])} rows={dep.violations.map((v) => Object.values(v).map((x) => (Array.isArray(x) ? x.join(", ") : String(x))))} caption="Where it breaks" />}</div>}
            </Section></>}
          <Section title="Slips to watch for in the course notes"><ul className="list-disc pl-5 text-sm">{ref.slips.map((s, i) => <li key={i}>{s}</li>)}</ul></Section>
        </div>
      )}
      {tab === "model" && (
        <div className="space-y-3"><Section title="Relational model terms"><Table head={["Term", "Meaning"]} rows={ref.concepts.map((c) => [c.term, c.what])} /></Section>
          <Section title="A short history"><Table head={["When", "What happened"]} rows={ref.history.map((h) => [h.when, h.what])} /></Section></div>
      )}
      {tab === "arch" && (
        <div className="space-y-3"><Section title="Deployment topologies"><Table head={["Topology", "What it is", "Example", "Worth knowing"]} rows={ref.topologies.map((t) => [t.name, t.what, t.example, t.note])} /></Section>
          <Section title="Distributed and clustered databases" note="These need several servers and can't run in this app. Read them as design choices to weigh."><Table head={["Idea", "What it is", "Worth knowing"]} rows={ref.distributed.map((t) => [t.name, t.what, t.note])} /></Section></div>
      )}
      {tab === "who" && (
        <div className="space-y-3"><Section title="Who uses a database, and with what"><Table head={["Role", "What they do", "Typical tools"]} rows={ref.roles.map((r) => [r.role, r.does, r.tools])} /></Section>
          {ref.products.map((p) => <Section key={p.name} title={p.name}><ul className="list-disc pl-5 text-sm">{p.facts.map((f, i) => <li key={i}>{f}</li>)}</ul><p className="mt-2 text-xs text-muted">{p.free}</p></Section>)}
          <Lesson text={ref.licensing} /></div>
      )}
    </div>
  );
}
