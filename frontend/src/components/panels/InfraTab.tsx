"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const num = (v: any) => Number(v);
const json = (t: string, what: string) => { try { return JSON.parse(t); } catch { throw new Error(`${what} isn't valid JSON.`); } };
const tri = (v: string) => (v === "yes" ? true : v === "no" ? false : null);
const pretty = (x: unknown) => JSON.stringify(x, null, 1);
const YN = ["unknown", "yes", "no"];

const TOOLS: ToolSpec[] = [
  { id: "gpo", label: "Group Policy resolver", endpoint: "/api/infra/gpo", note: "Which setting wins for a user or computer? Paste JSON: the object (name, groups) and the chain from Local down to the OU. Link order 1 wins within a container; Enforced beats Block Inheritance.",
    fields: [{ k: "j", label: "Object and chain (JSON)", type: "area", rows: 10 }],
    build: (v) => json(v.j, "The Group Policy input"), sample: (s) => ({ j: pretty(s.gpo) }) },
  { id: "ldif", label: "LDIF checker", endpoint: "/api/infra/ldif/check", note: "Check an LDIF file before you run ldapadd or ldapmodify: required attributes, RDN match, duplicates, missing parent entries, plain-text passwords.",
    fields: [{ k: "text", label: "LDIF", type: "area", rows: 10 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.ldif }) },
  { id: "ldifb", label: "LDIF builder", endpoint: "/api/infra/ldif/build", note: "Build a correct user, group or OU entry. Base64 and DN escaping are handled; it is checked before you see it.",
    fields: [{ k: "kind", label: "Kind", type: "select", options: ["user", "group", "ou"], def: "user" }, { k: "base_dn", label: "Base DN", def: "dc=example,dc=com" }, { k: "given", label: "Given name (user)", def: "Ada" }, { k: "sn", label: "Surname (user)", def: "Lovelace" }, { k: "uid", label: "uid (user)", def: "alovelace" }, { k: "mail", label: "Email (user, optional)", def: "" }, { k: "name", label: "Name (group or OU)", def: "" }, { k: "ou", label: "Parent OU", def: "" }, { k: "members", label: "Member DNs (group, one per line)", type: "area", rows: 3 }],
    build: (v) => ({ kind: v.kind, fields: Object.fromEntries(Object.entries(v).filter(([k, x]) => k !== "kind" && k !== "__fields" && String(x).trim() !== "")) }) },
  { id: "rbac", label: "RBAC audit", endpoint: "/api/infra/rbac", note: "Find undefined roles, inheritance loops, over-wide roles, direct grants and separation-of-duties conflicts.",
    fields: [{ k: "j", label: "Roles, users and conflicts (JSON)", type: "area", rows: 10 }], build: (v) => json(v.j, "The RBAC input"), sample: (s) => ({ j: pretty(s.rbac) }) },
  { id: "raid", label: "RAID rebuild risk", endpoint: "/api/infra/raid-risk", note: "Capacity is the easy part. This is the chance of a read error or a second failure while the array rebuilds.",
    fields: [{ k: "level", label: "RAID level", type: "select", options: ["0", "1", "5", "6", "10"], def: "5" }, { k: "disks", label: "Disks", type: "number", def: "8" }, { k: "size_tb", label: "TB per disk", type: "number", def: "16" }, { k: "ure_exponent", label: "Unrecoverable read error, one in 10^N bits", type: "number", def: "14" }, { k: "rebuild_mb_s", label: "Rebuild speed MB/s", type: "number", def: "100" }, { k: "afr_pct", label: "Annual failure rate %", type: "number", def: "2" }],
    build: (v) => ({ level: v.level, disks: num(v.disks), size_tb: num(v.size_tb), ure_exponent: num(v.ure_exponent), rebuild_mb_s: num(v.rebuild_mb_s), afr_pct: num(v.afr_pct) }) },
  { id: "backup", label: "Backup planner", endpoint: "/api/infra/backup", note: "Full, incremental and differential side by side: storage used, restore chain, restore time, and whether you meet your RPO and RTO.",
    fields: [{ k: "full_gb", label: "Full backup GB", type: "number", def: "500" }, { k: "change_pct", label: "Daily change %", type: "number", def: "5" }, { k: "days", label: "Days kept", type: "number", def: "28" }, { k: "full_every", label: "Full every N days", type: "number", def: "7" }, { k: "restore_mb_s", label: "Restore MB/s", type: "number", def: "100" }, { k: "rpo_h", label: "RPO hours", type: "number", def: "24" }, { k: "rto_h", label: "RTO hours", type: "number", def: "8" }, { k: "interval_h", label: "Backup every N hours", type: "number", def: "24" }],
    build: (v) => Object.fromEntries(Object.entries(v).filter(([k]) => k !== "__fields").map(([k, x]) => [k, num(x)])) },
  { id: "dr", label: "Disaster recovery check", endpoint: "/api/infra/dr", note: "Per system: can the backup interval meet the RPO, can the restore meet the RTO, was a restore tested lately, and is the 3-2-1 rule met?",
    fields: [{ k: "j", label: "Systems (JSON list)", type: "area", rows: 10 }], build: (v) => ({ systems: json(v.j, "The systems list") }), sample: (s) => ({ j: pretty(s.dr) }) },
  { id: "lb", label: "Load balancer simulator", endpoint: "/api/infra/lb", note: "Round robin, weighted, least connections and IP hash on the same traffic, with an optional dead server.",
    fields: [{ k: "j", label: "Servers (JSON list)", type: "area", rows: 4, def: '[{"name":"web1"},{"name":"web2","weight":2},{"name":"web3"}]' }, { k: "requests", label: "Requests", type: "number", def: "2000" }, { k: "clients", label: "Distinct clients", type: "number", def: "50" }, { k: "mean_ms", label: "Mean request ms", type: "number", def: "200" }, { k: "fail", label: "Failed server name (optional)" }, { k: "seed", label: "Seed", type: "number", def: "5" }],
    build: (v) => ({ servers: json(v.j, "The servers list"), requests: num(v.requests), clients: num(v.clients), mean_ms: num(v.mean_ms), seed: num(v.seed), fail: String(v.fail).trim() || null }) },
  { id: "http", label: "HTTP status lookup", endpoint: "/api/infra/http-lookup", note: "What a status code means and what to check first.",
    fields: [{ k: "code", label: "Status code", type: "number", def: "502" }], build: (v) => ({ code: num(v.code) }) },
  { id: "triage", label: "Website triage", endpoint: "/api/infra/triage", note: "Answer what you know; it points at the first layer that is broken: DNS, TCP, TLS, then HTTP.",
    fields: [{ k: "dns", label: "Name resolves?", type: "select", options: YN, def: "unknown" }, { k: "tcp", label: "TCP connects?", type: "select", options: YN, def: "unknown" }, { k: "tls", label: "TLS handshake OK?", type: "select", options: YN, def: "unknown" }, { k: "code", label: "HTTP status (blank if none)", type: "number", def: "" }, { k: "else", label: "Works from elsewhere?", type: "select", options: YN, def: "unknown" }, { k: "slow", label: "Slow?", type: "select", options: ["no", "yes"], def: "no" }],
    build: (v) => ({ dns_resolves: tri(v.dns), tcp_connects: tri(v.tcp), tls_ok: tri(v.tls), http_status_code: v.code === "" ? null : num(v.code), from_elsewhere_works: tri(v.else), latency_slow: v.slow === "yes" }) },
  { id: "log", label: "Web access log summary", endpoint: "/api/infra/log", note: "Paste common-format access log lines: status classes, error paths, top clients and scanner probes.",
    fields: [{ k: "text", label: "Log lines", type: "area", rows: 8 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.log }) },
];

export function InfraTab() {
  const [id, setId] = useState("gpo");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => {
    Promise.all([getJson<R>("/api/infra/gpo/sample"), getJson<R>("/api/infra/ldif/sample"), getJson<R>("/api/infra/rbac/sample"), getJson<R>("/api/infra/dr/sample"), getJson<R>("/api/infra/log/sample")])
      .then(([gpo, l, rbac, dr, log]) => setSamples({ gpo, ldif: l.text, rbac, dr: dr.systems, log: log.text })).catch(() => setSamples(null));
  }, []);
  const spec = TOOLS.find((t) => t.id === id)!;
  return (
    <Section title="Infrastructure labs" note="Offline models of Group Policy, LDAP, RAID, backup, DR and load balancing. They explain and check; they do not touch a real directory, array or server.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={id} onChange={setId} label="Infrastructure tools" />
      <ToolView key={id} spec={spec} samples={samples} />
    </Section>
  );
}
