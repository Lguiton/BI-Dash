"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
type Fld = { k: string; label: string; area?: boolean };
const TOOLS: Record<string, { label: string; path: string; fields: Fld[]; def: Record<string, string>; help: string }> = {
  ospf: { label: "OSPF cost", path: "calc/ospf", fields: [{ k: "link_mbps", label: "Link speed (Mbps)" }, { k: "reference_mbps", label: "Reference bandwidth (Mbps)" }], def: { link_mbps: "1000", reference_mbps: "100" }, help: "See why gigabit and faster links tie at cost 1 with the default reference." },
  stp: { label: "Spanning tree root", path: "calc/stp", fields: [{ k: "bridges", label: "Switches, one per line: name, priority, mac", area: true }], def: { bridges: "SW1,32768,00:1a:2b:3c:4d:5e\nSW2,32768,00:1a:2b:3c:4d:01\nCORE,4096,00:1a:2b:3c:4d:99" }, help: "Which switch becomes the root, and why." },
  ipv6: { label: "IPv6 plan", path: "calc/ipv6", fields: [{ k: "prefix", label: "Starting prefix" }, { k: "subnet_prefix", label: "Subnet size (usually 64)" }, { k: "count", label: "How many to list" }], def: { prefix: "2001:db8:abcd::/48", subnet_prefix: "64", count: "8" }, help: "Carve a /48 or /56 into /64 LANs." },
  eui64: { label: "EUI-64 address", path: "calc/eui64", fields: [{ k: "mac", label: "MAC address" }, { k: "prefix", label: "Prefix (/64)" }], def: { mac: "00:1a:2b:3c:4d:5e", prefix: "fe80::/64" }, help: "The address a device builds from its MAC." },
  poe: { label: "PoE budget", path: "calc/poe", fields: [{ k: "switch_watts", label: "Switch PoE budget (W)" }, { k: "devices", label: "Devices: name, watts or class (af/at/bt3/bt4), quantity", area: true }], def: { switch_watts: "370", devices: "Camera,12.95,8\nAccess point,at,4" }, help: "Will the switch power everything?" },
  fiber: { label: "Fiber budget", path: "calc/fiber", fields: [{ k: "length_km", label: "Length (km)" }, { k: "wavelength", label: "Wavelength nm (850, 1300, 1310, 1550)" }, { k: "connectors", label: "Connector pairs" }, { k: "splices", label: "Splices" }, { k: "tx_dbm", label: "Transmit power (dBm)" }, { k: "rx_sensitivity_dbm", label: "Receiver sensitivity (dBm)" }], def: { length_km: "2", wavelength: "1310", connectors: "2", splices: "0", tx_dbm: "-3", rx_sensitivity_dbm: "-18" }, help: "Loss and margin for a fiber link." },
  link: { label: "Wi-Fi / wireless link", path: "calc/link", fields: [{ k: "tx_dbm", label: "Transmit power (dBm)" }, { k: "tx_gain_dbi", label: "Transmit antenna gain (dBi)" }, { k: "rx_gain_dbi", label: "Receive antenna gain (dBi)" }, { k: "freq_mhz", label: "Frequency (MHz)" }, { k: "distance_m", label: "Distance (m)" }, { k: "rx_sensitivity_dbm", label: "Receiver sensitivity (dBm)" }, { k: "obstruction_db", label: "Obstruction loss (dB)" }], def: { tx_dbm: "20", tx_gain_dbi: "3", rx_gain_dbi: "3", freq_mhz: "5800", distance_m: "200", rx_sensitivity_dbm: "-80", obstruction_db: "0" }, help: "Will a wireless link have enough margin?" },
  tcp: { label: "TCP speed limit", path: "calc/tcp", fields: [{ k: "rtt_ms", label: "Round-trip time (ms)" }, { k: "loss_pct", label: "Packet loss (%)" }], def: { rtt_ms: "50", loss_pct: "1" }, help: "Why a fast line still downloads slowly." },
  fw: { label: "Firewall review", path: "firewall", fields: [{ k: "text", label: "Paste firewall or access list rules", area: true }], def: { text: "permit ip any any\nallow tcp any any eq 3389" }, help: "Finds common risky rules. A pattern check, not a full audit." },
};
const TABS = [...Object.entries(TOOLS).map(([id, t]) => ({ id, label: t.label })), { id: "ref", label: "VPN, QoS, Wi-Fi, monitoring" }];
const tone = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "muted") as "bad" | "warn" | "muted";
const skip = new Set(["note", "verdict", "advice", "tips", "findings", "counts", "good_practice", "caveat", "why", "devices", "order", "first"]);

