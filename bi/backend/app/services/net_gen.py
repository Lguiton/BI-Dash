"""Network config generators and checkers: VLANs, trunks, router-on-a-stick, loopbacks, route selection.
Text in, text out: nothing here touches a device. Generated configs are for labs (Packet Tracer, GNS3, EVE-NG)
and for learning the shape of a config; read every line before pasting it anywhere that matters."""
import ipaddress
import re


class GenError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


PORT_RE = re.compile(r"^[A-Za-z][A-Za-z-]*\d+(/\d+){0,3}$")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
RESERVED = range(1002, 1006)          # legacy Token Ring / FDDI VLANs, cannot be used or deleted


def _vid(v, what="VLAN id") -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise GenError(f"{what} must be a whole number from 1 to 4094.") from None
    if not 1 <= n <= 4094:
        raise GenError(f"{what} {n} is out of range: VLAN ids run from 1 to 4094 (0 and 4095 are reserved).")
    if n in RESERVED:
        raise GenError(f"{what} {n} is reserved (1002 to 1005 are legacy Token Ring and FDDI VLANs).")
    return n


def _port(p, what="Port") -> str:
    p = str(p).strip()
    if not PORT_RE.match(p):
        raise GenError(f"{what} '{p[:20]}' doesn't look like an interface name. Use forms like fa0/1 or g0/1.")
    return p


def _mask(net: ipaddress.IPv4Network) -> str:
    return str(net.netmask)


