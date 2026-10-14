"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Section, Table, Tabs, errMsg } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const area = (k: string, label: string, def: string, rows = 5) => ({ k, label, type: "area" as const, def, rows });

const SIM: ToolSpec[] = [
  { id: "switch", label: "Switch and VLANs", endpoint: "/api/netsim/switch", note: "Ports: 'port access 10' or 'port trunk 10,20'. Frames: 'in_port source_mac dest_mac [vlan_tag for trunk ports]'. Watch the MAC table fill in.",
    fields: [area("p", "Ports", "1 access 10\n2 access 10\n3 access 20\n4 trunk 10,20", 4), area("f", "Frames", "1 aa:00:00:00:00:01 ff:ff:ff:ff:ff:ff\n2 aa:00:00:00:00:02 aa:00:00:00:00:01", 6)], build: (v) => ({ ports: v.p, frames: v.f }), sample: (s) => ({ p: s.switch.ports, f: s.switch.frames }) },
  { id: "stp", label: "Spanning tree", endpoint: "/api/netsim/stp", note: "Bridges: 'name priority mac' (priority in steps of 4096). Links: 'bridgeA bridgeB cost'. Finds the root and which ports forward or block.",
    fields: [area("b", "Bridges", "SW1 32768 00:00:00:00:00:01\nSW2 32768 00:00:00:00:00:02\nSW3 32768 00:00:00:00:00:03", 4), area("l", "Links", "SW1 SW2 4\nSW2 SW3 4\nSW1 SW3 4", 4)], build: (v) => ({ bridges: v.b, links: v.l }), sample: (s) => ({ b: s.stp.bridges, l: s.stp.links }) },
  { id: "spf", label: "OSPF shortest path", endpoint: "/api/netsim/spf", note: "Links: 'routerA routerB cost'. Shows each route, its cost, and equal-cost paths.",
    fields: [area("l", "Links", "R1 R2 10\nR1 R3 10\nR2 R4 10\nR3 R4 10\nR4 R5 5", 5), { k: "s", label: "From router", type: "text", def: "R1" }], build: (v) => ({ links: v.l, source: v.s }), sample: (s) => ({ l: s.spf.links, s: s.spf.source }) },
  { id: "bgp", label: "BGP best path", endpoint: "/api/netsim/bgp", note: "One route per line: name | weight | local_pref | as_path | origin | med | ebgp or ibgp | igp_metric | router_id.",
    fields: [area("r", "Routes", "A | 0 | 100 | 65001 65002 | igp | 0 | ebgp | 10 | 1.1.1.1\nB | 0 | 200 | 65003 65004 65005 | igp | 0 | ebgp | 10 | 2.2.2.2", 5)], build: (v) => ({ routes: v.r }), sample: (s) => ({ r: s.bgp.routes }) },
  { id: "acl", label: "ACL tester", endpoint: "/api/netsim/acl", note: "Rules: 'permit|deny tcp|udp|icmp|ip source [eq port] destination [eq port]'. Packets: 'tcp src dst srcport dstport'. First match wins; the tool warns about lines that can never match.",
    fields: [area("r", "Rules", "permit tcp 10.0.0.0/24 any eq 443\ndeny ip 10.0.0.0/24 any\npermit ip any any", 5), area("p", "Packets", "tcp 10.0.0.5 8.8.8.8 40000 443\nudp 10.0.0.9 1.1.1.1 5000 53", 4)], build: (v) => ({ rules: v.r, packets: v.p }), sample: (s) => ({ r: s.acl.rules, p: s.acl.packets }) },
  { id: "nat", label: "NAT and PAT", endpoint: "/api/netsim/nat", note: "Flows: 'tcp|udp inside_ip inside_port outside_ip outside_port'. See the translation table build up.",
    fields: [{ k: "i", label: "Inside network", type: "text", def: "192.168.1.0/24" }, { k: "pub", label: "Public address", type: "text", def: "203.0.113.5" }, area("f", "Flows", "tcp 192.168.1.10 51000 93.184.216.34 443\ntcp 192.168.1.11 51000 93.184.216.34 443", 4)], build: (v) => ({ inside: v.i, public_ip: v.pub, flows: v.f }), sample: (s) => ({ i: s.nat.inside, pub: s.nat.public_ip, f: s.nat.flows }) },
];

