"""Build and check a dnsmasq config for a small DHCP + DNS server (the Linux lab server in many IT courses).

Text in, text out. Nothing is installed or started. The generator validates every address against the subnet, so a typo
becomes an error here instead of a server that silently refuses to hand out leases.
"""
from __future__ import annotations

import ipaddress
import re

MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", re.I)
HOST = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.I)
DOMAIN = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$|^[a-z0-9-]{1,63}$", re.I)
LEASE = re.compile(r"^(\d{1,5}[smhdw]?|infinite)$", re.I)
IFACE = re.compile(r"^[A-Za-z0-9_.:-]{1,15}$")


class DnsmasqError(ValueError):
    pass


def _ip(v, what):
    try:
        return ipaddress.IPv4Address(str(v).strip())
    except ValueError as e:
        raise DnsmasqError(f"{what} '{str(v)[:40]}' is not a valid IPv4 address.") from e


def _lease_seconds(s: str) -> int | None:
    s = s.lower()
    if s == "infinite":
        return None
    m = re.fullmatch(r"(\d+)([smhdw]?)", s)
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[m.group(2)]


def generate(f: dict) -> dict:
    """f: interface, subnet (CIDR), gateway, range_start, range_end, lease, domain, dns (list), upstream (list),
    reservations [{mac, ip, host}], records [{name, ip}], authoritative, log_queries, cache_size, no_resolv."""
    if not isinstance(f, dict):
        raise DnsmasqError("Send the settings as an object.")
    try:
        net = ipaddress.IPv4Network(str(f.get("subnet", "")).strip(), strict=False)
    except ValueError as e:
        raise DnsmasqError("Give the subnet in CIDR form, for example 192.168.50.0/24.") from e
    if net.prefixlen > 29 or net.prefixlen < 16:
        raise DnsmasqError("Use a subnet between /16 and /29 so there is room for a range and a server.")
    iface = str(f.get("interface", "")).strip()
    if iface and not IFACE.fullmatch(iface):
        raise DnsmasqError("Interface names are letters, digits, dot, dash, colon or underscore, up to 15 characters (for example eth0 or enp0s3).")
    hosts = list(net.hosts())
    gw = _ip(f["gateway"], "Gateway") if f.get("gateway") else hosts[0]
    server = _ip(f["server_ip"], "Server address") if f.get("server_ip") else gw
    for a, name in ((gw, "Gateway"), (server, "Server address")):
        if a not in net or a in (net.network_address, net.broadcast_address):
            raise DnsmasqError(f"{name} {a} is not a usable address in {net}.")
    start = _ip(f["range_start"], "Range start") if f.get("range_start") else hosts[min(99, len(hosts) // 2)] if len(hosts) > 100 else hosts[len(hosts) // 3]
    end = _ip(f["range_end"], "Range end") if f.get("range_end") else hosts[-1] if len(hosts) <= 100 else hosts[min(len(hosts) - 1, 199)]
    for a, name in ((start, "Range start"), (end, "Range end")):
        if a not in net or a in (net.network_address, net.broadcast_address):
            raise DnsmasqError(f"{name} {a} is not a usable address in {net}.")
    if int(start) > int(end):
        raise DnsmasqError("The range start must come before the range end.")
    lease = str(f.get("lease", "12h")).strip() or "12h"
    if not LEASE.fullmatch(lease):
        raise DnsmasqError("Lease time is a number with s, m, h, d or w (for example 12h or 1d), or 'infinite'.")
    domain = str(f.get("domain", "")).strip()
    if domain and not DOMAIN.fullmatch(domain):
        raise DnsmasqError("The domain should look like lab.local or example.com.")
    dns = [str(x).strip() for x in (f.get("dns") or []) if str(x).strip()]
    dns_ips = [_ip(x, "DNS server") for x in dns]
    upstream = [_ip(x, "Upstream DNS server") for x in (f.get("upstream") or []) if str(x).strip()]
    warnings: list[str] = []
    notes: list[str] = []
    if int(start) <= int(gw) <= int(end):
        warnings.append(f"The gateway {gw} is inside the dynamic range, so it could be handed to a client. Move the range or the gateway.")
    if int(start) <= int(server) <= int(end):
        warnings.append(f"This server's own address {server} is inside the dynamic range. Keep fixed addresses outside it.")
    secs = _lease_seconds(lease)
    if secs is not None and secs < 120:
        warnings.append("Leases under 2 minutes cause constant renewals. 1 to 24 hours suits most small networks.")
    if secs is None:
        warnings.append("Infinite leases never free an address, so a range fills up and stays full.")
    size = int(end) - int(start) + 1
    if size < 5:
        warnings.append(f"The range holds only {size} addresses.")

    res, seen_mac, seen_ip, seen_host, res_lines = [], set(), set(), set(), []
    for i, r in enumerate(f.get("reservations") or [], 1):
        if not isinstance(r, dict):
            raise DnsmasqError(f"Reservation {i} should have a mac, an ip and a host name.")
        mac = str(r.get("mac", "")).strip().lower().replace("-", ":")
        if not MAC.fullmatch(mac):
            raise DnsmasqError(f"Reservation {i}: '{str(r.get('mac', ''))[:30]}' is not a MAC address (six pairs like aa:bb:cc:dd:ee:ff).")
        ip = _ip(r.get("ip"), f"Reservation {i} address")
        if ip not in net or ip in (net.network_address, net.broadcast_address):
            raise DnsmasqError(f"Reservation {i}: {ip} is not a usable address in {net}.")
        host = str(r.get("host", "")).strip()
        if host and not HOST.fullmatch(host):
            raise DnsmasqError(f"Reservation {i}: host name '{host[:30]}' may only use letters, digits and dashes.")
        if mac in seen_mac:
            raise DnsmasqError(f"Reservation {i}: the MAC {mac} appears twice.")
        if ip in seen_ip or ip in (gw, server):
            raise DnsmasqError(f"Reservation {i}: {ip} is already used by another reservation, the gateway or this server.")
        if host and host.lower() in seen_host:
            raise DnsmasqError(f"Reservation {i}: the host name {host} appears twice.")
        seen_mac.add(mac), seen_ip.add(ip)
        if host:
            seen_host.add(host.lower())
        res_lines.append(f"dhcp-host={mac}{',' + host if host else ''},{ip}")
        res.append({"mac": mac, "ip": str(ip), "host": host})
    rec_lines = []
    for i, r in enumerate(f.get("records") or [], 1):
        if not isinstance(r, dict) or not str(r.get("name", "")).strip():
            raise DnsmasqError(f"DNS record {i} needs a name and an address.")
        name = str(r["name"]).strip().lower()
        if not DOMAIN.fullmatch(name):
            raise DnsmasqError(f"DNS record {i}: '{name[:40]}' is not a valid name.")
        rec_lines.append(f"host-record={name},{_ip(r.get('ip'), f'DNS record {i} address')}")

    L = ["# Generated by the practice app. Review it, then test with: dnsmasq --test --conf-file=<file>", ""]
    if iface:
        L += [f"interface={iface}", "bind-interfaces"]
    else:
        notes.append("No interface set: dnsmasq will listen on every interface. Name one (interface=eth0) so it does not offer leases on the wrong network.")
        warnings.append("No interface chosen: dnsmasq may answer DHCP on every network this machine is connected to.")
    L += [f"listen-address=127.0.0.1,{server}"] if iface else []
    L += ["", "# DHCP", f"dhcp-range={start},{end},{net.netmask},{lease}", f"dhcp-option=option:router,{gw}"]
    L.append("dhcp-option=option:dns-server," + (",".join(str(x) for x in dns_ips) if dns_ips else str(server)))
    if domain:
        L += [f"domain={domain}", "expand-hosts"]
    if f.get("authoritative", True):
        L.append("dhcp-authoritative")
    if res_lines:
        L += ["", "# Fixed addresses (reservations)"] + res_lines
    L += ["", "# DNS"]
    if f.get("no_resolv") or upstream:
        L.append("no-resolv")
    L += [f"server={u}" for u in upstream] if upstream else ["# no upstream set: dnsmasq will use /etc/resolv.conf"]
    cache = f.get("cache_size", 150)
    if not isinstance(cache, int) or isinstance(cache, bool) or not 0 <= cache <= 10000:
        raise DnsmasqError("Cache size is a whole number from 0 to 10000.")
    L.append(f"cache-size={cache}")
    L += rec_lines
    if f.get("log_queries"):
        L += ["", "# Logging (turn off when finished: it is noisy)", "log-queries", "log-dhcp"]
    cfg = "\n".join(L) + "\n"
    if not any(x for x in dns_ips if x != server) and not upstream:
        notes.append("Clients are told to use this server for DNS, and it forwards using the machine's own resolver. Check that works with: dig @" + str(server) + " example.com")
    return {
        "config": cfg, "network": str(net), "usable_hosts": len(hosts), "range_size": size, "gateway": str(gw), "server": str(server),
        "reservations": res, "warnings": warnings, "notes": notes,
        "commands": [f"sudo cp dnsmasq.conf /etc/dnsmasq.d/lab.conf", "dnsmasq --test", "sudo systemctl restart dnsmasq", "sudo systemctl status dnsmasq --no-pager",
                     f"sudo ss -ulpn | grep -E ':(53|67)\\b'", f"dig @{server} example.com", "sudo journalctl -u dnsmasq -f   # watch DISCOVER / OFFER / REQUEST / ACK", "sudo dhclient -v <client-interface>   # on a test client"],
        "pitfalls": ["Port 53 already in use: on Ubuntu, systemd-resolved listens on 127.0.0.53. Either stop its stub listener (DNSStubListener=no in /etc/systemd/resolved.conf) or let dnsmasq bind only your LAN address (bind-interfaces, which this config sets).",
                     "Run only one DHCP server on a network. A router's DHCP plus yours gives clients random answers.",
                     "A firewall must allow UDP 67 (DHCP) and UDP/TCP 53 (DNS) on the server.",
                     "Reservations matched by MAC only work if the client does not randomise its MAC (phones often do on Wi-Fi)."],
        "lesson": "dnsmasq does DHCP and a small DNS cache/forwarder in one process. The four DHCP steps are Discover, Offer, Request, Acknowledge; the journal shows each one, which is the fastest way to see where a client got stuck.",
        "limit": "Generates and validates text only. It does not check that the interface exists, that port 53 is free, or that another DHCP server is on the network.",
    }


def check(text: str) -> dict:
    """Read a pasted dnsmasq.conf and point out the problems that stop leases or confuse clients."""
    if not isinstance(text, str) or not text.strip():
        raise DnsmasqError("Paste a dnsmasq config first.")
    if len(text) > 100_000:
        raise DnsmasqError("That config is too long to check (100,000 characters at most).")
    problems: list[dict] = []
    add = lambda lvl, ln, msg: problems.append({"level": lvl, "line": ln, "message": msg})  # noqa: E731
    ranges, hosts, ifaces, opts, macs, ips = [], [], [], set(), {}, {}
    authoritative = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key == "dhcp-range":
            parts = [p.strip() for p in val.split(",")]
            parts = [p for p in parts if not p.startswith("set:") and not p.startswith("tag:")]
            try:
                a, b = ipaddress.IPv4Address(parts[0]), ipaddress.IPv4Address(parts[1])
            except (ValueError, IndexError):
                add("error", n, "dhcp-range needs a start and an end address: dhcp-range=192.168.50.100,192.168.50.200,255.255.255.0,12h")
                continue
            if int(a) > int(b):
                add("error", n, "The range start is after the range end.")
            mask = parts[2] if len(parts) > 2 and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", parts[2]) else None
            lease = parts[-1] if len(parts) > 2 and LEASE.fullmatch(parts[-1]) else None
            if not lease:
                add("warn", n, "No lease time given: dnsmasq will use its default of one hour.")
            ranges.append((a, b, mask, n))
        elif key == "dhcp-host":
            m = re.search(r"([0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})", val, re.I)
            ip = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", val)
            if not m:
                add("warn", n, "This dhcp-host line has no MAC address; it matches by name or ID instead.")
            else:
                mac = m.group(1).lower().replace("-", ":")
                if mac in macs:
                    add("error", n, f"MAC {mac} already has a reservation on line {macs[mac]}.")
                macs[mac] = n
            if ip:
                try:
                    a = ipaddress.IPv4Address(ip.group(1))
                    if str(a) in ips:
                        add("error", n, f"Address {a} is already reserved on line {ips[str(a)]}.")
                    ips[str(a)] = n
                    hosts.append((a, n))
                except ValueError:
                    add("error", n, f"'{ip.group(1)}' is not a valid IPv4 address.")
        elif key in ("interface", "listen-address"):
            ifaces.append(val)
        elif key == "dhcp-authoritative":
            authoritative = True
        elif key == "dhcp-option":
            opts.add(val.split(",")[0].replace("option:", "").strip())
        elif key == "server" and not re.fullmatch(r"(/[^/]+/)?[\d.]+(#\d+)?|/[^/]+/", val):
            add("warn", n, "This 'server=' line does not look like an upstream DNS address.")
    if not ranges:
        add("warn", 0, "No dhcp-range, so this server hands out no addresses (it is DNS only).")
    for a, b, mask, ln in ranges:
        if mask:
            try:
                net = ipaddress.IPv4Network(f"{a}/{mask}", strict=False)
                if b not in net:
                    add("error", ln, f"The range end {b} is outside {net}: start and end must be in the same subnet.")
            except ValueError:
                add("error", ln, f"'{mask}' is not a valid netmask.")
    for (a1, b1, _, l1), (a2, b2, _, l2) in zip(ranges, ranges[1:]):
        if int(a1) <= int(b2) and int(a2) <= int(b1):
            add("error", l2, f"This range overlaps the range on line {l1}.")
    if ranges and "router" not in opts and "3" not in opts:
        add("warn", 0, "No default gateway is offered (dhcp-option=option:router,<gateway>). Clients get an address but cannot leave the subnet.")
    if ranges and "dns-server" not in opts and "6" not in opts:
        add("info", 0, "No dns-server option: clients will be told to use this machine for DNS. That is fine if dnsmasq is also your DNS server.")
    if ranges and not ifaces:
        add("warn", 0, "No interface or listen-address: dnsmasq will answer on every interface it can see.")
    if ranges and not authoritative:
        add("info", 0, "Without dhcp-authoritative, a client that remembers an old lease from another server may wait before it gets a new one.")
    errs = sum(1 for p in problems if p["level"] == "error")
    warns = sum(1 for p in problems if p["level"] == "warn")
    return {"ranges": len(ranges), "reservations": len(macs), "problems": problems, "errors": errs, "warnings": warns,
            "verdict": "Fix the errors first." if errs else ("Usable, with things to review." if warns else "No problems found by this check."),
            "limit": "Reads the text only. The real test is dnsmasq --test, then watching the journal while a client asks for an address."}


SAMPLE_CHECK = """interface=eth0
dhcp-range=192.168.50.100,192.168.50.200,255.255.255.0,12h
dhcp-range=192.168.50.150,192.168.50.250,255.255.255.0,12h
dhcp-host=aa:bb:cc:dd:ee:01,printer,192.168.50.20
dhcp-host=aa:bb:cc:dd:ee:01,scanner,192.168.50.21
dhcp-host=aa:bb:cc:dd:ee:02,nas,192.168.50.20
server=1.1.1.1
"""