def vlan_plan(vlans: list[dict], trunk_port: str = "g0/1", router_port: str = "g0/0", native: int = 1, allowed: list[int] | None = None,
              style: str = "roas", encapsulation_line: bool = False, loopback: str | None = None, router_name: str = "R1", switch_name: str = "S1") -> dict:
    if not isinstance(vlans, list) or not 1 <= len(vlans) <= 20:
        raise GenError("Give 1 to 20 VLANs, each with id, name, subnet and ports.")
    if style not in ("roas", "svi"):
        raise GenError("style must be roas (router on a stick) or svi (Layer 3 switch).")
    trunk_port, router_port = _port(trunk_port, "Trunk port"), _port(router_port, "Router port")
    nat = _vid(native, "Native VLAN")
    rows, ids, used_ports, warns, nets = [], set(), {}, [], []
    for i, v in enumerate(vlans, 1):
        vid = _vid(v.get("id"), f"VLAN {i} id")
        if vid in ids:
            raise GenError(f"VLAN {vid} appears twice.")
        ids.add(vid)
        name = str(v.get("name", "")).strip()
        if not NAME_RE.match(name):
            raise GenError(f"VLAN {vid}: name must be 1 to 32 letters, digits, - or _ (no spaces).")
        try:
            net = ipaddress.ip_network(str(v.get("subnet", "")).strip(), strict=False)
        except ValueError:
            raise GenError(f"VLAN {vid}: '{str(v.get('subnet'))[:30]}' isn't a valid subnet like 192.168.10.0/24.") from None
        if net.version != 4 or net.prefixlen > 30:
            raise GenError(f"VLAN {vid}: use an IPv4 subnet of /30 or larger so there is room for hosts and a gateway.")
        if str(v.get("subnet", "")).strip().split("/")[0] != str(net.network_address):
            warns.append(f"VLAN {vid}: {v.get('subnet')} has host bits set; used {net} instead.")
        for other_id, other in nets:
            if net.overlaps(other):
                raise GenError(f"VLAN {vid} subnet {net} overlaps VLAN {other_id} subnet {other}. Each VLAN needs its own range.")
        nets.append((vid, net))
        gw = v.get("gateway")
        try:
            gwip = ipaddress.ip_address(str(gw).strip()) if gw else next(net.hosts())
        except ValueError:
            raise GenError(f"VLAN {vid}: gateway '{str(gw)[:30]}' isn't an IP address.") from None
        if gwip not in net or gwip in (net.network_address, net.broadcast_address):
            raise GenError(f"VLAN {vid}: gateway {gwip} must be a usable address inside {net}.")
        ports = []
        for p in v.get("ports") or []:
            p = _port(p, f"VLAN {vid} port")
            if p.lower() == trunk_port.lower():
                raise GenError(f"{p} is the trunk port; it can't also be an access port for VLAN {vid}.")
            if p.lower() in used_ports:
                raise GenError(f"{p} is assigned to VLAN {used_ports[p.lower()]} and VLAN {vid}. A port is in one access VLAN.")
            used_ports[p.lower()] = vid
            ports.append(p)
        rows.append({"id": vid, "name": name, "net": net, "gw": gwip, "ports": ports})
    allow = sorted(set(allowed)) if allowed else sorted(ids | ({nat} if nat in ids else set()))
    for a in allow:
        _vid(a, "Allowed VLAN")
    missing = [r["id"] for r in rows if r["id"] not in allow]
    if missing:
        warns.append(f"VLAN {', '.join(map(str, missing))} is not in the trunk's allowed list, so its traffic will never reach the router.")
    if nat == 1:
        warns.append("Native VLAN is the default VLAN 1. Untagged traffic and several control protocols ride it; best practice is an unused VLAN on both ends of every trunk.")
    elif nat not in ids:
        warns.append(f"Native VLAN {nat} has no subnet here. That is fine (it carries untagged frames only) but it must match on both ends.")
    if any(1 == r["id"] for r in rows):
        warns.append("A user VLAN with id 1 is the default VLAN. Use another id for user traffic.")
    sw = [f"{switch_name}# configure terminal"]
    for r in rows:
        sw += [f"{switch_name}(config)# vlan {r['id']}", f"{switch_name}(config-vlan)# name {r['name']}", f"{switch_name}(config-vlan)# exit"]
    if nat not in ids and nat != 1:
        sw += [f"{switch_name}(config)# vlan {nat}", f"{switch_name}(config-vlan)# name NATIVE-UNUSED", f"{switch_name}(config-vlan)# exit"]
    for r in rows:
        for p in r["ports"]:
            sw += [f"{switch_name}(config)# interface {p}", f"{switch_name}(config-if)# switchport mode access", f"{switch_name}(config-if)# switchport access vlan {r['id']}", f"{switch_name}(config-if)# exit"]
    sw.append(f"{switch_name}(config)# interface {trunk_port}")
    if encapsulation_line:
        sw.append(f"{switch_name}(config-if)# switchport trunk encapsulation dot1q")
    sw += [f"{switch_name}(config-if)# switchport mode trunk", f"{switch_name}(config-if)# switchport trunk allowed vlan {','.join(map(str, allow))}"]
    if nat != 1:
        sw.append(f"{switch_name}(config-if)# switchport trunk native vlan {nat}")
    sw += [f"{switch_name}(config-if)# exit", f"{switch_name}(config)# end", f"{switch_name}# copy running-config startup-config"]
    rt = [f"{router_name}# configure terminal"]
    if style == "roas":
        rt += [f"{router_name}(config)# interface {router_port}", f"{router_name}(config-if)# no shutdown", f"{router_name}(config-if)# exit"]
        for r in rows:
            sub = f"{router_port}.{r['id']}"
            rt += [f"{router_name}(config)# interface {sub}", f"{router_name}(config-subif)# encapsulation dot1Q {r['id']}", f"{router_name}(config-subif)# ip address {r['gw']} {_mask(r['net'])}", f"{router_name}(config-subif)# exit"]
        if nat != 1 or nat in ids:
            warns.append(f"On the router, if VLAN {nat} must carry untagged traffic, configure its subinterface as 'encapsulation dot1Q {nat} native' (or leave the physical interface for it).")
        rt += [f"{router_name}(config)# end"]
    else:
        rt = [f"{switch_name}(config)# ip routing"]
        for r in rows:
            rt += [f"{switch_name}(config)# interface vlan {r['id']}", f"{switch_name}(config-if)# ip address {r['gw']} {_mask(r['net'])}", f"{switch_name}(config-if)# no shutdown", f"{switch_name}(config-if)# exit"]
        rt.append(f"{switch_name}(config)# end")
        warns.append("In SVI mode the Layer 3 switch routes, so there is no router and no trunk to one. The 'router' block above is added to the switch.")
    lo = []
    if loopback:
        try:
            lip = ipaddress.ip_address(str(loopback).strip())
        except ValueError:
            raise GenError(f"Loopback '{str(loopback)[:30]}' isn't an IP address.") from None
        if lip.version != 4:
            raise GenError("Loopback must be IPv4 here.")
        if any(lip in r["net"] for r in rows):
            raise GenError(f"Loopback {lip} falls inside a VLAN subnet. Use an address that belongs to no other interface, such as 1.1.1.1 in a lab or 10.255.255.1.")
        lo = [f"{router_name}(config)# interface loopback0", f"{router_name}(config-if)# ip address {lip} 255.255.255.255", f"{router_name}(config-if)# no shutdown", f"{router_name}(config-if)# exit",
              "! A loopback is up as long as the device is. Another router can only ping it if it has a route to it (static, OSPF, EIGRP...)."]
    verify = {"switch": ["show vlan brief", "show interfaces trunk", f"show interfaces {trunk_port} switchport"],
              "router": (["show ip interface brief", "show ip route connected", f"show interfaces {router_port}.{rows[0]['id']}"] if style == "roas" else ["show ip interface brief", "show ip route connected"]) + (["show ip interface brief | include Loopback"] if loopback else [])}
    return {"style": style, "switch_config": sw, "router_config": rt, "loopback_config": lo, "verify": verify, "warnings": warns,
            "hosts": [{"vlan": r["id"], "subnet": str(r["net"]), "gateway": str(r["gw"]), "mask": _mask(r["net"]), "first_host": next((str(h) for h in r["net"].hosts() if h != r["gw"]), None)} for r in rows],
            "lesson": "Router-on-a-stick: one physical router link carries every VLAN as tagged frames. The router has one subinterface per VLAN, and each subinterface's address is that VLAN's default gateway. Traffic between VLANs goes up the trunk, is routed, and comes back down the same cable, so that single link is the bottleneck.",
            "limit": "A generator, not a simulator: it does not model the devices. Some switch models (for example the 2960) have no 'switchport trunk encapsulation' command because they only support 802.1Q; that line is optional here. Older Layer 3 switches need it before 'mode trunk'."}


