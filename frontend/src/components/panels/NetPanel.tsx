"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";

const TABS = [
  { id: "subnet", label: "Subnet and VLSM" }, { id: "config", label: "Config review" }, { id: "capture", label: "Packet capture" },
  { id: "diag", label: "DNS and reachability" }, { id: "calc", label: "Calculators" }, { id: "ref", label: "Reference" },
];

export function NetPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Practice tools for networks you own. They work on text you paste and on public hosts; scanners and live captures are explained in the Tool map, not built.
      </p>
      <Tabs tabs={TABS} value={tab} onChange={onTab} label="Network tools" />
      {tab === "subnet" && <SubnetTab />}
      {tab === "config" && <TextTool kind="config" />}
      {tab === "capture" && <TextTool kind="capture" />}
      {tab === "diag" && <DiagTab />}
      {tab === "calc" && <CalcTab />}
      {tab === "ref" && <RefTab />}
    </div>
  );
}

const sev = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "high" ? "bad" : s === "medium" ? "warn" : s === "info" ? "muted" : "muted");

// ---------------------------------------------------------------- subnetting
interface Sub { network: string; prefix: number; netmask: string; wildcard: string; broadcast: string | null; first_host: string; last_host: string; total_addresses: number; usable_hosts: number; scope: string; class: string | null; netmask_binary?: string; note: string }
interface Vlsm { plan: { name: string; hosts_needed: number; network: string; netmask: string; first_host: string; last_host: string; broadcast: string; usable_hosts: number; spare: number }[]; used_addresses: number; free_addresses: number; note: string }

