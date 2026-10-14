"""Network protocol simulators for learning: switch learning and VLANs, spanning tree, OSPF shortest path,
BGP best path, ACL and NAT testers. Small models that show the rule used at each step."""
from __future__ import annotations

import heapq
import ipaddress
import re

from app.services.netlab import NetError

MAXL = 400


def _lines(text: str, what: str, lo: int = 1) -> list[str]:
    out = [l.split("#")[0].strip() for l in (text or "").splitlines()]
    out = [l for l in out if l]
    if len(out) < lo:
        raise NetError(f"Enter at least {lo} {what}.")
    if len(out) > MAXL:
        raise NetError(f"Keep it to {MAXL} lines.")
    return out


def _mac(t: str) -> str:
    h = re.sub(r"[^0-9a-fA-F]", "", t)
    if len(h) != 12:
        raise NetError(f"'{t}' is not a MAC address. Use 12 hex digits such as aa:bb:cc:00:00:01.")
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)).lower()


# ---------------------------------------------------------------- switch
def switch(ports: str, frames: str) -> dict:
    cfg: dict[str, tuple[str, set[int]]] = {}
    for l in _lines(ports, "port line"):
        p = l.split()
        if len(p) != 3 or p[1] not in ("access", "trunk"):
            raise NetError(f"Port line '{l}': use 'port access 10' or 'port trunk 10,20'.")
        try:
            v = {int(x) for x in p[2].split(",")}
        except ValueError:
            raise NetError(f"Port line '{l}': VLANs must be numbers.") from None
        if any(not 1 <= x <= 4094 for x in v) or (p[1] == "access" and len(v) != 1):
            raise NetError(f"Port line '{l}': an access port has one VLAN (1 to 4094).")
        cfg[p[0]] = (p[1], v)
    table: dict[tuple[int, str], str] = {}
    out = []
    for l in _lines(frames, "frame line"):
        p = l.split()
        if len(p) not in (3, 4):
            raise NetError(f"Frame line '{l}': use 'in_port source_mac dest_mac [vlan_tag]'.")
        inp = p[0]
        if inp not in cfg:
            raise NetError(f"Frame line '{l}': port {inp} is not configured.")
        kind, vl = cfg[inp]
        src, dst = _mac(p[1]), _mac(p[2])
        if int(src[:2], 16) & 1:
            raise NetError(f"Frame line '{l}': a source MAC cannot be a group address.")
        if kind == "access":
            vlan = next(iter(vl))
        else:
            if len(p) != 4:
                out.append({"frame": l, "action": "drop", "why": "Arrived on a trunk without a VLAN tag; this model drops it (a real trunk puts it in the native VLAN)."})
                continue
            vlan = int(p[3])
            if vlan not in vl:
                out.append({"frame": l, "action": "drop", "why": f"VLAN {vlan} is not allowed on trunk port {inp}."})
                continue
        learned = table.get((vlan, src)) != inp
        moved = (vlan, src) in table and table[(vlan, src)] != inp
        table[(vlan, src)] = inp
        members = sorted(k for k, (kd, v) in cfg.items() if vlan in v and k != inp)
        group = int(dst[:2], 16) & 1
        if not group and (vlan, dst) in table:
            tgt = table[(vlan, dst)]
            if tgt == inp:
                act, why = "filter", f"Destination is known on the same port ({inp}); the switch does not send it back."
            else:
                act, why = f"forward to {tgt}", f"Destination {dst} was learned on port {tgt} in VLAN {vlan}."
            outp = [tgt] if tgt != inp else []
        else:
            outp = members
            act = "flood to " + (", ".join(members) if members else "no ports")
            why = "Broadcast or multicast: sent to every port in the VLAN except the one it came in on." if group else f"Destination {dst} is not in the table yet (unknown unicast): flooded in VLAN {vlan} only."
        out.append({"frame": l, "vlan": vlan, "learned": ("moved" if moved else "new") if learned else "refreshed", "action": act, "out_ports": outp, "why": why})
    return {"steps": out, "table": [{"vlan": v, "mac": m, "port": p} for (v, m), p in sorted(table.items())],
            "lesson": "A switch learns the SOURCE address of every frame and uses the DESTINATION to choose where to send it. Unknown or broadcast frames flood, but only inside their own VLAN."}


