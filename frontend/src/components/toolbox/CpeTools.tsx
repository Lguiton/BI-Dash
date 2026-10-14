"use client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { postJson } from "@/lib/api";
import { Section, Tabs } from "@/components/panels/kit";
import { fetchText, HtmlFrame, Pick } from "./common";
import { FieldHowTo, Out, TA, TI, lines, cols, useRun } from "./fieldcommon";

const TABS = [{ id: "how", label: "How to do / fix" }, { id: "parts", label: "Parts check" }, { id: "battery", label: "Battery life" }, { id: "sketch", label: "Sketch writer" }, { id: "plan", label: "Test plan" }];
const BOARDS = [{ id: "uno", label: "Arduino Uno (5 V)" }, { id: "esp32", label: "ESP32 (3.3 V)" }, { id: "pico", label: "Raspberry Pi Pico (3.3 V)" }, { id: "rpi4", label: "Raspberry Pi 4 (3.3 V)" }];
const PARTS_HELP = "One part per line: name, quantity, unit cost, current in mA, pins used, voltage (3.3, 5 or both)";

export function CpeTools() {
  const [tab, setTab] = useState("how");
  return (
    <div className="grid gap-4">
      <Tabs label="Computer engineering tools" value={tab} onChange={setTab} tabs={TABS} />
      {tab === "how" && <FieldHowTo area="Computer engineering" agent="cpe" examples="e.g. board resets when the motor starts, battery dies too fast" />}
      {tab === "parts" && <Parts />}
      {tab === "battery" && <Battery />}
      {tab === "sketch" && <Sketch />}
      {tab === "plan" && <Plan />}
    </div>
  );
}

function Parts() {
  const [board, setBoard] = useState("esp32");
  const [txt, setTxt] = useState("DHT22 sensor, 1, 4, 2.5, 1, 3.3\nRelay module, 1, 3, 70, 1, 5");
  const [ma, setMa] = useState("");
  const r = useRun<Record<string, unknown>>();
  const parts = () => lines(txt).map((l) => { const c = cols(l); return { name: c[0], qty: Number(c[1] || 1), unit_cost: Number(c[2] || 0), current_ma: Number(c[3] || 0), pins: Number(c[4] || 0), voltage: c[5] || "3.3" }; });
  return (
    <Section title="Parts list checker" note="Adds up cost, pins and current, and warns about voltage mismatches and a supply that is too small. It is a paper check: confirm against each datasheet.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="grid gap-2">
        <Pick label="Board" value={board} onChange={setBoard} options={BOARDS} />
        <TA label="Parts" value={txt} onChange={setTxt} placeholder={PARTS_HELP} />
        <p className="text-xs text-muted">{PARTS_HELP}</p>
        <TI label="Supply limit in mA (optional)" value={ma} onChange={setMa} w="w-40" />
        <div><button className="btn" disabled={r.busy || !board} onClick={() => r.run(() => postJson("/api/fieldbox/cpe/parts", { board, parts: parts(), supply_ma: ma ? Number(ma) : null }), "Could not check the parts.")}>Check parts</button></div>
      </div>
      <Out data={r.res} hide={["parts", "board"]} />
    </Section>
  );
}

function Battery() {
  const [v, setV] = useState({ battery_mah: "2000", active_ma: "80", sleep_ma: "0.1", active_s: "5", period_s: "600" });
  const r = useRun<Record<string, unknown>>();
  const set = (k: keyof typeof v) => (x: string) => setV({ ...v, [k]: x });
  return (
    <Section title="Battery runtime estimator" note="Gives a range, not one number, because batteries lose capacity with cold and age.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="flex flex-wrap items-end gap-2">
        <TI label="Battery capacity (mAh)" value={v.battery_mah} onChange={set("battery_mah")} w="w-36" />
        <TI label="Awake current (mA)" value={v.active_ma} onChange={set("active_ma")} w="w-36" />
        <TI label="Sleep current (mA)" value={v.sleep_ma} onChange={set("sleep_ma")} w="w-36" />
        <TI label="Awake seconds per cycle" value={v.active_s} onChange={set("active_s")} w="w-36" />
        <TI label="Cycle length (seconds)" value={v.period_s} onChange={set("period_s")} w="w-36" />
        <button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/cpe/runtime", Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x)]))), "Could not estimate.")}>Estimate</button>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Sketch() {
  const [f, setF] = useState({ platform: "arduino", sensor: "dht22", pin: "4", interval_s: "10", output: "serial", url: "" });
  const r = useRun<Record<string, unknown>>();
  const set = (k: keyof typeof f) => (x: string) => setF({ ...f, [k]: x });
  return (
    <Section title="Sketch writer" note="Writes starter code as text for you to paste into the Arduino or Thonny editor. It never uploads anything to a board.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="flex flex-wrap items-end gap-2">
        <Pick label="Platform" value={f.platform} onChange={set("platform")} options={[{ id: "arduino", label: "Arduino / ESP32 (C++)" }, { id: "micropython", label: "MicroPython" }]} />
        <Pick label="Sensor" value={f.sensor} onChange={set("sensor")} options={[{ id: "dht22", label: "DHT22 temperature and humidity" }, { id: "analog", label: "Analog sensor" }, { id: "button", label: "Button" }, { id: "relay", label: "Relay or LED" }]} />
        <TI label="Pin number" value={f.pin} onChange={set("pin")} w="w-24" />
        <TI label="Seconds between readings" value={f.interval_s} onChange={set("interval_s")} w="w-36" />
        <Pick label="Output" value={f.output} onChange={set("output")} options={[{ id: "serial", label: "Serial monitor" }, { id: "wifi_post", label: "Send over Wi-Fi" }]} />
        {f.output === "wifi_post" && <TI label="Web address to send to" value={f.url} onChange={set("url")} w="w-64" placeholder="https://example.com/data" />}
        <button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/cpe/sketch", { ...f, pin: Number(f.pin), interval_s: Number(f.interval_s) }), "Could not write the sketch.")}>Write sketch</button>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Plan() {
  const [project, setProject] = useState("");
  const [parts, setParts] = useState("");
  const [ma, setMa] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="Test plan" note="A printable power-up and test checklist to hand over with the build.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <TI label="Project name" value={project} onChange={setProject} w="w-72" />
        <TA label="Parts (one per line)" value={parts} onChange={setParts} rows={4} />
        <TI label="Expected current draw (mA, optional)" value={ma} onChange={setMa} w="w-48" />
        <div><button className="btn" onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/cpe/testplan", { project, parts: lines(parts), expected_ma: Number(ma || 0) })); } catch (e) { setErr(e instanceof Error ? e.message : "Could not build the plan."); setHtml(null); } }}>Build test plan</button></div>
      </div>
      {html && <HtmlFrame html={html} name="test-plan.html" />}
    </Section>
  );
}
