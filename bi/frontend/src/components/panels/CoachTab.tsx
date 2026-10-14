"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TOOLS: ToolSpec[] = [
  { id: "report", label: "Check a new ticket", endpoint: "/api/infra/ticket/review", note: "Paste the title and description. It shows what a technician would still have to ask, and a template to fill in.",
    fields: [{ k: "title", label: "Title", def: "" }, { k: "body", label: "Description", type: "area", rows: 7 }], build: (v) => ({ title: v.title, body: v.body }), sample: (s) => ({ title: s.bad.title, body: s.bad.body }) },
  { id: "good", label: "Try a good example", endpoint: "/api/infra/ticket/review", note: "A well-written ticket for comparison. Load it, run it, and see what a high score looks like.",
    fields: [{ k: "title", label: "Title" }, { k: "body", label: "Description", type: "area", rows: 7 }], build: (v) => ({ title: v.title, body: v.body }), sample: (s) => ({ title: s.good.title, body: s.good.body }) },
  { id: "res", label: "Check a closing note", endpoint: "/api/infra/ticket/resolution", note: "A good closing note holds the cause, the fix, the check and a way to prevent a repeat, so the next person with this problem can use it.",
    fields: [{ k: "note", label: "Resolution note", type: "area", rows: 5 }], build: (v) => ({ note: v.note }), sample: (s) => ({ note: s.resolution.note }) },
  { id: "prio", label: "Suggest a priority", endpoint: "/api/infra/ticket/priority", note: "Impact (how many people, how important) by urgency (workaround, deadline).",
    fields: [{ k: "n", label: "People affected", type: "number", def: "1" }, { k: "wa", label: "Is there a workaround?", type: "select", options: ["yes", "no"], def: "yes" }, { k: "dl", label: "Deadline today?", type: "select", options: ["no", "yes"], def: "no" }, { k: "sec", label: "Security related?", type: "select", options: ["no", "yes"], def: "no" }, { k: "bc", label: "Business critical?", type: "select", options: ["no", "yes"], def: "no" }],
    build: (v) => ({ users_affected: Number(v.n), workaround: v.wa === "yes", deadline: v.dl === "yes", security: v.sec === "yes", business_critical: v.bc === "yes" }) },
];

export function CoachTab() {
  const [id, setId] = useState("report");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/infra/ticket/sample").then(setSamples).catch(() => setSamples(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id)!;
  return (
    <Section title="Ticket-writing coach" note="A ticket is a message to someone who cannot see your screen. These checks look for the information they will need. They match words, so they cannot tell whether the details are right.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={id} onChange={setId} label="Ticket coach tools" />
      <ToolView key={id} spec={spec} samples={samples} />
    </Section>
  );
}
