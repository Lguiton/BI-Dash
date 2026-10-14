"""Vehicle data decoders: CAN signals (DBC style), J1939 identifiers, OBD-II codes and PIDs, ISO-TP messages, and EV charging pilot signals.

These read data you paste (frames from a logger, a code from a scan tool). They never connect to a vehicle. Meanings follow the public
SAE J1939, J1772, ISO 15765 and ISO 14229 conventions; manufacturer-specific codes need the maker's information.
"""
from __future__ import annotations

import re

from app.services.cpe_lab import CpeError


def _hex_bytes(text: str, name="Data", max_len=64) -> list[int]:
    t = re.sub(r"0x|[\s,:-]", "", (text or "").lower())
    if not t or len(t) % 2 or not re.fullmatch(r"[0-9a-f]+", t):
        raise CpeError(f"{name} must be pairs of hex digits, for example 11 22 33 44.")
    b = [int(t[i:i + 2], 16) for i in range(0, len(t), 2)]
    if len(b) > max_len:
        raise CpeError(f"{name} is too long (at most {max_len} bytes).")
    return b


def _bits(data: list[int], start: int, length: int, motorola: bool) -> int:
    total = len(data) * 8
    if length < 1 or length > 64:
        raise CpeError("Signal length must be 1 to 64 bits.")
    if motorola:
        pos, val = start, 0
        for _ in range(length):
            if pos < 0 or pos >= total:
                raise CpeError("A signal runs past the end of the data.")
            byte, bit = divmod(pos, 8)
            val = (val << 1) | ((data[byte] >> bit) & 1)
            pos = pos + 15 if pos % 8 == 0 else pos - 1
        return val
    if start < 0 or start + length > total:
        raise CpeError("A signal runs past the end of the data.")
    big = int.from_bytes(bytes(data), "little")
    return (big >> start) & ((1 << length) - 1)