# ------------------------------------------------------------------ trunk check
def _expand(s: str) -> set[int] | None:
    """'10,20,30-32' -> {..}.  None means all VLANs."""
    s = s.strip().lower()
    if s in ("all", ""):
        return None
    out: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            a, b = int(m[1]), int(m[2])
            if b - a > 4094:
                raise GenError("A VLAN range is too large.")
            out |= set(range(a, b + 1))
        elif part.isdigit():
            out.add(int(part))
        else:
            raise GenError(f"I can't read the VLAN list '{s[:40]}'.")
    return out


def parse_switch(text: str) -> dict:
    if not (text or "").strip():
        raise GenError("Paste both switch configs.")
    if len(text) > 200_000:
        raise GenError("That config is over 200 KB. Paste the interface and VLAN parts only.", 413)
    vlans, ifaces, cur = {}, {}, None
    cur_vlan = None
    for raw in text.splitlines():
        line = re.sub(r"^\S+(?:\([^)]*\))?#\s*", "", raw.strip())
        if not line or line.startswith("!"):
            continue
        low = line.lower()
        m = re.match(r"^vlan (\d+)$", low)
        if m:
            cur_vlan, cur = int(m[1]), None
            vlans.setdefault(cur_vlan, "")
            continue
        m = re.match(r"^name (\S+)$", line, re.I)
        if m and cur_vlan is not None:
            vlans[cur_vlan] = m[1]
            continue
        m = re.match(r"^interface (\S+)$", line, re.I)
        if m:
            cur, cur_vlan = m[1].lower(), None
            ifaces.setdefault(cur, {"mode": None, "allowed": None, "native": 1, "access": 1, "encap": None})
            continue
        if cur and low.startswith("switchport"):
            d = ifaces[cur]
            if m := re.match(r"^switchport mode (access|trunk|dynamic auto|dynamic desirable)$", low):
                d["mode"] = m[1]
            elif m := re.match(r"^switchport trunk allowed vlan (?:(add|remove|except|none) )?(.+)$", low):
                op, lst = m[1], m[2]
                if op == "none":
                    d["allowed"] = set()
                elif op == "add":
                    d["allowed"] = None if d["allowed"] is None else (d["allowed"] | (_expand(lst) or set()))
                elif op == "remove" or op == "except":
                    d["allowed"] = d["allowed"] if d["allowed"] is not None else set(range(1, 4095))
                    d["allowed"] = (d["allowed"] - (_expand(lst) or set())) if op == "remove" else (set(range(1, 4095)) - (_expand(lst) or set()))
                else:
                    d["allowed"] = _expand(lst)
            elif m := re.match(r"^switchport trunk native vlan (\d+)$", low):
                d["native"] = int(m[1])
            elif m := re.match(r"^switchport access vlan (\d+)$", low):
                d["access"] = int(m[1])
            elif low.startswith("switchport trunk encapsulation"):
                d["encap"] = low.split()[-1]
    return {"vlans": vlans, "ifaces": ifaces}


