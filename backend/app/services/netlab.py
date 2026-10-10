"""Network Engineer track: subnetting, config review, packet-capture reading, DNS and reachability checks, calculators and references.

Honest limits
* Subnet, VLSM and calculator results are exact arithmetic (Python's ipaddress module).
* The config review is a set of text-pattern checks on a pasted config (Cisco IOS style plus generic). It is not a CIS benchmark
  audit and can't know your design. A clean result means "none of these patterns matched".
* The capture reader parses `tcpdump -nn` TEXT lines. It reads text you paste; it never captures packets. Findings are leads.
* DNS here returns A/AAAA addresses only (use nslookup or dig for MX, TXT and others). TCP checks refuse private addresses and test
  ONE port per request: this is a diagnostic, not a port scanner.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import time
from collections import Counter, defaultdict

from app.services import security

MAX_TEXT = 400_000


class NetError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _net(text: str):
    try:
        return ipaddress.ip_network((text or "").strip(), strict=False)
    except ValueError:
        raise NetError("That isn't a valid network. Use CIDR like 192.168.10.0/24 or 2001:db8::/48.") from None


# ---------------------------------------------------------------- subnetting
def subnet(cidr: str) -> dict:
    n = _net(cidr)
    v4 = n.version == 4
    total = n.num_addresses
    if v4:
        usable = total if n.prefixlen == 32 else (2 if n.prefixlen == 31 else max(total - 2, 0))
        hosts = list(n.hosts()) if total <= 1024 else None
        first = str(n.network_address + 1) if n.prefixlen < 31 else str(n.network_address)
        last = str(n.broadcast_address - 1) if n.prefixlen < 31 else str(n.broadcast_address)
    else:
        usable, hosts, first, last = total, None, str(n.network_address), str(n.broadcast_address)
    ip = ipaddress.ip_address(str(n.network_address))
    out = {"input": cidr.strip(), "version": n.version, "network": str(n.network_address), "prefix": n.prefixlen, "netmask": str(n.netmask),
           "wildcard": str(n.hostmask), "broadcast": str(n.broadcast_address) if v4 else None, "first_host": first, "last_host": last,
           "total_addresses": total, "usable_hosts": usable,
           "scope": ("private" if n.is_private else "global"), "loopback": n.is_loopback, "link_local": n.is_link_local, "multicast": n.is_multicast,
           "class": None}
    if v4:
        b = int(ip) >> 24
        out["class"] = "A" if b < 128 else "B" if b < 192 else "C" if b < 224 else "D (multicast)" if b < 240 else "E (reserved)"
        out["netmask_binary"] = ".".join(f"{int(o):08b}" for o in str(n.netmask).split("."))
    out["note"] = "Classful ranges (A/B/C) are history; routing uses the prefix length. /31 is a point-to-point link; /32 is a single host." if v4 else \
                  "IPv6 subnets are normally /64 on a LAN. Hosts aren't counted because the ranges are enormous."
    return out


def split(cidr: str, new_prefix: int) -> dict:
    n = _net(cidr)
    maxp = 32 if n.version == 4 else 128
    if not isinstance(new_prefix, int) or new_prefix <= n.prefixlen or new_prefix > maxp:
        raise NetError(f"The new prefix must be longer than /{n.prefixlen} and at most /{maxp}.")
    if new_prefix - n.prefixlen > 8:
        raise NetError("That would make more than 256 subnets. Split by at most 8 bits at a time.")
    subs = [subnet(str(s)) for s in n.subnets(new_prefix=new_prefix)]
    return {"parent": str(n), "count": len(subs),
            "subnets": [{"network": f"{s['network']}/{s['prefix']}", "first_host": s["first_host"], "last_host": s["last_host"],
                         "broadcast": s["broadcast"], "usable_hosts": s["usable_hosts"]} for s in subs]}


def vlsm(base: str, needs: list[dict]) -> dict:
    n = _net(base)
    if n.version != 4:
        raise NetError("The VLSM planner is for IPv4.")
    if not needs or len(needs) > 50:
        raise NetError("Give between 1 and 50 subnets to plan.")
    reqs = []
    for i, r in enumerate(needs):
        try:
            hosts = int(r.get("hosts"))
        except (TypeError, ValueError):
            raise NetError(f"Row {i + 1}: hosts must be a whole number.") from None
        if not 1 <= hosts <= 2_000_000:
            raise NetError(f"Row {i + 1}: hosts must be between 1 and 2,000,000.")
        reqs.append({"name": (str(r.get("name") or f"Subnet {i + 1}"))[:40], "hosts": hosts})
    plan, cursor, end = [], int(n.network_address), int(n.broadcast_address)
    for r in sorted(reqs, key=lambda x: -x["hosts"]):
        need = r["hosts"] + 2                      # network and broadcast addresses, the classic subnetting rule
        bits = (need - 1).bit_length()
        prefix = 32 - bits
        size = 1 << bits
        start = -(-cursor // size) * size           # align up to the block size
        if start + size - 1 > end or prefix < n.prefixlen:
            raise NetError(f"{base} is too small: it ran out of room at '{r['name']}' ({r['hosts']} hosts). Use a bigger block or fewer hosts.")
        sn = ipaddress.ip_network((start, prefix))
        s = subnet(str(sn))
        plan.append({"name": r["name"], "hosts_needed": r["hosts"], "network": f"{s['network']}/{prefix}", "netmask": s["netmask"],
                     "first_host": s["first_host"], "last_host": s["last_host"], "broadcast": s["broadcast"], "usable_hosts": s["usable_hosts"],
                     "spare": s["usable_hosts"] - r["hosts"]})
        cursor = start + size
    used = cursor - int(n.network_address)
    return {"base": str(n), "plan": plan, "used_addresses": used, "free_addresses": n.num_addresses - used,
            "note": "Largest subnets are placed first and each one starts on its own boundary, which wastes the least space."}


def contains(cidr: str, ip: str) -> dict:
    n = _net(cidr)
    try:
        a = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        raise NetError("That isn't a valid IP address.") from None
    return {"network": str(n), "ip": str(a), "inside": a.version == n.version and a in n}


def overlaps(cidrs: list[str]) -> dict:
    nets = [_net(c) for c in cidrs[:60]]
    pairs = []
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            if nets[i].version == nets[j].version and nets[i].overlaps(nets[j]):
                pairs.append({"a": str(nets[i]), "b": str(nets[j]),
                              "relation": "identical" if nets[i] == nets[j] else ("a contains b" if nets[i].supernet_of(nets[j]) else "b contains a")})
    return {"checked": len(nets), "overlaps": pairs, "ok": not pairs}


def summarize(cidrs: list[str]) -> dict:
    nets = [_net(c) for c in cidrs[:200]]
    v4 = [n for n in nets if n.version == 4]
    v6 = [n for n in nets if n.version == 6]
    out = [str(n) for n in ipaddress.collapse_addresses(v4)] + [str(n) for n in ipaddress.collapse_addresses(v6)]
    return {"input_count": len(nets), "summary": out, "note": "Route summarisation: the fewest prefixes that cover exactly these networks (nothing extra)."}


# ---------------------------------------------------------------- config review
SAMPLE_CONFIG = """! Made-up switch config. Addresses are from the documentation ranges.
hostname SW-ACCESS-01
!
enable password cisco123
no service password-encryption
!
username admin privilege 15 password 0 letmein
!
snmp-server community public RO
snmp-server community private RW
ip http server
!
interface Vlan1
 ip address 192.0.2.10 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/1
 switchport mode access
 switchport access vlan 1
