"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Table, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "vd", label: "Wire and voltage drop" }, { id: "load", label: "Circuit load" }, { id: "energy", label: "Energy cost" }, { id: "size", label: "AC sizing" }, { id: "dt", label: "AC air check" }, { id: "ohm", label: "Ohm's law" }, { id: "who", label: "Who does what" }];

function In({ label, v, set, w = "w-28" }: { label: string; v: string; set: (s: string) => void; w?: string }) {
  return <label className="text-xs">{label}<input className={`input block ${w}`} inputMode="decimal" value={v} onChange={(e) => set(e.target.value)} /></label>;
}

/** Electrical and HVAC calculators for planning, quoting and talking to licensed trades. Reference only. */
export function ElecHvacLab() {
  const [tab, setTab] = useState("vd");
  const [err, setErr] = useState<string | null>(null);
  const [out, setOut] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [f, setF] = useState<Record<string, string>>({ amps: "20", length_ft: "100", awg: "12", volts: "120", breaker_amps: "15", loads: "Space heater, 1500\nLamp, 60", watts: "1000", hours_per_day: "5", rate_per_kwh: "0.13", sqft: "400", ceiling_ft: "8", people: "2", supply_f: "55", return_f: "75", ohm_v: "120", ohm_i: "10", ohm_r: "", ohm_w: "" });
  const [sun, setSun] = useState("average");
  const [ins, setIns] = useState("average");
  const [cont, setCont] = useState(false);
  const [kitchen, setKitchen] = useState(false);
  const s = (k: string) => (v: string) => setF((x) => ({ ...x, [k]: v }));
  useEffect(() => { if (tab === "who" && !ref) getJson<R>("/api/elec/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, [tab, ref]);
  const run = async (path: string, body: unknown) => { setErr(null); try { setOut(await postJson<R>(`/api/elec/${path}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check your numbers.")); } };
  const pick = (id: string) => { setTab(id); setOut(null); setErr(null); };
  return (
    <section className="card space-y-3 p-4" aria-label="Electrical and HVAC lab">
      <h2 className="text-base font-semibold">Electrical, HVAC and appliances: planning and quoting aids</h2>
      <p className="rounded border border-line p-2 text-xs"><Badge tone="warn">Licensed work</Badge> Household wiring, panels, gas, and refrigerant need a licensed professional. These tools help you plan, quote and ask the right questions. For appliance and AC owner-level checks, search the How to repair guides (IT dashboard) or ask the agent.</p>
      <Tabs tabs={TABS} value={tab} onChange={pick} label="Electrical and HVAC lab" />
      {err && <ErrorBanner message={err} />}
      {tab === "vd" && (
        <Section title="Wire size and voltage drop" note="Copper wire, one-way length to the load.">
          <div className="flex flex-wrap items-end gap-2"><In label="Current (A)" v={f.amps} set={s("amps")} /><In label="One-way length (ft)" v={f.length_ft} set={s("length_ft")} /><In label="Wire (AWG)" v={f.awg} set={s("awg")} w="w-20" /><In label="Volts" v={f.volts} set={s("volts")} w="w-20" />
            <button className="btn btn-primary" onClick={() => run("voltage-drop", { amps: f.amps, length_ft: f.length_ft, awg: Number(f.awg), volts: f.volts })}>Calculate</button></div>
          {out && <div className="mt-2 space-y-1 text-sm"><p>{out.volts_lost} V lost ({out.percent}%), {out.volts_at_load} V at the load. 60 C ampacity of this wire: {out.ampacity_60c} A.</p><p>{out.verdict}</p><p>Smallest size under 3%: <strong>{out.smallest_size_under_3pct}</strong></p><p className="text-xs text-muted">{out.note}</p></div>}
        </Section>
      )}
      {tab === "load" && (
        <Section title="Circuit load" note="One device per line: name, watts.">
          <div className="flex flex-wrap items-end gap-2"><In label="Volts" v={f.volts} set={s("volts")} w="w-20" /><In label="Breaker (A)" v={f.breaker_amps} set={s("breaker_amps")} w="w-24" />
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={cont} onChange={(e) => setCont(e.target.checked)} /> Runs 3+ hours (continuous)</label></div>
          <textarea className="field mt-2 h-24 w-full font-mono text-xs" aria-label="Devices" value={f.loads} onChange={(e) => s("loads")(e.target.value)} />
          <button className="btn btn-primary mt-2" onClick={() => run("circuit-load", { volts: f.volts, breaker_amps: f.breaker_amps, loads: f.loads, continuous: cont })}>Check the circuit</button>
          {out && <div className="mt-2 space-y-1 text-sm"><p>{out.total_watts} W = {out.amps} A on a {out.breaker_amps} A breaker ({out.usable_amps} A usable): <strong>{out.percent_of_usable}%</strong></p><p>{out.verdict}</p><p className="text-xs text-muted">{out.rule}</p></div>}
        </Section>
      )}
      {tab === "energy" && (
        <Section title="What does it cost to run?" note="Use the rate on your own bill.">
          <div className="flex flex-wrap items-end gap-2"><In label="Watts" v={f.watts} set={s("watts")} /><In label="Hours per day" v={f.hours_per_day} set={s("hours_per_day")} /><In label="Rate ($/kWh)" v={f.rate_per_kwh} set={s("rate_per_kwh")} />
            <button className="btn btn-primary" onClick={() => run("energy", { watts: f.watts, hours_per_day: f.hours_per_day, rate_per_kwh: f.rate_per_kwh })}>Calculate</button></div>
          {out && <p className="mt-2 text-sm">{out.kwh} kWh in 30 days = <strong>${out.cost}</strong> a month, about ${out.per_year} a year. <span className="text-xs text-muted">{out.note}</span></p>}
        </Section>
      )}
      {tab === "size" && (
        <Section title="Rough AC size for a room or home" note="A starting point only. A contractor's load calculation decides the real size.">
          <div className="flex flex-wrap items-end gap-2"><In label="Floor area (sq ft)" v={f.sqft} set={s("sqft")} /><In label="Ceiling (ft)" v={f.ceiling_ft} set={s("ceiling_ft")} w="w-20" /><In label="People" v={f.people} set={s("people")} w="w-20" />
            <label className="text-xs">Sun<select className="input block" value={sun} onChange={(e) => setSun(e.target.value)}><option>low</option><option>average</option><option>high</option></select></label>
            <label className="text-xs">Insulation<select className="input block" value={ins} onChange={(e) => setIns(e.target.value)}><option>poor</option><option>average</option><option>good</option></select></label>
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={kitchen} onChange={(e) => setKitchen(e.target.checked)} /> Kitchen</label>
            <button className="btn btn-primary" onClick={() => run("hvac-size", { sqft: f.sqft, ceiling_ft: f.ceiling_ft, people: f.people, sun, insulation: ins, kitchen })}>Estimate</button></div>
          {out && <div className="mt-2 text-sm"><p><strong>{Number(out.btu_per_hour).toLocaleString()} BTU/h</strong> (about {out.tons} tons).</p><p className="text-xs text-muted">{out.note}</p></div>}
        </Section>
      )}
      {tab === "dt" && (
        <Section title="Is the AC cooling properly? (air temperature split)" note="Run the system 15 minutes, then measure return air and supply air with a thermometer.">
          <div className="flex flex-wrap items-end gap-2"><In label="Supply air (F)" v={f.supply_f} set={s("supply_f")} /><In label="Return air (F)" v={f.return_f} set={s("return_f")} />
            <button className="btn btn-primary" onClick={() => run("delta-t", { supply_f: f.supply_f, return_f: f.return_f })}>Check</button></div>
          {out && <div className="mt-2 space-y-1 text-sm"><p>Split: <strong>{out.split_f} F</strong></p><p>{out.verdict}</p><p className="text-xs text-muted">{out.how}</p></div>}
        </Section>
      )}
      {tab === "ohm" && (
        <Section title="Ohm's law and power" note="Fill in exactly two boxes.">
          <div className="flex flex-wrap items-end gap-2"><In label="Volts" v={f.ohm_v} set={s("ohm_v")} /><In label="Amps" v={f.ohm_i} set={s("ohm_i")} /><In label="Ohms" v={f.ohm_r} set={s("ohm_r")} /><In label="Watts" v={f.ohm_w} set={s("ohm_w")} />
            <button className="btn btn-primary" onClick={() => run("ohm", { volts: f.ohm_v, amps: f.ohm_i, ohms: f.ohm_r, watts: f.ohm_w })}>Solve</button></div>
          {out && <p className="mt-2 font-mono text-sm">{out.volts} V, {out.amps} A, {out.ohms} ohms, {out.watts} W</p>}
        </Section>
      )}
      {tab === "who" && ref && (
        <div className="space-y-3">
          <Table head={["Job", "Who does it"]} caption="Who does what" rows={ref.who_does_what.map((w: R) => [w.job, w.who])} />
          <Table head={["Circuit", "Typical breaker and wire"]} caption="Typical household circuits (reference)" rows={ref.typical_circuits.map((c: R) => [c.circuit, c.breaker])} />
          <Table head={["Wire (AWG)", "Ohms per 1000 ft", "Ampacity (60 C)"]} caption="Copper wire" rows={ref.wire.map((w: R) => [String(w.awg), String(w.ohms_per_1000ft), `${w.ampacity_60c} A`])} />
          <ul className="list-disc space-y-1 pl-5 text-xs">{ref.hvac_facts.map((x: string) => <li key={x}>{x}</li>)}</ul>
          <p className="text-xs text-muted">{ref.note}</p>
        </div>
      )}
    </section>
  );
}
