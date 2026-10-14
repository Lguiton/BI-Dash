"""Computer engineering tools: parts list checker, sketch writer (text only), battery runtime estimator, and a printable test plan.

Everything is arithmetic you can check by hand, or text for you to copy. Nothing talks to hardware. Numbers are typical datasheet-style values: always confirm
against the datasheet of the exact part before you build."""
from __future__ import annotations

import html
import math
import re

E = html.escape
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")

BOARDS = {
    "uno": {"label": "Arduino Uno (5 V)", "logic_v": 5.0, "pins": 18, "pin_ma": 20, "supply_ma_3v3": 150, "supply_ma_5v": 500, "adc_bits": 10},
    "esp32": {"label": "ESP32 dev board (3.3 V logic)", "logic_v": 3.3, "pins": 24, "pin_ma": 12, "supply_ma_3v3": 500, "supply_ma_5v": 500, "adc_bits": 12},
    "pico": {"label": "Raspberry Pi Pico (3.3 V logic)", "logic_v": 3.3, "pins": 26, "pin_ma": 12, "supply_ma_3v3": 300, "supply_ma_5v": 300, "adc_bits": 12},
    "rpi4": {"label": "Raspberry Pi 4 (3.3 V GPIO)", "logic_v": 3.3, "pins": 26, "pin_ma": 16, "supply_ma_3v3": 500, "supply_ma_5v": 1200, "adc_bits": 0},
}


class CpeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _num(v, what, lo=0.0, hi=1e9) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise CpeError(f"{what} must be a number.") from None
    if not lo <= x <= hi:
        raise CpeError(f"{what} must be between {lo:g} and {hi:g}.")
    return x


# ------------------------------------------------------------------ parts list checker
def parts_check(board: str, parts: list[dict], supply_ma: float | None = None, supply_v: float = 5.0) -> dict:
    b = BOARDS.get(board)
    if not b:
        raise CpeError("board must be one of: " + ", ".join(BOARDS) + ".")
    if not isinstance(parts, list) or not parts:
        raise CpeError("Add at least one part.")
    sv = _num(supply_v, "Supply voltage", 1, 60)
    rows, cost, pins, ma5, ma33 = [], 0.0, 0, 0.0, 0.0
    findings: list[dict] = []
    for p in parts[:80]:
        nm = str(p.get("name") or "").strip()[:60]
        if not nm:
            raise CpeError("Every part needs a name.")
        qty = int(_num(p.get("qty", 1), "Quantity", 0, 10000))
        unit = _num(p.get("unit_cost", 0), f"Cost of {nm}", 0, 100000)
        ma = _num(p.get("current_ma", 0), f"Current of {nm}", 0, 100000)
        pu = int(_num(p.get("pins", 0), f"Pins for {nm}", 0, 60))
        v = str(p.get("voltage", "3.3"))
        if v not in ("3.3", "5", "both", "other"):
            raise CpeError(f"Voltage for {nm} must be 3.3, 5, both or other.")
        cost += qty * unit
        pins += qty * pu
        if v == "5":
            ma5 += qty * ma
        else:
            ma33 += qty * ma
        if v == "5" and b["logic_v"] < 4.5 and pu:
            findings.append({"severity": "high", "part": nm, "says": f"{nm} runs at 5 V but the {b['label']} pins are {b['logic_v']:g} V. Its signal wires need a level shifter or a voltage divider, or you can damage the board."})
        if v == "3.3" and b["logic_v"] > 4.5 and pu:
            findings.append({"severity": "medium", "part": nm, "says": f"{nm} is a 3.3 V part on a 5 V board. Check it tolerates 5 V signals, or add a level shifter."})
        if v == "other":
            findings.append({"severity": "medium", "part": nm, "says": f"{nm} needs its own supply. Share a common ground with the board and do not power it from a pin."})
        if ma > b["pin_ma"] and pu and ma < 1000 and p.get("powered_from_pin"):
            findings.append({"severity": "high", "part": nm, "says": f"{nm} draws about {ma:g} mA, more than one pin can give ({b['pin_ma']} mA). Drive it through a transistor or MOSFET from the supply rail."})
        rows.append({"name": nm, "qty": qty, "unit_cost": unit, "line_cost": round(qty * unit, 2), "current_ma": ma, "pins": pu, "voltage": v})
    total_ma = ma5 + ma33
    cap = float(supply_ma) if supply_ma not in (None, "") else float(b["supply_ma_5v"])
    if total_ma > cap * 0.8:
        findings.append({"severity": "high" if total_ma > cap else "medium", "part": "", "says": f"Total draw is about {total_ma:.0f} mA against a {cap:.0f} mA supply. Keep the load under 80% ({cap * 0.8:.0f} mA) so it does not brown out. Use a bigger supply or power the heavy parts separately."})
    if ma33 > b["supply_ma_3v3"] and b["logic_v"] < 4.5:
        findings.append({"severity": "medium", "part": "", "says": f"The 3.3 V parts draw about {ma33:.0f} mA, more than the board's 3.3 V regulator comfortably gives ({b['supply_ma_3v3']} mA). Use an external 3.3 V regulator."})
    if pins > b["pins"]:
        findings.append({"severity": "high", "part": "", "says": f"You need {pins} pins but the board has about {b['pins']} usable ones. Use an I2C expander or a bigger board."})
    elif pins > b["pins"] * 0.8:
        findings.append({"severity": "low", "part": "", "says": f"{pins} of about {b['pins']} pins used. Leave a few spare for later changes."})
    status = "problems" if any(f["severity"] == "high" for f in findings) else "check" if findings else "ok"
    return {"board": b["label"], "parts": rows, "total_cost": round(cost, 2), "pins_needed": pins, "pins_available": b["pins"], "total_current_ma": round(total_ma, 1), "supply_ma": cap, "supply_v": sv,
            "load_pct": round(100 * total_ma / cap, 1) if cap else None, "status": status, "findings": findings,
            "caution": "Typical values only. Confirm each part's voltage, current and pin limits in its datasheet. Cost is the sum you typed in; add shipping, spares and tax."}


