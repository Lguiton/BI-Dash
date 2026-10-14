"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const area = (k: string, label: string, def: string, rows = 5) => ({ k, label, type: "area" as const, def, rows });
const num = (k: string, label: string, def: string) => ({ k, label, type: "number" as const, def });

const TOOLS: ToolSpec[] = [
  { id: "dbt", label: "Model builder (dbt-style)", endpoint: "/api/datalab/dbt", note: "Seeds are small tables you paste as CSV. Models are SELECTs that read each other with ref(). The tool works out the build order, builds them in a private in-memory database, and runs your tests. It never touches your own data.",
    fields: [area("s", "Seeds (-- seed: name, then CSV)", "", 7), area("m", "Models (-- model: name, then SELECT)", "", 8), area("t", "Tests", "", 4)], build: (v) => ({ seeds: v.s, models: v.m, tests: v.t }), sample: (s) => ({ s: s.dbt.seeds, m: s.dbt.models, t: s.dbt.tests }) },
  { id: "calc", label: "Formula engine", endpoint: "/api/datalab/formulas", note: "One cell per line, like A1: 10 or B1: =A1*2. Supports SUM, AVERAGE, MIN, MAX, COUNT, IF, AND, OR, NOT, ROUND, IFERROR, SUMIF, COUNTIF, VLOOKUP and a few text functions. Shows the calculation order and finds circular references.",
    fields: [area("c", "Cells", "A1: 10\nA2: 20\nA3: =SUM(A1:A2)", 12)], build: (v) => ({ cells: v.c }), sample: (s) => ({ c: s.calc }) },
  { id: "dag", label: "Task scheduler", endpoint: "/api/datalab/dag", note: "One task per line: name | depends on (comma list or -) | minutes | fails first N times | retries | retry delay minutes. Time is simulated; nothing runs.",
    fields: [area("t", "Tasks", "", 7), num("w", "Workers at once", "2")], build: (v) => ({ tasks: v.t, workers: Number(v.w) }), sample: (s) => ({ t: s.dag.tasks, w: String(s.dag.workers) }) },
  { id: "cron", label: "Cron schedule", endpoint: "/api/datalab/cron", note: "Five fields: minute hour day-of-month month day-of-week. Shows the next run times.",
    fields: [{ k: "e", label: "Expression", type: "text", def: "30 2 * * 1-5" }, { k: "s", label: "Start from (optional, 2026-03-01 08:30)", type: "text", def: "" }, num("n", "How many", "5")], build: (v) => ({ expression: v.e, start: v.s, count: Number(v.n) }) },
  { id: "stream", label: "Stream simulator", endpoint: "/api/datalab/stream", note: "Events are 'event_time key value' in arrival order. See which partition each key lands in, how consumers share them, and which late events are dropped.",
    fields: [area("e", "Events", "", 7), num("p", "Partitions", "3"), num("c", "Consumers", "2"), { k: "k", label: "Window", type: "select", options: ["tumbling", "sliding", "session"], def: "tumbling" }, num("w", "Window size (or session gap for session)", "10"), num("sl", "Sliding step", "5"), num("l", "Allowed lateness", "2")],
    build: (v) => ({ events: v.e, partitions: Number(v.p), consumers: Number(v.c), kind: v.k, window: Number(v.w), slide: Number(v.sl), lateness: Number(v.l), gap: Number(v.w) }), sample: (s) => ({ e: s.stream.events, p: String(s.stream.partitions), c: String(s.stream.consumers), w: String(s.stream.window), l: String(s.stream.lateness) }) },
];

export function DataLab() {
  const [ref, setRef] = useState<R | null>(null);
  const [id, setId] = useState("dbt");
  useEffect(() => { getJson<R>("/api/datalab/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id) ?? TOOLS[0];
  return (
    <Section title="Data tools lab" note="Small, safe versions of tools data teams use: model builds with tests, spreadsheet formulas, job scheduling and streams. They teach how the tools decide; for production use the real tools.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={spec.id} onChange={setId} label="Data tools" />
      <ToolView key={spec.id} spec={spec} samples={ref?.samples ?? null} />
      {ref && <>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes common in the sources</summary><ul className="list-disc pl-5">{ref.slips.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary><ul className="list-disc pl-5">{ref.not_built.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      </>}
    </Section>
  );
}
