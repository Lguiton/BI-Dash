"""Vehicle electronics practice tools: 12 V wiring, vehicle buses, EV charging and high-voltage basics.

Built from twelve wiring and architecture diagrams (zonal architecture, dashboard harness, smart keyless entry, airbag SRS, 360-degree camera,
automotive Ethernet, EV high-voltage layout, AC and DC charging). These tools do arithmetic and explain systems. They are not a repair
manual: the vehicle's own service manual wiring diagram always wins, and values marked 'rule of thumb' are not standards.
"""
from __future__ import annotations

import math
import re

from app.services.cpe_lab import CpeError, _num

RHO = 0.0172  # ohm mm^2 / m, copper at 20 C
# mm^2: (nearest AWG, rough continuous amps in a bundle at under about 85 C ambient). Rule of thumb only: use the wire maker's table.
WIRE = {0.35: ("22", 4), 0.5: ("20", 6), 0.75: ("18", 9), 1.0: ("17", 12), 1.5: ("16", 16), 2.5: ("14", 22), 4.0: ("12", 30), 6.0: ("10", 38), 10.0: ("8", 52), 16.0: ("6", 70), 25.0: ("4", 95)}
FUSES = [1, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]


def wire(load_a: float, length_m: float, volts: float = 12.0, max_drop_pct: float = 3.0, round_trip: bool = True, continuous: bool = True) -> dict:
    i, l, v, dp = _num(load_a, "Load (A)", 0.01), _num(length_m, "Length (m)", 0.1), _num(volts, "Supply (V)", 5), _num(max_drop_pct, "Allowed drop (%)", 0.1, 20)
    path = l * (2 if round_trip else 1)
    ok = []
    for mm2, (awg, amps) in WIRE.items():
        r = RHO * path / mm2
        drop = i * r
        ok.append({"mm2": mm2, "awg_nearest": awg, "ampacity_rule_of_thumb": amps, "drop_v": round(drop, 3), "drop_pct": round(100 * drop / v, 2), "ok_current": i <= amps, "ok_drop": 100 * drop / v <= dp})
    good = [w for w in ok if w["ok_current"] and w["ok_drop"]]
    pick = good[0] if good else None
    need = i * (1.25 if continuous else 1.0)
    fuse = next((f for f in FUSES if f >= need), None)
    note = []
    if pick and fuse and fuse > pick["ampacity_rule_of_thumb"]:
        note.append(f"A {fuse} A fuse is above this wire's rated current ({pick['ampacity_rule_of_thumb']} A): choose the next thicker wire so the fuse protects it.")
    if not pick:
        note.append("No size in the table meets both limits: shorten the run, use a higher voltage, or split the load.")
    return {"recommended": pick, "fuse_a": fuse, "fuse_rule": "Fuse at about 125% of a continuous load, and never above the wire's rating: the fuse protects the wire, not the device.",
            "path_length_m": path, "all_sizes": ok, "notes": note, "power_lost_w": round(i * i * RHO * path / pick["mm2"], 2) if pick else None,
            "lesson": "Voltage drop is current times wire resistance, and the return path counts. A thin wire to a high-current load wastes power as heat and starves the load."}


def harness_check(text: str) -> dict:
    """Lines: circuit | load amps | one-way length m | wire mm2 | fuse A (optional)."""
    rows = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        p = [x.strip() for x in ln.split("|")]
        if len(p) < 4:
            raise CpeError(f"Line '{ln}': use circuit | load A | length m | wire mm2 | fuse A (optional).")
        try:
            a, m, w = float(p[1]), float(p[2]), float(p[3])
            f = float(p[4]) if len(p) > 4 and p[4] else None
        except ValueError:
            raise CpeError(f"Line '{ln}': load, length, wire and fuse must be numbers.")
        if w not in WIRE:
            raise CpeError(f"Line '{ln}': wire size {w:g} mm2 is not in the table ({', '.join(f'{x:g}' for x in WIRE)}).")
        rows.append((p[0], a, m, w, f))
    if not rows:
        raise CpeError("Give at least one circuit.")
    out = []
    for name, a, m, w, f in rows:
        drop = 100 * a * RHO * 2 * m / w / 12
        issues = []
        rate = WIRE[w][1]
        if a > rate:
            issues.append(f"Load {a:g} A is above the wire's rule-of-thumb rating {rate} A.")
        if drop > 3:
            issues.append(f"Voltage drop {drop:.1f}% is above 3%.")
        if f is None:
            issues.append("No fuse listed.")
        else:
            if f > rate:
                issues.append(f"Fuse {f:g} A is bigger than the wire can carry ({rate} A): the wire can burn before the fuse blows.")
            if f < a * 1.0:
                issues.append(f"Fuse {f:g} A is smaller than the load {a:g} A: it will blow in normal use.")
        out.append({"circuit": name, "drop_pct": round(drop, 2), "status": "fix" if issues else "ok", "issues": issues})
    return {"circuits": out, "problems": sum(1 for o in out if o["status"] == "fix"), "lesson": "Check three things per circuit: wire carries the load, drop is small, and the fuse is no larger than the wire."}


