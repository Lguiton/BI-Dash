"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
type F = [string, string, string];
const CALCS: { id: string; label: string; note: string; fields: F[] }[] = [
  { id: "drive", label: "Drive motor size", note: "Force and torque at the wheel for a rolling robot.", fields: [["mass_kg", "Mass (kg)", "5"], ["wheel_mm", "Wheel diameter (mm)", "100"], ["speed_ms", "Top speed (m/s)", "1"], ["accel_ms2", "Acceleration (m/s2)", "0.5"], ["incline_deg", "Incline (deg)", "0"], ["wheels", "Driven wheels", "2"], ["rolling", "Rolling resistance", "0.03"], ["efficiency", "Efficiency (0-1)", "0.7"], ["safety", "Safety factor", "2"]] },
  { id: "gearbox", label: "Gearbox", note: "Trade speed for torque.", fields: [["motor_rpm", "Motor rpm", "6000"], ["motor_torque_nm", "Motor torque (N m)", "0.02"], ["ratio", "Ratio (n:1)", "30"], ["efficiency", "Efficiency", "0.85"]] },
  { id: "battery", label: "Battery runtime", note: "Minutes of run time and the pack's current limit.", fields: [["capacity_mah", "Capacity (mAh)", "5000"], ["voltage", "Voltage (V)", "11.1"], ["avg_current_a", "Average current (A)", "5"], ["c_rating", "C rating", "20"], ["peak_current_a", "Peak current (A)", "40"], ["usable", "Usable fraction", "0.8"]] },
  { id: "servo", label: "Servo torque", note: "Worst case with the arm horizontal.", fields: [["arm_cm", "Arm length (cm)", "20"], ["load_kg", "Load (kg)", "0.5"], ["arm_mass_kg", "Arm mass (kg)", "0.1"], ["safety", "Safety factor", "2"]] },
  { id: "arm_ik", label: "Arm: inverse kinematics", note: "Joint angles to reach a point (two-link arm).", fields: [["l1", "Link 1", "10"], ["l2", "Link 2", "10"], ["x", "Target x", "10"], ["y", "Target y", "10"]] },
  { id: "arm_fk", label: "Arm: forward kinematics", note: "Where the arm ends up for given angles.", fields: [["l1", "Link 1", "10"], ["l2", "Link 2", "10"], ["a1_deg", "Angle 1 (deg)", "45"], ["a2_deg", "Angle 2 (deg)", "30"]] },
  { id: "diff_drive", label: "Differential drive path", note: "Where a two-wheel robot ends up.", fields: [["v_left", "Left speed (m/s)", "0.5"], ["v_right", "Right speed (m/s)", "0.6"], ["wheelbase_m", "Wheelbase (m)", "0.2"], ["seconds", "Seconds", "5"]] },
  { id: "encoder", label: "Encoder", note: "Distance per tick.", fields: [["counts_per_rev", "Counts per rev (motor)", "11"], ["wheel_mm", "Wheel diameter (mm)", "65"], ["gear_ratio", "Gear ratio", "30"]] },
  { id: "ultrasonic", label: "Ultrasonic distance", note: "From echo time.", fields: [["echo_us", "Echo time (us)", "1166"], ["temp_c", "Temperature (C)", "20"]] },
];
const TABS = [{ id: "calc", label: "Calculators" }, { id: "pid", label: "PID tuning" }, { id: "learn", label: "Concepts" }, { id: "parts", label: "Sensors and drivers" }, { id: "build", label: "Wiring and safety" }, { id: "proj", label: "Starter projects" }];
const PID_F: F[] = [["kp", "Kp", "2"], ["ki", "Ki", "1"], ["kd", "Kd", "0"], ["setpoint", "Setpoint", "1"], ["tau", "Plant time constant (s)", "1"], ["gain", "Plant gain", "1"], ["dead_time", "Delay (s)", "0"], ["umax", "Output limit", "10"], ["seconds", "Seconds", "10"]];

