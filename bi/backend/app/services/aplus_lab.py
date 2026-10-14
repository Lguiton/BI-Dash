"""CompTIA A+ study area (Core 1 220-1201 and Core 2 220-1202), inside the IT Specialist track.

What is here:
  * an objective map with domain weights, a self-rating per objective and a readiness score weighted the way the exam is
  * a practice question bank (graded here, the answers never leave the server) with results kept per domain
  * drills for ports and acronyms, a symptom finder, and reference tables
  * working tools for objectives that can be tools: IP address check, DHCP scope planner, SPF/DKIM/DMARC record checker,
    display calculator, power supply sizer, backup planner, script reviewer

Honest limits: it is a study aid written for this project, not the exam and not affiliated with CompTIA; the question bank is
small, so a high score here does not predict a pass; readiness is your own self-rating blended with practice results; hands-on
objectives (opening a laptop, crimping a cable, using a Mac) need real equipment; the tools use exact arithmetic or fixed rules
and print their assumptions; the script reviewer reads text and never runs it.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import math
import random
import re

from app.services import aplus_data as D
from app.services.aplus_acronyms import ACRONYMS
from app.services import state, workspaces


class AplusError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _n(v, name, lo, hi) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise AplusError(f"{name} must be a number from {lo:g} to {hi:g}.")
    return float(v)


def _ws() -> str:
    return workspaces.active()


# ------------------------------------------------------------------ objectives, progress, readiness
LEVELS = {0: "not started", 1: "learning", 2: "can do with notes", 3: "confident"}


def _kv(key: str) -> dict:
    try:
        d = json.loads(state.kv_get(f"{key}:{_ws()}", "{}") or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _qid(exam: str, number: str, i: int) -> str:
    return f"c{exam}-{number}-{i}"


def objectives() -> dict:
    prog, stats = _kv("aplus_progress"), _kv("aplus_stats")
    objs = D.objectives()
    qcount: dict[str, int] = {}
    for (ex, dom), qs in D.QUESTIONS.items():
        for q in qs:
            qcount[f"{ex}:{q['obj']}"] = qcount.get(f"{ex}:{q['obj']}", 0) + 1
    for o in objs:
        o["level"] = int(prog.get(o["id"], 0))
        o["questions"] = qcount.get(o["id"], 0)
    exams = []
    for ex, e in D.EXAMS.items():
        doms = []
        for dk, (label, weight) in e["domains"].items():
            mine = [o for o in objs if o["exam"] == ex and o["domain"] == dk]
            avg = sum(o["level"] for o in mine) / (3 * len(mine)) if mine else 0
            st = stats.get(f"{ex}:{dk}", [0, 0])
            acc = round(100 * st[0] / st[1]) if st[1] else None
            doms.append({"key": dk, "label": label, "weight": weight, "objectives": len(mine), "self_pct": round(100 * avg), "practice_pct": acc, "practice_answered": st[1]})
        ready = sum(d["weight"] * (0.6 * d["self_pct"] + 0.4 * (d["practice_pct"] if d["practice_pct"] is not None else d["self_pct"])) for d in doms) / 100
        exams.append({"exam": ex, **{k: e[k] for k in ("code", "name", "questions", "minutes", "pass")}, "domains": doms, "readiness_pct": round(ready),
                      "study_next": sorted(doms, key=lambda d: -d["weight"] * (100 - (0.6 * d["self_pct"] + 0.4 * (d["practice_pct"] if d["practice_pct"] is not None else d["self_pct"]))))[0]["label"]})
    return {"exams": exams, "objectives": objs, "levels": LEVELS, "method": D.METHOD,
            "note": "Readiness blends your self-rating (60%) with practice results (40%) and weights each domain as the exam does. It is a guide for what to study next, not a prediction.",
            "fine_print": "Both exams are 90 questions in 90 minutes with multiple-choice and performance-based items. Read the current objectives from CompTIA before you book: they are updated."}


def set_level(obj_id: str, level: int) -> dict:
    if obj_id not in {o["id"] for o in D.objectives()}:
        raise AplusError("No such objective.", 404)
    if isinstance(level, bool) or level not in LEVELS:
        raise AplusError("Level must be 0, 1, 2 or 3.")
    p = _kv("aplus_progress")
    p[obj_id] = int(level)
    state.kv_set(f"aplus_progress:{_ws()}", json.dumps(p))
    return {"saved": True}


# ------------------------------------------------------------------ practice questions
def _bank() -> list[dict]:
    out = []
    for (ex, dom), qs in D.QUESTIONS.items():
        for i, q in enumerate(qs):
            qid = _qid(ex, q["obj"], i)
            opts = [q["ok"], *q["bad"]]
            rnd = random.Random(int(hashlib.sha256(qid.encode()).hexdigest()[:8], 16))
            order = list(range(len(opts)))
            rnd.shuffle(order)
            out.append({"id": qid, "exam": ex, "domain": dom, "obj": f"{ex}:{q['obj']}", "q": q["q"], "options": [opts[k] for k in order], "answer": order.index(0), "why": q["why"]})
    return out


def quiz(exam: str = "", domain: str = "", n: int = 10, seed: int = 0) -> dict:
    n = int(_n(n, "Questions", 1, 60))
    pool = [q for q in _bank() if (not exam or q["exam"] == exam) and (not domain or q["domain"] == domain)]
    if not pool:
        raise AplusError("No questions for that choice.", 404)
    rnd = random.Random(seed or None)
    pick = rnd.sample(pool, min(n, len(pool)))
    return {"questions": [{"id": q["id"], "domain": q["domain"], "obj": q["obj"], "q": q["q"], "options": q["options"]} for q in pick], "available": len(pool),
            "note": "Questions are scenario-style but fewer than a real exam bank. Missed ones tell you where to read, not whether you will pass."}


def grade(answers: dict) -> dict:
    if not isinstance(answers, dict) or not answers or len(answers) > 100:
        raise AplusError("Send your answers as {question id: option number}.")
    bank = {q["id"]: q for q in _bank()}
    results, right = [], 0
    stats = _kv("aplus_stats")
    for qid, a in answers.items():
        q = bank.get(qid)
        if q is None:
            raise AplusError(f"Unknown question {qid}.", 404)
        if isinstance(a, bool) or not isinstance(a, int) or not 0 <= a < len(q["options"]):
            raise AplusError(f"Question {qid} needs one of the listed options.")
        ok = a == q["answer"]
        right += ok
        k = f"{q['exam']}:{q['domain']}"
        st = stats.setdefault(k, [0, 0])
        st[0] += ok
        st[1] += 1
        results.append({"id": qid, "ok": ok, "yours": a, "answer": q["answer"], "correct": q["options"][q["answer"]], "why": q["why"], "obj": q["obj"]})
    state.kv_set(f"aplus_stats:{_ws()}", json.dumps(stats))
    miss = sorted({r["obj"] for r in results if not r["ok"]})
    return {"right": right, "total": len(results), "pct": round(100 * right / len(results)), "results": results, "review": miss,
            "message": "Re-read these objectives: " + ", ".join(miss) if miss else "No misses. Try a different domain or more questions."}


def reset_results() -> dict:
    state.kv_set(f"aplus_stats:{_ws()}", "{}")
    return {"cleared": True}


# ------------------------------------------------------------------ drills
def cards(kind: str = "acronyms", n: int = 20, exam: str = "", seed: int = 0) -> dict:
    n = int(_n(n, "Cards", 1, 100))
    rnd = random.Random(seed or None)
    if kind == "acronyms":
        items = [(k, v[0]) for k, v in ACRONYMS.items() if not exam or exam in v[1]]
        pick = rnd.sample(items, min(n, len(items)))
        return {"kind": kind, "cards": [{"front": a, "back": b} for a, b in pick], "available": len(items),
                "note": "Some expansions in CompTIA's own lists were wrong and are corrected here (CAC, WISP, HDMI, VNC, RADIUS, SAML, SPICE, AAAA); XXS is XSS."}
    if kind == "ports":
        pick = rnd.sample(D.PORTS, min(n, len(D.PORTS)))
        return {"kind": kind, "cards": [{"front": f"Port {p[0]}", "back": f"{p[1]} ({p[2]}). {p[3]}"} for p in pick], "available": len(D.PORTS), "note": "Cover the answer and say it aloud before you flip."}
    raise AplusError("Kind must be acronyms or ports.")


def symptoms(query: str = "", exam: str = "") -> dict:
    q = (query or "").strip().lower()
    rows = []
    for ex, obj, sym, causes, checks in D.SYMPTOMS:
        if exam and ex != exam:
            continue
        hay = f"{sym} {' '.join(causes)} {' '.join(checks)}".lower()
        if q and not all(w in hay for w in q.split()):
            continue
        rows.append({"exam": ex, "obj": f"{ex}:{obj}", "symptom": sym, "causes": causes, "checks": checks})
    return {"results": rows, "method": D.METHOD, "note": D.SYMPTOM_NOTE}


def reference(topic: str = "") -> dict:
    if topic:
        if topic not in D.REFERENCE:
            raise AplusError("No such topic.", 404)
        return {"topic": topic, "sections": D.REFERENCE[topic]}
    return {"topics": list(D.REFERENCE), "ports": [{"port": p[0], "service": p[1], "transport": p[2], "note": p[3]} for p in D.PORTS], "sections": D.REFERENCE}


# ------------------------------------------------------------------ tools
def ip_check(address: str, mask: str = "", gateway: str = "") -> dict:
    """Classify an address the way an A+ technician reads it, and sanity-check mask and gateway if given."""
    try:
        ip = ipaddress.ip_address((address or "").strip())
    except ValueError:
        raise AplusError("That isn't an IP address.") from None
    notes, kind = [], "public"
    if ip.version == 4:
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            kind = "APIPA (self-assigned)"
            notes.append("The PC could not get an address from DHCP. Check the cable or Wi-Fi, the DHCP server and its scope, and run ipconfig /renew.")
        elif ip.is_loopback:
            kind = "loopback"
            notes.append("127.0.0.1 points at this computer. A successful ping proves only that the network stack works.")
        elif ip.is_private:
            kind = "private"
            notes.append("Private ranges are 10.0.0.0/8, 172.16.0.0 to 172.31.255.255 and 192.168.0.0/16. They don't route on the internet; NAT shares one public address.")
        elif ip.is_multicast:
            kind = "multicast"
        elif ip.is_reserved or ip.is_unspecified:
            kind = "reserved"
        else:
            notes.append("A public address, reachable from the internet unless a firewall blocks it.")
    else:
        if ip.is_loopback:
            kind = "loopback (::1)"
        elif ip.is_link_local:
            kind = "link-local (fe80::/10)"
            notes.append("Used on the local link only; every IPv6 interface has one.")
        elif ip in ipaddress.ip_network("fc00::/7"):
            kind = "unique local (private)"
        elif ip.is_multicast:
            kind = "multicast"
        else:
            notes.append("A global address.")
    out = {"address": str(ip), "version": ip.version, "kind": kind, "notes": notes}
    if mask or gateway:
        if ip.version != 4:
            raise AplusError("The mask and gateway check is for IPv4.")
        try:
            net = ipaddress.ip_network(f"{ip}/{mask.strip()}", strict=False)
        except ValueError:
            raise AplusError("That isn't a valid subnet mask (try 255.255.255.0 or /24).") from None
        out.update(network=str(net), usable_hosts=max(net.num_addresses - 2, 0), broadcast=str(net.broadcast_address))
        if gateway:
            try:
                gw = ipaddress.ip_address(gateway.strip())
            except ValueError:
                raise AplusError("The gateway isn't an IP address.") from None
            if gw not in net:
                out["notes"].append(f"The gateway {gw} is outside {net}. The PC can't reach it directly, so it can't leave its own network. Fix the gateway or the mask.")
            elif gw == net.network_address or gw == net.broadcast_address:
                out["notes"].append("The gateway is the network or broadcast address, which can't be a host.")
            else:
                out["notes"].append("The gateway is inside the same network, as it must be.")
        if ip == net.network_address or ip == net.broadcast_address:
            out["notes"].append("This address is the network or broadcast address and can't be given to a host.")
    return out


def dhcp_scope(network: str, start: str, end: str, exclusions: list[str] | None = None, reservations: int = 0, devices: int = 0, lease_hours: float = 24) -> dict:
    try:
        net = ipaddress.ip_network((network or "").strip(), strict=False)
        a, b = ipaddress.ip_address(start.strip()), ipaddress.ip_address(end.strip())
    except ValueError:
        raise AplusError("Enter a network such as 192.168.1.0/24 and start and end addresses.") from None
    if net.version != 4:
        raise AplusError("The scope planner is for IPv4.")
    if a not in net or b not in net or int(a) > int(b):
        raise AplusError("Start and end must be inside the network, start first.")
    if a == net.network_address or b == net.broadcast_address:
        raise AplusError("The scope can't include the network or broadcast address.")
    pool = int(b) - int(a) + 1
    taken: set[int] = set()
    for e in (exclusions or [])[:20]:
        parts = [p.strip() for p in str(e).split("-")]
        try:
            lo, hi = ipaddress.ip_address(parts[0]), ipaddress.ip_address(parts[-1])
        except ValueError:
            raise AplusError(f"'{e}' isn't an address or a range like 192.168.1.10-192.168.1.20.") from None
        for x in range(max(int(lo), int(a)), min(int(hi), int(b)) + 1):
            taken.add(x)
    excl = len(taken)
    res = int(_n(reservations, "Reservations", 0, 100000))
    dev = int(_n(devices, "Devices", 0, 100000))
    lease = _n(lease_hours, "Lease (hours)", 0.1, 24 * 365)
    free = max(pool - excl - res, 0)
    notes = []
    if dev:
        if free < dev:
            notes.append(f"{dev} devices but only {free} addresses to hand out. Some will fail and fall back to APIPA (169.254.x.x). Widen the scope or use a bigger subnet.")
        elif free < dev * 1.2:
            notes.append("Fewer than 20% spare addresses. Leases that haven't expired still hold addresses, so busy times may run out.")
        else:
            notes.append("Enough room, with spare for visitors and leases that haven't expired yet.")
    if lease > 24 * 7 and dev:
        notes.append("A long lease on a busy or guest network keeps addresses tied up. Shorten it so unused addresses return sooner.")
    if lease < 1:
        notes.append("Very short leases create constant renewals.")
    notes.append("Reservations tie a fixed address to a device's MAC address, good for printers and servers. Put static or reserved devices outside the dynamic pool, or exclude them, so two devices never get the same address.")
    return {"network": str(net), "mask": str(net.netmask), "pool": pool, "excluded": excl, "reserved": res, "available": free, "lease_hours": lease, "notes": notes,
            "limit": "Reservations are counted as taken whether or not they sit inside the pool; adjust if yours are outside it."}


_SPF_LOOKUP = re.compile(r"^(include:|a(:|/|$)|mx(:|/|$)|ptr|exists:|redirect=)", re.I)


def mail_records(text: str) -> dict:
    """Read pasted TXT records for SPF, DKIM and DMARC and say what is weak. Reads text only; it does no DNS lookups."""
    if not isinstance(text, str) or not text.strip():
        raise AplusError("Paste one or more TXT records.")
    if len(text) > 20000:
        raise AplusError("Too much text; paste the records only.")
    recs = [t.strip().strip('"') for t in re.split(r"\n+", text) if t.strip()]
    found, spf = [], 0
    for r in recs:
        low = r.lower()
        f: list[dict] = []

        def add(level, msg, fix=""):
            f.append({"level": level, "message": msg, "fix": fix})
        if low.startswith("v=spf1"):
            spf += 1
            kind = "SPF"
            terms = low.split()[1:]
            lookups = sum(1 for t in terms if _SPF_LOOKUP.match(t.lstrip("+-~?")))
            end = next((t for t in reversed(terms) if t.lstrip("+-~?").startswith("all")), None)
            if end is None:
                add("warn", "No 'all' at the end, so there is no default policy.", "End with -all (reject) or ~all (soft fail).")
            elif end.startswith("-all"):
                add("ok", "-all: anything not listed is rejected.")
            elif end.startswith("~all"):
                add("info", "~all: unlisted senders are marked suspicious but usually delivered.", "Move to -all once you are sure every sender is listed.")
            else:
                add("bad", f"{end} lets anyone send as your domain." if end.startswith(("+", "all")) else f"{end} gives no protection.", "Use -all or ~all.")
            if lookups > 10:
                add("bad", f"{lookups} DNS lookups; SPF allows at most 10, so evaluation fails.", "Remove includes or flatten the record.")
            elif lookups > 8:
                add("warn", f"{lookups} DNS lookups, close to the limit of 10.")
            if "ptr" in terms:
                add("warn", "'ptr' is discouraged: slow and unreliable.")
        elif low.startswith("v=dkim1") or ("k=rsa" in low and "p=" in low):
            kind = "DKIM"
            m = re.search(r"p=([A-Za-z0-9+/=\s]*)", r)
            key = (m.group(1) if m else "").replace(" ", "")
            if not m or not key:
                add("bad" if m else "warn", "The public key is empty (p=), which means the key was revoked." if m else "No p= public key.", "Publish the key from your mail provider.")
            else:
                try:
                    nbytes = len(base64.b64decode(key + "=" * (-len(key) % 4), validate=True))
                    bits = "about 1024-bit" if nbytes < 200 else ("about 2048-bit" if nbytes < 400 else "4096-bit or larger")
                    add("warn" if nbytes < 200 else "ok", f"RSA key {bits}.", "Use 2048-bit keys." if nbytes < 200 else "")
                except (binascii.Error, ValueError):
                    add("bad", "The p= value isn't valid base64 (check for a broken or truncated paste).")
            if "t=y" in low.replace(" ", ""):
                add("info", "t=y marks the key as testing; receivers may ignore failures.")
        elif low.startswith("v=dmarc1"):
            kind = "DMARC"
            tags = dict(x.strip().split("=", 1) for x in r.split(";") if "=" in x)
            tags = {k.strip().lower(): v.strip() for k, v in tags.items()}
            p = tags.get("p", "").lower()
            if p == "reject":
                add("ok", "p=reject: failing mail is rejected.")
            elif p == "quarantine":
                add("ok", "p=quarantine: failing mail goes to spam.", "Move to reject when reports show no legitimate failures.")
            elif p == "none":
                add("warn", "p=none only monitors; it blocks nothing.", "Read the reports, then move to quarantine and reject.")
            else:
                add("bad", "Missing or invalid p= policy.", "Set p=none, quarantine or reject.")
            if "rua" not in tags:
                add("warn", "No rua= address, so you will not receive aggregate reports.")
            pct = tags.get("pct")
            if pct and pct.isdigit() and int(pct) < 100:
                add("info", f"pct={pct}: the policy applies to only {pct}% of failing mail.")
        else:
            continue
        found.append({"type": kind, "record": r[:200], "findings": f})
    if spf > 1:
        found.append({"type": "SPF", "record": "(several)", "findings": [{"level": "bad", "message": f"{spf} SPF records: a domain may have only one, and more than one makes SPF fail.", "fix": "Merge them into one record."}]})
    if not found:
        raise AplusError("No SPF, DKIM or DMARC record found. SPF starts v=spf1, DKIM v=DKIM1, DMARC v=DMARC1.")
    return {"records": found, "lesson": "SPF lists who may send, DKIM signs the message, and DMARC says what to do when they fail and where to send reports. Mail systems want all three.",
            "limit": "Reads the text you paste and applies fixed rules; it does not look up your live DNS, follow includes or prove delivery."}


def display_calc(width_px: float, height_px: float, diagonal_in: float, refresh_hz: float = 60) -> dict:
    w, h, d, hz = _n(width_px, "Width", 100, 20000), _n(height_px, "Height", 100, 20000), _n(diagonal_in, "Diagonal", 1, 200), _n(refresh_hz, "Refresh rate", 24, 1000)
    ppi = math.hypot(w, h) / d
    g = math.gcd(int(w), int(h))
    gbps = w * h * hz * 24 / 1e9
    named = {(1280, 720): "HD (720p)", (1920, 1080): "Full HD (1080p)", (2560, 1440): "QHD (1440p)", (3840, 2160): "4K UHD", (7680, 4320): "8K"}.get((int(w), int(h)), "")
    return {"pixel_density_ppi": round(ppi, 1), "megapixels": round(w * h / 1e6, 2), "aspect_ratio": f"{int(w) // g}:{int(h) // g}", "name": named, "uncompressed_gbps": round(gbps, 2),
            "reading": "Sharp at arm's length." if ppi >= 110 else ("Adequate for a desktop monitor; individual pixels may be visible up close." if ppi >= 90 else "Pixels will be visible at desk distance; fine for TVs seen from far away."),
            "cable_note": "Bandwidth here is uncompressed 24-bit colour, before blanking and compression. High resolution at a high refresh rate needs a recent HDMI or DisplayPort version, and a cable certified for it.",
            "lesson": "Pixel density is pixels per inch of the diagonal. More pixels on the same screen size means a sharper image, at the cost of video-card load and cable bandwidth."}


_PSU_SIZES = [300, 350, 400, 450, 500, 550, 650, 750, 850, 1000, 1200, 1600]


def psu_size(cpu_w: float = 65, gpu_w: float = 0, drives: int = 1, fans: int = 3, ram_sticks: int = 2, other_w: float = 20, headroom_pct: float = 30) -> dict:
    cpu, gpu, other, head = _n(cpu_w, "CPU watts", 0, 1000), _n(gpu_w, "GPU watts", 0, 1500), _n(other_w, "Other watts", 0, 1000), _n(headroom_pct, "Headroom", 0, 100)
    dr, fa, ram = int(_n(drives, "Drives", 0, 64)), int(_n(fans, "Fans", 0, 64)), int(_n(ram_sticks, "RAM sticks", 0, 16))
    board = 50
    parts = {"CPU": cpu, "Graphics card": gpu, "Motherboard": board, "RAM": ram * 4, "Drives": dr * 7, "Fans": fa * 3, "Other": other}
    load = sum(parts.values())
    need = load * (1 + head / 100)
    pick = next((s for s in _PSU_SIZES if s >= need), None)
    return {"parts": parts, "load_w": round(load), "with_headroom_w": round(need), "suggested_psu_w": pick,
            "note": "Estimated from the figures you entered; use the maker's listed power for your actual parts." + ("" if pick else " That is beyond common single supplies; check the parts."),
            "lesson": "Size for the worst-case load plus headroom: supplies run coolest and most efficiently at about half to 70 percent load, and headroom covers aging and upgrades. Check the connectors too: the 20+4 pin board connector, the CPU power plug and the GPU power cables.",
            "also_check": ["Supply connectors match the parts (CPU 4/8-pin, GPU 6/8-pin)", "Input voltage switch (110-120 V vs 220-240 V)", "Efficiency rating, modular cables if you want tidy routing", "A redundant supply for servers"]}


def backup_plan(full_gb: float, daily_change_gb: float, days: int = 28, full_every_days: int = 7, copies: int = 3, media_types: int = 2, offsite: int = 1) -> dict:
    full, ch = _n(full_gb, "Full backup size", 0.01, 1e7), _n(daily_change_gb, "Daily change", 0, 1e7)
    days = int(_n(days, "Days kept", 1, 365))
    fe = int(_n(full_every_days, "Full backup every (days)", 1, 365))
    fulls = math.ceil(days / fe)
    schemes = []
    # incremental: each non-full day stores that day's change; restore = last full + every incremental since
    inc_store = fulls * full + (days - fulls) * ch
    diff_store = fulls * full + sum((d % fe) * ch for d in range(days) if d % fe)
    synth_store = inc_store           # synthetic full is built on the backup server from earlier backups: same stored data, shorter restore
    worst = fe - 1
    schemes.append({"scheme": "Full every day", "stored_gb": round(days * full, 1), "restore_sets": 1, "note": "Simplest restore, most space and time."})
    schemes.append({"scheme": "Incremental", "stored_gb": round(inc_store, 1), "restore_sets": 1 + worst, "note": "Smallest backups. Restore needs the full plus every incremental since; one bad link breaks the chain."})
    schemes.append({"scheme": "Differential", "stored_gb": round(diff_store, 1), "restore_sets": 2 if worst else 1, "note": "Each backup holds everything since the last full: restore needs only the full and the latest differential."})
    schemes.append({"scheme": "Synthetic full", "stored_gb": round(synth_store, 1), "restore_sets": 1, "note": "The backup server assembles a new full from earlier backups without reading the source again; restore is as simple as a full."})
    rule = {"copies": int(copies), "media": int(media_types), "offsite": int(offsite)}
    ok321 = rule["copies"] >= 3 and rule["media"] >= 2 and rule["offsite"] >= 1
    return {"full_gb": full, "daily_change_gb": ch, "days": days, "full_every_days": fe, "schemes": schemes, "rule_3_2_1": {**rule, "meets": ok321,
            "message": "Meets 3-2-1: three copies, two kinds of media, one offsite." if ok321 else "Does not meet 3-2-1 (three copies, two media, one offsite). Add what is missing."},
            "rotation": "Grandfather-father-son keeps daily (son), weekly (father) and monthly (grandfather) sets, rotating media.",
            "lesson": "Incremental backs up changes since the last backup of any kind; differential since the last full. Whatever you pick, a backup you have never restored is a hope, not a backup: test restores on a schedule.",
            "limit": "Straight-line estimate: it assumes every day changes the same amount and ignores compression and deduplication."}


_SCRIPT_TYPES = {".bat": "Windows batch", ".cmd": "Windows batch", ".ps1": "PowerShell", ".vbs": "VBScript", ".sh": "Bash/shell", ".js": "JavaScript", ".py": "Python"}
_RISKS = [
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r|remove-item[^\n]*-recurse[^\n]*-force|\bdel\s+/[sfq]|\brd\s+/s|\brmdir\s+/s", "bad", "Deletes files recursively", "Run with a dry run on a test folder first, and make sure the path can't be empty or the wrong drive."),
    (r"\bformat\s+[a-z]:|diskpart|\bmkfs\b|\bdd\s+if=", "bad", "Formats or overwrites a disk", "Almost never belongs in a routine script. Confirm the target disk."),
    (r"invoke-expression|\biex\b|eval\s*\(|\beval\s", "bad", "Runs text as code", "Whatever feeds it controls your machine. Avoid it."),
    (r"downloadstring|downloadfile|invoke-webrequest|\bcurl\b[^\n]*\|\s*(sh|bash)|\bwget\b[^\n]*\|\s*(sh|bash)|bitsadmin|certutil[^\n]*-urlcache", "bad", "Downloads and may run something from the internet", "Check the source and verify a hash. This is how malware is delivered."),
    (r"-executionpolicy\s+bypass|set-executionpolicy", "warn", "Changes or bypasses PowerShell's execution policy", "Know why; it weakens a safeguard."),
    (r"net\s+user[^\n]*\s/add|net\s+localgroup\s+administrators|useradd|usermod\s+-a?g?\s*sudo", "bad", "Creates a user or grants admin rights", "Account changes should go through approved tools and be logged."),
    (r"set-mppreference|disable[^\n]*defender|netsh\s+advfirewall[^\n]*off|ufw\s+disable|setenforce\s+0", "bad", "Turns off security protection", "Don't leave protections off; use targeted exceptions."),
    (r"reg\s+(add|delete)|set-itemproperty[^\n]*hk|new-itemproperty[^\n]*hk|regedit", "warn", "Edits the registry", "Back up the key first."),
    (r"\bchmod\s+(-r\s+)?777|\bchmod\s+-r\b", "warn", "Opens permissions widely", "Grant the least access needed."),
    (r"schtasks\s+/create|crontab|new-scheduledtask|register-scheduledtask", "info", "Creates a scheduled task", "Persistent tasks are normal for automation but are also how malware stays; document it."),
    (r"password\s*[=:]\s*['\"]?\S+|apikey|secret\s*[=:]", "warn", "May contain a hard-coded secret", "Keep passwords out of scripts; use a secrets store."),
    (r"shutdown|restart-computer|\breboot\b|\bhalt\b", "info", "Restarts or shuts down the machine", "Warn users and confirm it won't run at the wrong time."),
]


def script_review(text: str, filename: str = "") -> dict:
    if not isinstance(text, str) or not text.strip():
        raise AplusError("Paste the script text.")
    if len(text) > 200000:
        raise AplusError("Script is too long (limit 200,000 characters).")
    ext = re.search(r"\.[A-Za-z0-9]+$", filename or "")
    kind = _SCRIPT_TYPES.get(ext.group(0).lower(), "") if ext else ""
    if not kind:
        t = text.lstrip()
        kind = ("Bash/shell" if t.startswith("#!") and ("sh" in t.split("\n", 1)[0]) else "PowerShell" if re.search(r"\$[A-Za-z_]+\s*=|Get-[A-Z]", t) else "Windows batch" if re.search(r"^@?echo\s+off", t, re.I | re.M) else "unknown")
    out = []
    low = text.lower()
    for pat, level, what, tip in _RISKS:
        m = re.search(pat, low)
        if m:
            line = low[:m.start()].count("\n") + 1
            out.append({"level": level, "line": line, "finding": what, "advice": tip, "text": text.splitlines()[line - 1].strip()[:140]})
    order = {"bad": 0, "warn": 1, "info": 2}
    out.sort(key=lambda x: (order[x["level"]], x["line"]))
    verdict = "high risk: do not run without understanding every flagged line" if any(x["level"] == "bad" for x in out) else ("review the flagged lines before running" if out else "nothing obviously dangerous found")
    return {"type": kind, "lines": len(text.splitlines()), "findings": out, "verdict": verdict,
            "habits": ["Read the whole script before you run it.", "Test on a non-production machine or a snapshot.", "Back up first.", "Prefer scripts from sources you trust, and check a hash if one is published.", "Log what the script changes."],
            "limit": "A pattern scan, not a malware scanner. It never runs the script and can miss obfuscated or novel tricks; a clean result is not proof of safety."}
