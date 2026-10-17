"""Advanced networking lab: routing, spanning tree, IPv6 planning, PoE and fiber budgets, wireless link budget, TCP throughput, firewall rule review, VPN and QoS reference.
Planning and local calculation only. Nothing connects to a device. Lab-test changes before a client network, and always keep a way back in (console, out-of-band, saved config)."""
from __future__ import annotations

import ipaddress
import math
import re

NOTE = "Planning estimates. Confirm with vendor specs and test on the real network in a safe window with a rollback."


class NetError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _f(v, name, lo=0.0, hi=1e12, strict=True) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise NetError(f"{name} must be a number.") from None
    if (x <= lo if strict else x < lo) or x > hi:
        raise NetError(f"{name} must be {'more than' if strict else 'at least'} {lo:g} and at most {hi:g}.")
    return x


def ospf_cost(link_mbps, reference_mbps=100) -> dict:
    l, r = _f(link_mbps, "Link speed (Mbps)", 0, 1e7), _f(reference_mbps, "Reference bandwidth (Mbps)", 0, 1e7)
    cost = max(1, int(r // l))
    return {"cost": cost, "note": "OSPF cost = reference bandwidth / link speed, minimum 1. With the default 100 Mbps reference, gigabit and faster links all cost 1, so raise the reference bandwidth (the same on every router) on modern networks. Paths with the lowest total cost win."}


def stp_root(bridges) -> dict:
    rows = []
    for ln in (bridges if isinstance(bridges, list) else str(bridges).splitlines()):
        p = [x.strip() for x in str(ln).split(",")]
        if len(p) < 3 or not p[0]:
            continue
        try:
            pr = int(p[1])
            mac = int(re.sub(r"[^0-9a-fA-F]", "", p[2]), 16)
        except ValueError:
            raise NetError(f"Could not read '{ln}'. Use: name, priority, mac (for example SW1, 32768, 00:1a:2b:3c:4d:5e).") from None
        if pr % 4096 or not 0 <= pr <= 61440:
            raise NetError("Bridge priority must be a multiple of 4096 from 0 to 61440.")
        rows.append((pr, mac, p[0], p[2]))
    if len(rows) < 2:
        raise NetError("Give at least two switches, one per line: name, priority, mac.")
    rows.sort()
    return {"root": rows[0][2], "order": [{"name": n, "priority": pr, "mac": m} for pr, _x, n, m in rows],
            "why": "The switch with the lowest priority wins; a tie goes to the lowest MAC address. The root should be your core switch, not whichever is oldest.",
            "tips": ["Set the core switch priority explicitly (for example 4096) and a backup root at 8192.", "Enable PortFast and BPDU Guard on access ports.", "Use rapid spanning tree (RSTP) for faster recovery.", "Keep loops deliberate: a cabling mistake can cause a broadcast storm."], "note": NOTE}


def ipv6_plan(prefix, subnet_prefix=64, count=8) -> dict:
    try:
        net = ipaddress.ip_network(str(prefix).strip(), strict=False)
        sp, n = int(subnet_prefix), int(count)
    except (ValueError, TypeError):
        raise NetError("Give an IPv6 prefix like 2001:db8:abcd::/48.") from None
    if net.version != 6:
        raise NetError("That is an IPv4 prefix. Give an IPv6 prefix such as 2001:db8:abcd::/48.")
    if sp < net.prefixlen or sp > 128 or not 1 <= n <= 256:
        raise NetError("The subnet prefix must be longer than the starting prefix (usually /64), and count 1 to 256.")
    total = 2 ** (sp - net.prefixlen)
    subs = []
    for i, s in enumerate(net.subnets(new_prefix=sp)):
        if i >= n:
            break
        subs.append(str(s))
    return {"network": str(net), "subnets_available": str(total) if total < 10**12 else f"about {total:.2e}", "first": subs,
            "advice": ["Use /64 for every LAN: many IPv6 features (SLAAC) require it.", "A typical business gets a /48 (65,536 subnets) or /56 (256).", "Plan by site and VLAN: put the VLAN number in a nibble so addresses are readable.", "Do not block ICMPv6 entirely: neighbor discovery needs it."], "note": NOTE}


def eui64(mac, prefix="fe80::/64") -> dict:
    h = re.sub(r"[^0-9a-fA-F]", "", str(mac))
    if len(h) != 12:
        raise NetError("Give a 12-digit MAC address like 00:1a:2b:3c:4d:5e.")
    b = bytearray(bytes.fromhex(h))
    b[0] ^= 0x02
    iid = bytes(b[:3]) + b"\xff\xfe" + bytes(b[3:])
    try:
        net = ipaddress.ip_network(str(prefix), strict=False)
    except ValueError:
        raise NetError("Give a /64 prefix like fe80::/64.") from None
    addr = ipaddress.ip_address(int(net.network_address) | int.from_bytes(iid, "big"))
    return {"address": str(addr), "note": "EUI-64 flips the 7th bit of the first byte and inserts ff:fe in the middle. Many systems now use random privacy addresses instead."}


POE_CLASS = {"af": ("802.3af (PoE)", 15.4), "at": ("802.3at (PoE+)", 30.0), "bt3": ("802.3bt type 3 (PoE++)", 60.0), "bt4": ("802.3bt type 4 (PoE++)", 90.0)}


def poe_budget(switch_watts, devices) -> dict:
    budget = _f(switch_watts, "Switch PoE budget (W)", 0, 5000)
    rows, total = [], 0.0
    for ln in (devices if isinstance(devices, list) else str(devices).splitlines()):
        p = [x.strip() for x in str(ln).split(",")]
        if len(p) < 2 or not p[0]:
            continue
        w = POE_CLASS[p[1].lower()][1] if p[1].lower() in POE_CLASS else _f(p[1], f"Watts for {p[0]}", 0, 100)
        q = int(_f(p[2], "Quantity", 0, 500)) if len(p) > 2 and p[2] else 1
        rows.append({"device": p[0], "watts_each": w, "qty": q, "watts": round(w * q, 1)})
        total += w * q
    if not rows:
        raise NetError("List devices one per line: name, watts or class (af, at, bt3, bt4), quantity. Example: Camera, 12.95, 8")
    head = budget - total
    return {"devices": rows, "total_w": round(total, 1), "budget_w": budget, "headroom_w": round(head, 1), "percent_used": round(total / budget * 100, 1),
            "verdict": "Over budget: some devices will not power up." if head < 0 else "Tight: under 20% headroom, so adding devices or cold weather can overload it." if head < budget * 0.2 else "Comfortable headroom.",
            "tips": ["Plan with the device's maximum draw, not typical.", "Powered devices get less than the switch port provides after cable loss: check the standard.", "Keep Ethernet runs under 100 m and use proper cable (copper, not copper-clad aluminum)."], "note": NOTE}


ATTEN = {"850": (3.5, "Multimode 850 nm"), "1300": (1.5, "Multimode 1300 nm"), "1310": (0.35, "Single-mode 1310 nm"), "1550": (0.22, "Single-mode 1550 nm")}


def fiber_budget(length_km, wavelength="1310", connectors=2, splices=0, tx_dbm=-3.0, rx_sensitivity_dbm=-18.0, margin_db=3.0) -> dict:
    L = _f(length_km, "Length (km)", 0, 200)
    w = str(wavelength)
    if w not in ATTEN:
        raise NetError("Wavelength must be 850, 1300, 1310 or 1550 (nm).")
    c, s = int(_f(connectors, "Connector pairs", -1, 50, False)), int(_f(splices, "Splices", -1, 200, False))
    tx, rx, m = _f(tx_dbm, "Transmit power (dBm)", -60, 40, False), _f(rx_sensitivity_dbm, "Receiver sensitivity (dBm)", -80, 20, False), _f(margin_db, "Margin (dB)", -1, 20, False)
    loss = L * ATTEN[w][0] + c * 0.5 + s * 0.1
    avail = tx - rx
    rec = tx - loss
    return {"fiber_type": ATTEN[w][1], "total_loss_db": round(loss, 2), "power_budget_db": round(avail, 2), "received_dbm": round(rec, 2), "margin_left_db": round(avail - loss, 2),
            "ok": avail - loss >= m, "verdict": "Link should work with the margin you asked for." if avail - loss >= m else "Not enough margin: shorten the run, cut connectors and splices, or use stronger optics.",
            "note": "Typical values (about 0.5 dB per connector pair, 0.1 dB per splice). Use the optics datasheet and test with a power meter or OTDR after install. Never look into a live fiber or connector."}


def fspl(freq_mhz, distance_m) -> dict:
    f, d = _f(freq_mhz, "Frequency (MHz)", 0, 1e6), _f(distance_m, "Distance (m)", 0, 1e7)
    loss = 20 * math.log10(d / 1000) + 20 * math.log10(f) + 32.44
    return {"free_space_loss_db": round(loss, 1), "note": "Open-air loss only. Walls, glass and people add 3 to 20 dB each in real buildings, and 5 GHz loses more than 2.4 GHz through walls."}


def link_budget(tx_dbm, tx_gain_dbi, rx_gain_dbi, freq_mhz, distance_m, rx_sensitivity_dbm, obstruction_db=0, margin_db=10) -> dict:
    tx, tg, rg = _f(tx_dbm, "Transmit power (dBm)", -50, 60, False), _f(tx_gain_dbi, "Transmit antenna gain (dBi)", -20, 60, False), _f(rx_gain_dbi, "Receive antenna gain (dBi)", -20, 60, False)
    rs, ob, m = _f(rx_sensitivity_dbm, "Receiver sensitivity (dBm)", -120, 0, False), _f(obstruction_db, "Obstruction loss (dB)", -1, 100, False), _f(margin_db, "Margin (dB)", -1, 60, False)
    loss = fspl(freq_mhz, distance_m)["free_space_loss_db"]
    rx = tx + tg + rg - loss - ob
    fade = rx - rs
    return {"free_space_loss_db": loss, "received_dbm": round(rx, 1), "fade_margin_db": round(fade, 1), "ok": fade >= m,
            "verdict": "Looks workable with the margin you asked for." if fade >= m else "Not enough margin: shorten the distance, raise antenna gain or power, or remove obstructions.",
            "note": "A planning estimate. Do a real site survey with a spectrum tool before installing, and stay within legal power limits."}


def tcp_throughput(rtt_ms, loss_pct, mss_bytes=1460) -> dict:
    rtt, p, mss = _f(rtt_ms, "Round-trip time (ms)", 0, 10000), _f(loss_pct, "Packet loss (%)", 0, 100) / 100, _f(mss_bytes, "MSS (bytes)", 0, 9000)
    mbps = mss * 8 / (rtt / 1000) * 1.22 / math.sqrt(p) / 1e6
    return {"max_throughput_mbps": round(mbps, 2), "note": "Mathis model for a single TCP flow: even 1% loss at 50 ms caps one connection near 2 Mbps. High latency and a little loss limit speed more than the line speed does. Fix loss first (duplex mismatch, bad cable, congestion, Wi-Fi)."}


FW_RULES = [
    ("high", r"(?i)(permit|allow|accept)\s+(ip|any|all)\s+(any|0\.0\.0\.0/0)\s+(any|0\.0\.0\.0/0)", "An allow-everything rule.", "Replace with the exact sources, destinations and ports needed."),
    ("high", r"(?i)(permit|allow|accept)[^\n]*\b(tcp|udp)?[^\n]*(any|0\.0\.0\.0/0)[^\n]*(eq\s+)?\b(23|telnet)\b", "Telnet allowed from anywhere.", "Block telnet and use SSH from specific addresses."),
    ("high", r"(?i)(permit|allow|accept)[^\n]*(any|0\.0\.0\.0/0)[^\n]*\b(3389|rdp)\b", "Remote Desktop open to the internet.", "Put RDP behind a VPN or gateway with MFA."),
    ("high", r"(?i)(permit|allow|accept)[^\n]*(any|0\.0\.0\.0/0)[^\n]*\b(445|139|smb|netbios)\b", "File sharing open to the internet.", "Never expose SMB. Remove this rule."),
    ("high", r"(?i)(permit|allow|accept)[^\n]*(any|0\.0\.0\.0/0)[^\n]*\b(3306|1433|5432|27017|6379|mysql|mssql|postgres)\b", "A database port is open to the internet.", "Restrict to the application server's address."),
    ("medium", r"(?i)(permit|allow|accept)[^\n]*(any|0\.0\.0\.0/0)[^\n]*\b(22|ssh)\b", "SSH open to any address.", "Limit to your management network or use a VPN, keys and fail2ban-style protection."),
    ("medium", r"(?i)ip\s+access-list\s+extended[^\n]*\n(?:(?!deny)[^\n])*$", "An access list that ends without a deny and log.", "End with an explicit deny and log to see what is blocked."),
    ("low", r"(?i)(permit|allow|accept)[^\n]*\bicmp\b[^\n]*(any|0\.0\.0\.0/0)", "ICMP allowed from anywhere.", "Allow only the ICMP types you need (echo is fine on internal networks)."),
]


def firewall_review(text: str) -> dict:
    text = text or ""
    if len(text.strip()) < 8:
        raise NetError("Paste firewall or access list rules (iptables, Cisco ACL, or a plain list).")
    if len(text) > 20000:
        raise NetError("Keep it under 20,000 characters.")
    finds = []
    for sev, pat, msg, fix in FW_RULES:
        for m in re.finditer(pat, text):
            ln = text.count("\n", 0, m.start()) + 1
            finds.append({"severity": sev, "line": ln, "problem": msg, "fix": fix, "rule": text.splitlines()[ln - 1].strip()[:110]})
    seen, out = set(), []
    for f in finds:
        k = (f["problem"], f["line"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda f: (order[f["severity"]], f["line"]))
    return {"findings": out[:30], "counts": {k: sum(1 for f in out if f["severity"] == k) for k in order},
            "good_practice": ["Default deny: allow only what is needed.", "Rules by source, destination and port, not 'any'.", "Log denies, and review them.", "Put every rule in a change record and remove unused ones.", "Back up the config before editing and keep a console or out-of-band way in."],
            "caveat": "Pattern matching on common mistakes, not a full rule analysis. Read the rule order and test from outside.", "note": NOTE}


VPN = [
    {"type": "WireGuard", "good": "Simple, fast, small codebase; good for site-to-site and remote access", "watch": "Needs a way to manage keys and users at scale"},
    {"type": "IPsec (IKEv2)", "good": "Supported by almost every firewall and router, the standard for site-to-site", "watch": "Complex to configure; mismatched settings and NAT cause trouble"},
    {"type": "OpenVPN or SSL VPN", "good": "Works through most firewalls, flexible authentication", "watch": "Slower than WireGuard and needs patching"},
    {"type": "Zero trust network access (ZTNA)", "good": "Per-app access with identity and device checks; no broad network exposure", "watch": "Subscription cost and setup work"},
    {"type": "Cloud VPN gateway", "good": "Connects an office to AWS, Azure or Google networks", "watch": "Plan address ranges so they do not overlap"},
]
QOS = ["Classify first: voice, video, business apps, normal, bulk.", "Mark traffic (DSCP: voice EF, video AF41, business AF31, default 0, bulk CS1).", "Queue priority for voice with a strict limit, and share the rest by weight.", "Shape to just under the ISP rate so your queue, not the ISP's, controls order.", "QoS only helps when a link is full: fix capacity first."]
LAYERS = [
    ("1 Physical", "Link lights, cable, port, power, interference. Swap the cable or port."), ("2 Data link", "VLAN, duplex mismatch, MAC table, spanning tree, port security. Check counters for errors."),
    ("3 Network", "IP address, mask, gateway, routing, ping and traceroute. Check the route table and ACLs."), ("4 Transport", "Ports open, firewall, NAT, retransmits. Use packet capture to see resets and retransmits."),
    ("5 to 7 Application", "DNS, certificates, authentication, the server app. Test with another client and read the app logs.")]
SNMP = [("1.3.6.1.2.1.1.3.0", "sysUpTime", "How long the device has been up"), ("1.3.6.1.2.1.2.2.1.8", "ifOperStatus", "Interface up or down"), ("1.3.6.1.2.1.2.2.1.10 / .16", "ifInOctets / ifOutOctets", "Bytes in and out, for utilization"),
        ("1.3.6.1.2.1.2.2.1.14 / .20", "ifInErrors / ifOutErrors", "Errors on an interface"), ("1.3.6.1.4.1.2021.11", "UCD CPU (Linux net-snmp)", "CPU load on Linux hosts")]


def reference() -> dict:
    return {"vpn": VPN, "qos": QOS, "layers": [{"layer": a, "check": b} for a, b in LAYERS], "snmp": [{"oid": a, "name": b, "means": c} for a, b, c in SNMP],
            "monitoring": ["Use SNMPv3 with authentication and encryption, not v1 or v2c community strings 'public' and 'private'.", "Send device logs (syslog) to one server and keep them for at least 90 days.", "Collect NetFlow or sFlow to see who is using the bandwidth.", "Alert on interface errors, high utilization, device down and certificate expiry.", "Change default credentials and restrict management to a management network."],
            "routing": ["Static routes: simple and predictable for small sites.", "OSPF: link state, good inside a campus; use areas, set the router ID and reference bandwidth, and authenticate neighbors.", "BGP: between networks (ISPs and clouds); filter prefixes and set max-prefix limits.", "Never redistribute routes without filters."],
            "wifi": ["Use 2.4 GHz channels 1, 6 and 11 only, and prefer 5 or 6 GHz for capacity.", "Place access points for coverage and capacity: about 1 per 25 to 50 active clients.", "Survey with a spectrum tool; walls and metal change everything.", "Use WPA3 or WPA2-Enterprise (802.1X) for staff and a separate guest VLAN.", "Keep firmware updated and disable WPS."], "note": NOTE}


def calc(kind: str, args: dict) -> dict:
    fn = {"ospf": ospf_cost, "stp": stp_root, "ipv6": ipv6_plan, "eui64": eui64, "poe": poe_budget, "fiber": fiber_budget, "fspl": fspl, "link": link_budget, "tcp": tcp_throughput}.get(kind)
    if not fn:
        raise NetError("Unknown calculator.")
    try:
        return fn(**{k: v for k, v in (args or {}).items() if k in fn.__code__.co_varnames[:fn.__code__.co_argcount]})
    except TypeError as e:
        raise NetError("Missing a value: " + str(e).split("argument")[-1].strip(" '")) from None
