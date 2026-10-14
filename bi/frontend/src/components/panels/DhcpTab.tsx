"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const lines = (t: string) => String(t).split("\n").map((x) => x.trim()).filter(Boolean);
const TOOLS: ToolSpec[] = [
  { id: "gen", label: "Build a dnsmasq config", endpoint: "/api/infra/dnsmasq/generate", note: "A small DHCP and DNS server. Every address is checked against the subnet before you get the text.",
    fields: [{ k: "interface", label: "Interface", def: "eth0" }, { k: "subnet", label: "Subnet (CIDR)", def: "192.168.50.0/24" }, { k: "gateway", label: "Gateway (blank = first address)", def: "" }, { k: "range_start", label: "Range start", def: "192.168.50.100" }, { k: "range_end", label: "Range end", def: "192.168.50.200" }, { k: "lease", label: "Lease time", def: "12h" }, { k: "domain", label: "Domain", def: "lab.local" }, { k: "upstream", label: "Upstream DNS (comma separated)", def: "1.1.1.1, 9.9.9.9" },
      { k: "res", label: "Reservations: mac, ip, host (one per line)", type: "area", rows: 3, def: "aa:bb:cc:dd:ee:01, 192.168.50.20, printer" }, { k: "rec", label: "DNS names: name, ip (one per line)", type: "area", rows: 2, def: "nas.lab.local, 192.168.50.30" }, { k: "log", label: "Log queries?", type: "select", options: ["no", "yes"], def: "no" }],
    build: (v) => ({ interface: v.interface, subnet: v.subnet, gateway: v.gateway, range_start: v.range_start, range_end: v.range_end, lease: v.lease, domain: v.domain,
      upstream: String(v.upstream).split(",").map((x) => x.trim()).filter(Boolean),
      reservations: lines(v.res).map((l) => { const [mac, ip, host] = l.split(",").map((x) => x.trim()); return { mac, ip, host: host ?? "" }; }),
      records: lines(v.rec).map((l) => { const [name, ip] = l.split(",").map((x) => x.trim()); return { name, ip }; }), log_queries: v.log === "yes" }) },
  { id: "check", label: "Check a dnsmasq config", endpoint: "/api/infra/dnsmasq/check", note: "Paste dnsmasq.conf. Finds overlapping ranges, duplicate reservations, a missing gateway option and more.",
    fields: [{ k: "text", label: "dnsmasq.conf", type: "area", rows: 10 }], build: (v) => ({ text: v.text }), sample: (s) => ({ text: s.text }) },
];

export function DhcpTab() {
  const [id, setId] = useState("gen");
  const [samples, setSamples] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/infra/dnsmasq/sample").then(setSamples).catch(() => setSamples(null)); }, []);
  const spec = TOOLS.find((t) => t.id === id)!;
  return (
    <Section title="DHCP and DNS server (dnsmasq)" note="Text in, text out. Nothing is installed or started. Test the real thing in a virtual machine with dnsmasq --test.">
      <Tabs tabs={TOOLS.map((t) => ({ id: t.id, label: t.label }))} value={id} onChange={setId} label="dnsmasq tools" />
      <ToolView key={id} spec={spec} samples={samples} />
    </Section>
  );
}