SWITCH_SAMPLE = {"ports": "1 access 10\n2 access 10\n3 access 20\n4 trunk 10,20", "frames": "1 aa:00:00:00:00:01 ff:ff:ff:ff:ff:ff\n2 aa:00:00:00:00:02 aa:00:00:00:00:01\n1 aa:00:00:00:00:01 aa:00:00:00:00:02\n3 b2:00:00:00:00:03 aa:00:00:00:00:01\n4 cc:00:00:00:00:04 ff:ff:ff:ff:ff:ff 20"}


# ---------------------------------------------------------------- spanning tree
def stp(bridges: str, links: str) -> dict:
    br: dict[str, tuple[int, str]] = {}
    for l in _lines(bridges, "bridge line"):
        p = l.split()
        if len(p) != 3:
            raise NetError(f"Bridge line '{l}': use 'name priority mac'.")
        try:
            pr = int(p[1])
        except ValueError:
            raise NetError(f"Bridge line '{l}': priority must be a number.") from None
        if pr % 4096 or not 0 <= pr <= 61440:
            raise NetError(f"Bridge line '{l}': priority must be a multiple of 4096 from 0 to 61440.")
        if p[0] in br:
            raise NetError(f"Bridge '{p[0]}' is listed twice.")
        br[p[0]] = (pr, _mac(p[2]))
    if len(br) < 2:
        raise NetError("Give at least two bridges.")
    bid = {n: (v[0], v[1]) for n, v in br.items()}
    lk = []
    for l in _lines(links, "link line"):
        p = l.split()
        if len(p) != 3 or p[0] not in br or p[1] not in br or p[0] == p[1]:
            raise NetError(f"Link line '{l}': use 'bridgeA bridgeB cost' with two different known bridges.")
        try:
            c = int(p[2])
        except ValueError:
            raise NetError(f"Link line '{l}': cost must be a number.") from None
        if c < 1:
            raise NetError(f"Link line '{l}': cost must be 1 or more.")
        lk.append((p[0], p[1], c))
    root = min(bid, key=lambda n: bid[n])
    dist = {n: float("inf") for n in br}
    dist[root] = 0
    pq = [(0, root)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for a, b, c in lk:
            for x, y in ((a, b), (b, a)):
                if x == u and d + c < dist[y]:
                    dist[y] = d + c
                    heapq.heappush(pq, (dist[y], y))
    if any(v == float("inf") for v in dist.values()):
        raise NetError("Some bridges are not connected to the others.")
    rootport = {}
    for n in br:
        if n == root:
            continue
        cands = []
        for i, (a, b, c) in enumerate(lk):
            if n in (a, b):
                nb = b if a == n else a
                if dist[nb] + c == dist[n]:
                    cands.append((bid[nb], i, nb))
        cands.sort()
        rootport[n] = cands[0][1]
    roles = []
    for i, (a, b, c) in enumerate(lk):
        ends = {}
        for n, o in ((a, b), (b, a)):
            if rootport.get(n) == i:
                ends[n] = ("root", f"{n} reaches the root through this link at cost {dist[n]}.")
        des = None
        if len(ends) == 0:
            des = min((a, b), key=lambda n: (dist[n], bid[n]))
        elif len(ends) == 1:
            des = next(o for o in (a, b) if o not in ends)
        for n in (a, b):
            if n in ends:
                continue
            if n == des:
                ends[n] = ("designated", f"{n} has the lowest cost to the root on this segment ({dist[n]})" + ("" if dist[a] != dist[b] else "; costs tie, so the lower bridge ID wins") + ".")
            else:
                ends[n] = ("blocked", f"The other end of this link is designated with a better path, so {n} blocks to prevent a loop.")
        roles.append({"link": f"{a} - {b}", "cost": c, "ends": {n: {"role": r, "why": w} for n, (r, w) in ends.items()}})
    return {"root": root, "root_why": "Lowest bridge ID wins: priority first, then MAC address.", "root_cost": {n: dist[n] for n in br}, "links": roles,
            "blocked": sum(1 for r in roles for e in r["ends"].values() if e["role"] == "blocked"),
            "lesson": "Spanning tree elects one root, gives every other switch one path to it (the root port), picks one forwarding port per segment (designated), and blocks the rest to break loops."}


STP_SAMPLE = {"bridges": "SW1 32768 00:00:00:00:00:01\nSW2 32768 00:00:00:00:00:02\nSW3 32768 00:00:00:00:00:03", "links": "SW1 SW2 4\nSW2 SW3 4\nSW1 SW3 4"}


# ---------------------------------------------------------------- OSPF shortest path
def spf(links: str, source: str) -> dict:
    adj: dict[str, list[tuple[str, int]]] = {}
    for l in _lines(links, "link line", 1):
        p = l.split()
        if len(p) != 3:
            raise NetError(f"Link line '{l}': use 'routerA routerB cost'.")
        try:
            c = int(p[2])
        except ValueError:
            raise NetError(f"Link line '{l}': cost must be a number.") from None
        if not 1 <= c <= 65535:
            raise NetError(f"Link line '{l}': OSPF cost is 1 to 65535.")
        adj.setdefault(p[0], []).append((p[1], c))
        adj.setdefault(p[1], []).append((p[0], c))
    if source not in adj:
        raise NetError(f"Source router '{source}' is not in the links.")
    dist = {source: 0}
    prev: dict[str, set[str]] = {source: set()}
    pq = [(0, source)]
    done = set()
    steps = []
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        steps.append(f"Settle {u} at cost {d}.")
        for v, c in adj[u]:
            nd = d + c
            if v not in dist or nd < dist[v]:
                dist[v], prev[v] = nd, {u}
                heapq.heappush(pq, (nd, v))
                steps.append(f"  {v} via {u}: cost {nd}.")
            elif nd == dist[v] and u not in prev[v]:
                prev[v].add(u)
                steps.append(f"  {v} via {u}: cost {nd} (equal, so two equal-cost paths).")

    def paths(n):
        if n == source:
            return [[source]]
        return [p + [n] for q in sorted(prev[n]) for p in paths(q)]

    rows = []
    for n in sorted(dist):
        if n == source:
            continue
        ps = paths(n)
        rows.append({"to": n, "cost": dist[n], "paths": [" > ".join(p) for p in ps], "next_hops": sorted({p[1] for p in ps}), "ecmp": len(ps) > 1})
    return {"source": source, "routes": rows, "steps": steps,
            "lesson": "Every OSPF router has the same map and runs this same shortest-path calculation from itself. Equal costs give equal-cost paths that can share traffic."}


SPF_SAMPLE = {"links": "R1 R2 10\nR1 R3 10\nR2 R4 10\nR3 R4 10\nR4 R5 5", "source": "R1"}


# ---------------------------------------------------------------- BGP best path
_ORIGIN = {"igp": 0, "egp": 1, "incomplete": 2}


def bgp(routes: str) -> dict:
    rs = []
    for l in _lines(routes, "route line", 1):
        p = [x.strip() for x in l.split("|")]
        if len(p) != 9:
            raise NetError(f"Route '{l}': use 'name | weight | local_pref | as_path | origin | med | ebgp or ibgp | igp_metric | router_id'.")
        try:
            r = {"name": p[0], "weight": int(p[1]), "local_pref": int(p[2]), "as_path": p[3].split() if p[3] not in ("", "-") else [], "origin": p[4].lower(),
                 "med": int(p[5]), "type": p[6].lower(), "igp": int(p[7]), "rid": p[8]}
            r["as_len"] = len(r["as_path"])
            ipaddress.ip_address(r["rid"])
        except ValueError:
            raise NetError(f"Route '{l}': numbers must be whole numbers and the router id an IP address.") from None
        if r["origin"] not in _ORIGIN or r["type"] not in ("ebgp", "ibgp"):
            raise NetError(f"Route '{l}': origin is igp, egp or incomplete; type is ebgp or ibgp.")
        rs.append(r)
    if len(rs) < 2:
        raise NetError("Give at least two routes to the same prefix.")
    rules = [("Highest weight (Cisco-only, local to the router)", lambda r: -r["weight"]), ("Highest local preference", lambda r: -r["local_pref"]), ("Shortest AS path", lambda r: r["as_len"]),
             ("Lowest origin (IGP, then EGP, then incomplete)", lambda r: _ORIGIN[r["origin"]]), ("Lowest MED (normally compared only between routes from the same neighbor AS)", lambda r: r["med"]),
             ("Prefer eBGP over iBGP", lambda r: 0 if r["type"] == "ebgp" else 1), ("Lowest IGP metric to the next hop", lambda r: r["igp"]),
             ("Lowest router ID", lambda r: int(ipaddress.ip_address(r["rid"])))]
    alive = list(rs)
    log = []
    winner_rule = None
    for name, key in rules:
        best = min(key(r) for r in alive)
        keep = [r for r in alive if key(r) == best]
        if len(keep) < len(alive):
            log.append({"rule": name, "kept": [r["name"] for r in keep], "removed": [r["name"] for r in alive if r not in keep]})
            if len(keep) == 1 and winner_rule is None:
                winner_rule = name
        else:
            log.append({"rule": name, "kept": [r["name"] for r in alive], "removed": []})
        alive = keep
        if len(alive) == 1:
            break
    return {"best": alive[0]["name"], "decided_by": winner_rule, "steps": log,
            "note": "Real routers have a few more steps and vendor differences; the order here is the common one. MED is compared across all routes in this model.",
            "lesson": "BGP does not pick the shortest or fastest path. It walks an ordered list of tie-breakers, and the first rule that separates the routes decides."}


BGP_SAMPLE = {"routes": "A | 0 | 100 | 65001 65002 | igp | 0 | ebgp | 10 | 1.1.1.1\nB | 0 | 200 | 65003 65004 65005 | igp | 0 | ebgp | 10 | 2.2.2.2\nC | 0 | 100 | 65006 | igp | 0 | ibgp | 5 | 3.3.3.3"}


# ---------------------------------------------------------------- ACL
def _cidr(t: str):
    if t == "any":
        return ipaddress.ip_network("0.0.0.0/0")
    try:
        return ipaddress.ip_network(t if "/" in t else t + "/32", strict=False)
    except ValueError:
        raise NetError(f"'{t}' is not a network. Use any, 10.0.0.1 or 10.0.0.0/24.") from None


def _acl_rules(text: str):
    rules = []
    for l in _lines(text, "ACL line"):
        p = l.lower().split()
        if len(p) < 4 or p[0] not in ("permit", "deny") or p[1] not in ("ip", "tcp", "udp", "icmp"):
            raise NetError(f"ACL line '{l}': use 'permit|deny tcp|udp|icmp|ip source [eq port] destination [eq port]'.")
        i = 2
        src = _cidr(p[i]); i += 1
        sp = dp = None
        if i + 1 < len(p) and p[i] == "eq":
            sp = int(p[i + 1]); i += 2
        if i >= len(p):
            raise NetError(f"ACL line '{l}': the destination is missing.")
        dst = _cidr(p[i]); i += 1
        if i + 1 < len(p) and p[i] == "eq":
            dp = int(p[i + 1]); i += 2
        if i != len(p):
            raise NetError(f"ACL line '{l}': could not read the end of the line.")
        if (sp is not None or dp is not None) and p[1] not in ("tcp", "udp"):
            raise NetError(f"ACL line '{l}': ports only work with tcp or udp.")
        rules.append({"text": l, "action": p[0], "proto": p[1], "src": src, "dst": dst, "sp": sp, "dp": dp})
    return rules


def _hit(r, proto, s, d, sp, dp):
    return (r["proto"] in ("ip", proto)) and s in r["src"] and d in r["dst"] and (r["sp"] is None or r["sp"] == sp) and (r["dp"] is None or r["dp"] == dp)


def acl(rules: str, packets: str) -> dict:
    rl = _acl_rules(rules)
    out = []
    used = set()
    for l in _lines(packets, "packet line"):
        p = l.lower().split()
        if len(p) < 3 or p[0] not in ("tcp", "udp", "icmp"):
            raise NetError(f"Packet '{l}': use 'tcp|udp|icmp source_ip dest_ip [source_port dest_port]'.")
        try:
            s, d = ipaddress.ip_address(p[1]), ipaddress.ip_address(p[2])
            sp, dp = (int(p[3]), int(p[4])) if len(p) >= 5 else (None, None)
        except ValueError:
            raise NetError(f"Packet '{l}': check the addresses and ports.") from None
        hit = next((i for i, r in enumerate(rl) if _hit(r, p[0], s, d, sp, dp)), None)
        if hit is None:
            out.append({"packet": l, "result": "deny", "rule": "implicit deny at the end", "why": "No line matched. Every ACL ends with an invisible deny of everything."})
        else:
            used.add(hit)
            out.append({"packet": l, "result": rl[hit]["action"], "rule": f"line {hit + 1}: {rl[hit]['text']}", "why": "First matching line wins; later lines are not read."})
    warns = []
    for j, r in enumerate(rl):
        for i in range(j):
            e = rl[i]
            if e["proto"] in ("ip", r["proto"]) and r["src"].subnet_of(e["src"]) and r["dst"].subnet_of(e["dst"]) and (e["sp"] in (None, r["sp"])) and (e["dp"] in (None, r["dp"])):
                warns.append(f"Line {j + 1} ('{r['text']}') can never match: line {i + 1} ('{e['text']}') already catches everything it would." + ("" if e["action"] == r["action"] else " They disagree, so this is probably a mistake."))
                break
    return {"results": out, "warnings": warns, "unused_lines": [i + 1 for i in range(len(rl)) if i not in used],
            "lesson": "ACL lines are read top to bottom and the first match wins. Put specific lines before general ones. A real ACL also depends on which interface and direction it is applied to."}


ACL_SAMPLE = {"rules": "permit tcp 10.0.0.0/24 any eq 443\ndeny ip 10.0.0.0/24 any\npermit ip any any\ndeny tcp 10.0.0.5 any eq 23", "packets": "tcp 10.0.0.5 8.8.8.8 40000 443\ntcp 10.0.0.5 8.8.8.8 40001 23\nudp 10.0.0.9 1.1.1.1 5000 53\nicmp 192.168.1.1 10.0.0.1"}


# ---------------------------------------------------------------- NAT / PAT
def nat(inside: str, public_ip: str, flows: str) -> dict:
    try:
        inet = ipaddress.ip_network(inside, strict=False)
        pub = ipaddress.ip_address(public_ip)
    except ValueError:
        raise NetError("Check the inside network (192.168.1.0/24) and the public address.") from None
    if any(pub in ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")):
        raise NetError("The outside address of a NAT should be a public address, not a private one.")
    table: dict[tuple, int] = {}
    nxt = 1024
    rows = []
    for l in _lines(flows, "flow line"):
        p = l.lower().split()
        if len(p) != 5 or p[0] not in ("tcp", "udp"):
            raise NetError(f"Flow '{l}': use 'tcp|udp inside_ip inside_port outside_ip outside_port'.")
        try:
            ia, ip_, oa, op = ipaddress.ip_address(p[1]), int(p[2]), ipaddress.ip_address(p[3]), int(p[4])
        except ValueError:
            raise NetError(f"Flow '{l}': check the addresses and ports.") from None
        if ia not in inet:
            rows.append({"flow": l, "result": "not translated", "why": f"{ia} is not in the inside network {inet}; this NAT leaves it alone."})
            continue
        key = (p[0], str(ia), ip_)
        fresh = key not in table
        if fresh:
            table[key] = nxt
            nxt += 1
        rows.append({"flow": l, "result": f"{ia}:{ip_} becomes {pub}:{table[key]}", "new_entry": fresh, "why": "A new entry was made: PAT gives each inside address and port its own outside port." if fresh else "An existing entry is reused; replies to the outside port are mapped back to the inside host."})
    return {"flows": rows, "table": [{"proto": k[0], "inside": f"{k[1]}:{k[2]}", "outside": f"{pub}:{v}"} for k, v in table.items()],
            "limit": "A single public address has about 64,000 usable ports in total, so about 64,000 simultaneous translations per protocol and destination.",
            "lesson": "PAT (NAT overload) shares one public address by rewriting the source port. The table is what lets replies find their way back; inbound connections with no entry are dropped."}


NAT_SAMPLE = {"inside": "192.168.1.0/24", "public_ip": "203.0.113.5", "flows": "tcp 192.168.1.10 51000 93.184.216.34 443\ntcp 192.168.1.11 51000 93.184.216.34 443\ntcp 192.168.1.10 51000 93.184.216.34 443\nudp 10.9.9.9 4000 8.8.8.8 53"}

SLIPS = [
    "Many switch diagrams show a switch 'learning' by the destination address. It learns the SOURCE address of each frame and looks up the DESTINATION.",
    "Spanning tree guides often say the root is the fastest or the biggest switch. It is the one with the lowest bridge ID (priority, then MAC), whatever its speed.",
    "BGP is often described as choosing the 'shortest path'. AS-path length is only the third rule; weight and local preference come first.",
    "ACL examples that put 'permit ip any any' above a deny line make the deny dead code. Order matters: the first match wins.",
    "NAT tutorials say it 'hides' the network and so is a firewall. Translation is not a security control; the stateful filtering around it is.",
]
NOT_BUILT = ["A real switch, router or firewall; this is a model that shows the rules.", "Wireless, MPLS, multicast routing, OSPF areas and BGP policy beyond the common order.", "Live packet capture (needs the computer's network card; see the capture reader for saved files)."]


def reference() -> dict:
    return {"samples": {"switch": SWITCH_SAMPLE, "stp": STP_SAMPLE, "spf": SPF_SAMPLE, "bgp": BGP_SAMPLE, "acl": ACL_SAMPLE, "nat": NAT_SAMPLE}, "slips": SLIPS, "not_built": NOT_BUILT}
