"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TOOLS: ToolSpec[] = [
  { id: "review", label: "Principles check", endpoint: "/api/frames/principles/review", note: "Describe a design, policy or setup. Finds wording that breaks defense in depth, least privilege, separation of duties, security by design, KISS, or leans on obscurity.",
    fields: [{ k: "text", label: "Describe the design", type: "area", rows: 5 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.text }) },
  { id: "cia", label: "CIA classifier", endpoint: "/api/frames/cia", note: "Describe an incident or a control. Which of confidentiality, integrity and availability does it touch?",
    fields: [{ k: "text", label: "Incident or control", type: "area", rows: 3 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.incident }) },
];

export function FrameTab() {
  const [id, setId] = useState("principles");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/frames/design/sample").then(setSamples).catch(() => setSamples(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id);
  return (
    <Section title="Security principles, CIA and NIST CSF" note="Thinking tools. They read what you type and the answers you give; nothing is scanned.">
      <Tabs tabs={[{ id: "principles", label: "The principles" }, ...TOOLS.map((t) => ({ id: t.id, label: t.label })), { id: "csf", label: "NIST CSF self-check" }]} value={id} onChange={setId} label="Security frameworks" />
      {id === "principles" && <Principles />}
      {spec && <ToolView key={id} spec={spec} samples={samples} />}
      {id === "csf" && <Csf />}
    </Section>
  );
}

function Principles() {
  const [d, setD] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/frames/principles").then(setD).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <Table caption="The five principles and the anti-principle" head={["Principle", "Means", "Example", "Red flag", "Ask"]} rows={d.principles.map((p: R) => [p.name, p.meaning, p.example, p.red_flag, p.ask])} />
      <Table caption="The CIA triad" head={["Property", "Means", "Attacks", "Controls"]} rows={Object.entries(d.cia).map(([k, v]: [string, any]) => [k, v.means, v.attacks, v.controls])} />
      <div><h4 className="text-sm font-semibold">Mistakes in the source material</h4><ul className="list-disc pl-5 text-sm">{d.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></div>
    </div>
  );
}

function Csf() {
  const [q, setQ] = useState<R | null>(null);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/frames/csf").then(setQ).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  const go = () => { setErr(null); postJson<R>("/api/frames/csf/score", { answers: ans }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Answer at least one question.")); }); };
  if (!q) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      {q.functions.map((f: R) => (
        <fieldset key={f.id} className="rounded border border-line p-3">
          <legend className="px-1 text-sm font-semibold">{f.name} {f.added && <Badge tone="muted">{f.added}</Badge>}</legend>
          <p className="mb-2 text-xs text-muted">{f.what}</p>
          {f.questions.map((x: R) => (
            <div key={x.id} className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="min-w-0 flex-1">{x.text}</span>
              <select className="field w-28" aria-label={x.text} value={ans[x.id] ?? ""} onChange={(e) => setAns((a) => { const n = { ...a }; if (e.target.value) n[x.id] = e.target.value; else delete n[x.id]; return n; })}>
                <option value="">—</option>{q.options.map((o: string) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
        </fieldset>
      ))}
      <button className="btn" onClick={go}>Score it</button>
      {err && <ErrorBanner message={err} />}
      {res && (
        <div className="space-y-3">
          <Stat label="Overall" value={`${res.overall}%`} />
          <Table caption="By function" head={["Function", "Score", "Answered", "Level"]} rows={res.functions.map((f: R) => [f.function, f.score ?? "—", `${f.answered}/${f.of}`, f.level])} />
          <Table caption="Do these next" head={["Function", "Gap", "Do"]} rows={res.next_actions.map((g: R) => [g.function, g.gap, g.do])} />
          <p className="text-xs text-muted">{res.note} {res.limit}</p>
        </div>
      )}
    </div>
  );
}
