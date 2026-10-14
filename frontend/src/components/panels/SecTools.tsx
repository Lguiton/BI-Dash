"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const area = (k: string, label: string, def: string, rows = 5) => ({ k, label, type: "area" as const, def, rows });

const TOOLS: ToolSpec[] = [
  { id: "jwt", label: "Token (JWT) inspector", endpoint: "/api/sectools/jwt", note: "Decodes a JWT and lists weaknesses. Decoding is not verifying. Do not paste live production tokens; use a test token.",
    fields: [area("t", "Token", "", 4), { k: "s", label: "Shared secret to check HS256 (optional, test only)", type: "text", def: "" }], build: (v) => ({ token: v.t, secret: v.s || null }) },
  { id: "cert", label: "Certificate inspector", endpoint: "/api/sectools/cert", note: "Paste a public certificate (BEGIN CERTIFICATE). Never paste a private key.",
    fields: [area("p", "Certificate (PEM)", "", 8)], build: (v) => ({ pem: v.p }) },
  { id: "cvss", label: "CVSS 3.1 score", endpoint: "/api/sectools/cvss", note: "Turns a CVSS 3.1 vector into the base score and explains each metric.",
    fields: [{ k: "v", label: "Vector", type: "text", def: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" }], build: (v) => ({ vector: v.v }), sample: (s) => ({ v: s.cvss }) },
  { id: "stride", label: "STRIDE worksheet", endpoint: "/api/sectools/stride", note: "List the parts of your design: 'name | external, process, store or flow'. Get the threat questions for each.",
    fields: [area("t", "Elements", "User | external\nWeb app | process\nOrders database | store", 7)], build: (v) => ({ text: v.t }), sample: (s) => ({ t: s.stride }) },
  { id: "code", label: "Code pattern scanner", endpoint: "/api/sectools/code-scan", note: "A first-pass scan of pasted code for common weak patterns. It reads lines, not meaning, and misses and over-flags. Secrets are masked in the results.",
    fields: [area("t", "Code", "", 10)], build: (v) => ({ text: v.t }), sample: (s) => ({ t: s.code }) },
  { id: "sigma", label: "Detection rule tester", endpoint: "/api/sectools/sigma", note: "Write a Sigma-style rule (YAML) and test it against events, one JSON object per line.",
    fields: [area("r", "Rule", "", 10), area("e", "Events", "", 5)], build: (v) => ({ rule: v.r, events: v.e }), sample: (s) => ({ r: s.sigma.rule, e: s.sigma.events }) },
  { id: "playbook", label: "Playbook simulator", endpoint: "/api/sectools/playbook", note: "Rules like 'when severity >= high -> isolate_host'. Nothing is run; actions that cut off a user or machine wait for a human.",
    fields: [area("r", "Rules", "", 5), area("a", "Alert (JSON)", "", 3)], build: (v) => ({ rules: v.r, alert: v.a }), sample: (s) => ({ r: s.playbook.rules, a: s.playbook.alert }) },
];

export function SecTools() {
  const [ref, setRef] = useState<R | null>(null);
  const [id, setId] = useState("jwt");
  useEffect(() => { getJson<R>("/api/sectools/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id) ?? TOOLS[0];
  return (
    <Section title="Defender study tools" note="These work on text you paste and send nothing anywhere. They are for learning and for first-pass checks on your own systems.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={spec.id} onChange={setId} label="Defender tools" />
      <ToolView key={spec.id} spec={spec} samples={ref?.samples ?? null} />
      {ref && <>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes common in the sources</summary><ul className="list-disc pl-5">{ref.slips.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary><ul className="list-disc pl-5">{ref.not_built.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      </>}
    </Section>
  );
}