def can_load(bitrate_kbps: float, frames: list) -> dict:
    br = _num(bitrate_kbps, "Bit rate (kbit/s)", 10, 1000) * 1000
    if not isinstance(frames, list) or not frames or len(frames) > 200:
        raise CpeError("Give 1 to 200 message lines.")
    tot, rows = 0.0, []
    for f in frames:
        name = str(f.get("name", "msg"))[:30]
        dlc = _num(f.get("bytes"), "Data bytes", 0, 8, True)
        per = _num(f.get("per_second"), "Messages per second", 0.0)
        ext = bool(f.get("extended"))
        base = (67 if ext else 47) + 8 * dlc
        stuff = (((54 if ext else 34) + 8 * dlc - 1) // 4)
        bits = base + stuff
        load = per * bits / br
        tot += load
        rows.append({"name": name, "bits_worst_case": bits, "bits_no_stuffing": base, "load_pct": round(100 * load, 2)})
    pct = 100 * tot
    verdict = ("Light load." if pct < 30 else "Busy: fine for periodic traffic, but little room for bursts." if pct < 50 else "Heavy: latency will rise; split the bus or raise the rate." if pct < 70 else "Overloaded by the usual rule of thumb (70%): messages will be delayed or lost.")
    return {"bus_load_pct": round(pct, 2), "rows": rows, "verdict": verdict, "assumption": "Classic CAN, worst-case bit stuffing. CAN FD uses a faster data phase and is not modelled.",
            "lesson": "Bus load is bits per second used divided by bits per second available. Leave headroom, because faults and bursts add traffic."}


def can_termination(measured_ohm: float) -> dict:
    m = _num(measured_ohm, "Measured resistance", 0.0)
    if m < 10:
        v = "About 0 ohm: CAN-H and CAN-L are shorted together or to each other through a fault."
    elif 55 <= m <= 65:
        v = "About 60 ohm: two 120 ohm terminators in parallel, as expected."
    elif 110 <= m <= 130:
        v = "About 120 ohm: one terminator is missing, or a wire to one end is open."
    elif 35 <= m <= 45:
        v = "About 40 ohm: a third terminator or a node with its own terminator is on the bus."
    elif m > 1000:
        v = "Open circuit: no terminators are connected or the wires are broken. Measure with the bus powered down."
    else:
        v = "Not a typical value: look for a short, a wrong terminator or an extra termination in a node."
    return {"verdict": v, "how": "Switch the vehicle off and wait, then measure between CAN-H and CAN-L at the connector. Expect about 60 ohm.", "lesson": "The two end nodes each carry 120 ohm. They sit in parallel, so a healthy bus reads 60 ohm."}


BUSES = [
    {"bus": "LIN", "speed": "up to 19.2 kbit/s", "wires": "1 wire plus ground", "use": "Cheap sensors and actuators: window switches, mirrors, seat motors", "note": "One master, up to 15 or so slaves."},
    {"bus": "CAN (classic)", "speed": "up to 1 Mbit/s (500 kbit/s common)", "wires": "twisted pair, CAN-H and CAN-L", "use": "Powertrain, brakes, body", "note": "Terminated with 120 ohm at both ends; broadcast messages with priority by ID."},
    {"bus": "CAN FD", "speed": "data phase typically 2 to 8 Mbit/s", "wires": "twisted pair", "use": "Newer ECUs needing more data per frame (64 bytes)", "note": "Same wiring idea as CAN, different controllers."},
    {"bus": "FlexRay", "speed": "10 Mbit/s", "wires": "twisted pair (often two channels)", "use": "Time-critical chassis systems in some vehicles", "note": "Time-triggered; largely replaced by Ethernet and CAN FD."},
    {"bus": "100BASE-T1 / 1000BASE-T1", "speed": "100 Mbit/s and 1 Gbit/s", "wires": "one twisted pair", "use": "Cameras, radar, infotainment, domain and zone links", "note": "Point-to-point through switches. Not the same cable as office Ethernet."},
    {"bus": "10BASE-T1S", "speed": "10 Mbit/s", "wires": "one pair, multidrop possible", "use": "Replacing CAN or LIN on sensor links", "note": "Newer; check support in your target vehicle."},
]

SYSTEMS = [
    {"id": "zonal", "name": "Zonal architecture", "diagram": "Zonal vehicle architecture: complete wiring and ECU layout",
     "what": "Instead of one ECU for each function wired all the way across the car, a few zone controllers sit near each corner. Each zone controller wires up nearby sensors and actuators and talks to a central computer over a fast backbone (Ethernet).",
     "parts": ["Front, left, right and rear zone controllers", "Central gateway (CAN and Ethernet)", "Body control module", "Engine, transmission and brake ECUs"],
     "why": "Shorter, lighter harnesses, fewer connectors, and features that can be added by software.",
     "check": "Which functions live in which zone? Where does a wire from a door switch go, and over what bus does the signal leave the zone?",
     "caution": "The diagram still shows separate engine, transmission and brake ECUs, so it is a hybrid of zonal and traditional design."},
    {"id": "dash", "name": "Dashboard harness", "diagram": "Smart dashboard wiring harness and the next-generation harness",
     "what": "The dashboard harness joins the cluster, infotainment, HVAC, airbag, steering switches, junction blocks and the body control module. A clock spring carries signals through the rotating steering wheel.",
     "parts": ["Instrument cluster", "Infotainment head unit", "Clock spring", "Driver and passenger junction blocks (fuses and relays)", "Body control module"],
     "why": "Most customer complaints (no lights, no start, warning lamps) end at a connector, a fuse or a ground in this harness.",
     "check": "Unplug and look for green corrosion, bent pins or a pin pushed back. Check fuse, then power, then ground, then signal.",
     "caution": "Airbag connectors are yellow. Never probe or test them with a meter or test lamp."},
    {"id": "eth", "name": "Automotive Ethernet network", "diagram": "Automotive Ethernet wiring network",
     "what": "Cameras, radar, lidar and displays send a lot of data, so they connect by single-pair Ethernet (100BASE-T1 or 1000BASE-T1) through zone switches to a central gateway. CAN and LIN remain for slower devices.",
     "parts": ["Central gateway", "Zone Ethernet switches", "Front and surround cameras, radar, lidar", "Telematics unit", "MATEnet and H-MTD connectors"],
     "why": "Video and radar streams need megabits per second, which CAN cannot carry.",
     "check": "A camera that drops out: check the connector and cable first, then the switch port and power.",
     "caution": "Single-pair automotive Ethernet is not the 8-wire cable used in offices, and cable length and quality limits are strict."},
    {"id": "keyless", "name": "Smart keyless entry and immobilizer", "diagram": "Smart keyless entry system",
     "what": "The car sends a low-frequency challenge from antennas in the door handles and cabin. The key answers by radio. The body control module checks the answer and the immobilizer transponder before it allows entry or starting.",
     "parts": ["Smart key", "Low-frequency antennas (door handles, cabin, boot)", "Radio receiver", "Body control module", "Door modules", "Push-start switch", "Steering lock and immobilizer"],
     "why": "It replaces a mechanical key with an electronic challenge and response.",
     "check": "A key that works at one door but not another points to that door's antenna or wiring.",
     "caution": "Learning how it works is fine. This app does not teach how to program keys, bypass an immobilizer, or relay a signal: that work belongs to the vehicle maker's dealer or a licensed locksmith with proof of ownership."},
    {"id": "srs", "name": "Airbag (SRS) system", "diagram": "Airbag SRS system: complete wiring",
     "what": "Impact sensors tell the airbag control unit that a crash is happening. The unit decides which airbags and belt pretensioners to fire, using seat-belt and occupant sensors to adjust. A clock spring feeds the driver airbag in the steering wheel.",
     "parts": ["Airbag control unit", "Front and side impact sensors", "Driver, passenger and curtain airbags", "Belt pretensioners and buckle switches", "Occupant classification sensor", "Clock spring", "Warning lamp"],
     "why": "A fault disables the whole system and lights the warning lamp, so it must be fixed, not ignored.",
     "check": "Read fault codes with the right scan tool, check connectors for corrosion, and look for a damaged clock spring.",
     "caution": "Airbags can fire and injure you. Disconnect the battery and wait the manufacturer's stated time, never probe a yellow connector, and never apply power to a deployment circuit. This work is for trained technicians."},
    {"id": "avm", "name": "360-degree camera system", "diagram": "360 camera system: four cameras, ECU and display",
     "what": "Four wide-angle cameras (front, rear, and one in each mirror) feed an around-view ECU. It corrects the lens distortion, stitches the images into a top-down view and shows it on the head unit. Steering angle and speed adjust the guide lines.",
     "parts": ["Front, rear and two side cameras", "Around-view monitor ECU", "Display or head unit", "Steering angle sensor", "Reverse lamp signal and vehicle speed"],
     "why": "Seams and bad calibration after a bumper or mirror repair are the usual faults.",
     "check": "After replacing a camera or mirror the system usually needs a calibration with floor targets.",
     "caution": "The four 180-degree views overlap; they do not add up to a 720-degree picture. Never rely on the camera alone when manoeuvring."},
    {"id": "ev_hv", "name": "EV high-voltage architecture", "diagram": "EV high-voltage architecture",
     "what": "The traction battery feeds an inverter that drives the motor, a DC-DC converter that charges the 12 V battery, a heater, and the charging ports through a high-voltage distribution unit. An interlock loop and contactors switch the high voltage off if anything is open.",
     "parts": ["Traction battery pack", "Inverter and motor", "On-board charger", "DC-DC converter (HV to 12 V)", "HV distribution unit", "HV coolant heater", "HV interlock", "12 V battery"],
     "why": "The 12 V system is still needed to wake and control the high-voltage system.",
     "check": "A dead 12 V battery is the common reason an EV will not wake, even with a full traction battery.",
     "caution": "Above 60 V DC is treated as high voltage in vehicle standards and can kill. Orange cables mean stop: only trained and equipped people may work on them."},
    {"id": "charge", "name": "AC and DC charging", "diagram": "EV charging system wiring and DC fast charging architecture",
     "what": "With AC charging, the wall box only provides power and a safety signal; the car's on-board charger converts it to DC. With DC fast charging, the station does the conversion and sends DC straight to the battery, talking to the car to set the current. Control pilot (CP) and proximity pilot (PP) tell the car what the cable can carry and that the plug is in.",
     "parts": ["EVSE or DC charging station", "Inlet (Type 1, Type 2, CCS, CHAdeMO)", "Control pilot and proximity pilot", "On-board charger", "Battery management system", "Contactors and pre-charge"],
     "why": "The car, cable and station negotiate before any high power flows, which is why a worn pilot pin stops charging.",
     "check": "If charging will not start: check the plug seats, the cable, a lock fault, then the station's error code.",
     "caution": "Do not modify or bypass the safety signals, and never charge from a damaged inlet or cable."},
]

SLIPS = [
    "Wiring diagrams (all twelve): wire colours are not a universal code. Ethernet is blue in the zonal diagram, purple in the dashboard diagram and teal in the Ethernet diagram. CAN-high is orange, green or brown depending on the sheet. Real colours are set by each manufacturer. Always use the vehicle's own wiring diagram.",
    "Zonal vehicle diagram: the cabin door module is labelled 'Doar Control Module' twice, and the same door parts are drawn under both 'Front Door' and 'Cabin' zones, so one set looks like two. It also still lists separate engine, transmission and brake ECUs, so it shows a mix of traditional and zonal design.",
    "EV AC and DC charging diagram: the DC side is titled 'CHAdeMO / CCS' but only a CCS inlet is drawn, and its pin list shows 'CAN'. CHAdeMO uses CAN; CCS talks over power-line communication on the control pilot line. The two are different inlets and different protocols.",
    "EV AC and DC charging diagram: the AC side is labelled 'Level 1 / Level 2', which are North American terms, but draws a Type 2 inlet with L1, L2, L3, N and PE. North America uses a Type 1 (J1772) inlet with single-phase L1 and L2. The standards are mixed.",
    "DC fast charging diagram: the cable colour key lists 'Neutral (Blue)' twice, one with a purple swatch, and uses 'Control Signal (Purple)' as well, so two different signals share one colour. The colour key also disagrees with the in-car diagrams, which show high-voltage negative in orange.",
    "EV high-voltage diagram: the 'HV junction box', 'HV distribution unit (HVDU)' and 'high-voltage distribution unit' are drawn as separate parts, but they are names for the same job. The legend gives HV+ and HV- almost the same orange, so you cannot tell them apart by colour.",
    "Smart keyless diagram: the antenna drawn in each door handle is labelled both 'LF' (low frequency, sends the challenge) and 'RF' (radio frequency, receives the answer). The radio receiver for the key is normally one unit in the body, not an antenna in each handle. The wiring key uses yellow for both ignition power and illumination, and blue for both CAN-low and sensor signals.",
    "Dashboard harness diagram: the 'Steering Column ECU (SAS / ESC)' label mixes the steering angle sensor (SAS) with electronic stability control (ESC), which is a brake system controller, not a steering column unit.",
    "360 camera diagram: the coverage graphic shows four views of 180 degrees each, which add to 720 degrees. They overlap; stitching depends on that overlap and on calibration, which the diagram does not mention.",
    "Airbag diagram: it shows no warning about handling. It also leaves out the backup energy store inside the control unit that can fire the airbag for a short time after the battery is disconnected, which is why a wait time is needed.",
    "Networking devices poster: 'switch' and 'hub' are drawn with the same box and the hub is presented as a normal choice; hubs are obsolete. A home 'router' is normally router, switch, access point, firewall and DHCP server in one box, and the poster does not say so.",
]
NOT_BUILT = ["Diagnosing a real vehicle: reading fault codes, scoping a CAN signal, or measuring a harness needs a scan tool, a meter and the service manual.",
             "Key programming, immobilizer bypass, relay or signal capture, and work on airbag or high-voltage circuits. These are safety and security-sensitive and are not built or taught here beyond how the systems work.",
             "Vehicle-specific wiring diagrams and fuse tables: they belong to each maker's service information."]


def charge(capacity_kwh: float, start_pct: float, target_pct: float, source: str, volts: float = 230, amps: float = 32, phases: int = 1, station_kw: float = 50, vehicle_max_kw: float = 100, onboard_kw: float = 11, taper_after_pct: float = 80, taper_factor: float = 0.4) -> dict:
    cap = _num(capacity_kwh, "Battery capacity (kWh)", 1, 400)
    s, t = _num(start_pct, "Start (%)", 0, 100), _num(target_pct, "Target (%)", 0, 100)
    if t <= s:
        raise CpeError("The target must be above the start.")
    if source not in ("ac", "dc"):
        raise CpeError("Source must be ac or dc.")
    energy = cap * (t - s) / 100
    if source == "ac":
        v, a, ph = _num(volts, "Voltage", 100, 480), _num(amps, "Current (A)", 1, 200), _num(phases, "Phases", 1, 3, True)
        if ph == 2:
            raise CpeError("Phases must be 1 or 3.")
        evse = (math.sqrt(3) * v * a if ph == 3 else v * a) / 1000
        power = min(evse, _num(onboard_kw, "On-board charger (kW)", 1, 50))
        eff = 0.9
        hours = energy / (power * eff)
        limit = "the car's on-board charger" if onboard_kw < evse else "the wall box"
        return {"energy_added_kwh": round(energy, 2), "evse_kw": round(evse, 2), "usable_kw": round(power, 2), "limited_by": limit, "assumed_efficiency": eff, "hours": round(hours, 2), "from_the_grid_kwh": round(energy / eff, 2),
                "working": "Single phase P = V x I; three phase P = sqrt(3) x V(line) x I. Time = energy / (power x efficiency). Efficiency is a rule of thumb.",
                "lesson": "The slowest of the wall box, cable and on-board charger sets the speed."}
    p = min(_num(station_kw, "Station (kW)", 1, 1000), _num(vehicle_max_kw, "Vehicle maximum (kW)", 1, 1000))
    ta, tf = _num(taper_after_pct, "Taper after (%)", 10, 100), _num(taper_factor, "Taper factor", 0.05, 1)
    fast = max(0.0, min(t, ta) - s)
    slow = max(0.0, t - max(s, ta))
    e_fast, e_slow = cap * fast / 100, cap * slow / 100
    eff = 0.95
    h = e_fast / (p * eff) + e_slow / (p * tf * eff)
    return {"energy_added_kwh": round(energy, 2), "used_kw": p, "limited_by": "the station" if station_kw < vehicle_max_kw else "the vehicle", "minutes": round(h * 60, 1), "assumed_efficiency": eff,
            "assumed_taper": f"Above {ta:g}% the power falls to {tf * 100:g}% of maximum (a simple stand-in for a real charge curve).",
            "lesson": "DC charging slows down as the battery fills, so 10 to 80% is much faster than 80 to 100%. A real charge curve depends on temperature and battery."}


def pack(series: int, parallel: int, cell_v: float = 3.7, cell_ah: float = 5.0, cell_kg: float | None = None) -> dict:
    s, p = _num(series, "Cells in series", 1, 400, True), _num(parallel, "Cells in parallel", 1, 400, True)
    v, ah = _num(cell_v, "Cell voltage", 1.0, 5.0), _num(cell_ah, "Cell capacity (Ah)", 0.1)
    pv, pah = s * v, p * ah
    out = {"pack_voltage_v": round(pv, 1), "pack_ah": round(pah, 1), "pack_kwh": round(pv * pah / 1000, 2), "cells": s * p, "series_groups": s, "parallel_per_group": p,
           "voltage_class": "High voltage (above 60 V DC): trained staff only." if pv > 60 else "Low voltage.",
           "lesson": "Series adds voltage, parallel adds capacity. Energy is voltage times amp-hours."}
    if cell_kg:
        out["cell_mass_kg"] = round(s * p * _num(cell_kg, "Cell mass (kg)", 0.001), 1)
    return out


def precharge(bus_v: float, cap_uf: float, resistor_ohm: float) -> dict:
    v, c, r = _num(bus_v, "Bus voltage", 1), _num(cap_uf, "Capacitance (uF)", 1) * 1e-6, _num(resistor_ohm, "Resistor (ohm)", 1)
    tau = r * c
    return {"tau_ms": round(tau * 1000, 2), "time_to_95pct_ms": round(3 * tau * 1000, 1), "peak_current_a": round(v / r, 2), "resistor_energy_j": round(0.5 * c * v * v, 1),
            "without_precharge_peak_note": "With no resistor, only the wire's tiny resistance limits the first rush of current, which can weld the contactor.",
            "lesson": "A pre-charge resistor charges the inverter's capacitors slowly before the main contactor closes. The resistor must absorb the stored energy (half C V squared) without overheating."}


def isolation(bus_v: float, measured_kohm: float) -> dict:
    v, r = _num(bus_v, "Bus voltage", 1), _num(measured_kohm, "Measured isolation (kohm)", 0.0)
    need_dc, need_ac = v * 100 / 1000, v * 500 / 1000
    status = "Fail (below the DC limit)" if r < need_dc else "Pass for DC only (below the AC limit)" if r < need_ac else "Pass"
    return {"minimum_dc_kohm": need_dc, "minimum_ac_kohm": need_ac, "measured_kohm": r, "status": status,
            "note": "100 ohm per volt for DC circuits and 500 ohm per volt for AC circuits are the limits usually quoted from the electric-vehicle safety standards. Check the current regulation and the maker's value.",
            "lesson": "Isolation resistance keeps the high-voltage system electrically separate from the chassis. If it falls, a person touching the car could complete a circuit."}


def systems() -> list[dict]:
    return SYSTEMS


def reference() -> dict:
    return {"systems": SYSTEMS, "buses": BUSES, "slips": SLIPS, "not_built": NOT_BUILT,
            "sample_harness": "Headlights | 10 | 3 | 1.0 | 15\nFuel pump | 8 | 4 | 0.5 | 20\nHorn | 7 | 2 | 1.5 | 10\nAux lights | 25 | 5 | 2.5 | 40\nRadio | 3 | 3 | 0.75 |",
            "sample_can": [{"name": "Engine speed", "bytes": 8, "per_second": 100}, {"name": "Wheel speeds", "bytes": 8, "per_second": 100}, {"name": "Steering angle", "bytes": 4, "per_second": 50}, {"name": "Body status", "bytes": 8, "per_second": 20}]}