def trunk_check(a: str, b: str, iface_a: str = "", iface_b: str = "") -> dict:
    A, B = parse_switch(a), parse_switch(b)

    def pick(P, name, label):
        trunks = {k: v for k, v in P["ifaces"].items() if v["mode"] in ("trunk", "dynamic desirable", "dynamic auto")}
        if name:
            k = name.strip().lower()
            if k not in P["ifaces"]:
                raise GenError(f"{label}: interface '{name[:20]}' not found in the pasted config.")
            return k, P["ifaces"][k]
        if len(trunks) == 1:
            k = next(iter(trunks))
            return k, trunks[k]
        raise GenError(f"{label}: found {len(trunks)} trunk-capable interfaces; name the one that faces the other switch.")
    ka, da = pick(A, iface_a, "Switch A")
    kb, db = pick(B, iface_b, "Switch B")
    out, ok = [], True

    def add(sev, title, detail):
        nonlocal ok
        if sev in ("bad", "warn"):
            ok = ok and sev != "bad"
        out.append({"severity": sev, "title": title, "detail": detail})
    ma, mb = da["mode"], db["mode"]
    both_auto = ma == "dynamic auto" and mb == "dynamic auto"
    if "access" in (ma, mb) or ma is None or mb is None:
        add("bad", "No trunk will form", f"A is {ma or 'default (dynamic auto or access, by model)'} and B is {mb or 'default'}. Set 'switchport mode trunk' on both ends, or make one end dynamic desirable.")
    elif both_auto:
        add("bad", "Both ends are dynamic auto", "Dynamic auto waits to be asked and so does the other side: the link stays an access port. Set one end to trunk or dynamic desirable.")
    else:
        add("ok", "Trunk modes can form a trunk", f"A: {ma}, B: {mb}.")
        if "dynamic desirable" in (ma, mb):
            add("info", "Dynamic trunking (DTP) is in use", "DTP negotiates automatically and can be abused; fixed 'mode trunk' plus 'switchport nonegotiate' is the safer lab-to-production habit.")
    if da["native"] != db["native"]:
        add("bad", "Native VLAN mismatch", f"A uses VLAN {da['native']} and B uses VLAN {db['native']}. Untagged frames land in different VLANs and Cisco switches log a CDP native VLAN mismatch. Make both ends the same.")
    else:
        add("ok", "Native VLAN matches", f"Both ends use VLAN {da['native']}.")
    if da["encap"] and db["encap"] and da["encap"] != db["encap"]:
        add("bad", "Encapsulation mismatch", f"A: {da['encap']}, B: {db['encap']}. Use dot1q on both.")
    al_a, al_b = da["allowed"], db["allowed"]
    if al_a != al_b:
        only_a = sorted((al_a if al_a is not None else set(range(1, 4095))) - (al_b if al_b is not None else set(range(1, 4095))))
        only_b = sorted((al_b if al_b is not None else set(range(1, 4095))) - (al_a if al_a is not None else set(range(1, 4095))))
        show = lambda x: ", ".join(map(str, x[:12])) + (" ..." if len(x) > 12 else "")
        add("bad", "Allowed VLAN lists differ", f"Allowed only on A: {show(only_a) or 'none'}. Allowed only on B: {show(only_b) or 'none'}. A VLAN must be allowed on both ends or its traffic stops at the link.")
    else:
        add("ok", "Allowed VLAN lists match", "all VLANs" if al_a is None else f"VLANs {', '.join(map(str, sorted(al_a)))}")
    if al_a is None and al_b is None:
        add("warn", "Trunk carries every VLAN", "No allowed list on either end. Limit it to the VLANs that need to cross.")
    need = sorted((al_a if al_a is not None else set(A["vlans"])) & (al_b if al_b is not None else set(B["vlans"])))
    for vid in need:
        if vid in (1, 1002, 1003, 1004, 1005):
            continue
        ma_, mb_ = vid in A["vlans"], vid in B["vlans"]
        if ma_ != mb_:
            add("bad", f"VLAN {vid} is defined on only one switch", f"{'A' if ma_ else 'B'} has 'vlan {vid}', the other doesn't. A VLAN must exist in each switch's database to forward traffic (or use VTP, which has its own risks).")
    for vid in sorted(set(A["vlans"]) & set(B["vlans"])):
        if A["vlans"][vid] != B["vlans"][vid]:
            add("warn", f"VLAN {vid} has different names", f"A: '{A['vlans'][vid]}', B: '{B['vlans'][vid]}'. Not a fault, but confusing at 2 am.")
    return {"a": ka, "b": kb, "ok": ok, "findings": out,
            "lesson": "A trunk works only when both ends agree on mode, native VLAN and allowed VLANs, and when each VLAN exists on both switches. Most 'VLAN 20 can't reach VLAN 20 on the other switch' tickets are one of these four.",
            "limit": "Reads pasted text only. It doesn't see live state (check 'show interfaces trunk'), STP blocking, cabling or speed/duplex."}