/** Advanced networking: routing, spanning tree, IPv6, PoE, fiber, wireless, TCP and firewall checks. Local calculations only; nothing connects to a device. */
export function NetProLab() {
  const [tab, setTab] = useState("ospf");
  const [f, setF] = useState<Record<string, string>>({});
  const [out, setOut] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const t = TOOLS[tab];
  const val = (k: string) => f[`${tab}.${k}`] ?? t?.def[k] ?? "";
  useEffect(() => { if (tab === "ref" && !ref) getJson<R>("/api/netpro/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, [tab, ref]);
  async function go() {
    if (!t) return;
    setErr(null);
    const body: R = {};
    t.fields.forEach((x) => { body[x.k] = val(x.k); });
    try { setOut(await postJson<R>(`/api/netpro/${t.path}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check what you entered.")); }
  }
  const list = (a: unknown) => (Array.isArray(a) ? a : []) as any[];
  return (
    <section className="card space-y-3 p-4" aria-label="Advanced networking lab">
      <h2 className="text-base font-semibold">Advanced networking: routing, switching, IPv6, PoE, fiber, wireless and firewall review</h2>
      <p className="text-xs text-muted">Planning math and checks run on this computer. Nothing connects to a device. Test changes in a lab or a safe window, and keep a way back in.</p>
      <Tabs tabs={TABS} value={tab} onChange={(v) => { setTab(v); setOut(null); setErr(null); }} label="Networking tools" />
      {err && <ErrorBanner message={err} />}
      {t && (
        <Section title={t.label} note={t.help}>
          <div className="grid gap-2 sm:grid-cols-2">
            {t.fields.map((x) => (
              <label key={x.k} className={`text-xs ${x.area ? "sm:col-span-2" : ""}`}>{x.label}
                {x.area ? <textarea className="input mt-1 w-full font-mono" rows={4} value={val(x.k)} onChange={(e) => setF((s) => ({ ...s, [`${tab}.${x.k}`]: e.target.value }))} />
                  : <input className="input mt-1 w-full" value={val(x.k)} onChange={(e) => setF((s) => ({ ...s, [`${tab}.${x.k}`]: e.target.value }))} />}
              </label>
            ))}
          </div>
          <button className="btn mt-2" onClick={go}>Check</button>
          {out && (
            <div className="mt-3 space-y-2 text-sm" role="status">
              {out.verdict && <p><strong>{out.verdict}</strong></p>}
              {out.root && <p>Root bridge: <strong>{out.root}</strong></p>}
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                {Object.entries(out).filter(([k, v]) => !skip.has(k) && (typeof v === "number" || typeof v === "string" || typeof v === "boolean")).map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k.replace(/_/g, " ")}</dt><dd>{String(v)}</dd></div>)}
              </dl>
              {list(out.first).length > 0 && <ul className="list-disc pl-5 font-mono text-xs">{list(out.first).map((x, i) => <li key={i}>{x}</li>)}</ul>}
              {list(out.order).length > 0 && <ol className="list-decimal pl-5 text-xs">{list(out.order).map((x, i) => <li key={i}>{x.name}: priority {x.priority}, {x.mac}</li>)}</ol>}
              {list(out.devices).length > 0 && <ul className="text-xs">{list(out.devices).map((x, i) => <li key={i}>{x.device}: {x.qty} x {x.watts_each} W = {x.watts} W</li>)}</ul>}
              {out.why && <p className="text-xs">{out.why}</p>}
              {list(out.findings).length > 0 && <ul className="space-y-1">{list(out.findings).map((x, i) => <li key={i} className="rounded border border-line p-2"><Badge tone={tone(x.severity)}>{x.severity}</Badge> <strong>{x.problem}</strong> (line {x.line})<div className="font-mono text-xs text-muted">{x.rule}</div><div className="text-xs">{x.fix}</div></li>)}</ul>}
              {out.findings && list(out.findings).length === 0 && <p className="text-muted">No common mistakes found. That is not proof the rules are safe.</p>}
              {[...list(out.advice), ...list(out.tips), ...list(out.good_practice)].length > 0 && <ul className="list-disc pl-5 text-xs">{[...list(out.advice), ...list(out.tips), ...list(out.good_practice)].map((x, i) => <li key={i}>{x}</li>)}</ul>}
              {(out.note || out.caveat) && <p className="text-xs text-muted">{out.note} {out.caveat}</p>}
            </div>
          )}
        </Section>
      )}
      {tab === "ref" && ref && (
        <div className="space-y-3 text-sm">
          <Section title="VPN choices"><ul className="space-y-1">{list(ref.vpn).map((v, i) => <li key={i}><strong>{v.type}</strong>: {v.good}. <span className="text-muted">Watch: {v.watch}</span></li>)}</ul></Section>
          <Section title="QoS"><ul className="list-disc pl-5 text-xs">{list(ref.qos).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
          <Section title="Troubleshoot by layer"><ul className="space-y-1 text-xs">{list(ref.layers).map((x, i) => <li key={i}><strong>{x.layer}</strong>: {x.check}</li>)}</ul></Section>
          <Section title="Monitoring"><ul className="list-disc pl-5 text-xs">{list(ref.monitoring).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
          <Section title="SNMP objects"><ul className="space-y-1 text-xs">{list(ref.snmp).map((x, i) => <li key={i}><code>{x.oid}</code> {x.name}: {x.means}</li>)}</ul></Section>
          <Section title="Routing"><ul className="list-disc pl-5 text-xs">{list(ref.routing).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
          <Section title="Wi-Fi design"><ul className="list-disc pl-5 text-xs">{list(ref.wifi).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
        </div>
      )}
    </section>
  );
}
