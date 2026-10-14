"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";
import { Drills, PracticeShell } from "./FundPractice";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "shell", label: "Practice shell" }, { id: "drills", label: "Drills" }, { id: "num", label: "Numbers and logic" }, { id: "store", label: "Storage" }, { id: "perm", label: "Permissions" }, { id: "ip6", label: "IPv6" }, { id: "cmd", label: "Command finder" }, { id: "ref", label: "Reference" }];

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
const In = ({ label, v, set, mono }: { label: string; v: string; set: (s: string) => void; mono?: boolean }) => <Field label={label}><input className={`field ${mono ? "font-mono" : ""}`} value={v} onChange={(e) => set(e.target.value)} /></Field>;

export function FundTab() {
  const [tab, setTab] = useState("shell");
  return (
    <section className="card space-y-4 p-4" aria-label="IT fundamentals">
      <h2 className="text-base font-semibold">IT fundamentals: how computers count, store and protect data</h2>
      <Lesson text="Small calculators for the basics every support person uses: number systems, logic, storage sizes, Linux permissions, IPv6 and the command for a task in Windows and Linux. They only calculate; nothing is run on your machine." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="IT fundamentals" />
      {tab === "shell" && <PracticeShell />}
      {tab === "drills" && <Drills />}
      {tab === "num" && <><Convert /><Encode /><Logic /></>}
      {tab === "store" && <Storage />}
      {tab === "perm" && <Perm />}
      {tab === "ip6" && <Ip6 />}
      {tab === "cmd" && <Commands />}
      {tab === "ref" && <Reference />}
    </section>
  );
}