# ------------------------------------------------------------------ battery runtime
def runtime(battery_mah: float, active_ma: float, sleep_ma: float, active_s: float, period_s: float) -> dict:
    cap = _num(battery_mah, "Battery capacity", 1, 1e7)
    a, s = _num(active_ma, "Active current", 0, 1e5), _num(sleep_ma, "Sleep current", 0, 1e5)
    ta, tp = _num(active_s, "Active seconds", 0, 1e6), _num(period_s, "Period seconds", 1, 1e7)
    if ta > tp:
        raise CpeError("Active time cannot be longer than the whole cycle.")
    avg = (a * ta + s * (tp - ta)) / tp
    if avg <= 0:
        raise CpeError("The average current is zero, so there is no runtime to estimate.")
    out = {}
    for name, derate in (("pessimistic", 0.6), ("typical", 0.75), ("optimistic", 0.9)):
        h = cap * derate / avg
        out[name] = {"hours": round(h, 1), "days": round(h / 24, 1)}
    return {"average_ma": round(avg, 3), "duty_pct": round(100 * ta / tp, 2), "runtime": out,
            "says": f"Average draw is {avg:.2f} mA, so expect about {out['typical']['days']} days (between {out['pessimistic']['days']} and {out['optimistic']['days']}).",
            "arithmetic": [f"Average = ({a:g} mA x {ta:g} s + {s:g} mA x {tp - ta:g} s) / {tp:g} s = {avg:.3f} mA", f"Usable capacity = {cap:g} mAh x 60% to 90% (batteries, cold and age lose capacity)", f"Hours = usable mAh / {avg:.3f} mA"],
            "caution": "Real runtime depends on temperature, battery age, regulator losses and radio bursts. Measure the real current with a meter before promising a battery life."}


# ------------------------------------------------------------------ sketch writer (text only)
SENSORS = {"dht22": "DHT22 temperature and humidity", "analog": "Analog sensor (e.g. soil moisture, light)", "button": "Button or digital input", "relay": "Relay or LED output"}
OUTPUTS = ("serial", "wifi_post")