# ------------------------------------------------------------------ route selection
AD = {"connected": 0, "static": 1, "ebgp": 20, "eigrp": 90, "ospf": 110, "isis": 115, "rip": 120, "eigrp-external": 170, "ibgp": 200}


def route_select(routes: list[dict], destination: str) -> dict:
    try:
        dest = ipaddress.ip_address(str(destination).strip())
    except ValueError:
        raise GenError("Destination must be an IP address such as 10.1.2.3.") from None
    if not isinstance(routes, list) or not 1 <= len(routes) <= 40:
        raise GenError("Give 1 to 40 candidate routes.")
    cands = []
    for i, r in enumerate(routes, 1):
        try:
            net = ipaddress.ip_network(str(r.get("prefix", "")).strip(), strict=False)
        except ValueError:
            raise GenError(f"Route {i}: '{str(r.get('prefix'))[:30]}' isn't a prefix like 10.0.0.0/8.") from None
        proto = str(r.get("protocol", "")).strip().lower()
        if r.get("ad") not in (None, ""):
            try:
                ad = int(r["ad"])
            except (TypeError, ValueError):
                raise GenError(f"Route {i}: administrative distance must be a number from 0 to 255.") from None
            if not 0 <= ad <= 255:
                raise GenError(f"Route {i}: administrative distance must be 0 to 255.")
        elif proto in AD:
            ad = AD[proto]
        else:
            raise GenError(f"Route {i}: protocol '{proto[:15]}' unknown. Use one of {', '.join(AD)} or give an AD.")
        try:
            metric = float(r.get("metric", 0) or 0)
        except (TypeError, ValueError):
            raise GenError(f"Route {i}: metric must be a number.") from None
        cands.append({"i": i, "net": net, "proto": proto or f"AD {ad}", "ad": ad, "metric": metric, "via": str(r.get("next_hop", ""))[:40], "matches": net.version == dest.version and dest in net})
    matching = [c for c in cands if c["matches"]]
    if not matching:
        return {"destination": str(dest), "winner": None, "table": _table(cands, None), "steps": ["No route contains this destination. With no default route (0.0.0.0/0) the packet is dropped and the router replies 'destination unreachable'."], "lesson": ROUTE_LESSON}
    longest = max(c["net"].prefixlen for c in matching)
    pool = [c for c in matching if c["net"].prefixlen == longest]
    steps = [f"{len(matching)} route(s) contain {dest}. The most specific prefix wins first: /{longest}."]
    if len(pool) > 1:
        best_ad = min(c["ad"] for c in pool)
        pool2 = [c for c in pool if c["ad"] == best_ad]
        steps.append(f"{len(pool)} routes share /{longest}, so the lowest administrative distance (most trusted source) decides: AD {best_ad}.")
        pool = pool2
        if len(pool) > 1:
            best_m = min(c["metric"] for c in pool)
            pool = [c for c in pool if c["metric"] == best_m]
            steps.append(f"Same AD, so the lowest metric wins: {best_m:g}." + (" Equal metrics let OSPF/EIGRP load-balance across the routes (ECMP)." if len(pool) > 1 else ""))
    else:
        steps.append("Only one route has that prefix length, so administrative distance and metric aren't even consulted.")
    return {"destination": str(dest), "winner": [c["i"] for c in pool], "table": _table(cands, {c["i"] for c in pool}), "steps": steps, "lesson": ROUTE_LESSON}


