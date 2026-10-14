"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TOOLS: ToolSpec[] = [
  { id: "systems", label: "Systems connectivity", endpoint: "/api/infoaudit/systems", note: "One line per system: name | information it holds (add * for the master) | where it sends data (target:auto or target:manual). Finds manual transfers, isolated systems and information with no master.",
    fields: [{ k: "text", label: "Systems", type: "area", rows: 7 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.systems }) },
  { id: "metrics", label: "Metric audit", endpoint: "/api/infoaudit/metrics", note: "One line per metric: metric | report | owner | decision it supports | reviewed (weekly, monthly, quarterly, yearly or never).",
    fields: [{ k: "text", label: "Metrics", type: "area", rows: 7 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.metrics }) },
  { id: "documents", label: "Document inventory", endpoint: "/api/infoaudit/documents", note: "One line per document: title | owner | location | version | last review (YYYY-MM-DD). Finds duplicates, version words in names, missing owners and stale reviews.",
    fields: [{ k: "text", label: "Documents", type: "area", rows: 7 }, { k: "stale", label: "Stale after (days)", type: "number", def: "365" }], build: (v) => ({ text: v.text, stale_days: Number(v.stale) }), sample: (s) => ({ text: s.documents }) },
  { id: "cost", label: "Search time cost", endpoint: "/api/infoaudit/search-cost", note: "What looking for information costs a year. Replace the guesses with a timed test.",
    fields: [{ k: "people", label: "People", type: "number", def: "40" }, { k: "per", label: "Searches per person per day", type: "number", def: "3" }, { k: "min", label: "Minutes per search", type: "number", def: "8" }, { k: "rate", label: "Hourly cost", type: "number", def: "35" }],
    build: (v) => ({ people: Number(v.people), searches_per_day: Number(v.per), minutes_each: Number(v.min), hourly_cost: Number(v.rate) }) },
  { id: "key", label: "Key-person risk", endpoint: "/api/infoaudit/key-person", note: "One line per responsibility: responsibility | primary | backup | documented (yes/no) | next audit or deadline (YYYY-MM-DD, optional). Answers: if this person left tomorrow?",
    fields: [{ k: "text", label: "Responsibilities", type: "area", rows: 7 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.key_person }) },
];

export function SotTab() {
  const [id, setId] = useState("systems");
  const [samples, setSamples] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/infoaudit/sample").then(setSamples).catch(() => setSamples(null)); getJson<R>("/api/infoaudit/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id)!;
  return (
    <Section title="Single source of truth audits" note="Reads rows you type. It cannot see your real systems; a clean result only means your list was clean.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={id} onChange={setId} label="Single source of truth audits" />
      <ToolView key={id} spec={spec} samples={samples} />
      {ref && <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the source whitepaper</summary><ul className="list-disc pl-5">{ref.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>}
    </Section>
  );
}
