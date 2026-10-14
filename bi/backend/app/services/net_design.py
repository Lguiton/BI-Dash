"""Network design planner and networking glossary. Pure functions: requirements in, a plan and a checklist out."""
from __future__ import annotations

import math

from app.services import netlab


class DesignError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


STEPS = [
    ("req", "Gather the business requirements", "Why the network is needed, the budget, constraints, legacy systems to support, and the growth you expect."),
    ("assess", "Assess the current network", "Diagram and document devices, cabling and technologies; decide what to reuse and what to replace."),
    ("goals", "Define goals you can measure", "Performance, security and manageability targets, e.g. '95% of sites under 50 ms', 'guest traffic isolated'."),
    ("logical", "Design the logical network", "Address plan, VLANs, routing, DNS and DHCP, security zones. Done before buying anything."),
    ("devices", "Select devices and technologies", "Routers, switches, firewalls, access points, servers, management and security software, sized with headroom."),
    ("physical", "Design the physical network", "Racks, cabling, power, cooling and diagrams of every connection."),
    ("secure", "Plan security and resilience", "Zones, firewall rules, remote access, backups, redundant paths and a failure plan."),
    ("implement", "Plan the implementation", "Timeline, people, change windows, testing, rollback and a pilot before the full cutover."),
    ("document", "Document and hand over", "Diagrams, address plan, configs and requirements stored where the next person can find them; set up monitoring."),
]


def _int(d: dict, k: str, lo: int, hi: int, default: int | None = None) -> int:
    v = d.get(k, default)
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise DesignError(f"'{k}' must be a whole number.") from None
    if not lo <= n <= hi:
        raise DesignError(f"'{k}' must be between {lo} and {hi}.")
    return n


