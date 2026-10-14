"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Field, Section, Stat, Table, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function DesignTab() {
  const [id, setId] = useState("plan");
  return (
    <Section title="Network design" note="Plan on paper first. These sizing sketches are for learning; a real design needs a site survey and measured traffic.">
      <Tabs tabs={[{ id: "plan", label: "Design planner" }, { id: "steps", label: "Design steps" }, { id: "gloss", label: "Glossary" }, { id: "ports", label: "Ports" }]} value={id} onChange={setId} label="Network design" />
      {id === "plan" && <Planner />}
      {id === "steps" && <Steps />}
      {id === "gloss" && <Gloss />}
      {id === "ports" && <Ports />}
    </Section>
  );
}

function Planner() {
  const [groups, setGroups] = useState("Office, 40\nWarehouse, 15\nReception, 6");
  const [o, setO] = useState({ growth_pct: "25", sites: "1", base: "10.20.0.0/16", redundancy: "links", wifi: "yes", guest: "yes", remote: "yes" });
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const go = () => {
    setErr(null);
    const gs = groups.split("\n").map((l) => l.split(",").map((x) => x.trim())).filter((p) => p[0]).map((p) => ({ name: p[0], hosts: Number(p[1]) }));
    postJson<R>("/api/frames/design/plan", { spec: { groups: gs, growth_pct: Number(o.growth_pct), sites: Number(o.sites), base: o.base, redundancy: o.redundancy, wifi: o.wifi === "yes", guest_wifi: o.guest === "yes", remote_access: o.remote === "yes" } })
      .then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Check the requirements.")); });
  };
  const sel = (k: keyof typeof o, label: string, opts: string[]) => <Field label={label}><select className="field" aria-label={label} value={o[k]} onChange={(e) => setO({ ...o, [k]: e.target.value })}>{opts.map((x) => <option key={x}>{x}</option>)}</select></Field>;
  return (
    <div className="space-y-3">
      <Field label="Groups: name, hosts (one per line)"><textarea className="field font-mono" rows={4} aria-label="Groups" value={groups} onChange={(e) => setGroups(e.target.value)} /></Field>
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Growth % over the design life"><input className="field" aria-label="Growth percent" value={o.growth_pct} onChange={(e) => setO({ ...o, growth_pct: e.target.value })} /></Field>
        <Field label="Sites"><input className="field" aria-label="Sites" value={o.sites} onChange={(e) => setO({ ...o, sites: e.target.value })} /></Field>
        <Field label="Address block"><input className="field" aria-label="Address block" value={o.base} onChange={(e) => setO({ ...o, base: e.target.value })} /></Field>
        {sel("redundancy", "Redundancy", ["none", "links", "full"])}{sel("wifi", "Wi-Fi", ["yes", "no"])}{sel("guest", "Guest Wi-Fi", ["yes", "no"])}{sel("remote", "Remote access", ["yes", "no"])}
      </div>
      <button className="btn" onClick={go}>Plan it</button>
      {err && <ErrorBanner message={err} />}
      {res && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Size" value={res.size} /><Stat label="Users" value={String(res.users)} /><Stat label="Growth" value={`${res.growth_pct}%`} /><Stat label="Free addresses" value={String(res.free_addresses)} /></div>
          <p className="text-sm">{res.topology}</p>
          <Table caption="Address plan" head={["Subnet", "Network", "Hosts needed", "Usable", "Spare"]} rows={res.addressing.map((a: R) => [a.name, a.network, a.hosts_needed, a.usable_hosts, a.spare])} />
          <Table caption="Devices" head={["Item", "Count", "Note"]} rows={res.devices.map((d: R) => [d.item, d.count, d.note])} />
          <p className="text-sm"><b>Security zones:</b> {res.zones.join(", ")}</p>
          {res.risks.length > 0 && <div><h4 className="text-sm font-semibold">Risks</h4><ul className="list-disc pl-5 text-sm">{res.risks.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul></div>}
          <p className="text-xs text-muted">{res.limit}</p>
        </div>
      )}
    </div>
  );
}

function useGet(url: string) {
  const [d, setD] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>(url).then(setD).catch((e) => setErr(errMsg(e, "Could not load."))); }, [url]);
  return { d, err };
}

function Steps() {
  const { d, err } = useGet("/api/frames/design/steps");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      <ol className="list-decimal pl-5 text-sm">{d.steps.map((s: R) => <li key={s.id}><b>{s.step}.</b> {s.detail}</li>)}</ol>
      <div><h4 className="text-sm font-semibold">Mistakes in the source material</h4><ul className="list-disc pl-5 text-sm">{d.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></div>
    </div>
  );
}

function Gloss() {
  const [q, setQ] = useState("");
  const { d, err } = useGet(`/api/frames/glossary?q=${encodeURIComponent(q)}`);
  return (
    <div className="space-y-2">
      <Field label="Search terms"><input className="field" aria-label="Search terms" value={q} onChange={(e) => setQ(e.target.value)} /></Field>
      {err && <ErrorBanner message={err} />}
      {d && <Table caption={`${d.count} terms`} head={["Term", "Full name", "Meaning", "Note"]} rows={d.terms.map((t: R) => [t.term, t.full, t.meaning, t.note])} />}
    </div>
  );
}

function Ports() {
  const { d, err } = useGet("/api/frames/ports");
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-2">
      <Table caption="Common default ports" head={["Port", "Protocol", "Service"]} rows={d.ports.map((p: R) => [p.port, p.protocol, p.service])} />
      <p className="text-xs text-muted">{d.note} {d.legacy}</p>
    </div>
  );
}