ROUTE_LESSON = ("Order of decisions: 1) longest prefix match, 2) lowest administrative distance among routes for that same prefix, 3) lowest metric within one protocol. "
                "Administrative distance never overrides a more specific prefix: a /24 from RIP beats a /16 from OSPF for an address in the /24.")


def _table(cands, winners):
    return [{"route": c["i"], "prefix": str(c["net"]), "protocol": c["proto"], "ad": c["ad"], "metric": c["metric"], "via": c["via"], "contains_destination": c["matches"], "selected": bool(winners and c["i"] in winners)} for c in cands]


# ------------------------------------------------------------------ cable chooser
CABLES = [
    ("Cat 5e", 100, "1 Gbps at 100 m", "UTP", "Fine for 1 Gbps and PoE; cheapest."),
    ("Cat 6", 250, "1 Gbps at 100 m; 10 Gbps only to about 37 to 55 m (depends on crosstalk)", "UTP or shielded", "The usual office and home choice."),
    ("Cat 6a", 500, "10 Gbps at 100 m", "Shielded or unshielded", "The practical 10 Gbps cable for a full-length run."),
    ("Cat 7", 600, "10 Gbps at 100 m", "S/FTP", "Defined by ISO/IEC (class F), not recognised by TIA. Uses GG45 or TERA connectors; ending it in an RJ45 plug is outside the standard. Cat 6a is almost always the better buy."),
    ("Cat 8", 2000, "25 or 40 Gbps up to 30 m", "S/FTP", "Short data-centre runs between switches and servers only."),
]