def sketch(platform: str, sensor: str, pin: int, interval_s: int = 10, output: str = "serial", url: str = "") -> dict:
    if platform not in ("arduino", "micropython"):
        raise CpeError("platform must be arduino or micropython.")
    if sensor not in SENSORS:
        raise CpeError("sensor must be one of: " + ", ".join(SENSORS) + ".")
    pin = int(_num(pin, "Pin", 0, 60))
    iv = int(_num(interval_s, "Interval", 1, 86400))
    if output not in OUTPUTS:
        raise CpeError("output must be serial or wifi_post.")
    if output == "wifi_post":
        if not re.fullmatch(r"https?://[A-Za-z0-9._:/\-]{3,150}", url or ""):
            raise CpeError("Give the web address to send readings to, like https://example.com/readings.")
    if platform == "arduino":
        if sensor == "dht22":
            body, head = "float t = dht.readTemperature();\n  float h = dht.readHumidity();\n  if (isnan(t) || isnan(h)) { Serial.println(\"read failed\"); return; }\n  String line = String(t) + \",\" + String(h);", f"#include <DHT.h>\nDHT dht({pin}, DHT22);\n"
            setup = "dht.begin();"
        elif sensor == "analog":
            head, setup, body = "", f"pinMode({pin}, INPUT);", f"int raw = analogRead({pin});\n  String line = String(raw);"
        elif sensor == "button":
            head, setup, body = "", f"pinMode({pin}, INPUT_PULLUP);", f"int pressed = digitalRead({pin}) == LOW;\n  String line = String(pressed);"
        else:
            head, setup, body = "", f"pinMode({pin}, OUTPUT);", f"static bool on = false;\n  on = !on;\n  digitalWrite({pin}, on ? HIGH : LOW);\n  String line = String(on);"
        if output == "wifi_post":
            head = "#include <WiFi.h>\n#include <HTTPClient.h>\n" + head + 'const char* WIFI_NAME = "YOUR_WIFI_NAME";      // fill in\nconst char* WIFI_PASS = "YOUR_WIFI_PASSWORD";  // fill in; do not share this file with it filled in\n' + f'const char* URL = "{url}";\n'
            setup = 'WiFi.begin(WIFI_NAME, WIFI_PASS);\n  while (WiFi.status() != WL_CONNECTED) { delay(500); }\n  ' + setup
            send = 'HTTPClient http;\n  http.begin(URL);\n  http.addHeader("Content-Type", "text/plain");\n  http.POST(line);\n  http.end();'
        else:
            send = "Serial.println(line);"
            setup = "Serial.begin(115200);\n  " + setup
        code = f"{head}\nvoid setup() {{\n  {setup}\n}}\n\nvoid loop() {{\n  {body}\n  {send}\n  delay({iv * 1000});\n}}\n"
        lang = "cpp"
        libs = ["DHT sensor library (by Adafruit)"] if sensor == "dht22" else []
        if output == "wifi_post":
            libs.append("Needs an ESP32 board (WiFi.h). It will not compile for an Uno.")
    else:
        lines = ["import time", "from machine import Pin, ADC"]
        if sensor == "dht22":
            lines += ["import dht", f"d = dht.DHT22(Pin({pin}))"]
            read = "d.measure()\n    line = '%s,%s' % (d.temperature(), d.humidity())"
        elif sensor == "analog":
            lines += [f"a = ADC(Pin({pin}))"]
            read = "line = str(a.read_u16())"
        elif sensor == "button":
            lines += [f"b = Pin({pin}, Pin.IN, Pin.PULL_UP)"]
            read = "line = str(1 if b.value() == 0 else 0)"
        else:
            lines += [f"o = Pin({pin}, Pin.OUT)"]
            read = "o.value(not o.value())\n    line = str(o.value())"
        if output == "wifi_post":
            lines += ["import network, urequests", "w = network.WLAN(network.STA_IF); w.active(True)", "w.connect('YOUR_WIFI_NAME', 'YOUR_WIFI_PASSWORD')   # fill in; keep this file private once filled in",
                      "while not w.isconnected():\n    time.sleep(0.5)"]
            send = f"urequests.post('{url}', data=line).close()"
        else:
            send = "print(line)"
        code = "\n".join(lines) + f"\n\nwhile True:\n    {read}\n    {send}\n    time.sleep({iv})\n"
        lang, libs = "python", []
    return {"title": f"{SENSORS[sensor]} on pin {pin} ({platform})", "language": lang, "code": code,
            "explain": [f"Reads the {SENSORS[sensor].lower()} every {iv} seconds and {'prints it to the serial monitor' if output == 'serial' else 'sends it to your web address'}.", "Pin numbers differ between boards: check the one you typed is the pin you wired."],
            "libraries": libs, "run_first": ["Wire it with the power off, then check the wiring against the pin number.", "Start with serial output so you can see the readings before adding Wi-Fi."], "verify": "Open the serial monitor at 115200 and watch for a sensible reading every interval.",
            "caution": "Text only: nothing was uploaded to a board. Fill in Wi-Fi details yourself and never share the filled-in file."}


# ------------------------------------------------------------------ test plan
def test_plan(project: str, parts: list[str], expected_ma: float = 0, supply_v: float = 5.0) -> str:
    pr = str(project or "").strip()[:80]
    if not pr:
        raise CpeError("Name the project.")
    ps = [str(p).strip()[:60] for p in (parts or []) if str(p).strip()][:40]
    steps = [("Before power", [f"Check every part against the parts list: {', '.join(ps) or 'none listed'}", "Look for solder bridges, bent pins and reversed polarity (LEDs, electrolytic capacitors, diodes)", "With power OFF, use the meter's continuity beep: confirm supply and ground are NOT connected to each other",
                                "Confirm each module's voltage rating matches its supply rail"]),
             ("First power-up", [f"Use a current-limited supply or a meter in series. Expect about {expected_ma:g} mA at {supply_v:g} V" if expected_ma else "Measure the current draw and write it down", "If the current is more than double what you expect, or anything gets hot, switch off and look for a short",
                                 "Measure the voltage on each rail and write it down"]),
             ("Function tests", [f"Test {p} on its own, then with the others" for p in ps] or ["Test each part on its own"]) ,
             ("Soak test", ["Run it for at least 1 hour and look for resets, heat and drifting readings", "Move cables gently: intermittent faults show up as resets or odd readings"]),
             ("Sign-off", ["Record the final measurements next to the expected values", "Photograph the wiring for the handoff", "Write down the date, the firmware version and who tested it"])]
    body = "".join(f"<h2>{E(t)}</h2><ul>" + "".join(f"<li>&#9744; {E(x)}</li>" for x in items) + "</ul>" for t, items in steps)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Test plan: {E(pr)}</title><style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px}}h1{{font-size:22px}}h2{{font-size:15px;margin-top:18px;border-bottom:1px solid #ccc}}li{{margin:4px 0;list-style:none}}"
            f".sig{{margin-top:28px;border-top:1px solid #000;width:260px;padding-top:4px;font-size:12px}}</style></head><body><h1>Test plan: {E(pr)}</h1><p>Tested by ____________ Date ____________</p>{body}<div class='sig'>Signature</div></body></html>")