function Fields({ f, v, set }: { f: F[]; v: Record<string, string>; set: (k: string, s: string) => void }) {
  return <div className="flex flex-wrap items-end gap-2">{f.map(([k, l]) => <label key={k} className="text-xs">{l}<input className="input block w-28" inputMode="decimal" value={v[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></label>)}</div>;
}
function Out({ r }: { r: R }) {
  const scal = Object.entries(r).filter(([k, v]) => (typeof v === "number" || typeof v === "string" || typeof v === "boolean") && k !== "note");
  const lists = Object.entries(r).filter(([, v]) => Array.isArray(v) && v.length && typeof v[0] === "string");
  return (
    <div className="mt-2 space-y-2 text-sm">
      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">{scal.map(([k, v]) => <div key={k}><dt className="inline text-xs text-muted">{k.replace(/_/g, " ")}: </dt><dd className="inline font-semibold">{String(v)}</dd></div>)}</dl>
      {Array.isArray(r.solutions) && r.solutions.map((s: R) => <p key={s.name}><b>{s.name}:</b> angle 1 {s.angle1_deg} deg, angle 2 {s.angle2_deg} deg</p>)}
      {Array.isArray(r.end) && <p>End point: ({r.end[0]}, {r.end[1]}); elbow ({r.elbow?.[0]}, {r.elbow?.[1]})</p>}
      {lists.map(([k, v]) => <ul key={k} className="list-disc space-y-1 pl-5 text-xs">{(v as string[]).map((x) => <li key={x}>{x}</li>)}</ul>)}
      {r.note && <p className="text-xs text-muted">{r.note}</p>}
    </div>
  );
}
function Plot({ t, y, sp }: { t: number[]; y: number[]; sp: number }) {
  const W = 360, H = 140, tmax = t[t.length - 1] || 1, ymax = Math.max(sp, ...y, 0.001) * 1.1, ymin = Math.min(0, ...y);
  const px = (i: number) => (t[i] / tmax) * (W - 10) + 5, py = (v: number) => H - 8 - ((v - ymin) / (ymax - ymin)) * (H - 16);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md rounded border border-line" role="img" aria-label="Response curve against the setpoint">
      <line x1="5" x2={W - 5} y1={py(sp)} y2={py(sp)} stroke="currentColor" strokeDasharray="4 3" opacity="0.5" />
      <polyline fill="none" stroke="currentColor" strokeWidth="2" points={y.map((v, i) => `${px(i)},${py(v)}`).join(" ")} />
    </svg>
  );
}

/** Robotics for the Computer Engineer dashboard: sizing calculators, PID and kinematics, sensors, drivers, wiring and safety, and starter projects. Reference and planning only. */
export function RoboticsLab() {
  const [tab, setTab] = useState("calc");
  const [cid, setCid] = useState("drive");
  const [vals, setVals] = useState<Record<string, Record<string, string>>>(() => Object.fromEntries([...CALCS.map((c) => [c.id, Object.fromEntries(c.fields.map(([k, , d]) => [k, d]))]), ["pid", Object.fromEntries(PID_F.map(([k, , d]) => [k, d]))]]));
  const [out, setOut] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (["learn", "parts", "build", "proj"].includes(tab) && !ref) getJson<R>("/api/robotics/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, [tab, ref]);
  const set = (id: string) => (k: string, s: string) => setVals((x) => ({ ...x, [id]: { ...x[id], [k]: s } }));
  const run = async (id: string) => { setErr(null); try { setOut(await postJson<R>(`/api/robotics/calc/${id}`, vals[id])); } catch (e) { setOut(null); setErr(errMsg(e, "Check your numbers.")); } };
  const cur = CALCS.find((c) => c.id === cid) ?? CALCS[0];
  return (
    <section className="card space-y-3 p-4" aria-label="Robotics lab">
      <h2 className="text-base font-semibold">Robotics: motors, sensors, control, kinematics and projects</h2>
      <p className="rounded border border-line p-2 text-xs"><Badge tone="warn">Bench first</Badge> These are planning estimates. Test with the robot lifted off the ground, add a hardware stop, and handle lithium batteries carefully.</p>
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setOut(null); setErr(null); }} label="Robotics lab" />
      {err && <ErrorBanner message={err} />}
      {tab === "calc" && (
        <Section title={cur.label} note={cur.note}>
          <label className="mb-2 block text-xs">Calculator <select className="input ml-2 w-56" value={cid} onChange={(e) => { setCid(e.target.value); setOut(null); setErr(null); }}>{CALCS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
          <Fields f={cur.fields} v={vals[cid]} set={set(cid)} />
          <button className="btn btn-primary mt-2" onClick={() => run(cid)}>Calculate</button>
          {out && <Out r={out} />}
        </Section>
      )}
      {tab === "pid" && (
        <Section title="PID tuning sandbox" note="A simple motor-like model. See what P, I and D each do, then retune on the real robot.">
          <Fields f={PID_F} v={vals.pid} set={set("pid")} />
          <button className="btn btn-primary mt-2" onClick={() => run("pid")}>Simulate</button>
          {out && out.y && (<div className="mt-2 space-y-2"><Plot t={out.t} y={out.y} sp={out.setpoint} /><Out r={{ ...out, t: undefined, y: undefined }} /></div>)}
        </Section>
      )}
      {tab === "learn" && ref && <dl className="space-y-2 text-sm">{ref.concepts.map((c: R) => <div key={c.h}><dt className="font-semibold">{c.h}</dt><dd className="text-muted">{c.p}</dd></div>)}</dl>}
      {tab === "parts" && ref && (
        <div className="space-y-4">
          <Section title="Sensors"><ul className="space-y-2 text-sm">{ref.sensors.map((s: R) => <li key={s.name} className="rounded border border-line p-2"><b>{s.name}</b>: {s.use}. <span className="text-muted">How: {s.how}. Watch: {s.watch}.</span></li>)}</ul></Section>
          <Section title="Motor drivers and actuators"><ul className="space-y-2 text-sm">{ref.drivers.map((s: R) => <li key={s.type} className="rounded border border-line p-2"><b>{s.type}</b> ({s.examples}): {s.for}. <span className="text-muted">{s.tips}.</span></li>)}</ul></Section>
        </div>
      )}
      {tab === "build" && ref && (
        <div className="grid gap-4 md:grid-cols-2">
          <Section title="Wiring checklist"><ul className="list-disc space-y-1 pl-5 text-sm">{ref.wiring.map((w: string) => <li key={w}>{w}</li>)}</ul></Section>
          <Section title="Safety"><ul className="list-disc space-y-1 pl-5 text-sm">{ref.safety.map((w: string) => <li key={w}>{w}</li>)}</ul></Section>
        </div>
      )}
      {tab === "proj" && ref && <ul className="space-y-3 text-sm">{ref.projects.map((p: R) => (
        <li key={p.id} className="rounded border border-line p-3"><p className="font-semibold">{p.title} <Badge tone="muted">{p.level}</Badge></p><p className="text-xs text-muted">Parts: {p.parts}</p>
          <ol className="mt-1 list-decimal space-y-1 pl-5">{p.steps.map((s: string) => <li key={s}>{s}</li>)}</ol><p className="mt-1 text-xs">You learn: {p.learn}</p></li>
      ))}</ul>}
    </section>
  );
}