function SubnetTab() {
  const [cidr, setCidr] = useState("192.168.10.0/26");
  const [sub, setSub] = useState<Sub | null>(null);
  const [splitTo, setSplitTo] = useState("28");
  const [split, setSplit] = useState<{ subnets: { network: string; first_host: string; last_host: string; usable_hosts: number }[] } | null>(null);
  const [base, setBase] = useState("10.20.0.0/22");
  const [needs, setNeeds] = useState("Staff, 60\nGuest Wi-Fi, 20\nServers, 10\nLink A-B, 2\nLink B-C, 2");
  const [plan, setPlan] = useState<Vlsm | null>(null);
  const [list, setList] = useState("10.0.0.0/24\n10.0.0.128/25\n10.0.1.0/24");
  const [ovl, setOvl] = useState<{ ok: boolean; overlaps: { a: string; b: string; relation: string }[] } | null>(null);
  const [sum, setSum] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const act = async (f: () => Promise<void>, m: string) => { setErr(null); try { await f(); } catch (e) { setErr(errMsg(e, m)); } };
  const parseNeeds = () => needs.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => { const i = l.lastIndexOf(","); return { name: l.slice(0, i).trim() || l, hosts: Number(l.slice(i + 1)) }; });
  const cidrs = () => list.split(/[\s,]+/).filter(Boolean);
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Subnet calculator">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Network (CIDR)"><input className="field w-56" value={cidr} onChange={(e) => setCidr(e.target.value)} maxLength={60} /></Field>
          <button className="btn btn-primary" onClick={() => act(async () => { setSub(await postJson<Sub>("/api/net/subnet", { cidr })); setSplit(null); }, "Couldn't calculate that.")}>Calculate</button>
        </div>
        {sub && (
          <div className="mt-3 space-y-3">
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat label="Network" value={`${sub.network}/${sub.prefix}`} sub={sub.scope} />
              <Stat label="Usable hosts" value={sub.usable_hosts.toLocaleString()} sub={`${sub.total_addresses.toLocaleString()} addresses`} />
              <Stat label="Netmask" value={sub.netmask} sub={`wildcard ${sub.wildcard}`} />
              <Stat label="Host range" value={`${sub.first_host}`} sub={`to ${sub.last_host}${sub.broadcast ? ` · broadcast ${sub.broadcast}` : ""}`} />
            </div>
            {sub.netmask_binary && <p className="font-mono text-xs">{sub.netmask_binary}{sub.class ? ` · class ${sub.class}` : ""}</p>}
            <p className="text-xs text-muted">{sub.note}</p>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Split into /"><input className="field w-20" type="number" min={1} max={128} value={splitTo} onChange={(e) => setSplitTo(e.target.value)} /></Field>
              <button className="btn" onClick={() => act(async () => setSplit(await postJson("/api/net/split", { cidr, new_prefix: Number(splitTo) })), "Couldn't split that.")}>Split</button>
            </div>
            {split && <Table head={["Subnet", "First host", "Last host", "Usable"]} caption="Subnets" rows={split.subnets.map((s) => [s.network, s.first_host, s.last_host, String(s.usable_hosts)])} />}
          </div>
        )}
      </Section>

      <Section title="VLSM planner" note="Biggest subnets first, each on its own boundary. One line per subnet: name, then a comma and the number of hosts.">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Address block"><input className="field" value={base} onChange={(e) => setBase(e.target.value)} maxLength={60} /></Field>
          <Field label="Subnets needed"><textarea className="field font-mono text-xs" rows={5} value={needs} onChange={(e) => setNeeds(e.target.value)} /></Field>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => act(async () => setPlan(await postJson<Vlsm>("/api/net/vlsm", { base, needs: parseNeeds() })), "Couldn't plan that.")}>Plan</button>
        {plan && (
          <div className="mt-3">
            <Table head={["Name", "Needs", "Subnet", "Mask", "Range", "Spare"]} caption="VLSM plan" rows={plan.plan.map((p) => [p.name, String(p.hosts_needed), p.network, p.netmask, `${p.first_host} - ${p.last_host}`, String(p.spare)])} />
            <p className="mt-1 text-xs text-muted">{plan.used_addresses.toLocaleString()} addresses used, {plan.free_addresses.toLocaleString()} free. {plan.note}</p>
          </div>
        )}
      </Section>

      <Section title="Overlaps and route summary">
        <Field label="Networks (space, comma or new line)"><textarea className="field font-mono text-xs" rows={4} value={list} onChange={(e) => setList(e.target.value)} /></Field>
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn" onClick={() => act(async () => setOvl(await postJson("/api/net/overlaps", { cidrs: cidrs() })), "Couldn't check that.")}>Check overlaps</button>
          <button className="btn" onClick={() => act(async () => setSum((await postJson<{ summary: string[] }>("/api/net/summarize", { cidrs: cidrs() })).summary), "Couldn't summarise that.")}>Summarise routes</button>
        </div>
        {ovl && (ovl.ok ? <p className="mt-2 text-sm"><Badge tone="ok">no overlaps</Badge></p>
          : <ul className="mt-2 space-y-1 text-sm">{ovl.overlaps.map((o) => <li key={o.a + o.b}><Badge tone="bad">overlap</Badge> {o.a} and {o.b}: {o.relation}</li>)}</ul>)}
        {sum && <p className="mt-2 text-sm">Summary: <code>{sum.join(", ")}</code></p>}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- config review and packet capture
interface Finding { severity: string; title: string; detail: string; fix?: string; advice?: string; evidence: string[] }
interface Review { findings: Finding[]; counts?: Record<string, number>; caveat: string; lines?: number; parsed?: number; protocols?: Record<string, number>;
  top_sources?: { ip: string; packets: number }[]; top_dest_ports?: { port: number; service: string; syn_or_udp: number }[]; handshakes_completed?: number }

