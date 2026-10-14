"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const CONF = { k: "conf", label: "Confidence (90, 95 or 99)", type: "number" as const, def: "95" };
const TOOLS: ToolSpec[] = [
  { id: "prop", label: "How far can this percent move?", endpoint: "/api/surveystats/proportion", note: "A survey percentage is an estimate. Enter the percent and how many people answered.",
    fields: [{ k: "p", label: "Percent", type: "number", def: "57" }, { k: "n", label: "People who answered", type: "number", def: "150" }, CONF], build: (v) => ({ percent: Number(v.p), n: Number(v.n), confidence: Number(v.conf) }) },
  { id: "cmp", label: "Is this gap real?", endpoint: "/api/surveystats/compare", note: "Two percentages from two separate groups, for example 44% of 150 last year and 57% of 150 this year. Small subgroups make big gaps that mean little.",
    fields: [{ k: "p1", label: "First percent", type: "number", def: "57" }, { k: "n1", label: "First group size", type: "number", def: "150" }, { k: "p2", label: "Second percent", type: "number", def: "44" }, { k: "n2", label: "Second group size", type: "number", def: "150" }, CONF],
    build: (v) => ({ percent1: Number(v.p1), n1: Number(v.n1), percent2: Number(v.p2), n2: Number(v.n2), confidence: Number(v.conf) }) },
  { id: "size", label: "How many people do I need?", endpoint: "/api/surveystats/sample-size", note: "Sample size for a wanted margin of error. Each subgroup you report needs this many by itself.",
    fields: [{ k: "m", label: "Margin (± points)", type: "number", def: "5" }, { k: "e", label: "Expected percent", type: "number", def: "50" }, CONF], build: (v) => ({ margin_points: Number(v.m), expected_percent: Number(v.e), confidence: Number(v.conf) }) },
  { id: "multi", label: "Pick-one or pick-several?", endpoint: "/api/surveystats/multi-select", note: "One line per answer: answer | percent. If the total is over 100, people picked more than one and 'greatest' wording is misleading.",
    fields: [{ k: "text", label: "Answers", type: "area", rows: 5 }, { k: "n", label: "People (optional)", type: "number", def: "150" }], build: (v) => ({ text: v.text, n: v.n ? Number(v.n) : null }), sample: (s) => ({ text: s.sample.multi }) },
  { id: "joint", label: "Joint and marginal table", endpoint: "/api/surveystats/joint", note: "One line per cell: x | y | probability. Gives row and column totals, conditionals, whether X and Y are independent, and covariance when values are numbers.",
    fields: [{ k: "text", label: "Cells", type: "area", rows: 6 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.sample.joint }) },
];

export function SurveyPanel() {
  const [id, setId] = useState("prop");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/surveystats/reference").then(setSamples).catch(() => setSamples(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id)!;
  return (
    <Section title="Survey numbers and probability tables" note="Assumes a simple random sample. A real survey with weights has wider error. These teach the idea; they do not replace the pollster's method.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={id} onChange={setId} label="Survey numbers" />
      <ToolView key={id} spec={spec} samples={samples} />
      {samples && <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the source sheet and report</summary><ul className="list-disc pl-5">{samples.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>}
    </Section>
  );
}
