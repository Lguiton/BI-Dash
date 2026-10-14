"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";
import { DhcpTab } from "./DhcpTab";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "plan", label: "VLAN and router-on-a-stick" }, { id: "trunk", label: "Trunk checker" }, { id: "route", label: "Route selection" }, { id: "cable", label: "Cable chooser" }, { id: "dhcp", label: "DHCP server (dnsmasq)" }, { id: "ref", label: "Devices, DHCP, protocols" }];

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body?: unknown, method: "post" | "get" = "post") => {
    setErr(null);
    (method === "get" ? getJson<T>(path) : postJson<T>(path, body)).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That didn't work.")); });
  };
  return { res, err, run };
}
const Out = ({ c }: { c: { err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);
const Code = ({ lines, label }: { lines: string[]; label: string }) => <pre aria-label={label} className="overflow-x-auto rounded border border-line bg-panel2 p-3 font-mono text-xs">{lines.join("\n")}</pre>;
const sev = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "bad" ? "bad" : s === "warn" ? "warn" : s === "ok" ? "ok" : "muted");

export function NetGen() {
  const [tab, setTab] = useState("plan");
  return (
    <section className="card space-y-4 p-4" aria-label="Network generators">
      <h2 className="text-base font-semibold">Config generators and checkers</h2>
      <Lesson text="Text in, text out: these build and check VLAN, trunk, router-on-a-stick and routing answers for lab practice (Packet Tracer, GNS3, EVE-NG). Nothing connects to a device." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Network generators" />
      {tab === "plan" && <Plan />}
      {tab === "trunk" && <Trunk />}
      {tab === "route" && <Route />}
      {tab === "cable" && <Cable />}
      {tab === "dhcp" && <DhcpTab />}
      {tab === "ref" && <Ref />}
    </section>
  );
}

function Plan() {
  const [t, setT] = useState("10, HR, 192.168.10.0/24, fa0/1 fa0/2\n20, IT, 192.168.20.0/24, fa0/3 fa0/4");
  const [trunk, setTrunk] = useState("g0/1"); const [rp, setRp] = useState("g0/0"); const [nat, setNat] = useState("1"); const [lo, setLo] = useState("");
  const [style, setStyle] = useState("roas"); const [enc, setEnc] = useState(false); const c = useCall();
  const go = () => c.run("/api/netgen/plan", {
    vlans: t.split("\n").map((l) => l.split(",").map((x) => x.trim())).filter((p) => p.length >= 3 && p[0]).map((p) => ({ id: p[0], name: p[1], subnet: p[2], ports: (p[3] ?? "").split(/\s+/).filter(Boolean) })),
    trunk_port: trunk, router_port: rp, native: Number(nat) || 1, style, encapsulation_line: enc, loopback: lo.trim() || null,
  });
  return (
    <Section title="VLAN, trunk and router-on-a-stick generator" note="One line per VLAN: id, name, subnet, ports separated by spaces. The gateway is the first address in the subnet.">
      <Field label="VLANs"><textarea className="field font-mono" rows={4} value={t} onChange={(e) => setT(e.target.value)} aria-label="VLAN lines" /></Field>
      <div className="mt-2 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Switch trunk port"><input className="field" value={trunk} onChange={(e) => setTrunk(e.target.value)} /></Field>
        <Field label="Router port"><input className="field" value={rp} onChange={(e) => setRp(e.target.value)} /></Field>
        <Field label="Native VLAN"><input className="field" value={nat} onChange={(e) => setNat(e.target.value)} /></Field>
        <Field label="Loopback (optional)"><input className="field" value={lo} onChange={(e) => setLo(e.target.value)} placeholder="1.1.1.1" /></Field>
        <Field label="Style"><select className="field" value={style} onChange={(e) => setStyle(e.target.value)}><option value="roas">Router on a stick</option><option value="svi">Layer 3 switch (SVI)</option></select></Field>
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={enc} onChange={(e) => setEnc(e.target.checked)} />Add trunk encapsulation line</label>
      </div>
      <div className="mt-2"><button className="btn btn-primary" onClick={go}>Generate</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <Warn items={c.res.warnings} />
        <h4 className="text-sm font-semibold">Switch</h4><Code lines={c.res.switch_config} label="Switch config" />
        <h4 className="text-sm font-semibold">{c.res.style === "roas" ? "Router" : "Layer 3 routing on the switch"}</h4><Code lines={c.res.router_config} label="Router config" />
        {c.res.loopback_config.length > 0 && <><h4 className="text-sm font-semibold">Loopback</h4><Code lines={c.res.loopback_config} label="Loopback config" /></>}
        <Table head={["VLAN", "Subnet", "Gateway", "Mask", "Example host"]} rows={(c.res.hosts as R[]).map((h) => [h.vlan, h.subnet, h.gateway, h.mask, h.first_host ?? "-"])} caption="Addressing" />
        <p className="text-sm">Verify with: {[...c.res.verify.switch, ...c.res.verify.router].map((v: string) => <code key={v} className="mr-2">{v}</code>)}</p>
        <Lesson text={c.res.lesson} /><p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

const A = "interface g0/1\n switchport mode trunk\n switchport trunk native vlan 99\n switchport trunk allowed vlan 10,20\n!\nvlan 10\n name HR\nvlan 20\n name IT\n";
function Trunk() {
  const [a, setA] = useState(A); const [b, setB] = useState(A.replace("native vlan 99", "native vlan 1").replace("allowed vlan 10,20", "allowed vlan 10")); const c = useCall();
  return (
    <Section title="Trunk checker" note="Paste the relevant parts of two switches. It finds mode, native VLAN, allowed VLAN and missing VLAN faults. The sample has two on purpose.">
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Switch A"><textarea className="field font-mono" rows={9} value={a} onChange={(e) => setA(e.target.value)} aria-label="Switch A config" /></Field>
        <Field label="Switch B"><textarea className="field font-mono" rows={9} value={b} onChange={(e) => setB(e.target.value)} aria-label="Switch B config" /></Field>
      </div>
      <div className="mt-2"><button className="btn btn-primary" onClick={() => c.run("/api/netgen/trunk", { a, b })}>Check trunk</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <Badge tone={c.res.ok ? "ok" : "bad"}>{c.res.ok ? "no faults found" : "faults found"}</Badge>
        <Table head={["Result", "Finding", "Detail"]} rows={(c.res.findings as R[]).map((f) => [<Badge key="s" tone={sev(f.severity)}>{f.severity}</Badge>, f.title, f.detail])} caption="Trunk findings" />
        <Lesson text={c.res.lesson} /><p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Route() {
  const [t, setT] = useState("10.0.0.0/8, static\n10.1.0.0/16, rip, 2\n10.1.0.0/16, ospf, 20\n0.0.0.0/0, ospf, 10");
  const [d, setD] = useState("10.1.2.3"); const c = useCall();
  const go = () => c.run("/api/netgen/route", { destination: d, routes: t.split("\n").map((l) => l.split(",").map((x) => x.trim())).filter((p) => p.length >= 2 && p[0]).map((p) => { const m = /^ad=(\d+)$/i.exec(p[1]); return { prefix: p[0], protocol: m ? "" : p[1], ad: m ? Number(m[1]) : null, metric: p[2] || 0, next_hop: p[3] ?? "" }; }) });
  return (
    <Section title="Which route does the router use?" note="One candidate per line: prefix, protocol (connected, static, ebgp, eigrp, ospf, rip, ibgp), metric, optional next hop. Or write the protocol as ad=95.">
      <Field label="Candidate routes"><textarea className="field font-mono" rows={5} value={t} onChange={(e) => setT(e.target.value)} aria-label="Candidate routes" /></Field>
      <div className="mt-2 flex items-end gap-2"><Field label="Destination"><input className="field" value={d} onChange={(e) => setD(e.target.value)} /></Field><button className="btn btn-primary" onClick={go}>Pick the route</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{(c.res.steps as string[]).map((s) => <li key={s}>{s}</li>)}</ol>
        <Table head={["#", "Prefix", "Source", "AD", "Metric", "Contains destination", "Used"]} rows={(c.res.table as R[]).map((r) => [r.route, r.prefix, r.protocol, r.ad, r.metric, r.contains_destination ? "yes" : "no", r.selected ? <Badge key="u" tone="ok">selected</Badge> : ""])} caption="Route table" />
        <Lesson text={c.res.lesson} />
      </div>}
    </Section>
  );
}

function Cable() {
  const [sp, setSp] = useState("10"); const [dist, setDist] = useState("80"); const [emi, setEmi] = useState(false); const c = useCall();
  return (
    <Section title="Which Ethernet cable?" note="Speed you need and the length of the run.">
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Speed (Gbps)"><input className="field" value={sp} onChange={(e) => setSp(e.target.value)} /></Field>
        <Field label="Run length (m)"><input className="field" value={dist} onChange={(e) => setDist(e.target.value)} /></Field>
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={emi} onChange={(e) => setEmi(e.target.checked)} />Electrically noisy place</label>
        <div className="flex items-end"><button className="btn btn-primary" onClick={() => c.run("/api/netgen/cable", { speed_gbps: Number(sp), distance_m: Number(dist), emi })}>Recommend</button></div>
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <Stat label="Pick" value={c.res.pick} sub={c.res.why} />
        <Table head={["Type", "MHz", "Speed and distance", "Shielding", "Note"]} rows={(c.res.table as R[]).map((r) => [r.type, r.mhz, r.speed, r.shielding, r.note])} caption="Cable categories" />
      </div>}
    </Section>
  );
}

function Ref() {
  const c = useCall();
  useEffect(() => { c.run("/api/netgen/reference", undefined, "get"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const r = c.res;
  return (
    <>
      <Out c={c} />
      {r && <>
        <Section title="Network devices and what they do"><Table head={["Device", "Layer", "Does", "Note"]} rows={(r.devices as R[]).map((x) => [x.device, x.layer, x.does, x.note])} caption="Devices" /></Section>
        <Section title="DHCP DORA, step by step"><Table head={["Step", "Direction", "Addresses and ports", "Note"]} rows={(r.dora as R[]).map((x) => [x.step, x.direction, x.addresses, x.note])} caption="DHCP" /></Section>
        <Section title="OSPF, EIGRP, BGP and RIP"><Table head={["Protocol", "Type", "Standard", "Metric", "Admin distance", "Multicast", "Use"]} rows={(r.protocols as R[]).map((x) => [x.name, x.type, x.standard, x.metric, x.ad, x.multicast, x.use])} caption="Routing protocols" />
          <p className="mt-2 text-sm">Administrative distance: {(r.admin_distance as R[]).map((x) => `${x.source} ${x.ad}`).join(", ")}.</p></Section>
        <Section title="Loopback addresses"><ul className="list-disc space-y-1 pl-5 text-sm">{(r.loopback as string[]).map((x) => <li key={x}>{x}</li>)}</ul></Section>
        <Section title="Mistakes seen in teaching posters"><ul className="list-disc space-y-1 pl-5 text-sm">{(r.slips as string[]).map((x) => <li key={x}>{x}</li>)}</ul><p className="mt-2 text-xs text-muted">Not built: {(r.not_built as string[]).join(" ")}</p></Section>
      </>}
    </>
  );
}