function TextTool({ kind }: { kind: "config" | "capture" }) {
  const [text, setText] = useState("");
  const [res, setRes] = useState<Review | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const base = kind === "config" ? "/api/net/config" : "/api/net/capture";
  const run = async () => {
    setBusy(true); setErr(null);
    try { setRes(await postJson<Review>(kind === "config" ? `${base}/audit` : `${base}/read`, { text })); } catch (e) { setErr(errMsg(e, "Couldn't read that.")); } finally { setBusy(false); }
  };
  const sample = async () => { setErr(null); try { setText((await getJson<{ text: string }>(`${base}/sample`)).text); setRes(null); } catch (e) { setErr(errMsg(e, "Couldn't load the sample.")); } };
  return (
    <div className="space-y-3">
      {err && <ErrorBanner message={err} />}
      <Section title={kind === "config" ? "Paste a router or switch config" : "Paste tcpdump -nn output"}
               note={kind === "config" ? "Cisco IOS style plus generic patterns. Pattern checks on text, not a CIS audit." : "Reads text only; it never captures packets. Findings are leads, not verdicts."}>
        <textarea className="field w-full font-mono text-xs" style={{ fontVariantLigatures: "none" }} rows={10} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label={kind === "config" ? "Config text" : "Capture text"} />
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={run}>{busy ? "Reading…" : kind === "config" ? "Review config" : "Read capture"}</button>
          <button className="btn" onClick={sample}>Load the sample</button>
        </div>
      </Section>
      {res && (
        <div className="space-y-3">
          {res.protocols && (
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat label="Lines parsed" value={`${res.parsed} of ${res.lines}`} />
              <Stat label="Protocols" value={Object.entries(res.protocols).map(([k, v]) => `${k} ${v}`).join(" · ")} />
              <Stat label="Handshakes seen" value={String(res.handshakes_completed ?? 0)} />
              <Stat label="Top source" value={res.top_sources?.[0]?.ip ?? "none"} sub={`${res.top_sources?.[0]?.packets ?? 0} packets`} />
            </div>
          )}
          {res.top_dest_ports && res.top_dest_ports.length > 0 && <Table head={["Port", "Service", "SYNs or UDP packets"]} caption="Destination ports" rows={res.top_dest_ports.map((p) => [String(p.port), p.service || "—", String(p.syn_or_udp)])} />}
          <Section title={res.findings.length ? `${res.findings.length} finding(s)` : "No findings"} note={res.caveat}>
            {res.findings.length === 0 && <p className="text-sm text-muted">None of the patterns matched.</p>}
            <ul className="space-y-2">
              {res.findings.map((f) => (
                <li key={f.title} className="rounded border border-line p-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={sev(f.severity)}>{f.severity}</Badge><span className="font-medium">{f.title}</span></div>
                  <p className="mt-1 text-xs text-muted">{f.detail}</p>
                  {(f.fix || f.advice) && <p className="mt-1 text-xs">{f.fix ? "Fix: " : "Next: "}{f.fix ?? f.advice}</p>}
                  {f.evidence.length > 0 && <pre className="mt-1 overflow-x-auto rounded bg-panel2 p-2 text-[11px]">{f.evidence.join("\n")}</pre>}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- DNS and reachability
function DiagTab() {
  const [host, setHost] = useState("example.com");
  const [port, setPort] = useState("443");
  const [dns, setDns] = useState<{ addresses: { address: string; version: number; scope: string }[]; lookup_ms: number; note: string } | null>(null);
  const [tcp, setTcp] = useState<{ ip: string; port: number; service: string; state: string; ms: number; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const act = async (f: () => Promise<void>, m: string) => { setBusy(true); setErr(null); try { await f(); } catch (e) { setErr(errMsg(e, m)); } finally { setBusy(false); } };
  return (
    <Section title="Name and port checks" note="Public hosts only. One port per test, 12 tests a minute. This is a diagnostic, not a scanner. Test only things you run or are allowed to test.">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Hostname"><input className="field w-64" value={host} onChange={(e) => setHost(e.target.value)} maxLength={253} /></Field>
        <button className="btn" disabled={busy} onClick={() => act(async () => { setDns(await postJson("/api/net/dns", { host })); }, "Lookup failed.")}>Look up DNS</button>
        <Field label="Port"><input className="field w-24" type="number" min={1} max={65535} value={port} onChange={(e) => setPort(e.target.value)} /></Field>
        <button className="btn btn-primary" disabled={busy} onClick={() => act(async () => { setTcp(await postJson("/api/net/tcp", { host, port: Number(port) })); }, "The check failed.")}>Test TCP port</button>
      </div>
      {dns && (
        <div className="mt-3">
          <Table head={["Address", "IP version", "Scope"]} caption="DNS answers" rows={dns.addresses.map((a) => [a.address, `v${a.version}`, a.scope])} />
          <p className="mt-1 text-xs text-muted">Answered in {dns.lookup_ms} ms. {dns.note}</p>
        </div>
      )}
      {tcp && (
        <p className="mt-3 text-sm"><Badge tone={tcp.state === "open" ? "ok" : tcp.state === "closed" ? "warn" : "muted"}>{tcp.state}</Badge> {tcp.ip}:{tcp.port}{tcp.service ? ` (${tcp.service})` : ""} in {tcp.ms} ms<span className="block text-xs text-muted">{tcp.note}</span></p>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- calculators
function CalcTab() {
  const [size, setSize] = useState("200");
  const [bw, setBw] = useState("100");
  const [eff, setEff] = useState("85");
  const [t, setT] = useState<{ human: string; effective_mbps: number; note: string } | null>(null);
  const [mbps, setMbps] = useState("1000");
  const [rtt, setRtt] = useState("80");
  const [win, setWin] = useState("64");
  const [b, setB] = useState<{ bdp_kb: number; window_limited_mbps: number; window_is_the_limit: boolean; advice: string; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const act = async (f: () => Promise<void>, m: string) => { setErr(null); try { await f(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="How long will the transfer take?">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Size (GB)"><input className="field w-28" type="number" value={size} onChange={(e) => setSize(e.target.value)} /></Field>
          <Field label="Link speed (Mbps)"><input className="field w-28" type="number" value={bw} onChange={(e) => setBw(e.target.value)} /></Field>
          <Field label="Efficiency (%)"><input className="field w-24" type="number" value={eff} onChange={(e) => setEff(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => act(async () => setT(await postJson("/api/net/transfer", { size_gb: Number(size), mbps: Number(bw), efficiency_pct: Number(eff) })), "Couldn't calculate that.")}>Calculate</button>
        </div>
        {t && <p className="mt-2 text-sm"><b>{t.human}</b> at about {t.effective_mbps} Mbps effective. <span className="text-xs text-muted">{t.note}</span></p>}
      </Section>
      <Section title="Is the TCP window the bottleneck?">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Link (Mbps)"><input className="field w-28" type="number" value={mbps} onChange={(e) => setMbps(e.target.value)} /></Field>
          <Field label="Round-trip time (ms)"><input className="field w-28" type="number" value={rtt} onChange={(e) => setRtt(e.target.value)} /></Field>
          <Field label="Window (KB)"><input className="field w-24" type="number" value={win} onChange={(e) => setWin(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => act(async () => setB(await postJson("/api/net/bdp", { mbps: Number(mbps), rtt_ms: Number(rtt), window_kb: Number(win) })), "Couldn't calculate that.")}>Calculate</button>
        </div>
        {b && (
          <div className="mt-2 text-sm">
            <p>Pipe holds <b>{b.bdp_kb.toLocaleString()} KB</b> in flight. One stream is limited to about <b>{b.window_limited_mbps} Mbps</b>. <Badge tone={b.window_is_the_limit ? "warn" : "ok"}>{b.window_is_the_limit ? "window-limited" : "window is enough"}</Badge></p>
            <p className="text-xs">{b.advice}</p><p className="text-xs text-muted">{b.note}</p>
          </div>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- reference
interface Ref { ports: { port: number; proto: string; service: string; note: string }[]; osi: { layer: number; name: string; examples: string; job: string; typical_faults: string }[]; commands: Record<string, { cmd: string; what: string }[]>; method: string[] }

function RefTab() {
  const [r, setR] = useState<Ref | null>(null);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Ref>("/api/net/reference", ctl.signal).then(setR).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the reference.")); });
    return () => ctl.abort();
  }, []);
  if (!r) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const ports = r.ports.filter((p) => !q || `${p.port} ${p.service} ${p.note}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="space-y-4">
      <Section title="Troubleshooting method"><ol className="list-decimal space-y-1 pl-5 text-sm">{r.method.map((m) => <li key={m}>{m}</li>)}</ol></Section>
      <Section title="OSI layers"><Table head={["Layer", "Name", "Examples", "Job", "Typical faults"]} caption="OSI layers" rows={r.osi.map((o) => [String(o.layer), o.name, o.examples, o.job, o.typical_faults])} /></Section>
      <Section title="Common ports">
        <Field label="Filter"><input className="field w-56" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. 3389 or ssh" /></Field>
        <div className="mt-2"><Table head={["Port", "Protocol", "Service", "Note"]} caption="Ports" rows={ports.map((p) => [String(p.port), p.proto, p.service, p.note])} /></div>
      </Section>
      {Object.entries(r.commands).map(([k, v]) => (
        <Section key={k} title={`Commands: ${k}`}><Table head={["Command", "What it tells you"]} caption={k} rows={v.map((c) => [<code key={c.cmd} className="break-all">{c.cmd}</code>, c.what])} /></Section>
      ))}
    </div>
  );
}