def cable_pick(speed_gbps: float, distance_m: float, emi: bool = False) -> dict:
    try:
        sp, d = float(speed_gbps), float(distance_m)
    except (TypeError, ValueError):
        raise GenError("Speed and distance must be numbers.") from None
    if not 0.1 <= sp <= 40:
        raise GenError("Speed must be between 0.1 and 40 Gbps.")
    if not 1 <= d <= 100:
        raise GenError("Twisted pair runs up to 100 m; use fibre beyond that.")
    if sp <= 1:
        pick, why = "Cat 5e or Cat 6", "Either carries 1 Gbps to 100 m. Pick Cat 6 if the price gap is small."
    elif sp <= 10:
        if d <= 37:
            pick, why = "Cat 6", "Cat 6 carries 10 Gbps for short runs (about 37 m, up to 55 m in good conditions). Cat 6a removes the doubt."
        else:
            pick, why = "Cat 6a", "10 Gbps over more than about 55 m needs Cat 6a."
    elif sp <= 40:
        pick, why = ("Cat 8", "25 or 40 Gbps over copper is Cat 8 and only to 30 m.") if d <= 30 else ("Fibre", "Copper can't do this speed at this distance.")
    else:
        pick, why = "Fibre", "Beyond 40 Gbps use fibre."
    if emi and pick not in ("Fibre",):
        why += " In a high-interference place (motors, welders, heavy power) use shielded cable that is properly grounded at both ends, or fibre, which ignores interference."
    return {"pick": pick, "why": why, "table": [{"type": n, "mhz": m, "speed": s, "shielding": sh, "note": note} for n, m, s, sh, note in CABLES]}


