"use client";
import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";
import { Section, Tabs } from "./kit";
import { ToolView, type ToolSpec } from "./LearnToolkit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const n = (v: string) => (v.trim() === "" ? null : Number(v));
const num = (k: string, label: string, def = "") => ({ k, label, type: "number" as const, def });

const NUMBERS: ToolSpec[] = [
  { id: "conv", label: "Number systems", endpoint: "/api/cpe/convert", note: "Type a number in any base from 2 to 36 and see it in binary, octal, decimal and hex, with two's complement for the bit width.",
    fields: [{ k: "t", label: "Number", type: "text", def: "-45" }, num("base", "Its base", "10"), num("bits", "Bit width", "8")], build: (v) => ({ text: v.t, base: Number(v.base), bits: Number(v.bits) }) },
  { id: "add", label: "Signed add and overflow", endpoint: "/api/cpe/signed-add", note: "Add or subtract two signed numbers in a fixed width and see when the result overflows.",
    fields: [num("a", "A", "100"), num("b", "B", "50"), num("bits", "Bit width", "8"), { k: "sub", label: "Operation", type: "select", options: ["add", "subtract"], def: "add" }], build: (v) => ({ a: Number(v.a), b: Number(v.b), bits: Number(v.bits), subtract: v.sub === "subtract" }) },
  { id: "float", label: "Floating point", endpoint: "/api/cpe/float", note: "See how a decimal is stored as sign, exponent and mantissa, and how far the stored value is from what you typed.",
    fields: [num("x", "Value", "0.1"), { k: "d", label: "Format", type: "select", options: ["float32", "float64"], def: "float32" }], build: (v) => ({ value: Number(v.x), double: v.d === "float64" }) },
];
const LOGIC: ToolSpec[] = [
  { id: "table", label: "Truth table and simplify", endpoint: "/api/cpe/logic", note: "Use AND, OR, NOT, XOR, NAND, NOR, brackets, or A' for NOT A, AB for A AND B, + for OR. Up to 6 variables.",
    fields: [{ k: "t", label: "Expression", type: "text", def: "A AND B OR A AND NOT B" }], build: (v) => ({ text: v.t }) },
  { id: "eq", label: "Are two expressions equal?", endpoint: "/api/cpe/equivalent", note: "Compares every input row. Try De Morgan: NOT(A AND B) and NOT A OR NOT B.",
    fields: [{ k: "a", label: "First", type: "text", def: "NOT(A AND B)" }, { k: "b", label: "Second", type: "text", def: "NOT A OR NOT B" }], build: (v) => ({ a: v.a, b: v.b }) },
];
const CIRCUITS: ToolSpec[] = [
  { id: "ohm", label: "Ohm's law and power", endpoint: "/api/cpe/ohm", note: "Fill in exactly two of the four boxes; the other two are worked out.",
    fields: [{ k: "v", label: "Voltage (V)", type: "text", def: "12" }, { k: "i", label: "Current (A)", type: "text", def: "" }, { k: "r", label: "Resistance (ohm)", type: "text", def: "4" }, { k: "p", label: "Power (W)", type: "text", def: "" }], build: (v) => ({ v: n(v.v), i: n(v.i), r: n(v.r), p: n(v.p) }) },
  { id: "res", label: "Series and parallel", endpoint: "/api/cpe/resistors", note: "Comma-separated resistor values in ohms.",
    fields: [{ k: "k", label: "Connection", type: "select", options: ["series", "parallel"], def: "parallel" }, { k: "v", label: "Values", type: "text", def: "100, 220, 470" }], build: (v) => ({ kind: v.k, values: v.v.split(",").map((x: string) => Number(x.trim())) }) },
  { id: "div", label: "Voltage divider", endpoint: "/api/cpe/divider", note: "Optionally add a load to see how it pulls the output down.",
    fields: [num("vin", "Input (V)", "12"), num("r1", "R1 (ohm)", "10000"), num("r2", "R2 (ohm)", "10000"), { k: "l", label: "Load (ohm, optional)", type: "text", def: "" }], build: (v) => ({ vin: Number(v.vin), r1: Number(v.r1), r2: Number(v.r2), load: n(v.l) }) },
  { id: "led", label: "LED resistor", endpoint: "/api/cpe/led", note: "Gives the exact value, the next standard E12 value and the resistor's power.",
    fields: [num("s", "Supply (V)", "12"), num("f", "LED forward voltage (V)", "2"), num("i", "Current (mA)", "20")], build: (v) => ({ supply: Number(v.s), forward: Number(v.f), current_ma: Number(v.i) }) },
  { id: "rc", label: "RC charge time", endpoint: "/api/cpe/rc", note: "Time constant of a resistor and capacitor.",
    fields: [num("r", "Resistance (ohm)", "10000"), num("c", "Capacitance (uF)", "100"), num("v", "Voltage (V)", "12")], build: (v) => ({ r: Number(v.r), c_uf: Number(v.c), v: Number(v.v) }) },
  { id: "col", label: "Resistor colour code", endpoint: "/api/cpe/color-code", note: "Four-band resistor: two digit bands, a multiplier and a tolerance.",
    fields: [{ k: "a", label: "Band 1", type: "text", def: "yellow" }, { k: "b", label: "Band 2", type: "text", def: "violet" }, { k: "m", label: "Multiplier", type: "text", def: "red" }, { k: "t", label: "Tolerance", type: "text", def: "gold" }], build: (v) => ({ b1: v.a, b2: v.b, mult: v.m, tol: v.t }) },
];
const ARCH: ToolSpec[] = [
  { id: "cache", label: "Cache address split", endpoint: "/api/cpe/cache", note: "Sizes must be powers of two. Ways of 1 is direct-mapped.",
    fields: [num("a", "Address bits", "32"), num("c", "Cache size (bytes)", "32768"), num("b", "Block size (bytes)", "64"), num("w", "Ways", "4")], build: (v) => ({ address_bits: Number(v.a), cache_bytes: Number(v.c), block_bytes: Number(v.b), ways: Number(v.w) }) },
  { id: "amat", label: "Average memory access time", endpoint: "/api/cpe/amat", note: "Hit time and miss penalty in the same unit (cycles or ns).",
    fields: [num("h", "Hit time", "1"), num("m", "Miss rate (%)", "5"), num("p", "Miss penalty", "100")], build: (v) => ({ hit_time: Number(v.h), miss_rate_pct: Number(v.m), miss_penalty: Number(v.p) }) },
  { id: "cpu", label: "CPU time", endpoint: "/api/cpe/cpu-time", note: "Time = instructions x CPI / clock rate.",
    fields: [num("n", "Instructions", "1000000000"), num("c", "CPI", "1.5"), num("g", "Clock (GHz)", "3")], build: (v) => ({ instructions: Number(v.n), cpi: Number(v.c), clock_ghz: Number(v.g) }) },
  { id: "amd", label: "Amdahl's law", endpoint: "/api/cpe/amdahl", note: "How much the whole improves when only part of it does.",
    fields: [num("p", "Share improved (%)", "90"), num("s", "Speedup of that part", "10")], build: (v) => ({ parallel_pct: Number(v.p), speedup_part: Number(v.s) }) },
  { id: "pipe", label: "Pipeline speedup", endpoint: "/api/cpe/pipeline", note: "Ideal pipeline plus stall cycles from hazards.",
    fields: [num("k", "Stages", "5"), num("n", "Instructions", "100"), num("s", "Stall cycles", "10")], build: (v) => ({ stages: Number(v.k), instructions: Number(v.n), stall_cycles: Number(v.s) }) },
  { id: "raid", label: "RAID capacity", endpoint: "/api/cpe/raid", note: "Levels 0, 1, 5, 6 and 10. RAID is not a backup.",
    fields: [num("l", "Level", "5"), num("d", "Disks", "4"), num("s", "Disk size (TB)", "4")], build: (v) => ({ level: Number(v.l), disks: Number(v.d), size_tb: Number(v.s) }) },
];
const WIRING: ToolSpec[] = [
  { id: "wire", label: "Wire, drop and fuse", endpoint: "/api/cpe/wire", note: "Finds the thinnest wire that carries the load within the allowed voltage drop, and a fuse that protects that wire. The ratings are rule-of-thumb values; use the wire maker's table.",
    fields: [num("a", "Load (A)", "10"), num("l", "One-way length (m)", "3"), num("v", "Supply (V)", "12"), num("d", "Allowed drop (%)", "3"), { k: "r", label: "Return path", type: "select", options: ["wire back to battery", "through the chassis"], def: "wire back to battery" }],
    build: (v) => ({ load_a: Number(v.a), length_m: Number(v.l), volts: Number(v.v), max_drop_pct: Number(v.d), round_trip: v.r.startsWith("wire") }) },
  { id: "harness", label: "Harness checker", endpoint: "/api/cpe/harness", note: "One line per circuit: circuit | load A | one-way length m | wire mm2 | fuse A (optional). Flags thin wire, high drop, and a fuse bigger than the wire.",
    fields: [{ k: "t", label: "Circuits", type: "area", rows: 7 }], build: (v) => ({ text: v.t }), sample: (s) => ({ t: s.auto.sample_harness }) },
  { id: "can", label: "CAN bus load", endpoint: "/api/cpe/can-load", note: "JSON list of messages. Worst-case bit stuffing; classic CAN only.",
    fields: [num("b", "Bit rate (kbit/s)", "500"), { k: "f", label: "Messages (JSON)", type: "area", rows: 7 }], build: (v) => ({ bitrate_kbps: Number(v.b), frames: JSON.parse(v.f) }), sample: (s) => ({ b: "500", f: JSON.stringify(s.auto.sample_can, null, 1) }) },
  { id: "term", label: "CAN termination check", endpoint: "/api/cpe/can-termination", note: "Power the car down, then measure between CAN-H and CAN-L at the connector.",
    fields: [num("m", "Measured resistance (ohm)", "60")], build: (v) => ({ measured_ohm: Number(v.m) }) },
];
const EV: ToolSpec[] = [
  { id: "acch", label: "AC charge time", endpoint: "/api/cpe/ev-charge", note: "Single or three phase, limited by the wall box or the car's on-board charger. Efficiency is a rule of thumb.",
    fields: [num("cap", "Battery (kWh)", "60"), num("s", "Start (%)", "20"), num("t", "Target (%)", "80"), num("v", "Voltage (V)", "230"), num("a", "Current (A)", "32"), num("p", "Phases (1 or 3)", "1"), num("o", "On-board charger (kW)", "11")],
    build: (v) => ({ capacity_kwh: Number(v.cap), start_pct: Number(v.s), target_pct: Number(v.t), source: "ac", volts: Number(v.v), amps: Number(v.a), phases: Number(v.p), onboard_kw: Number(v.o) }) },
  { id: "dcch", label: "DC fast charge time", endpoint: "/api/cpe/ev-charge", note: "Uses the lower of the station and the car, and a simple slow-down above a set level. Real charge curves depend on temperature and the battery.",
    fields: [num("cap", "Battery (kWh)", "75"), num("s", "Start (%)", "10"), num("t", "Target (%)", "80"), num("st", "Station (kW)", "150"), num("vm", "Vehicle maximum (kW)", "120"), num("ta", "Slow down after (%)", "80"), num("tf", "Power after that (fraction)", "0.4")],
    build: (v) => ({ capacity_kwh: Number(v.cap), start_pct: Number(v.s), target_pct: Number(v.t), source: "dc", station_kw: Number(v.st), vehicle_max_kw: Number(v.vm), taper_after_pct: Number(v.ta), taper_factor: Number(v.tf) }) },
  { id: "pack", label: "Battery pack layout", endpoint: "/api/cpe/ev-pack", note: "Series adds voltage, parallel adds capacity.",
    fields: [num("s", "Cells in series", "96"), num("p", "Cells in parallel", "3"), num("v", "Cell voltage (V)", "3.7"), num("ah", "Cell capacity (Ah)", "5")], build: (v) => ({ series: Number(v.s), parallel: Number(v.p), cell_v: Number(v.v), cell_ah: Number(v.ah) }) },
  { id: "pre", label: "Pre-charge circuit", endpoint: "/api/cpe/precharge", note: "Why a resistor charges the inverter's capacitors before the main contactor closes.",
    fields: [num("v", "Bus voltage (V)", "400"), num("c", "Capacitance (uF)", "1000"), num("r", "Resistor (ohm)", "100")], build: (v) => ({ bus_v: Number(v.v), cap_uf: Number(v.c), resistor_ohm: Number(v.r) }) },
  { id: "iso", label: "Insulation check", endpoint: "/api/cpe/isolation", note: "Compare a measured isolation resistance with the usual per-volt limits. Measuring it needs training and the right meter.",
    fields: [num("v", "Bus voltage (V)", "400"), num("k", "Measured (kohm)", "150")], build: (v) => ({ bus_v: Number(v.v), measured_kohm: Number(v.k) }) },
];
const area = (k: string, label: string, def = "", rows = 6) => ({ k, label, type: "area" as const, def, rows });
const SIM: ToolSpec[] = [
  { id: "logic", label: "Logic circuit", endpoint: "/api/cpesim/logic", note: "Write a netlist: INPUT lines, then NAME = GATE(a, b), and NAME = DFF(d) for a flip-flop. Give each input a row of 0 and 1 values to see the waveform.",
    fields: [area("n", "Netlist", "INPUT A B\nS = XOR(A, B)\nC = AND(A, B)", 8), area("s", "Inputs per step", "A: 0 0 1 1\nB: 0 1 0 1", 4), num("c", "Steps", "4")], build: (v) => ({ netlist: v.n, stimulus: v.s, cycles: Number(v.c) }),
    sample: (s) => ({ n: s.logic_samples.adder.netlist, s: s.logic_samples.adder.stimulus, c: "8" }) },
  { id: "cpu", label: "Tiny CPU", endpoint: "/api/cpesim/cpu", note: "A four-register teaching CPU with 64 bytes of memory. Step through the run, see the flags, and count the hazards a pipeline would meet.",
    fields: [area("p", "Program", "LDI R0, 0\nLDI R1, 5\nLOOP: ADD R0, R1\nDEC R1\nJNZ LOOP\nST [0], R0\nHALT", 10), num("m", "Step limit", "500")], build: (v) => ({ source: v.p, max_steps: Number(v.m) }),
    sample: (s) => ({ p: s.cpu_samples.multiply }) },
  { id: "dc", label: "Circuit solver", endpoint: "/api/cpesim/circuit-dc", note: "One part per line: V1 a 0 12 (source), R1 a b 10k, I1 a 0 2m, C1 a b 1u. Node 0 is ground. Values take k, m, u, n, p, M.",
    fields: [area("n", "Netlist", "V1 in 0 12\nR1 in out 10k\nR2 out 0 10k", 7)], build: (v) => ({ net: v.n }), sample: (s) => ({ n: s.net_samples.bridge }) },
  { id: "tran", label: "Charge and discharge", endpoint: "/api/cpesim/circuit-transient", note: "Steps a circuit with capacitors or inductors through time.",
    fields: [area("n", "Netlist", "V1 in 0 5\nR1 in out 1k\nC1 out 0 1u", 6), num("t", "End time (s)", "0.005"), num("st", "Steps", "100")], build: (v) => ({ net: v.n, t_end: Number(v.t), steps: Number(v.st) }), sample: (s) => ({ n: s.net_samples.rc }) },
  { id: "cache", label: "Cache trace", endpoint: "/api/cpesim/cache-trace", note: "Feed a list of byte addresses and see each hit or miss, and why a miss happened (first touch, capacity or conflict).",
    fields: [area("t", "Addresses", "0 64 128 192 0 64 128 192 256 0 4 68", 3), num("cb", "Cache bytes", "256"), num("bb", "Block bytes", "16"), num("w", "Ways", "2"), { k: "p", label: "Replacement", type: "select", options: ["LRU", "FIFO"], def: "LRU" }],
    build: (v) => ({ trace: v.t, cache_bytes: Number(v.cb), block_bytes: Number(v.bb), ways: Number(v.w), policy: v.p }), sample: (s) => ({ t: s.cache_sample }) },
];
const VEH: ToolSpec[] = [
  { id: "can", label: "CAN signals", endpoint: "/api/cpesim/can-signals", note: "Decode named signals from a CAN frame. One line per signal: name | start bit | length | intel or motorola | signed or unsigned | factor | offset | unit.",
    fields: [{ k: "d", label: "Frame bytes (hex)", type: "text", def: "1A 2C 00 64 00 00 7F FF" }, area("s", "Signals", "Engine speed | 0 | 16 | intel | unsigned | 0.25 | 0 | rpm", 5)], build: (v) => ({ data: v.d, signals: v.s }),
    sample: (s) => ({ d: s.vehicle.can_sample.data, s: s.vehicle.can_sample.signals }) },
  { id: "j1939", label: "J1939 message", endpoint: "/api/cpesim/j1939", note: "Split a 29-bit heavy-vehicle ID into priority, PGN and source, and decode known messages.",
    fields: [{ k: "i", label: "29-bit ID (hex)", type: "text", def: "0CF00400" }, { k: "d", label: "Data (hex)", type: "text", def: "00 00 00 A0 0F 00 00 00" }], build: (v) => ({ can_id: v.i, data: v.d }) },
  { id: "dtc", label: "Trouble code", endpoint: "/api/cpesim/dtc", note: "Reads the structure of a code and gives the generic meaning. A code is a symptom, not a part number.",
    fields: [{ k: "c", label: "Code", type: "text", def: "P0301" }], build: (v) => ({ code: v.c }) },
  { id: "pid", label: "OBD-II reading", endpoint: "/api/cpesim/obd-pid", note: "Turn the data bytes of a mode 01 reply into a value.",
    fields: [{ k: "p", label: "PID (hex)", type: "text", def: "0C" }, { k: "d", label: "Data bytes (hex)", type: "text", def: "1A F8" }], build: (v) => ({ pid: v.p, data: v.d }) },
  { id: "isotp", label: "Diagnostic frames", endpoint: "/api/cpesim/isotp", note: "One 8-byte frame per line. Reassembles multi-frame messages and names UDS services and error codes.",
    fields: [area("f", "Frames", "03 22 F1 90\n10 14 62 F1 90 57 41 55\n21 5A 5A 5A 38 54 38 42\n22 41 30 32 31 38 37 33", 6)], build: (v) => ({ frames: v.f }), sample: (s) => ({ f: s.vehicle.isotp_sample }) },
  { id: "cpd", label: "Charge pilot duty", endpoint: "/api/cpesim/cp-duty", note: "The duty cycle of the 1 kHz pilot signal tells the car how many amps it may draw.",
    fields: [num("x", "Duty (%)", "53")], build: (v) => ({ value: Number(v.x) }) },
  { id: "cps", label: "Charge pilot voltage", endpoint: "/api/cpesim/cp-state", note: "The pilot voltage tells both sides if a car is plugged in, ready, or needs ventilation.",
    fields: [num("x", "High-level voltage (V)", "5.8")], build: (v) => ({ value: Number(v.x) }) },
  { id: "ppr", label: "Plug proximity", endpoint: "/api/cpesim/pp-resistor", note: "The resistor in the charging plug tells the car the cable's current rating.",
    fields: [num("x", "Resistance (ohm)", "220")], build: (v) => ({ value: Number(v.x) }) },
];
const GROUPS: Record<string, { tools: ToolSpec[]; title: string; note: string }> = {
  numbers: { tools: NUMBERS, title: "Number systems", note: "Bits, signed numbers and floating point." },
  logic: { tools: LOGIC, title: "Boolean logic", note: "Truth tables and simplification." },
  circuits: { tools: CIRCUITS, title: "DC circuits", note: "Ohm's law and the parts you will use most. Build the circuit and measure it; a calculator is not a breadboard." },
  arch: { tools: ARCH, title: "Computer architecture", note: "Caches, performance and storage." },
  wiring: { tools: WIRING, title: "Vehicle wiring and buses", note: "12 V wiring and vehicle networks. The vehicle's own service manual always wins." },
  sim: { tools: SIM, title: "Simulators", note: "Run a small logic circuit, a teaching CPU, a circuit and a cache on your own input. These are classroom models, not full simulators." },
  veh: { tools: VEH, title: "Vehicle message decoders", note: "Decode CAN, J1939, OBD-II, diagnostic and charging-signal data. Check the maker's own definitions before you rely on a result." },
  ev: { tools: EV, title: "EV charging and high voltage", note: "Education only. High-voltage work is for trained people with the right equipment." },
};
const TABS = [{ id: "numbers", label: "Numbers" }, { id: "logic", label: "Logic" }, { id: "circuits", label: "Circuits" }, { id: "arch", label: "Architecture" }, { id: "wiring", label: "Vehicle wiring" }, { id: "ev", label: "EV" }, { id: "sim", label: "Simulators" }, { id: "veh", label: "Vehicle decoders" }, { id: "systems", label: "Systems reference" }];