export function NetSim() {
  const [ref, setRef] = useState<R | null>(null);
  const [id, setId] = useState("switch");
  useEffect(() => { getJson<R>("/api/netsim/reference").then(setRef).catch(() => setRef(null)); }, []);
  const spec = SIM.find((t) => t.id === id) ?? SIM[0];
  return (
    <Section title="Protocol simulators" note="Small models that show the rule used at each step. They teach how the protocols decide; they are not a replacement for a lab or real equipment.">
      <Tabs tabs={SIM.map((t) => ({ id: t.id, label: t.label }))} value={spec.id} onChange={setId} label="Simulators" />
      <ToolView key={spec.id} spec={spec} samples={ref?.samples ?? null} />
      {ref && <>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes common in network study guides</summary><ul className="list-disc pl-5">{ref.slips.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
        <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary><ul className="list-disc pl-5">{ref.not_built.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      </>}
    </Section>
  );
}

function toB64(buf: ArrayBuffer): string {
  const u = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
  return btoa(s);
}

export function PcapTab() {
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/netsim/reference").then(setInfo).catch(() => setInfo(null)); }, []);
  async function pick(f: File | undefined) {
    if (!f) return;
    setErr(null); setRes(null); setBusy(true);
    try { setRes(await postJson<R>("/api/netsim/pcap", { data: toB64(await f.arrayBuffer()) })); }
    catch (e) { setErr(errMsg(e, "Could not read that capture.")); }
    finally { setBusy(false); }
  }
  return (
    <Section title="Saved capture reader" note="Choose a .pcap or .pcapng file saved from Wireshark or tcpdump. The file is read by your own app and not sent anywhere else. Up to 6 MB.">
      <input type="file" accept=".pcap,.pcapng,.cap" aria-label="Capture file" onChange={(e) => pick(e.target.files?.[0])} />
      {busy && <p className="mt-2 text-sm text-muted">Reading...</p>}
      {err && <ErrorBanner message={err} />}
      {res && (
        <div className="mt-3 space-y-3 text-sm">
          <p><b>{res.packets}</b> packets over {res.seconds} s, average {res.avg_bytes} bytes{res.skipped ? `; ${res.skipped} could not be read` : ""}.</p>
          {res.findings.length > 0 && <ul className="list-disc rounded border border-line bg-panel2 p-2 pl-6">{res.findings.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>}
          <Table head={["Protocol", "Packets"]} rows={res.protocols.map((p: any[]) => [p[0], p[1]])} caption="Protocols" />
          <Table head={["Address", "Packets sent"]} rows={res.top_talkers.map((p: any[]) => [p[0], p[1]])} caption="Top talkers" />
          <Table head={["Conversation", "Packets"]} rows={res.top_conversations.map((p: R) => [p.pair, p.packets])} caption="Top conversations" />
          <Table head={["Destination port", "Packets"]} rows={res.top_dest_ports.map((p: any[]) => [p[0], p[1]])} caption="Busiest ports" />
          {res.dns_names.length > 0 && <Table head={["DNS name asked", "Times"]} rows={res.dns_names.map((p: any[]) => [p[0], p[1]])} caption="DNS questions" />}
          <p className="text-muted">{res.lesson}</p>
        </div>
      )}
      {info && <details className="mt-3 text-sm"><summary className="cursor-pointer">Limits and what is not built</summary><ul className="list-disc pl-5">{[...info.pcap_not_built, ...info.pcap_slips].map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>}
    </Section>
  );
}