def plan(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise DesignError("Send the requirements as an object.")
    groups = spec.get("groups")
    if not isinstance(groups, list) or not groups or len(groups) > 30:
        raise DesignError("Give 1 to 30 groups (departments or purposes) with a host count each.")
    growth = _int(spec, "growth_pct", 0, 300, 20)
    sites = _int(spec, "sites", 1, 50, 1)
    base = str(spec.get("base") or "10.20.0.0/16")
    redundancy = spec.get("redundancy") or "links"
    if redundancy not in ("none", "links", "full"):
        raise DesignError("Redundancy must be none, links or full.")
    wifi = bool(spec.get("wifi", True))
    guest = bool(spec.get("guest_wifi", False))
    remote = bool(spec.get("remote_access", False))
    needs, names = [], set()
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            raise DesignError(f"Group {i + 1} must be an object with name and hosts.")
        name = str(g.get("name") or f"Group {i + 1}").strip()[:40]
        if name.lower() in names:
            raise DesignError(f"Group name '{name}' is used twice.")
        names.add(name.lower())
        hosts = _int(g, "hosts", 1, 100_000)
        needs.append({"name": name, "hosts": hosts, "grown": math.ceil(hosts * (1 + growth / 100))})
    extra = [{"name": "Management", "hosts": 30}, {"name": "Servers", "hosts": 20}]
    if guest:
        extra.append({"name": "Guest wifi", "hosts": 60})
    rows = [{"name": n["name"], "hosts": n["grown"]} for n in needs] + [e for e in extra if e["name"].lower() not in names]
    try:
        v = netlab.vlsm(base, rows)
    except netlab.NetError as e:
        raise DesignError(str(e)) from None
    wired_total = sum(n["grown"] for n in needs)
    users = sum(n["hosts"] for n in needs)
    ports = math.ceil(wired_total * 1.2)
    switches = max(1, math.ceil(ports / 48))
    aps = max(1, math.ceil(users / 25)) if wifi else 0
    size = "small" if users <= 50 else "medium" if users <= 500 else "large"
    topo = {"small": "Star: one router/firewall and one or two switches, with access points on the switch.",
            "medium": "Collapsed core: a pair of core/distribution switches with access switches uplinked to both.",
            "large": "Three tiers (core, distribution, access), with each building or floor as its own distribution block."}[size]
    zones = ["Users", "Servers", "Management"] + (["Guest (internet only, isolated)"] if guest else []) + (["VPN (remote users)"] if remote else [])
    devices = [{"item": "Router / firewall", "count": 2 if redundancy == "full" else 1, "note": "Perimeter and inter-VLAN policy. A pair if downtime is unacceptable."},
               {"item": "Access switches (48-port)", "count": switches * (2 if redundancy == "full" else 1), "note": f"{ports} ports for {wired_total} planned wired hosts, 20% spare."},
               {"item": "Wireless access points", "count": aps, "note": "About one per 25 users; do a site survey before fixing the number."},
               {"item": "UPS units", "count": max(1, switches // 4 + 1), "note": "Keep the core and firewall up long enough to shut down cleanly."}]
    if sites > 1:
        devices.append({"item": "Site-to-site links", "count": sites - 1, "note": "VPN over the internet or a leased line; plan a second path to the main site."})
    risks = []
    if redundancy == "none":
        risks.append("No redundancy: a single switch, link or firewall failure takes users offline. Decide that consciously.")
    if growth < 10:
        risks.append("Growth under 10% a year is rarely realistic; readdressing later is painful.")
    if guest:
        risks.append("Guest wifi must be on its own VLAN with no route to internal subnets.")
    if remote:
        risks.append("Remote access needs MFA and should land in the VPN zone, not on the user VLANs.")
    if v["free_addresses"] < v["used_addresses"] // 4:
        risks.append(f"Less than a quarter of {base} is left; choose a bigger block.")
    if sites > 1:
        risks.append("Different sites need non-overlapping address blocks so they can be routed or joined later.")
    checklist = [{"id": i, "step": t, "detail": d} for i, t, d in STEPS]
    return {"size": size, "users": users, "growth_pct": growth, "addressing": v["plan"], "free_addresses": v["free_addresses"], "topology": topo, "zones": zones,
            "devices": devices, "risks": risks, "checklist": checklist,
            "limit": "A sizing sketch for learning. It does not replace a site survey, a vendor design or traffic measurements."}


GLOSSARY = [
    ("ARP", "Address Resolution Protocol", "Maps an IPv4 address to a MAC address on the local network (Layer 2 and 3 glue). It is not a troubleshooting protocol; ping uses ICMP for that.", "Hosts broadcast 'who has 192.168.1.1?' and the owner answers with its MAC."),
    ("Bridge", "", "Joins two network segments so they act as one network, forwarding by MAC address.", "A switch is essentially a multi-port bridge."),
    ("Client", "", "A device that requests a service from a server.", ""),
    ("DNS", "Domain Name System", "Translates names to IP addresses. Port 53.", ""),
    ("DHCP", "Dynamic Host Configuration Protocol", "Hands out IP addresses and settings (gateway, DNS). UDP ports 67 and 68.", "Discover, Offer, Request, Acknowledge."),
    ("FTP", "File Transfer Protocol", "Transfers files; sends everything, including the password, in clear text. Port 21 (control).", "Prefer SFTP (SSH, port 22) or FTPS."),
    ("Firewall", "", "Hardware or software that allows or blocks traffic by rules.", ""),
    ("Gateway", "", "The device that connects a network to another; usually the router address clients use as their default gateway.", ""),
    ("Hub", "", "Repeats every frame out of every other port. One collision domain, no filtering.", "Obsolete; replaced by switches."),
    ("HTTP / HTTPS", "Hypertext Transfer Protocol (Secure)", "Web page transfer. HTTPS adds TLS encryption. Ports 80 and 443.", ""),
    ("IMAP4", "Internet Message Access Protocol", "Reads email stored on the server, synced across devices. Port 143 (993 with TLS).", ""),
    ("POP3", "Post Office Protocol 3", "Downloads email to one device, usually removing it from the server. Port 110.", ""),
    ("SMTP", "Simple Mail Transfer Protocol", "Sends email. Port 25 between servers; 587 for submitting from clients.", ""),
    ("IDS / IPS", "Intrusion Detection / Prevention System", "IDS watches and alerts; IPS sits in line and can block.", ""),
    ("IPv4 / IPv6", "", "32-bit and 128-bit addresses.", ""),
    ("Modem", "Modulator-demodulator", "Converts between your network's signals and the line's (cable, DSL, fibre ONT).", ""),
    ("NIC", "Network Interface Card", "The hardware that connects a device to a network; wired or wireless. It has a MAC address.", ""),
    ("Node", "", "Any device on a network that can send or receive.", ""),
    ("OSI model", "Open Systems Interconnection", "Seven-layer reference model: physical, data link, network, transport, session, presentation, application.", "A teaching model; real networks follow TCP/IP."),
    ("RDP", "Remote Desktop Protocol", "Remote graphical desktop. TCP 3389. Never expose it directly to the internet.", ""),
    ("Repeater", "", "Regenerates a signal to extend its reach.", ""),
    ("Router", "", "Forwards packets between networks using IP addresses.", ""),
    ("SSH", "Secure Shell", "Encrypted remote command line (and SFTP). Port 22.", ""),
    ("Switch", "", "Forwards frames to the right port using a MAC address table.", ""),
    ("Telnet", "", "Remote command line with no encryption: the password crosses the network in clear text. Port 23. Use SSH.", ""),
    ("TCP", "Transmission Control Protocol", "Reliable, ordered delivery with a handshake; slower. Web, email, file transfer.", ""),
    ("UDP", "User Datagram Protocol", "No guarantee of delivery or order; low overhead. Streaming, games, DNS, voice.", ""),
    ("TCP/IP model", "", "Four layers: link, internet, transport, application.", ""),
    ("WAP / AP", "Wireless access point", "Connects Wi-Fi devices to the wired network.", ""),
    ("WLAN", "Wireless local area network", "Wi-Fi in a home or office. IEEE 802.11.", ""),
    ("WMAN", "Wireless metropolitan area network", "City-scale wireless, e.g. WiMAX. IEEE 802.16 (not 802.15).", ""),
    ("WPAN", "Wireless personal area network", "Short range (about 10 m): Bluetooth, Zigbee. IEEE 802.15.", ""),
    ("WWAN", "Wireless wide area network", "Cellular (4G, 5G, LTE) and satellite style coverage over large areas.", ""),
    ("WANET", "Wireless ad hoc network", "Devices connect directly to each other with no fixed infrastructure.", ""),
    ("WISP", "Wireless Internet service provider", "An internet provider that delivers service by radio (often fixed wireless) rather than cable. It is not the cellular network itself.", ""),
]


def glossary(term: str = "") -> dict:
    t = (term or "").strip().lower()
    rows = [{"term": a, "full": b, "meaning": c, "note": d} for a, b, c, d in GLOSSARY]
    if t:
        rows = [r for r in rows if t in r["term"].lower() or t in r["full"].lower() or t in r["meaning"].lower()]
    return {"count": len(rows), "terms": rows}


PORTS = [
    (20, "TCP", "FTP data (active mode)"), (21, "TCP", "FTP control"), (22, "TCP", "SSH, SFTP"), (23, "TCP", "Telnet (clear text)"), (25, "TCP", "SMTP"),
    (53, "UDP/TCP", "DNS"), (67, "UDP", "DHCP server"), (68, "UDP", "DHCP client"), (80, "TCP", "HTTP"), (110, "TCP", "POP3"), (123, "UDP", "NTP"),
    (143, "TCP", "IMAP4"), (161, "UDP", "SNMP"), (162, "UDP", "SNMP traps"), (389, "TCP/UDP", "LDAP"), (443, "TCP", "HTTPS"), (445, "TCP", "SMB (modern)"),
    (587, "TCP", "SMTP submission"), (636, "TCP", "LDAPS"), (993, "TCP", "IMAPS"), (3389, "TCP", "RDP"),
]


def ports() -> dict:
    return {"ports": [{"port": p, "protocol": pr, "service": s} for p, pr, s in PORTS],
            "note": "Defaults, not rules: a service can listen on any port. Numbers run 0 to 65535 (port 0 is reserved).",
            "legacy": "UDP/TCP 137-139 is NetBIOS over TCP/IP, an old companion to SMB, not the modern SMB port."}


SLIPS = [
    "Network design reading: the step list has six items but the recap lists seven, because 'develop an implementation plan' is tucked under 'Design the physical network'. It also has no logical design step (addressing, VLANs, routing), no security and resilience step and no testing or rollback. The planner here adds them.",
    "Network design reading: 'IBM Spectrum Control' is a storage-management product, and Netcool, Cloud Pak for Network Automation and SevOne monitor and automate a running network; they are not design tools. Wireshark analyses traffic and GNS3 simulates it; Visio draws diagrams. Treat the list as vendor marketing and check what each product does and whether it is still sold.",
    "Glossary: ARP is defined as 'a protocol that deals with troubleshooting network issues and setting up new devices'. ARP resolves an IPv4 address to a MAC address on the local network; troubleshooting is ICMP (ping, traceroute).",
    "Glossary: WMAN is said to use IEEE 802.15, the same as WPAN. WMAN is IEEE 802.16 (WiMAX).",
    "Glossary: WISP is defined as 'a cellular network that provides regional, nationwide, and global mesh coverage'. That is closer to a WWAN. A WISP is a wireless internet service provider, an ISP that delivers service by radio.",
    "Glossary: Telnet is listed with no warning. Telnet sends everything, passwords included, in clear text; use SSH. FTP has the same flaw.",
    "Glossary: 'A network protocol is rules for data between devices in the same network' is too narrow. Protocols such as IP, TCP and HTTP work across networks.",
]
