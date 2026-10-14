"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { VendorTab } from "./VendorTab";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const DIMS: [string, string][] = [["value", "Business value"], ["frequency", "Frequency"], ["stability", "Process stability"], ["measurability", "Measurability"], ["risk", "Risk level (5 = contained)"]];
const STAGE_IDS: [string, string][] = [["outcome", "1 Outcome defined"], ["process", "2 Process mapped"], ["exceptions", "3 Exceptions mapped"], ["readiness", "4 Data and security audited"], ["allocation", "5 Work split human/AI"], ["trial", "6 Trial run"], ["expand", "7 Expansion reviewed"]];
const num = (s: string) => (s.trim() === "" ? null : Number(s));
const TOOLS: ToolSpec[] = [
  { id: "ready", label: "Readiness", endpoint: "/api/aiimpl/readiness", note: "Score each dimension 1 (worst) to 5 (best). The scale and pass mark are this app's own rule of thumb; the guide gives none.",
    fields: DIMS.map(([k, label]) => ({ k, label, type: "number" as const, def: "3" })), build: (v) => ({ scores: Object.fromEntries(DIMS.map(([k]) => [k, Number(v[k])])) }),
    sample: (s) => Object.fromEntries(DIMS.map(([k]) => [k, String(s.readiness[k])])) },
  { id: "check", label: "Seven-stage checklist", endpoint: "/api/aiimpl/checklist", note: "Mark the stages you have actually finished. It tells you the next one and whether a trial is justified.",
    fields: STAGE_IDS.map(([k, label]) => ({ k, label, type: "select" as const, options: ["no", "yes"], def: "no" })), build: (v) => ({ done: Object.fromEntries(STAGE_IDS.map(([k]) => [k, v[k] === "yes"])) }) },
  { id: "exc", label: "Exception map", endpoint: "/api/aiimpl/exceptions", note: "One line per case: case | share % | rule-based (yes/no) | owner | what goes wrong. Shows how much is predictable and which exceptions have no owner.",
    fields: [{ k: "text", label: "Cases", type: "area", rows: 7 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.exceptions }) },
  { id: "auto", label: "Autonomy level", endpoint: "/api/aiimpl/autonomy", note: "Which of four levels the evidence supports. Uses the lower confidence bound of the accuracy on reviewed cases, not the raw percentage.",
    fields: [{ k: "cost", label: "Cost of an error", type: "select", options: ["low", "medium", "high"], def: "medium" }, { k: "rev", label: "Can it be undone?", type: "select", options: ["easy", "hard", "irreversible"], def: "easy" },
      { k: "reg", label: "Regulated?", type: "select", options: ["no", "yes"], def: "no" }, { k: "ok", label: "Cases reviewed and correct", type: "number", def: "290" }, { k: "n", label: "Cases reviewed", type: "number", def: "300" }, { k: "exc", label: "Exception share (%)", type: "number", def: "5" }],
    build: (v) => ({ error_cost: v.cost, reversible: v.rev, regulated: v.reg === "yes", correct: Number(v.ok), reviewed: Number(v.n), exception_pct: Number(v.exc) }) },
  { id: "value", label: "What can I claim?", endpoint: "/api/aiimpl/value-check", note: "Before and after numbers plus adoption, escalation and accuracy. Separates: the model works, it fits the workflow, people use it, the business number moved. Leave a box empty if you do not know.",
    fields: [{ k: "bc", label: "Baseline cycle (hours)", type: "number", def: "96" }, { k: "cc", label: "Current cycle (hours)", type: "number", def: "60" }, { k: "be", label: "Baseline error (%)", type: "number", def: "6" }, { k: "ce", label: "Current error (%)", type: "number", def: "4" },
      { k: "bt", label: "Baseline cost per item", type: "number", def: "11" }, { k: "ct", label: "Current cost per item", type: "number", def: "8" }, { k: "ad", label: "Adoption (%)", type: "number", def: "80" }, { k: "es", label: "Escalation (%)", type: "number", def: "12" },
      { k: "ac", label: "Accuracy (%)", type: "number", def: "95" }, { k: "tc", label: "Tool cost per month", type: "number", def: "2000" }, { k: "vol", label: "Items per month", type: "number", def: "5000" }],
    build: (v) => ({ baseline: { cycle_hours: num(v.bc), error_pct: num(v.be), cost_per_txn: num(v.bt) }, current: { cycle_hours: num(v.cc), error_pct: num(v.ce), cost_per_txn: num(v.ct) },
      adoption_pct: num(v.ad), escalation_pct: num(v.es), accuracy_pct: num(v.ac), tool_cost_per_month: Number(v.tc || 0), volume_per_month: Number(v.vol || 0) }) },
];

export function ImplPanel() {
  const [id, setId] = useState("ready");
  const [samples, setSamples] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [vref, setVref] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/aiimpl/vendor/reference").then(setVref).catch(() => setVref(null)); getJson<R>("/api/aiimpl/sample").then(setSamples).catch(() => setSamples(null)); getJson<R>("/api/aiimpl/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id);
  return (
    <Section title="AI implementation planner" note="Organises what you found in a real workflow. It cannot observe the workflow, and its scales are rules of thumb, not standards.">
      <Tabs tabs={[...TOOLS.map((t) => ({ id: t.id, label: t.label })), { id: "vendor", label: "Vendor scorecard" }]} value={id} onChange={setId} label="AI implementation planner" />
      {spec ? <ToolView key={id} spec={spec} samples={samples} /> : <VendorTab />}
      {ref && <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the source guides</summary><ul className="list-disc pl-5">{[...ref.slips, ...(vref?.slips ?? [])].map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>}
    </Section>
  );
}