# ------------------------------------------------------------------ reference
DEVICES = [
    ("Hub", "1", "Repeats every bit to every port", "One collision domain and one broadcast domain for all ports. Obsolete."),
    ("Repeater", "1", "Regenerates the signal", "Extends distance; no filtering."),
    ("Bridge", "2", "Learns MAC addresses and filters between two segments", "Splits collision domains."),
    ("Switch", "2 (3 if multilayer)", "Forwards by MAC address per port; VLANs", "Each port is its own collision domain; broadcast domain per VLAN."),
    ("Wireless access point", "1 and 2", "Bridges Wi-Fi clients to the wired LAN", "Joins one wireless and one wired medium into one network."),
    ("Wireless controller", "management", "Configures and coordinates many access points", "Central roaming, channels, power and policy."),
    ("Router", "3", "Forwards between networks by IP address", "Each interface is its own broadcast domain."),
    ("Firewall", "3 to 7", "Allows or blocks traffic by rule (address, port, state, application)", "Sits at a boundary between trust zones."),
    ("IDS / IPS", "3 to 7", "IDS detects and alerts; IPS sits in line and can block", "An IDS watching a copy of traffic can't stop anything."),
    ("Load balancer", "4 or 7", "Spreads requests across several servers and removes dead ones", "Improves availability and capacity."),
    ("Proxy server", "7", "Acts for a client when it requests web content; can filter and cache", "A reverse proxy does the same for servers."),
    ("Modem", "1", "Converts between the ISP's medium (cable, DSL, fibre ONT) and Ethernet", "Many home 'routers' combine modem, router, switch and access point."),
]
DORA = [
    ("Discover", "client to all", "0.0.0.0:68 to 255.255.255.255:67", "Broadcast: the client has no address and doesn't know the server."),
    ("Offer", "server to client", "server:67 to client", "Unicast to the client's MAC and offered address, or broadcast if the client asked for broadcast replies. Not always a broadcast."),
    ("Request", "client to all", "0.0.0.0:68 to 255.255.255.255:67", "Broadcast so that every server hears which offer was chosen and withdraws the others."),
    ("Acknowledge", "server to client", "server:67 to client", "Unicast or broadcast, as for the Offer. The lease starts here."),
]
PROTOCOLS = [
    ("OSPF", "Link-state", "Open (IETF)", "Cost (from bandwidth)", "110", "224.0.0.5 / 224.0.0.6", "Dijkstra SPF", "Large enterprises; areas keep the database small."),
    ("EIGRP", "Advanced distance-vector", "Cisco-originated; basic function published as RFC 7868", "Composite of bandwidth and delay (by default)", "90 internal, 170 external", "224.0.0.10", "DUAL", "Cisco-centred networks; unequal-cost load balancing."),
    ("BGP", "Path-vector", "Open (IETF)", "Path attributes (AS path, local preference, MED...)", "20 eBGP, 200 iBGP", "none: unicast TCP port 179", "Best-path selection by attributes", "Between organisations and ISPs; policy rather than speed."),
    ("RIP", "Distance-vector", "Open (IETF)", "Hop count (max 15)", "120", "224.0.0.9 (v2)", "Bellman-Ford", "Tiny labs only."),
]
SLIPS = [
    "Loopback poster, ping example: 'Success rate is 10% percent (5/5)' should read 100 percent. Five of five replies is 100 percent.",
    "Loopback poster: R1 and R2 only configure interfaces and loopbacks, with no static route or routing protocol. R1 would not reach 2.2.2.2: the ping needs a route to it (for example 'ip route 2.2.2.2 255.255.255.255 10.0.0.2'), otherwise the reply is '.....'.",
    "Loopback poster: 'always up' is true while the device runs and the interface isn't shut down; and a loopback address isn't always /32 (it is a good habit for router IDs).",
    "VLAN poster and trunk lab: the commands 'switchport trunk encapsulation dot1q' fail on switches that only support 802.1Q (such as the 2960); older Layer 3 switches require it. The poster doesn't say which.",
    "Router-on-a-stick poster: the router interface commands show masks cut off at the edge of the image ('255.255.255.0'), and the native VLAN isn't mentioned, although 'Native VLAN' appears on the VLAN poster.",
    "Trunk lab poster: the 'show interfaces trunk' sample shows Mode 'on' and Native VLAN 1; best practice is a non-default native VLAN, set the same on both switches.",
    "DHCP poster: the key points say Discover, Request and Acknowledge are broadcasts, while its packet tables show the Offer to 255.255.255.255 too. Offer and Acknowledge are usually unicast to the client, or broadcast only when the client's broadcast flag is set.",
    "OSPF/EIGRP/BGP poster: 'EIGRP: Cisco proprietary' is dated; Cisco published the base protocol as RFC 7868 (2016), though some features and most implementations remain Cisco's.",
    "Cat 6 vs Cat 7 poster: omits Cat 6a, the cable most 10 Gbps runs use. Cat 7 isn't a TIA category, and the GG45 connector needed for its full performance is not RJ45. The 'future-proofing' line oversells it.",
    "Cat 6 vs Cat 7 poster: the Cat 6 'Max speed 1 Gbps (10 Gbps up to 55 m)' row is a mix of two things; 10 Gbps on Cat 6 is a short-run result that depends on noise.",
    "Network devices poster: a 'Modem' is shown as converting digital and analog data; fibre and cable service converts between signal types, and many home boxes combine modem, router, switch and access point, so the single-purpose list hides that.",
]
NOT_BUILT = ["Packet Tracer, GNS3 and EVE-NG simulation. The generators and checkers prepare you to type the commands into one.", "Live router or switch access: nothing here connects to a device."]


def reference() -> dict:
    return {"devices": [{"device": a, "layer": b, "does": c, "note": d} for a, b, c, d in DEVICES],
            "dora": [{"step": a, "direction": b, "addresses": c, "note": d} for a, b, c, d in DORA],
            "protocols": [{"name": a, "type": b, "standard": c, "metric": d, "ad": e, "multicast": f, "algorithm": g, "use": h} for a, b, c, d, e, f, g, h in PROTOCOLS],
            "admin_distance": [{"source": k, "ad": v} for k, v in AD.items()],
            "loopback": ["A software interface that is up while the device is up and has no cable to fail.", "Used for a stable router ID, management addresses and as the source of routing sessions.", "Usually a /32. A ping to your own loopback proves only the local IP stack."],
            "slips": SLIPS, "not_built": NOT_BUILT}