function Group({ g, samples }: { g: { tools: ToolSpec[]; title: string; note: string }; samples: R | null }) {
  const [id, setId] = useState(g.tools[0].id);
  const spec = g.tools.find((t) => t.id === id) ?? g.tools[0];
  return (
    <Section title={g.title} note={g.note}>
      <Tabs tabs={g.tools.map((t) => ({ id: t.id, label: t.label }))} value={spec.id} onChange={setId} label={g.title} />
      <ToolView key={spec.id} spec={spec} samples={samples} />
    </Section>
  );
}

function Systems({ data }: { data: R | null }) {
  const [open, setOpen] = useState("zonal");
  if (!data) return null;
  const s = data.auto.systems.find((x: R) => x.id === open) ?? data.auto.systems[0];
  return (
    <Section title="Vehicle systems reference" note="What each system does, what to check, and the safety limits. Taken from the wiring diagrams; the mistakes in those diagrams are listed below.">
      <Tabs tabs={data.auto.systems.map((x: R) => ({ id: x.id, label: x.name }))} value={s.id} onChange={setOpen} label="Vehicle systems" />
      <div className="mt-3 space-y-2 text-sm">
        <p>{s.what}</p>
        <p><b>Parts:</b> {s.parts.join(", ")}.</p>
        <p><b>Why it matters:</b> {s.why}</p>
        <p><b>Check:</b> {s.check}</p>
        <p className="rounded border border-line bg-panel2 p-2"><b>Safety:</b> {s.caution}</p>
      </div>
      <details className="mt-3 text-sm"><summary className="cursor-pointer">Vehicle buses compared</summary>
        <ul className="list-disc pl-5">{data.auto.buses.map((b: R) => <li key={b.bus}><b>{b.bus}</b>: {b.speed}; {b.wires}. {b.use}. {b.note}</li>)}</ul></details>
      <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the diagrams and the course deck</summary>
        <ul className="list-disc pl-5">{[...data.auto.slips, ...data.lab.slips].map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
      <details className="mt-3 text-sm"><summary className="cursor-pointer">What is not built</summary>
        <ul className="list-disc pl-5">{[...data.lab.not_built, ...data.auto.not_built].map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></details>
    </Section>
  );
}

export function CpePanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  const [data, setData] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/cpe/reference").then(setData).catch(() => setData(null)); }, []);
  const [sim, setSim] = useState<R | null>(null);
  useEffect(() => { getJson<R>("/api/cpesim/reference").then(setSim).catch(() => setSim(null)); }, []);
  const g = GROUPS[tab];
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Practice calculators that show their working. They check your arithmetic; they do not replace building a circuit, using a meter, or reading a vehicle&apos;s service manual. Work on airbags, immobilizers and high-voltage systems is for trained people.
      </p>
      <Tabs tabs={TABS} value={tab} onChange={onTab} label="Computer engineering tools" />
      {g ? <Group key={tab} g={g} samples={tab === "sim" || tab === "veh" ? sim : data} /> : <Systems data={data} />}
    </div>
  );
}