!
interface GigabitEthernet0/24
 description UPLINK to CORE
 switchport mode trunk
!
ip access-list extended ANY-ANY
 permit ip any any
!
line vty 0 4
 password cisco
 login
 transport input all
!
end
"""


def _blocks(text: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("!"):
            continue
        if raw[0] not in " \t":
            out.append((raw.strip(), []))
        elif out:
            out[-1][1].append(raw.strip())
    return out


def audit_config(text: str) -> dict:
    if not (text or "").strip():
        raise NetError("Paste a config first.")
    if len(text) > MAX_TEXT:
        raise NetError("That config is over 400 KB. Paste one device at a time.")
    blocks = _blocks(text)
    top = [h for h, _ in blocks]
    all_lines = top + [l for _, ls in blocks for l in ls]
    f: list[dict] = []

    def add(sev, title, detail, fix, evidence=None):
        f.append({"severity": sev, "title": title, "detail": detail, "fix": fix, "evidence": (evidence or [])[:5]})

    def hits(pat):
        r = re.compile(pat, re.I)
        return [l for l in all_lines if r.search(l)]

    if (h := hits(r"^enable password\b")):
        add("high", "Enable password stored without a strong hash", "'enable password' is plain text or a reversible type 7.", "Use 'enable secret' with a type 8 or 9 hash.", h)
    if (h := hits(r"^enable secret 5\b")):
        add("medium", "Enable secret uses the older type 5 (MD5)", "Type 5 is weak against modern cracking.", "Use 'enable algorithm-type scrypt secret ...' (type 9).", h)
    if (h := hits(r"\bpassword 0\b")) or (h := [l for l in all_lines if re.match(r"^password\s+\S+$", l, re.I) and not re.match(r"^password [57] ", l, re.I)]):
        add("high", "Clear-text passwords in the config", "Anyone who can read the config (or a backup of it) can read these.", "Use 'username ... secret' and 'service password-encryption' at minimum.", h)
    if (h := hits(r"\bpassword 7\b")):
        add("medium", "Type 7 passwords are reversible", "Type 7 is obfuscation, not encryption; online tools decode it instantly.", "Replace with 'secret' hashes.", h)
    if not any(re.match(r"^service password-encryption", l, re.I) for l in top):
        add("low", "service password-encryption is off", "It only obscures type 0 passwords, but it stops casual shoulder-surfing of the file.", "Add 'service password-encryption'.")
    if (h := hits(r"transport input (all|telnet)")):
        add("high", "Telnet is allowed on the remote-access lines", "Telnet sends everything, passwords included, in clear text.", "Use 'transport input ssh' and enable SSH version 2.", h)
    if (h := hits(r"ip ssh version 1\b")):
        add("high", "SSH version 1 is enabled", "SSHv1 has known weaknesses.", "Use 'ip ssh version 2'.", h)
    if (h := hits(r"snmp-server community (public|private)\b")):
        add("high", "Default SNMP community string", "'public' and 'private' are the first things anyone tries.", "Use SNMPv3 with authentication and encryption, or at least a long random string and an ACL.", h)
    if (h := hits(r"snmp-server community \S+ rw\b")):
        add("high", "SNMP write access", "A read-write community lets someone change the device.", "Remove RW or move to SNMPv3 with a restricted view.", h)
    if (h := hits(r"^ip http server\b")):
        add("medium", "Plain HTTP management server is on", "Web management over HTTP exposes credentials.", "Use 'no ip http server' and 'ip http secure-server' if you need the web UI.", h)
    if (h := hits(r"permit (ip )?any any\b")):
        add("medium", "An access list permits everything", "'permit ip any any' makes the list a no-op for what follows.", "Allow only the traffic you need and end with an explicit deny and logging.", h)
    if not any(re.match(r"^(logging host|logging \d|logging server)", l, re.I) for l in top):
        add("low", "No remote logging server", "Logs kept only on the device vanish on reboot or compromise.", "Add 'logging host <address>'.")
    if not any(re.match(r"^ntp server", l, re.I) for l in top):
        add("low", "No NTP server", "Without synced time, logs from different devices can't be lined up.", "Add 'ntp server <address>'.")
    if not any(re.match(r"^banner", l, re.I) for l in top):
        add("info", "No login banner", "A legal-notice banner is expected by many policies.", "Add 'banner login ...'.")
    if not any(re.match(r"^aaa new-model", l, re.I) for l in top):
        add("low", "AAA isn't enabled", "Centralised login (RADIUS/TACACS+) gives per-user accounts and logs.", "Consider 'aaa new-model' with a server and a local fallback.")
    trunks_open, no_desc, vlan1, no_ps = [], [], [], 0
    for h, ls in blocks:
        if not re.match(r"^interface (gigabit|fastethernet|tengigabit|ethernet|port-channel)", h, re.I):
            continue
        if "switchport mode trunk" in ls and not any(l.startswith("switchport trunk allowed vlan") for l in ls):
            trunks_open.append(h)
        if not any(l.startswith("description") for l in ls):
            no_desc.append(h)
        if "switchport access vlan 1" in ls:
            vlan1.append(h)
        if "switchport mode access" in ls and not any(l.startswith("switchport port-security") for l in ls):
            no_ps += 1
    if trunks_open:
        add("medium", "Trunks carry every VLAN", "No allowed-VLAN list, so any VLAN can cross the link.", "Add 'switchport trunk allowed vlan ...' with only what's needed.", trunks_open)
    if vlan1:
        add("low", "Access ports sit in VLAN 1", "VLAN 1 is the default and carries control traffic; mixing users into it is poor hygiene.", "Use a dedicated VLAN for users and leave VLAN 1 empty.", vlan1)
    if no_desc:
        add("info", f"{len(no_desc)} interface(s) without a description", "Descriptions are what you read at 2 a.m. during an outage.", "Add 'description <what is connected>'.", no_desc)
    if no_ps:
        add("info", f"{no_ps} access port(s) without port security", "Anyone can plug anything in.", "Consider 'switchport port-security' or 802.1X.")
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    f.sort(key=lambda x: order[x["severity"]])
    return {"lines": len(text.splitlines()), "blocks": len(blocks), "findings": f, "counts": dict(Counter(x["severity"] for x in f)),
            "caveat": "Pattern checks on text. They don't know your design, other devices or the CIS benchmark. 'No findings' means these patterns didn't match."}


# ---------------------------------------------------------------- packet capture text (tcpdump -nn)
SAMPLE_CAPTURE = """10:00:00.000100 IP 192.0.2.50.51234 > 198.51.100.10.443: Flags [S], seq 1, win 64240, length 0
10:00:00.020100 IP 198.51.100.10.443 > 192.0.2.50.51234: Flags [S.], seq 9, ack 2, win 65535, length 0
10:00:00.020300 IP 192.0.2.50.51234 > 198.51.100.10.443: Flags [.], ack 1, win 502, length 0
10:00:00.021000 IP 192.0.2.50.51234 > 198.51.100.10.443: Flags [P.], seq 1:518, ack 1, win 502, length 517
10:00:01.000000 IP 203.0.113.9.40001 > 192.0.2.50.22: Flags [S], seq 100, win 1024, length 0
10:00:01.000100 IP 203.0.113.9.40002 > 192.0.2.50.23: Flags [S], seq 101, win 1024, length 0
10:00:01.000200 IP 203.0.113.9.40003 > 192.0.2.50.80: Flags [S], seq 102, win 1024, length 0
10:00:01.000300 IP 203.0.113.9.40004 > 192.0.2.50.443: Flags [S], seq 103, win 1024, length 0
10:00:01.000400 IP 203.0.113.9.40005 > 192.0.2.50.3389: Flags [S], seq 104, win 1024, length 0
10:00:01.000500 IP 203.0.113.9.40006 > 192.0.2.50.3306: Flags [S], seq 105, win 1024, length 0
10:00:01.000600 IP 192.0.2.50.22 > 203.0.113.9.40001: Flags [R.], seq 0, ack 101, win 0, length 0
10:00:01.000700 IP 192.0.2.50.23 > 203.0.113.9.40002: Flags [R.], seq 0, ack 102, win 0, length 0
10:00:02.000000 ARP, Request who-has 192.0.2.1 tell 192.0.2.50, length 28
10:00:02.001000 ARP, Reply 192.0.2.1 is-at 00:00:5e:00:53:01, length 28
10:00:03.000000 IP 192.0.2.50 > 198.51.100.53: ICMP echo request, id 1, seq 1, length 64
10:00:03.030000 IP 198.51.100.53 > 192.0.2.50: ICMP echo reply, id 1, seq 1, length 64
10:00:04.000000 IP 192.0.2.50.53211 > 198.51.100.53.53: UDP, length 32
"""
_TCP = re.compile(r"IP\s+(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+):\s+Flags\s+\[([^\]]*)\]")
_UDP = re.compile(r"IP\s+(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+):\s+UDP")
_ICMP = re.compile(r"IP\s+(\d+\.\d+\.\d+\.\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+):\s+ICMP\s+(echo request|echo reply|[^,]+)")
_ARP = re.compile(r"ARP,\s+Request who-has\s+(\S+)\s+tell\s+(\S+)")
WELL_KNOWN = {20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 67: "DHCP", 80: "HTTP", 110: "POP3", 123: "NTP", 143: "IMAP", 161: "SNMP",
              389: "LDAP", 443: "HTTPS", 445: "SMB", 514: "Syslog", 587: "SMTP submission", 993: "IMAPS", 1433: "SQL Server", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 8080: "HTTP alt"}


def read_capture(text: str) -> dict:
    if not (text or "").strip():
        raise NetError("Paste some tcpdump -nn output first.")
    if len(text) > MAX_TEXT:
        raise NetError("That capture text is over 400 KB. Paste a smaller slice.")
    lines = [l for l in text.splitlines() if l.strip()]
    proto, src, dst_ports = Counter(), Counter(), Counter()
    syn_to, synack_from, rst = defaultdict(set), set(), Counter()
    arp_asks = defaultdict(set)
    parsed = 0
    for l in lines:
        if m := _TCP.search(l):
            s, sp, d, dp, flags = m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), m.group(5)
            parsed += 1
            proto["TCP"] += 1
            src[s] += 1
            if flags == "S":
                syn_to[s].add((d, dp))
                dst_ports[dp] += 1
            elif flags.startswith("S."):
                synack_from.add((s, sp))
            if "R" in flags:
                rst[s] += 1
        elif m := _UDP.search(l):
            parsed += 1
            proto["UDP"] += 1
            src[m.group(1)] += 1
            dst_ports[int(m.group(4))] += 1
        elif m := _ICMP.search(l):
            parsed += 1
            proto["ICMP"] += 1
            src[m.group(1)] += 1
        elif m := _ARP.search(l):
            parsed += 1
            proto["ARP"] += 1
            arp_asks[m.group(2)].add(m.group(1))
    if not parsed:
        raise NetError("No lines looked like `tcpdump -nn` output. Expected lines like: 10:00:00.1 IP 192.0.2.1.5000 > 192.0.2.2.443: Flags [S], ...")
    find = []
    for s, targets in syn_to.items():
        unanswered = [t for t in targets if t not in synack_from]
        ports = sorted({p for _, p in targets})
        if len(ports) >= 5:
            find.append({"severity": "medium", "title": f"{s} sent SYNs to {len(ports)} different ports",
                         "detail": f"{len(unanswered)} of {len(targets)} targets never answered with SYN-ACK. This is the shape of a port scan, but also of a monitoring tool or a misconfigured client.",
                         "advice": "Check whether {0} is yours. If not, block it and look at what it reached.".format(s), "evidence": [f"{d}:{p}" for d, p in sorted(targets)[:8]]})
    for s, n in rst.items():
        if n >= 5:
            find.append({"severity": "low", "title": f"{s} sent {n} resets (RST)", "detail": "Many resets mean a closed port, a firewall reject or an application that gave up.", "advice": "Find which service the peer expected.", "evidence": []})
    for s, asks in arp_asks.items():
        if len(asks) >= 10:
            find.append({"severity": "low", "title": f"{s} asked ARP for {len(asks)} different hosts", "detail": "Sweeping a subnet looks like this, as does a freshly booted host.", "advice": "Check the host.", "evidence": []})
    top_ports = [{"port": p, "service": WELL_KNOWN.get(p, ""), "syn_or_udp": n} for p, n in dst_ports.most_common(8)]
    return {"lines": len(lines), "parsed": parsed, "protocols": dict(proto), "top_sources": [{"ip": ip, "packets": n} for ip, n in src.most_common(8)],
            "top_dest_ports": top_ports, "handshakes_completed": len(synack_from), "findings": find,
            "caveat": "Leads, not verdicts. This reads text you paste; it doesn't capture packets. Use Wireshark or tcpdump on a network you own to make a capture."}


# ---------------------------------------------------------------- DNS and reachability
HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


def dns_lookup(host: str, resolver=socket.getaddrinfo) -> dict:
    host = (host or "").strip().lower().rstrip(".")
    if not HOST_RE.match(host):
        raise NetError("Enter a hostname like example.com (no http://, no path).")
    t0 = time.perf_counter()
    try:
        infos = resolver(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise NetError(f"Couldn't look up '{host}'. The name may not exist, or this computer has no DNS access.", 502) from None
    ms = round((time.perf_counter() - t0) * 1000, 1)
    seen, out = set(), []
    for fam, _, _, _, sa in infos:
        a = sa[0]
        if a in seen:
            continue
        seen.add(a)
        ip = ipaddress.ip_address(a)
        out.append({"address": a, "version": ip.version, "scope": "private" if ip.is_private else "public"})
    return {"host": host, "addresses": out, "lookup_ms": ms,
            "note": "A and AAAA records only (what the resolver returns for connecting). Use nslookup or dig for MX, TXT, NS and CNAME."}


def tcp_check(host: str, port: int, resolver=socket.getaddrinfo, connector=None, timeout: float = 4.0) -> dict:
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise NetError("Port must be a whole number from 1 to 65535.")
    try:
        ip = security.resolve_public(host.strip().lower(), resolver)
    except security.SecError as e:
        raise NetError(str(e), e.status) from e
    t0 = time.perf_counter()
    try:
        s = (connector or socket.create_connection)((ip, port), timeout)
        s.close()
        state = "open"
    except socket.timeout:
        state = "filtered or no answer"
    except ConnectionRefusedError:
        state = "closed"
    except OSError as e:
        state = f"unreachable ({type(e).__name__})"
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {"host": host.strip().lower(), "ip": ip, "port": port, "service": WELL_KNOWN.get(port, ""), "state": state, "ms": ms,
            "note": "One TCP connection attempt. 'open' means a handshake completed. 'filtered' usually means a firewall dropped it. Only public addresses are allowed, one port at a time."}


# ---------------------------------------------------------------- calculators
def transfer_time(size_gb: float, mbps: float, efficiency_pct: float = 85.0) -> dict:
    for name, v, lo, hi in (("size", size_gb, 0.000001, 1e7), ("bandwidth", mbps, 0.001, 1e6), ("efficiency", efficiency_pct, 1, 100)):
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise NetError(f"{name} is out of range.")
    bits = size_gb * 8 * 1000 ** 3
    eff_bps = mbps * 1e6 * efficiency_pct / 100
    sec = bits / eff_bps
    return {"seconds": round(sec, 1), "human": _dur(sec), "effective_mbps": round(mbps * efficiency_pct / 100, 2),
            "note": "Size uses decimal GB (1 GB = 1000^3 bytes) like network gear. Efficiency covers protocol overhead and contention; real links vary."}


def bdp(mbps: float, rtt_ms: float, window_kb: float = 64.0) -> dict:
    for name, v, lo, hi in (("bandwidth", mbps, 0.001, 1e6), ("round-trip time", rtt_ms, 0.01, 5000), ("window", window_kb, 1, 1e6)):
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise NetError(f"{name} is out of range.")
    bdp_bytes = mbps * 1e6 / 8 * (rtt_ms / 1000)
    cap = window_kb * 1024 * 8 / (rtt_ms / 1000) / 1e6
    return {"bdp_bytes": round(bdp_bytes), "bdp_kb": round(bdp_bytes / 1024, 1), "window_limited_mbps": round(min(cap, mbps), 2),
            "window_is_the_limit": cap < mbps,
            "advice": ("The TCP window is smaller than the pipe: one stream can't fill the link. Enable window scaling or use parallel streams." if cap < mbps
                       else "The window is big enough to fill this link at this latency."),
            "note": "Bandwidth-delay product = how many bytes are 'in flight' on a full link. Throughput can't exceed window / round-trip time."}


def _dur(sec: float) -> str:
    if sec < 90:
        return f"{sec:.0f} seconds"
    if sec < 5400:
        return f"{sec / 60:.1f} minutes"
    if sec < 172800:
        return f"{sec / 3600:.1f} hours"
    return f"{sec / 86400:.1f} days"


# ---------------------------------------------------------------- reference
PORTS = [
    (20, "TCP", "FTP data", "Plain text. Prefer SFTP."), (21, "TCP", "FTP control", "Plain text. Prefer SFTP."), (22, "TCP", "SSH / SFTP", "Remote admin. Use keys, not passwords."),
    (23, "TCP", "Telnet", "Clear text. Replace with SSH."), (25, "TCP", "SMTP", "Server-to-server mail."), (53, "TCP/UDP", "DNS", "Name resolution."),
    (67, "UDP", "DHCP server", "Hands out addresses."), (68, "UDP", "DHCP client", ""), (69, "UDP", "TFTP", "No authentication. Config transfers only."),
    (80, "TCP", "HTTP", "Redirect to HTTPS."), (110, "TCP", "POP3", "Use 995 (TLS)."), (123, "UDP", "NTP", "Time sync."), (135, "TCP", "Windows RPC", "Don't expose."),
    (137, "UDP", "NetBIOS name", "Legacy."), (139, "TCP", "NetBIOS session", "Legacy."), (143, "TCP", "IMAP", "Use 993 (TLS)."), (161, "UDP", "SNMP", "Use v3."),
    (162, "UDP", "SNMP traps", ""), (389, "TCP/UDP", "LDAP", "Directory. Use 636 (LDAPS) or StartTLS."), (443, "TCP", "HTTPS", ""), (445, "TCP", "SMB", "Windows file sharing. Never expose to the internet."),
    (465, "TCP", "SMTPS", ""), (514, "UDP", "Syslog", "Unencrypted logs."), (587, "TCP", "SMTP submission", "Mail clients send here."), (636, "TCP", "LDAPS", ""),
    (993, "TCP", "IMAPS", ""), (995, "TCP", "POP3S", ""), (1433, "TCP", "SQL Server", "Keep off the internet."), (1521, "TCP", "Oracle", ""),
    (3306, "TCP", "MySQL", "Keep off the internet."), (3389, "TCP", "RDP", "A top ransomware entry point. Use a VPN."), (5432, "TCP", "PostgreSQL", "Keep off the internet."),
    (5900, "TCP", "VNC", "Weak by default."), (8080, "TCP", "HTTP alt", "Proxies and dev servers."),
]
OSI = [
    (7, "Application", "HTTP, DNS, SMTP, SSH", "What the user's program speaks", "Wrong URL, bad certificate, app timeouts"),
    (6, "Presentation", "TLS, encodings", "Format, encryption, compression", "Certificate or cipher mismatch"),
    (5, "Session", "Sessions, RPC", "Starting and ending conversations", "Dropped sessions, NAT timeouts"),
    (4, "Transport", "TCP, UDP", "Ports, reliability, flow control", "Firewall blocks a port, resets, retransmits"),
    (3, "Network", "IP, ICMP, routing", "Addressing and routing between networks", "Wrong gateway, no route, overlapping subnets"),
    (2, "Data link", "Ethernet, VLANs, ARP, Wi-Fi", "Frames on one link or segment", "VLAN mismatch, duplex mismatch, loops"),
    (1, "Physical", "Cables, fibre, radio", "Bits on the wire", "Bad cable, dead port, interference"),
]
COMMANDS = {
    "Windows (cmd / PowerShell)": [
        ("ipconfig /all", "Addresses, gateway, DNS servers and MAC for every adapter"), ("ipconfig /flushdns", "Clear the local DNS cache"),
        ("ping 8.8.8.8", "Is there a path at all? Try the gateway, then an IP, then a name"), ("tracert example.com", "Hops to a destination"),
        ("nslookup example.com", "Ask the configured DNS server"), ("netstat -ano", "Connections and listening ports with process IDs"),
        ("arp -a", "IP to MAC table on this machine"), ("route print", "The routing table"), ("Test-NetConnection example.com -Port 443", "PowerShell: TCP test to one port"),
        ("Get-NetIPConfiguration", "PowerShell: adapter summary"), ("netsh wlan show interfaces", "Wi-Fi signal, channel and speed"),
    ],
    "Linux / macOS": [
        ("ip addr", "Interfaces and addresses (macOS: ifconfig)"), ("ip route", "Routing table and default gateway"), ("ss -tulpn", "Listening ports and the program behind them"),
        ("dig example.com +short", "DNS lookup"), ("traceroute example.com", "Hops to a destination"), ("mtr example.com", "Traceroute and ping combined, live"),
        ("curl -I https://example.com", "Headers only: status, redirects, TLS"), ("tcpdump -nn -i eth0 port 53", "Capture DNS traffic (needs sudo; your own network only)"),
        ("iperf3 -c server", "Throughput test against an iperf3 server you run"), ("nmcli device status", "NetworkManager view of interfaces"),
    ],
    "Cisco IOS (read-only)": [
        ("show ip interface brief", "Every interface: address and up/down state"), ("show running-config", "The active configuration"), ("show ip route", "Routing table"),
        ("show vlan brief", "VLANs and their ports"), ("show interfaces trunk", "Trunk ports and allowed VLANs"), ("show mac address-table", "Which MAC is behind which port"),
        ("show cdp neighbors", "Directly connected Cisco devices"), ("show spanning-tree", "Root bridge and port roles"), ("show logging", "Recent device logs"),
        ("show arp", "IP to MAC table"),
    ],
}


def reference() -> dict:
    return {"ports": [{"port": p, "proto": pr, "service": s, "note": n} for p, pr, s, n in PORTS],
            "osi": [{"layer": a, "name": b, "examples": c, "job": d, "typical_faults": e} for a, b, c, d, e in OSI],
            "commands": {k: [{"cmd": c, "what": w} for c, w in v] for k, v in COMMANDS.items()},
            "method": ["Define the symptom: who, what, since when?", "Layer 1-2: link lights, cable, VLAN.", "Layer 3: can you ping your gateway, then an outside IP?",
                       "Name resolution: does the IP work but the name fail? It's DNS.", "Layer 4: is the port reachable (Test-NetConnection / tcp check)?",
                       "Application: certificates, proxies, the app's own logs.", "Change one thing at a time and write down what you changed."]}