def can_signals(data_hex: str, signals: str) -> dict:
    """Signal lines: name | start bit | length | intel or motorola | signed or unsigned | factor | offset | unit."""
    data = _hex_bytes(data_hex, "Data", 64)
    out = []
    for ln in (signals or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        p = [x.strip() for x in ln.split("|")]
        if len(p) < 7:
            raise CpeError(f"Line '{ln}': use name | start bit | length | intel/motorola | signed/unsigned | factor | offset | unit.")
        try:
            st, ln_bits, fac, off = int(p[1]), int(p[2]), float(p[5]), float(p[6])
        except ValueError:
            raise CpeError(f"Line '{ln}': start, length, factor and offset must be numbers.")
        if p[3].lower() not in ("intel", "motorola") or p[4].lower() not in ("signed", "unsigned"):
            raise CpeError(f"Line '{ln}': use intel or motorola, and signed or unsigned.")
        raw = _bits(data, st, ln_bits, p[3].lower() == "motorola")
        if p[4].lower() == "signed" and raw >> (ln_bits - 1):
            raw -= 1 << ln_bits
        out.append({"name": p[0], "raw": raw, "value": float(f"{raw * fac + off:.8g}"), "unit": p[7] if len(p) > 7 else "", "formula": f"{raw} x {fac:g} + {off:g}"})
    if not out:
        raise CpeError("Define at least one signal.")
    return {"data": " ".join(f"{b:02X}" for b in data), "signals": out,
            "lesson": "A CAN frame is just bytes. A signal definition says which bits, how to read them (byte order and sign), and how to scale: value = raw x factor + offset."}


CAN_SAMPLE = {"data": "1A 2C 00 64 00 00 7F FF", "signals": "Engine speed | 0 | 16 | intel | unsigned | 0.25 | 0 | rpm\nCoolant temp | 16 | 8 | intel | unsigned | 1 | -40 | C\nThrottle | 24 | 8 | intel | unsigned | 0.4 | 0 | %\nTorque | 55 | 16 | motorola | signed | 0.1 | 0 | Nm"}

_PGN = {61444: ("EEC1", "Electronic engine controller 1"), 65262: ("ET1", "Engine temperature 1"), 65265: ("CCVS", "Cruise control and vehicle speed"), 65266: ("LFE", "Fuel economy"),
        65263: ("EFL/P1", "Engine fluid level and pressure"), 65269: ("AMB", "Ambient conditions"), 65271: ("VEP1", "Vehicle electrical power"), 60416: ("TP.CM", "Transport protocol, connection management"),
        60160: ("TP.DT", "Transport protocol, data transfer"), 59904: ("Request", "Request for a PGN"), 65226: ("DM1", "Active diagnostic trouble codes")}


def j1939(can_id_hex: str, data_hex: str = "") -> dict:
    t = re.sub(r"0x|\s", "", (can_id_hex or "").lower())
    if not re.fullmatch(r"[0-9a-f]{1,8}", t):
        raise CpeError("The CAN ID must be up to 8 hex digits (29-bit identifier).")
    i = int(t, 16)
    if i >= 1 << 29:
        raise CpeError("A J1939 identifier is 29 bits (at most 1FFFFFFF).")
    prio, edp, dp, pf, ps, sa = (i >> 26) & 7, (i >> 25) & 1, (i >> 24) & 1, (i >> 16) & 0xFF, (i >> 8) & 0xFF, i & 0xFF
    pdu1 = pf < 240
    pgn = (edp << 17) | (dp << 16) | (pf << 8) | (0 if pdu1 else ps)
    nm, desc = _PGN.get(pgn, (None, None))
    res = {"id": f"{i:08X}", "priority": prio, "pgn": pgn, "pgn_hex": f"{pgn:04X}", "format": "PDU1 (addressed to one device)" if pdu1 else "PDU2 (broadcast)", "source_address": sa,
           "destination_address": ps if pdu1 else None, "name": nm, "description": desc, "signals": []}
    if data_hex.strip():
        d = _hex_bytes(data_hex, "Data", 8)
        d += [0xFF] * (8 - len(d))
        if pgn == 61444:
            raw = d[3] | (d[4] << 8)
            res["signals"].append({"name": "Engine speed (SPN 190)", "value": None if raw >= 0xFB00 else raw * 0.125, "unit": "rpm"})
        elif pgn == 65262:
            res["signals"].append({"name": "Engine coolant temperature (SPN 110)", "value": None if d[0] >= 0xFB else d[0] - 40, "unit": "C"})
        elif pgn == 65265:
            raw = d[1] | (d[2] << 8)
            res["signals"].append({"name": "Wheel-based vehicle speed (SPN 84)", "value": None if raw >= 0xFB00 else raw / 256, "unit": "km/h"})
    res["lesson"] = "A J1939 29-bit ID packs priority, the parameter group number (what the message is), and the sender's address. Values of FF mean 'not available'."
    return res


J1939_SAMPLE = {"id": "0CF00400", "data": "00 00 00 A0 0F 00 00 00"}

_SYS = {"P": "Powertrain (engine, transmission)", "B": "Body", "C": "Chassis", "U": "Network and communication"}
_PSUB = {"0": "Fuel and air metering and auxiliary emission controls", "1": "Fuel and air metering", "2": "Fuel and air metering (injector circuit)", "3": "Ignition system or misfire",
         "4": "Auxiliary emission controls", "5": "Vehicle speed, idle control and auxiliary inputs", "6": "Computer and output circuits", "7": "Transmission", "8": "Transmission", "9": "Transmission",
         "A": "Hybrid propulsion", "B": "Hybrid propulsion", "C": "Hybrid propulsion"}
_DTC = {"P0100": "Mass air flow circuit", "P0101": "Mass air flow circuit range or performance", "P0102": "Mass air flow circuit low input", "P0103": "Mass air flow circuit high input",
        "P0110": "Intake air temperature circuit", "P0115": "Engine coolant temperature circuit", "P0120": "Throttle position sensor A circuit", "P0130": "O2 sensor circuit (bank 1, sensor 1)",
        "P0171": "System too lean (bank 1)", "P0172": "System too rich (bank 1)", "P0174": "System too lean (bank 2)", "P0175": "System too rich (bank 2)", "P0300": "Random or multiple cylinder misfire",
        "P0301": "Cylinder 1 misfire", "P0302": "Cylinder 2 misfire", "P0303": "Cylinder 3 misfire", "P0304": "Cylinder 4 misfire", "P0325": "Knock sensor 1 circuit (bank 1)",
        "P0335": "Crankshaft position sensor A circuit", "P0340": "Camshaft position sensor A circuit (bank 1)", "P0401": "Exhaust gas recirculation flow insufficient", "P0420": "Catalyst efficiency below threshold (bank 1)",
        "P0430": "Catalyst efficiency below threshold (bank 2)", "P0440": "Evaporative emission system", "P0442": "Evaporative emission system, small leak", "P0455": "Evaporative emission system, large leak",
        "P0500": "Vehicle speed sensor", "P0505": "Idle control system", "P0562": "System voltage low", "P0563": "System voltage high", "P0600": "Serial communication link",
        "P0700": "Transmission control system", "U0100": "Lost communication with engine control module", "U0121": "Lost communication with anti-lock brake module", "U0140": "Lost communication with body control module"}


def dtc(code: str) -> dict:
    c = (code or "").strip().upper()
    if not re.fullmatch(r"[PBCU][0-3][0-9A-F]{3}", c):
        raise CpeError("A fault code is a letter P, B, C or U, then four more characters, for example P0301.")
    d2 = c[1]
    if c[0] == "P":
        scope = {"0": "Generic (set by SAE, same on every make)", "1": "Manufacturer-specific", "2": "Generic (set by SAE)", "3": "Mixed: P30xx to P33xx manufacturer-specific, P34xx to P39xx generic"}[d2]
    else:
        scope = "Generic (set by SAE)" if d2 == "0" else "Manufacturer-specific"
    known = _DTC.get(c)
    return {"code": c, "system": _SYS[c[0]], "scope": scope, "subsystem": _PSUB.get(c[2]) if c[0] == "P" else None, "meaning": known,
            "advice": ("A code names a circuit or condition, not a part to replace. Confirm with live data, a visual check and the maker's test steps before replacing anything." if known else
                       "Not in this app's short table. Look it up in the maker's service information: the code alone does not say which part failed."),
            "lesson": "First letter: system. Second digit: generic or manufacturer. Third: subsystem. The last two: the specific fault."}


_PID = {"04": ("Calculated engine load", lambda a: a[0] * 100 / 255, "%", 1), "05": ("Engine coolant temperature", lambda a: a[0] - 40, "C", 1), "0C": ("Engine speed", lambda a: (256 * a[0] + a[1]) / 4, "rpm", 2),
        "0D": ("Vehicle speed", lambda a: a[0], "km/h", 1), "0F": ("Intake air temperature", lambda a: a[0] - 40, "C", 1), "10": ("Mass air flow", lambda a: (256 * a[0] + a[1]) / 100, "g/s", 2),
        "11": ("Throttle position", lambda a: a[0] * 100 / 255, "%", 1), "2F": ("Fuel tank level", lambda a: a[0] * 100 / 255, "%", 1), "5C": ("Engine oil temperature", lambda a: a[0] - 40, "C", 1)}


def obd_pid(pid: str, data_hex: str) -> dict:
    p = (pid or "").strip().upper().replace("0X", "")
    if p not in _PID:
        raise CpeError("Known PIDs: " + ", ".join(f"{k} ({v[0]})" for k, v in _PID.items()))
    name, fn, unit, n = _PID[p]
    d = _hex_bytes(data_hex, "Data bytes", 8)
    if len(d) < n:
        raise CpeError(f"PID {p} needs {n} data byte(s).")
    return {"pid": p, "name": name, "value": float(f"{fn(d):.6g}"), "unit": unit, "bytes": " ".join(f"{b:02X}" for b in d[:n]),
            "lesson": "A mode 01 reply carries data bytes A, B... and each PID has its own formula. Engine speed is (256 x A + B) / 4."}


_UDS = {0x10: "Diagnostic session control", 0x11: "ECU reset", 0x14: "Clear diagnostic information", 0x19: "Read DTC information", 0x22: "Read data by identifier", 0x27: "Security access",
        0x28: "Communication control", 0x2E: "Write data by identifier", 0x31: "Routine control", 0x34: "Request download", 0x3E: "Tester present", 0x85: "Control DTC setting"}
_NRC = {0x10: "General reject", 0x11: "Service not supported", 0x12: "Sub-function not supported", 0x13: "Incorrect message length or format", 0x22: "Conditions not correct", 0x31: "Request out of range",
        0x33: "Security access denied", 0x35: "Invalid key", 0x36: "Exceeded number of attempts", 0x37: "Required time delay not expired", 0x78: "Response pending"}


def isotp(frames: str) -> dict:
    """One CAN frame per line (hex bytes). Joins ISO 15765-2 frames into messages and names the UDS service."""
    msgs, cur, i = [], None, 0
    for ln in (frames or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        b = _hex_bytes(ln, "A frame", 8)
        t, n = b[0] >> 4, b[0] & 15
        if t == 0:
            if n == 0 or n > len(b) - 1:
                raise CpeError(f"Frame '{ln}': single-frame length {n} does not match the data.")
            msgs.append(b[1:1 + n])
        elif t == 1:
            if len(b) < 2:
                raise CpeError(f"Frame '{ln}' is too short for a first frame.")
            cur = {"len": ((b[0] & 15) << 8) | b[1], "data": b[2:], "seq": 1}
        elif t == 2:
            if cur is None:
                raise CpeError(f"Frame '{ln}': consecutive frame with no first frame before it.")
            if n != cur["seq"] % 16:
                raise CpeError(f"Frame '{ln}': expected sequence {cur['seq'] % 16}, got {n}. A frame is missing or out of order.")
            cur["data"] += b[1:]
            cur["seq"] += 1
            if len(cur["data"]) >= cur["len"]:
                msgs.append(cur["data"][:cur["len"]])
                cur = None
        elif t == 3:
            continue  # flow control
        else:
            raise CpeError(f"Frame '{ln}': unknown ISO-TP type {t}.")
        i += 1
    if cur is not None:
        raise CpeError(f"The multi-frame message is incomplete: {len(cur['data'])} of {cur['len']} bytes received.")
    if not msgs:
        raise CpeError("No complete message found.")
    out = []
    for m in msgs:
        sid = m[0]
        if sid == 0x7F and len(m) >= 3:
            what = f"Negative response to service {m[1]:02X} ({_UDS.get(m[1], 'unknown')}): {_NRC.get(m[2], 'code ' + format(m[2], '02X'))}"
        elif sid >= 0x40 and (sid - 0x40) in _UDS:
            what = f"Positive response to {_UDS[sid - 0x40]}"
        elif sid in _UDS:
            what = f"Request: {_UDS[sid]}"
        else:
            what = "Service not in this short table"
        out.append({"hex": " ".join(f"{x:02X}" for x in m), "length": len(m), "meaning": what})
    return {"messages": out, "lesson": "A CAN frame holds 8 bytes, so longer diagnostic messages are split: a first frame with the length, then numbered consecutive frames. A positive reply adds 0x40 to the service number."}


ISOTP_SAMPLE = "03 22 F1 90\n10 14 62 F1 90 57 41 55\n21 5A 5A 5A 38 54 38 42\n22 41 30 32 31 38 37 33\n03 7F 22 31"


def cp_duty(duty_pct: float) -> dict:
    if isinstance(duty_pct, bool) or not isinstance(duty_pct, (int, float)) or not 0 <= duty_pct <= 100:
        raise CpeError("Duty must be 0 to 100.")
    d = float(duty_pct)
    if d < 3:
        return {"duty_pct": d, "amps": None, "meaning": "Not a valid charging signal (0 means the station is off or in error).", "lesson": "The station tells the car the most current it may draw with the duty cycle of a 1 kHz signal."}
    if d <= 7:
        return {"duty_pct": d, "amps": None, "meaning": "About 5%: the station asks the car to talk digitally (ISO 15118) to agree on charging.", "lesson": "The station tells the car the most current it may draw with the duty cycle of a 1 kHz signal."}
    if d < 10:
        return {"duty_pct": d, "amps": None, "meaning": "Between 7% and 10% is not defined: the car will not charge.", "lesson": "The station tells the car the most current it may draw with the duty cycle of a 1 kHz signal."}
    if d <= 85:
        a = d * 0.6
    elif d <= 96:
        a = (d - 64) * 2.5
    else:
        return {"duty_pct": d, "amps": None, "meaning": "Above 96% is not allowed: no charging.", "lesson": "The station tells the car the most current it may draw with the duty cycle of a 1 kHz signal."}
    return {"duty_pct": d, "amps": round(a, 1), "meaning": f"The station allows up to {a:.1f} A.", "rule": "10 to 85%: amps = duty x 0.6. Above 85 to 96%: amps = (duty - 64) x 2.5.",
            "lesson": "The station tells the car the most current it may draw with the duty cycle of a 1 kHz signal."}


def cp_state(volts: float) -> dict:
    if isinstance(volts, bool) or not isinstance(volts, (int, float)) or not -15 <= volts <= 15:
        raise CpeError("Voltage must be between -15 and 15.")
    v = float(volts)
    table = [(12, "A", "No vehicle connected"), (9, "B", "Vehicle connected, not ready to charge"), (6, "C", "Charging (vehicle ready)"), (3, "D", "Charging, ventilation required"), (0, "E", "Error: no power from the station"), (-12, "F", "Station fault or unavailable")]
    best = min(table, key=lambda t: abs(t[0] - v))
    tol = abs(best[0] - v)
    return {"volts": v, "state": best[1], "meaning": best[2], "close_to_nominal": tol <= 1.0,
            "note": "Nominal levels are +12, +9, +6, +3, 0 and -12 V (about 1 V tolerance). The high level of the signal is what the car and station read.",
            "lesson": "The control pilot voltage tells both sides what is happening: a resistor in the car pulls it from 12 V down to 9 V (connected) and 6 V (ready)."}


_PP = {1500: 13, 680: 20, 220: 32, 100: 63}


def pp_resistor(ohms: float) -> dict:
    if isinstance(ohms, bool) or not isinstance(ohms, (int, float)) or ohms <= 0:
        raise CpeError("Resistance must be above 0.")
    best = min(_PP, key=lambda r: abs(r - ohms))
    ok = abs(best - ohms) / best <= 0.1
    return {"measured_ohm": ohms, "nearest_standard_ohm": best, "cable_rating_a": _PP[best] if ok else None,
            "meaning": f"A cable rated for {_PP[best]} A." if ok else "Not a standard value: a worn pin or damaged cable can change it.",
            "lesson": "A resistor in the plug tells the car how much current the cable can carry (Type 2: 1.5 k = 13 A, 680 ohm = 20 A, 220 ohm = 32 A, 100 ohm = 63 A)."}


SLIPS = [
    "Vehicle decoders: a fault code points to a circuit or condition, not a part. Replacing the named sensor because of a code is a common and expensive mistake.",
    "Vehicle decoders: the fault-code table holds a few dozen generic codes only. Manufacturer-specific codes (second digit 1, or most B and C codes) mean different things on different makes.",
    "Vehicle decoders: the J1939 and PID formulas cover a handful of common signals. Real signal scaling for a given vehicle comes from its DBC or service documentation.",
]
NOT_BUILT = ["Connecting to a vehicle (OBD adapter, CAN interface) to read live data: it needs hardware and a driver on your computer.",
             "Writing to a vehicle, clearing codes or flashing: not built.",
             "Manufacturer-specific code tables and DBC files for particular vehicles."]


def reference() -> dict:
    return {"can_sample": CAN_SAMPLE, "j1939_sample": J1939_SAMPLE, "isotp_sample": ISOTP_SAMPLE, "slips": SLIPS, "not_built": NOT_BUILT, "pids": {k: v[0] for k, v in _PID.items()}}