function Convert() {
  const [v, setV] = useState("87"); const [b, setB] = useState("decimal"); const c = useCall();
  return (
    <Section title="Number converter" note="Type a number in any base and see the others, with the working.">
      <div className="grid gap-2 sm:grid-cols-3">
        <In label="Number" v={v} set={setV} mono />
        <Field label="Base"><select className="field" value={b} onChange={(e) => setB(e.target.value)}>{["decimal", "binary", "hex", "octal"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <div className="flex items-end"><button className="btn btn-primary" onClick={() => c.run("/api/itfund/convert", { value: v, base: b })}>Convert</button></div>
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Decimal" value={String(c.res.decimal)} /><Stat label="Binary" value={c.res.binary} /><Stat label="Hex" value={c.res.hex} /><Stat label="Octal" value={c.res.octal} /></div>
        {c.res.table && <Table head={c.res.table.map((t: R) => String(t.place))} rows={[c.res.table.map((t: R) => t.bit)]} />}
        <p className="text-sm">Check: {c.res.check}{c.res.ascii ? `. As ASCII this is "${c.res.ascii}".` : ""} ({c.res.bytes} byte{c.res.bytes > 1 ? "s" : ""})</p>
        <Lesson text={c.res.lesson} />
      </div>}
    </Section>
  );
}

function Encode() {
  const [t, setT] = useState("Aé€"); const c = useCall();
  return (
    <Section title="Text encoding" note="Characters become numbers, numbers become bytes.">
      <div className="flex flex-wrap items-end gap-2"><div className="min-w-48 flex-1"><In label="Text" v={t} set={setT} /></div><button className="btn btn-primary" onClick={() => c.run("/api/itfund/encode", { text: t })}>Encode</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2"><Table head={["Char", "Code point", "UTF-8 hex", "UTF-8 bits", "Bytes"]} rows={c.res.rows.map((r: R) => [r.char, r.code_point, r.utf8_hex, r.utf8_binary, r.bytes])} /><p className="text-sm">{c.res.characters} characters, {c.res.total_bytes} bytes.</p><Lesson text={c.res.lesson} /></div>}
    </Section>
  );
}

function Logic() {
  const [e, setE] = useState("(A AND B) OR NOT C"); const [g, setG] = useState("XOR"); const c = useCall(); const gt = useCall();
  return (
    <Section title="Logic gates and circuits" note="Gates: NOT AND OR XOR NAND NOR XNOR. Try your own expression with up to four inputs.">
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Gate"><select className="field" value={g} onChange={(x) => { setG(x.target.value); gt.run(`/api/itfund/gate?name=${x.target.value}`, undefined, "get"); }}>{["NOT", "AND", "OR", "XOR", "NAND", "NOR", "XNOR"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <button className="btn" onClick={() => gt.run(`/api/itfund/gate?name=${g}`, undefined, "get")}>Show table</button>
      </div>
      <Out c={gt} />
      {gt.res && <div className="mt-2"><p className="text-sm">{gt.res.gate}: {gt.res.rule}</p><Table head={gt.res.inputs === 1 ? ["A", "Out"] : ["A", "B", "Out"]} rows={gt.res.rows.map((r: R) => (gt.res!.inputs === 1 ? [r.a, r.out] : [r.a, r.b, r.out]))} /></div>}
      <div className="mt-3 flex flex-wrap items-end gap-2"><div className="min-w-64 flex-1"><In label="Expression" v={e} set={setE} mono /></div><button className="btn btn-primary" onClick={() => c.run("/api/itfund/circuit", { text: e })}>Truth table</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-1"><Table head={[...c.res.inputs, "Out"]} rows={c.res.rows.map((r: R) => [...c.res!.inputs.map((n: string) => r[n]), r.out])} /><p className="text-sm">{c.res.reading}</p><p className="text-xs text-muted">{c.res.note}</p></div>}
    </Section>
  );
}

function Storage() {
  const [v, setV] = useState("1"); const [u, setU] = useState("TB"); const c = useCall();
  return (
    <Section title="Storage units" note="Why a 1 TB drive shows about 931 GB.">
      <div className="grid gap-2 sm:grid-cols-3">
        <In label="Size" v={v} set={setV} />
        <Field label="Unit"><select className="field" value={u} onChange={(e) => setU(e.target.value)}>{["B", "KB", "MB", "GB", "TB", "PB"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <div className="flex items-end"><button className="btn btn-primary" onClick={() => c.run("/api/itfund/storage", { value: Number(v), unit: u })}>Calculate</button></div>
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        {c.res.drive && <p className="text-sm"><Badge tone="warn">drive</Badge> Labelled {c.res.drive.marketed}; the operating system shows {c.res.drive.shown} {c.res.drive.shown_unit} ({c.res.drive.as_gib} GiB, often printed as GB). That is {c.res.drive.difference_pct}% less in the same unit; nothing is missing.</p>}
        <Table head={["Unit", "Decimal (powers of 1000)", "Binary name", "Binary (powers of 1024)"]} rows={c.res.rows.map((r: R) => [r.unit, r.decimal, r.binary_name, r.binary])} />
        <Lesson text={c.res.lesson} /><p className="text-xs text-muted">{c.res.formula}</p>
      </div>}
    </Section>
  );
}

function Perm() {
  const [m, setM] = useState("754"); const [k, setK] = useState("file"); const [um, setUm] = useState("022"); const c = useCall();
  return (
    <Section title="Permission calculator" note="Octal (754, 1775) or symbolic (rwxr-xr--). Nothing is changed on disk.">
      <div className="grid gap-2 sm:grid-cols-4">
        <In label="Mode" v={m} set={setM} mono />
        <Field label="Applies to"><select className="field" value={k} onChange={(e) => setK(e.target.value)}><option value="file">file</option><option value="dir">directory</option></select></Field>
        <In label="umask (optional)" v={um} set={setUm} mono />
        <div className="flex items-end"><button className="btn btn-primary" onClick={() => c.run("/api/itfund/chmod", { mode: m, kind: k, umask: um })}>Explain</button></div>
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="grid grid-cols-2 gap-2"><Stat label="Octal" value={c.res.octal} /><Stat label="Symbolic" value={c.res.symbolic} /></div>
        <ul className="list-disc pl-5 text-sm">{c.res.meaning.map((x: string) => <li key={x}>{x}</li>)}</ul>
        {c.res.warnings.length > 0 && <Warn items={c.res.warnings} />}
        {c.res.umask && <p className="text-sm">With umask {c.res.umask.umask}, a new {k} gets <b>{c.res.umask.new_mode}</b> ({c.res.umask.symbolic}). {c.res.umask.lesson}</p>}
        <pre className="overflow-x-auto rounded bg-panel2 p-2 text-xs">{c.res.commands.join("\n")}</pre>
        <Lesson text={c.res.digits} /><p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Ip6() {
  const [a, setA] = useState("2001:0db8:0000:0000:0000:0000:0000:0001"); const c = useCall();
  return (
    <Section title="IPv6 address tool" note="Compress, expand and classify an address.">
      <div className="flex flex-wrap items-end gap-2"><div className="min-w-64 flex-1"><In label="Address" v={a} set={setA} mono /></div><button className="btn btn-primary" onClick={() => c.run("/api/itfund/ipv6", { address: a })}>Check</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <Table head={["Form", "Value"]} rows={[["Compressed", c.res.compressed], ["Expanded", c.res.expanded], ["/64 network", c.res.network_64], ["Interface ID", c.res.interface_id]]} />
        <p className="text-sm"><b>Type:</b> {c.res.type}</p>
        <ul className="list-disc pl-5 text-sm">{c.res.rules.map((x: string) => <li key={x}>{x}</li>)}</ul>
        <Lesson text={c.res.lesson} /><p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Commands() {
  const [q, setQ] = useState(""); const [r, setR] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>(`/api/itfund/commands?q=${encodeURIComponent(q)}`).then(setR).catch((e) => setErr(errMsg(e, "Couldn't search."))); }, [q]);
  return (
    <Section title="Windows and Linux command finder" note="Search by task: disk, user, permission, process, port.">
      <In label="Search" v={q} set={setQ} />
      {err && <ErrorBanner message={err} />}
      {r && <><p className="mt-1 text-xs text-muted">{r.rows.length} of {r.total} tasks. {r.note}</p>
        {r.rows.length === 0 ? <p className="text-sm text-muted">Nothing matches. Try one word.</p> :
          <Table head={["Task", "Windows", "Linux", "Note"]} rows={r.rows.map((x: R) => [x.task, <code key="w" className="text-xs">{x.windows}</code>, <code key="l" className="text-xs">{x.linux}</code>, x.note])} />}</>}
    </Section>
  );
}

function Reference() {
  const [d, setD] = useState<R | null>(null); const [t, setT] = useState("connections"); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/itfund").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, []);
  if (!d) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      <Field label="Topic"><select className="field" value={t} onChange={(e) => setT(e.target.value)}>{d.topics.map((x: string) => <option key={x} value={x}>{x.replace("_", " and ")}</option>)}</select></Field>
      <Table head={["Item", "What to know"]} rows={d.sections[t].map((x: R) => [x.item, x.note])} />
      <Section title="Slips found in the source course"><ul className="list-disc pl-5 text-sm">{d.slips.map((x: string) => <li key={x}>{x}</li>)}</ul></Section>
      <Section title="Not built here"><ul className="list-disc pl-5 text-sm">{d.not_built.map((x: string) => <li key={x}>{x}</li>)}</ul></Section>
    </div>
  );
}
