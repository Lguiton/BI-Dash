"""IT operations practice tools: storage risk, backup and disaster recovery, load balancing and web troubleshooting.

  raid_risk    - what a RAID rebuild really risks (unrecoverable read errors, exposure window), level by level
  backup_plan  - full, incremental and differential schemes compared: space, restore chain, restore time, data-loss window
  dr_check     - check each system's recovery time and recovery point against what its backups can actually deliver
  lb_sim       - watch round robin, weighted, least-connections and IP-hash balancing spread (and fail to spread) load
  http_status  - look up a status code: who is at fault, likely causes, what to check first
  site_triage  - from what you observed, find the failing layer (DNS, connection, TLS, HTTP) and the next command
  access_log   - summarize a web server access log: status mix, error paths, noisy clients, probing

Honest limits: arithmetic and simulations with the numbers you enter. Nothing here touches a disk, a server or a
network. Failure rates are manufacturer figures and real arrays differ; the load balancer simulation is a simple
model, not nginx, HAProxy or a cloud load balancer.
"""
from __future__ import annotations

import heapq
import math
import random
import re
from collections import Counter


class OpsError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _n(v, name, lo, hi, integer=False):
    if isinstance(v, bool):
        raise OpsError(f"{name} must be a number.")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise OpsError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise OpsError(f"{name} must be between {lo:g} and {hi:g}.")
    return int(x) if integer else x


# ------------------------------------------------------------------ RAID rebuild risk
RAID_RULES = {  # level: (min disks, write penalty, guaranteed failures survived, note)
    "0": (2, 1, 0, "No redundancy: any failure loses everything."),
    "1": (2, 2, 1, "Mirror: survives all but one copy."),
    "5": (3, 4, 1, "Single parity: during a rebuild every other disk must read perfectly."),
    "6": (4, 6, 2, "Double parity: survives a second failure or a read error during a rebuild."),
    "10": (4, 2, 1, "Striped mirrors: survives one failure per pair, but a second failure in the SAME pair loses the array."),
}


def raid_risk(level, disks, size_tb, ure_exponent=14, rebuild_mb_s=100, afr_pct=2.0) -> dict:
    lv = str(level).lower().replace("raid", "").strip()
    if lv not in RAID_RULES:
        raise OpsError("Level must be 0, 1, 5, 6 or 10.")
    n = _n(disks, "Disks", 2, 64, True); size = _n(size_tb, "Disk size (TB)", 0.1, 100)
    ure = _n(ure_exponent, "Read-error exponent (14 means 1 error per 10^14 bits)", 12, 18, True)
    speed = _n(rebuild_mb_s, "Rebuild speed (MB/s)", 1, 5000); afr = _n(afr_pct, "Annual failure rate (%)", 0.1, 20)
    mn, pen, tol, note = RAID_RULES[lv]
    if n < mn:
        raise OpsError(f"RAID {lv} needs at least {mn} disks.")
    if lv == "10" and n % 2:
        raise OpsError("RAID 10 needs an even number of disks.")
    usable = {"0": n * size, "1": size, "5": (n - 1) * size, "6": (n - 2) * size, "10": n // 2 * size}[lv]
    # data that must be read perfectly to rebuild one failed disk
    read_tb = {"0": 0, "1": size, "5": (n - 1) * size, "6": (n - 1) * size, "10": size}[lv]
    bits = read_tb * 1e12 * 8
    p_ure = 0.0 if read_tb == 0 else 1 - math.exp(-bits / (10 ** ure))
    hours = size * 1e6 / speed / 3600
    # chance a second disk in the exposed set also fails during the rebuild window
    exposed = {"0": 0, "1": 1, "5": n - 1, "6": n - 1, "10": 1}[lv]
    p_disk = 1 - (1 - afr / 100 * hours / 8766) ** exposed if exposed else 0.0
    if lv == "6":
        p_loss = p_ure * p_disk  # a read error AND a second failure are both needed to lose data with double parity
        why = "RAID 6 loses data only if a read error AND another failure coincide with the rebuild"
    elif lv == "0":
        p_loss = 1.0; why = "any single failure"
    else:
        p_loss = 1 - (1 - p_ure) * (1 - p_disk)
        why = "a read error on any surviving disk, or a second failure in the exposed set, during the rebuild"
    verdict = ("High risk on this size: prefer RAID 6 or RAID 10 and keep a tested backup." if p_loss > 0.1 and lv in ("5",) else
               "No protection." if lv == "0" else "Acceptable for the rebuild itself; RAID is still not a backup." if p_loss < 0.05 else "Material risk: consider more redundancy and shorter rebuilds.")
    return {"level": lv, "disks": n, "disk_tb": size, "usable_tb": round(usable, 2), "efficiency_pct": round(usable / (n * size) * 100, 1), "survives_failures": tol if lv != "10" else "1 guaranteed (more only if they hit different pairs)",
            "write_penalty": pen, "data_read_to_rebuild_tb": round(read_tb, 2), "rebuild_hours": round(hours, 1), "chance_of_read_error_during_rebuild_pct": round(p_ure * 100, 2),
            "chance_second_failure_during_rebuild_pct": round(p_disk * 100, 3), "chance_of_losing_data_in_one_rebuild_pct": round(p_loss * 100, 3), "why": why, "note": note, "verdict": verdict,
            "lesson": "RAID protects against a disk dying, not against deletion, ransomware, fire or a bad controller. Bigger disks mean longer rebuilds and more data that must be read perfectly, which is why single parity gets riskier as disks grow. RAID is not a backup.",
            "limit": "Uses the manufacturer's unrecoverable-read-error rate (enterprise drives often quote 1 in 10^15 or 10^16, consumer 1 in 10^14) and a constant failure rate. Real drives from one batch fail together more often than this assumes, and many arrays scrub and retry reads."}


# ------------------------------------------------------------------ backup schemes
def backup_plan(full_gb, change_pct=5, days=28, full_every=7, restore_mb_s=100, rpo_h=24, rto_h=8, interval_h=24) -> dict:
    full = _n(full_gb, "Full backup size (GB)", 0.1, 1e7); ch = _n(change_pct, "Daily change (%)", 0.01, 100); days = _n(days, "Days to model", 7, 366, True)
    every = _n(full_every, "Full backup every N days", 1, 90, True); speed = _n(restore_mb_s, "Restore speed (MB/s)", 1, 1e5)
    rpo = _n(rpo_h, "Recovery point objective (hours)", 0.01, 1e5); rto = _n(rto_h, "Recovery time objective (hours)", 0.01, 1e5); iv = _n(interval_h, "Hours between backups", 0.01, 1e4)
    daily = full * ch / 100
    rows = []
    for scheme in ("full", "incremental", "differential"):
        total = 0.0; worst_chain = 1; worst_gb = 0.0
        for d in range(days):
            k = d % every
            if scheme == "full" or k == 0:
                size = full
            elif scheme == "incremental":
                size = daily
            else:
                size = min(full, daily * k)
            total += size
            if scheme == "full":
                gb, chain = full, 1
            elif scheme == "incremental":
                gb, chain = full + daily * k, 1 + k
            else:
                gb, chain = full + min(full, daily * k), 1 if k == 0 else 2
            if gb > worst_gb:
                worst_gb = gb
            worst_chain = max(worst_chain, chain)
        hrs = worst_gb * 1024 / speed / 3600
        rows.append({"scheme": scheme, "stored_gb": round(total), "worst_restore_gb": round(worst_gb), "worst_restore_chain": f"{worst_chain} backup set(s)", "worst_restore_hours": round(hrs, 2),
                     "meets_rto": hrs <= rto, "backup_job_size_gb_typical": round(full if scheme == "full" else daily if scheme == "incremental" else daily * (every + 1) / 2)})
    rpo_ok = iv <= rpo
    return {"daily_change_gb": round(daily, 1), "rows": rows, "rpo": {"interval_h": iv, "objective_h": rpo, "met": rpo_ok,
            "reading": f"Backing up every {iv:g} h can lose up to {iv:g} h of work. " + ("That meets your recovery point objective." if rpo_ok else f"Your objective is {rpo:g} h, so back up more often.")},
            "reading": "Full is simplest to restore but stores the most. Incremental stores the least but a restore needs the last full plus EVERY incremental since, so one damaged set breaks the chain. Differential sits between: a restore needs the last full plus one differential, but each differential grows until the next full.",
            "lesson": "Choose by the restore, not the backup: how much data, how many sets, how long, and how many hours of work you can afford to lose (RPO) versus wait (RTO). Keep 3 copies on 2 kinds of media with 1 offsite, and test a restore.",
            "limit": "Assumes new changes each day (no file is changed twice) and no compression or deduplication, so differential sizes are upper bounds. Restore speed is a single number; real restores are slower with many small files or a congested network."}


def dr_check(systems) -> dict:
    if not isinstance(systems, list) or not 1 <= len(systems) <= 60:
        raise OpsError("Give between 1 and 60 systems.")
    rows, findings = [], []
    for i, s in enumerate(systems):
        if not isinstance(s, dict) or not str(s.get("name", "")).strip():
            raise OpsError(f"System {i + 1} needs a name.")
        nm = str(s["name"])[:60]
        rto = _n(s.get("rto_h", 24), f"{nm}: RTO", 0, 1e5); rpo = _n(s.get("rpo_h", 24), f"{nm}: RPO", 0, 1e5)
        iv = _n(s.get("backup_interval_h", 24), f"{nm}: backup interval", 0.01, 1e5); rest = _n(s.get("restore_h", 4), f"{nm}: restore time", 0, 1e5)
        tested = s.get("tested_days_ago"); tested = None if tested in (None, "") else _n(tested, f"{nm}: days since last restore test", 0, 36500)
        copies = _n(s.get("copies", 1), f"{nm}: copies", 0, 99, True); media = _n(s.get("media_types", 1), f"{nm}: media types", 0, 99, True); offsite = bool(s.get("offsite", False))
        issues = []
        if iv > rpo:
            issues.append(f"backs up every {iv:g} h but can only lose {rpo:g} h")
        if rest > rto:
            issues.append(f"restore takes {rest:g} h but must finish in {rto:g} h")
        if tested is None:
            issues.append("restore has never been tested")
        elif tested > 180:
            issues.append(f"restore last tested {int(tested)} days ago (test at least every 6 months)")
        if copies < 3 or media < 2 or not offsite:
            issues.append("fails 3-2-1 (3 copies, 2 media types, 1 offsite)")
        rows.append({"system": nm, "rto_h": rto, "rpo_h": rpo, "worst_data_loss_h": iv, "restore_h": rest, "status": "fail" if any(("backs up" in x or "restore takes" in x) for x in issues) else ("warn" if issues else "pass"), "issues": "; ".join(issues) or "ok"})
        for x in issues:
            findings.append(f"{nm}: {x}")
    return {"systems": rows, "failing": sum(1 for r in rows if r["status"] == "fail"), "warnings": sum(1 for r in rows if r["status"] == "warn"), "findings": findings[:80],
            "lesson": "A disaster recovery plan is promises with numbers. For every system, the time between backups must be within its recovery point objective and the tested restore time within its recovery time objective. An untested backup is a hope, not a plan.",
            "limit": "Checks the numbers you enter against each other. It cannot tell whether they are honest; measure restore time by actually restoring."}


DR_SAMPLE = [{"name": "Payroll database", "rto_h": 4, "rpo_h": 1, "backup_interval_h": 24, "restore_h": 6, "tested_days_ago": 400, "copies": 2, "media_types": 1, "offsite": False},
             {"name": "File server", "rto_h": 24, "rpo_h": 24, "backup_interval_h": 24, "restore_h": 8, "tested_days_ago": 30, "copies": 3, "media_types": 2, "offsite": True},
             {"name": "Intranet wiki", "rto_h": 72, "rpo_h": 24, "backup_interval_h": 24, "restore_h": 2, "copies": 3, "media_types": 2, "offsite": True}]


# ------------------------------------------------------------------ load balancing
def lb_sim(servers, requests=2000, seed=5, clients=50, mean_ms=200, fail=None) -> dict:
    if not isinstance(servers, list) or not 2 <= len(servers) <= 12:
        raise OpsError("Give between 2 and 12 servers.")
    names, weights = [], []
    for i, s in enumerate(servers):
        if not isinstance(s, dict):
            raise OpsError(f"Server {i + 1} must be an object with name and weight.")
        names.append(str(s.get("name") or f"srv{i + 1}")[:20]); weights.append(int(_n(s.get("weight", 1), "Weight", 1, 100, True)))
    if len(set(names)) != len(names):
        raise OpsError("Server names must be different.")
    N = _n(requests, "Requests", 50, 20000, True); C = _n(clients, "Distinct clients", 1, 5000, True); mean = _n(mean_ms, "Mean request time (ms)", 1, 60000)
    fail_idx = None
    if fail not in (None, ""):
        if fail not in names:
            raise OpsError("The server to fail must be one of the names.")
        fail_idx = names.index(fail)
    rng = random.Random(int(_n(seed, "Seed", 0, 10**6, True)))
    ips = [f"10.0.{rng.randrange(256)}.{rng.randrange(1, 255)}" for _ in range(C)]
    reqs = []
    for i in range(N):
        # heavy-tailed durations: a few requests are much longer than the average
        d = rng.expovariate(1 / mean) * (6 if rng.random() < 0.05 else 1)
        reqs.append((i * (mean / 4.0), ips[int(rng.random() ** 2 * C) % C], d))

    def h(ip):
        v = 2166136261
        for ch in ip.encode():
            v = ((v ^ ch) * 16777619) & 0xFFFFFFFF
        return v

    def run(algo, down=None):
        up = [i for i in range(len(names)) if i != down]
        count = [0] * len(names); peak = [0] * len(names); active = [[] for _ in names]
        cur = [0] * len(names); rr = 0; credits = [0] * len(names)
        for t, ip, d in reqs:
            for i in range(len(names)):
                while active[i] and active[i][0] <= t:
                    heapq.heappop(active[i])
            if algo == "round_robin":
                i = up[rr % len(up)]; rr += 1
            elif algo == "weighted_round_robin":
                tot = sum(weights[j] for j in up)
                for j in up:
                    credits[j] += weights[j]
                i = max(up, key=lambda j: credits[j]); credits[i] -= tot
            elif algo == "least_connections":
                i = min(up, key=lambda j: (len(active[j]) / weights[j], j))
            else:
                i = up[h(ip) % len(up)]
            count[i] += 1; heapq.heappush(active[i], t + d); peak[i] = max(peak[i], len(active[i]))
        return count, peak
    out = []
    algos = ("round_robin", "weighted_round_robin", "least_connections", "ip_hash")
    for a in algos:
        c, p = run(a, fail_idx)
        up_idx = [i for i in range(len(names)) if i != fail_idx]
        avg = sum(c) / len(up_idx)
        out.append({"algorithm": a, "share_pct": {names[i]: round(c[i] / N * 100, 1) for i in range(len(names))}, "peak_concurrent": {names[i]: p[i] for i in range(len(names))},
                    "busiest_vs_average": round(max(c) / avg, 2) if avg else None, "peak_ratio": round(max(p) / max(1, sum(p[i] for i in up_idx) / len(up_idx)), 2)})
    moved = None
    if fail_idx is not None:
        base = {ip: names[h(ip) % len(names)] for ip in ips}
        after_up = [i for i in range(len(names)) if i != fail_idx]
        after = {ip: names[after_up[h(ip) % len(after_up)]] for ip in ips}
        moved = round(sum(1 for ip in ips if base[ip] != after[ip] and base[ip] != names[fail_idx]) / len(ips) * 100, 1)
    reading = ("Round robin ignores server size and request length. Weighted round robin respects capacity. Least connections adapts to slow requests. IP hash keeps a client on one server (useful for sessions) "
               "but spreads unevenly when a few clients are busy.")
    if moved is not None:
        reading += f" With {fail} down, a plain hash-mod scheme also moved {moved}% of the clients that were on healthy servers, which loses their sessions: that is why real systems use consistent hashing or shared session storage."
    return {"requests": N, "clients": C, "failed": fail, "results": out, "healthy_clients_moved_by_rehash_pct": moved, "reading": reading,
            "lesson": "A load balancer spreads requests and removes failed servers using health checks. The algorithm decides how fair the spread is: pick for your traffic shape, not by habit. Layer 4 balancers route on IP and port; layer 7 balancers can route on URL, header or cookie.",
            "limit": "A simple model: one request type, durations drawn at random, no health-check delay, no connection reuse, no TLS cost. Real products (nginx, HAProxy, cloud balancers) differ in detail."}


# ------------------------------------------------------------------ HTTP status codes
HTTP = {
    200: ("OK", "none", "The request worked.", "Nothing to fix. If content is wrong, check caching or the app logic."),
    201: ("Created", "none", "A resource was created (POST/PUT).", "Check the Location header for its address."),
    204: ("No Content", "none", "Worked, and there is nothing to return.", "Normal for deletes and some updates."),
    206: ("Partial Content", "none", "A range of the file was returned (resume or streaming).", "Normal for downloads and video."),
    301: ("Moved Permanently", "config", "The URL changed for good; clients and search engines should use the new one.", "Check the Location header; fix old links; avoid redirect chains and loops."),
    302: ("Found (temporary redirect)", "config", "Temporary move, often login or language routing.", "Follow with curl -IL; unexpected redirects often mean sign-in or HTTP-to-HTTPS rules."),
    304: ("Not Modified", "none", "The browser's cached copy is still current.", "Normal. Hard-refresh if you are testing a change."),
    307: ("Temporary Redirect", "config", "Like 302 but the method must be kept.", "Check redirect rules."),
    308: ("Permanent Redirect", "config", "Like 301 but the method must be kept.", "Check redirect rules."),
    400: ("Bad Request", "client", "The server could not understand the request (malformed syntax, oversized headers or cookies).", "Clear cookies; check the URL, request body and header sizes."),
    401: ("Unauthorized", "client", "No valid credentials (it really means 'unauthenticated').", "Sign in, check tokens and expiry, check the WWW-Authenticate header."),
    403: ("Forbidden", "client", "You are known but not allowed.", "Check permissions, file ownership, IP allow-lists, directory-listing settings and web application firewall rules."),
    404: ("Not Found", "client", "Nothing at that URL.", "Check spelling, the file path, rewrite rules and whether the resource was removed."),
    405: ("Method Not Allowed", "client", "The URL exists but not for that method (for example POST to a read-only page).", "Check the allowed methods in the Allow header and the route definition."),
    408: ("Request Timeout", "client", "The server gave up waiting for the client to finish the request.", "Check the client's network; check server timeout settings."),
    409: ("Conflict", "client", "The request clashes with the current state (duplicate, edit conflict).", "Re-fetch the latest state and retry."),
    410: ("Gone", "client", "Removed on purpose and not coming back.", "Remove the links."),
    413: ("Content Too Large", "client", "The upload exceeds the server's limit.", "Raise the body-size limit (for example client_max_body_size in nginx) or send less."),
    414: ("URI Too Long", "client", "The URL is too long.", "Send data in the body instead of the query string."),
    415: ("Unsupported Media Type", "client", "The server does not accept that content type.", "Check the Content-Type header."),
    418: ("I'm a teapot", "joke", "An April Fools' joke code from RFC 2324.", "You should not see this in production."),
    422: ("Unprocessable Content", "client", "Well-formed but failed validation.", "Read the error body for which field failed."),
    429: ("Too Many Requests", "client", "Rate limit hit.", "Slow down; honour Retry-After; review the limit if legitimate."),
    500: ("Internal Server Error", "server", "The server failed in a way it did not expect (a bug or bad configuration).", "Read the application and web server error logs at that timestamp; check recent deployments."),
    501: ("Not Implemented", "server", "The server does not support that method.", "Check the method and server software."),
    502: ("Bad Gateway", "server", "A proxy or load balancer got an invalid reply from the server behind it.", "Check the upstream is running and listening, its port, and proxy timeouts and logs."),
    503: ("Service Unavailable", "server", "Overloaded or down for maintenance, usually temporary.", "Check capacity, health checks, maintenance mode and whether the app is crashing."),
    504: ("Gateway Timeout", "server", "A proxy waited too long for the server behind it.", "Look for slow queries or stuck upstreams; check proxy timeout settings."),
    505: ("HTTP Version Not Supported", "server", "The server does not support that HTTP version.", "Check the protocol version and server configuration."),
}


def http_status(code) -> dict:
    try:
        c = int(str(code).strip())
    except ValueError:
        raise OpsError("Enter a three-digit status code such as 404.") from None
    if not 100 <= c <= 599:
        raise OpsError("Status codes run from 100 to 599.")
    cls = {1: "Informational", 2: "Success", 3: "Redirection", 4: "Client error (the request is the problem)", 5: "Server error (the server is the problem)"}[c // 100]
    if c in HTTP:
        name, who, meaning, check = HTTP[c]
        return {"code": c, "name": name, "class": cls, "fault": who, "meaning": meaning, "check_first": check, "known": True}
    return {"code": c, "name": "Not in the common list", "class": cls, "fault": "client" if c // 100 == 4 else "server" if c // 100 == 5 else "none", "known": False,
            "meaning": f"Only the class is certain: {cls}.", "check_first": "Look the code up in the IANA HTTP Status Code Registry or the server's documentation; some applications use their own codes."}


def http_table() -> list[dict]:
    return [{"code": c, "name": v[0], "fault": v[1], "meaning": v[2], "check_first": v[3]} for c, v in sorted(HTTP.items())]


# ------------------------------------------------------------------ is the site down?
def site_triage(dns_resolves=None, tcp_connects=None, tls_ok=None, http_status_code=None, from_elsewhere_works=None, latency_slow=False) -> dict:
    steps = [("DNS", dns_resolves, "nslookup example.com   (or: dig example.com)", "The name does not resolve. Check spelling, your DNS server, the domain's records and expiry, and try another resolver (nslookup example.com 8.8.8.8)."),
             ("TCP connection", tcp_connects, "Test-NetConnection example.com -Port 443   (or: nc -vz example.com 443)", "The host does not accept connections. Check the host is up, the service is listening, a firewall or security group is not blocking, and the port number."),
             ("TLS (HTTPS)", tls_ok, "openssl s_client -connect example.com:443 -servername example.com", "The secure handshake fails. Check the certificate's expiry and name, the full chain, and the protocol versions both sides allow; also check the device's clock."),
             ("HTTP response", None if http_status_code in (None, "") else True, "curl -I https://example.com/", "")]
    failing = None
    for name, ok, cmd, fix in steps[:3]:
        if ok is False:
            failing = (name, cmd, fix); break
    code = None
    if failing is None and http_status_code not in (None, ""):
        code = http_status(http_status_code)
        if code["code"] >= 400:
            failing = ("HTTP response", steps[3][2], f"The server answered {code['code']} {code['name']}: {code['meaning']} Check first: {code['check_first']}")
    unknown = [s[0] for s in steps[:3] if s[1] is None]
    out = {"failing_layer": failing[0] if failing else None, "next_command": failing[1] if failing else None, "what_it_means": failing[2] if failing else None, "layers": [], "status": code,
           "untested_layers": unknown, "commands": {s[0]: s[2] for s in steps}}
    for name, ok, cmd, fix in steps[:3]:
        out["layers"].append({"layer": name, "result": "not tested" if ok is None else ("ok" if ok else "FAIL"), "command": cmd})
    scope = ""
    if from_elsewhere_works is True:
        scope = "It works from another network or device, so the fault is probably on your side: your DNS, proxy, firewall, VPN or local cache."
    elif from_elsewhere_works is False:
        scope = "It fails from elsewhere too, so the fault is on the site's side (or in its DNS)."
    if latency_slow and not failing:
        scope += " Slow but working points at load, a slow database or upstream, or a network path problem: compare curl -w timings for DNS, connect and first byte."
    out["scope"] = scope.strip()
    out["verdict"] = (f"Start at {failing[0]}." if failing else ("Every tested layer looks fine. If users still report a problem, test from their network and check application logs." if not unknown else f"Nothing has failed yet; test {', '.join(unknown)} next."))
    out["lesson"] = "Work up the layers in order: name resolution, connection, secure handshake, then the HTTP answer. The first layer that fails is where to look; everything above it is irrelevant until it is fixed. Compare from a second network to tell 'it is down' from 'it is down for me'."
    out["limit"] = "Reasons from the answers you give; it does not test anything itself. Run the commands yourself."
    return out


# ------------------------------------------------------------------ access log summary
_LOG = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) (\S+)(?: "[^"]*" "([^"]*)")?')
_PROBE = re.compile(r"(\.env|wp-login|wp-admin|xmlrpc|phpmyadmin|\.git/|etc/passwd|\.\./|/cgi-bin/|\bunion\b.*\bselect\b|<script|/admin|\.php\?)", re.I)


def access_log(text) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise OpsError("Paste web server access log lines (common or combined format).")
    if len(text) > 3_000_000:
        raise OpsError("Keep it under 3 MB.")
    status, errs, ips, ip_err, probes, methods, bad = Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), 0
    total = 0; five = Counter(); sent = 0
    for ln in text.splitlines()[:60000]:
        if not ln.strip():
            continue
        m = _LOG.match(ln)
        if not m:
            bad += 1; continue
        ip, meth, path, st, size, ua = m.groups(); st = int(st)
        total += 1; status[st // 100] += 1; methods[meth] += 1; ips[ip] += 1
        if size.isdigit():
            sent += int(size)
        if st >= 400:
            errs[(st, path.split("?")[0][:80])] += 1; ip_err[ip] += 1
        if st >= 500:
            five[path.split("?")[0][:80]] += 1
        if _PROBE.search(path):
            probes[ip] += 1
    if not total:
        raise OpsError("No lines matched the common or combined log format. Example: 203.0.113.9 - - [12/Oct/2026:10:01:02 +0000] \"GET /index.html HTTP/1.1\" 200 5120")
    r5 = status.get(5, 0) / total * 100; r4 = status.get(4, 0) / total * 100
    findings = []
    if r5 >= 1:
        findings.append(f"{r5:.1f}% of requests were server errors (5xx): look at the application and upstream logs for those paths.")
    if r4 >= 20:
        findings.append(f"{r4:.1f}% were client errors (4xx): broken links, missing assets or scanning.")
    for ip, n in probes.most_common(3):
        findings.append(f"{ip} made {n} request(s) for sensitive or exploit-style paths (probing); consider blocking or rate limiting.")
    for ip, n in ip_err.most_common(2):
        if n >= 20 and ip_err[ip] / ips[ip] > 0.8:
            findings.append(f"{ip} produced {n} errors out of {ips[ip]} requests: likely a scanner or a broken client.")
    return {"requests": total, "unparsed_lines": bad, "status_classes": {f"{k}xx": v for k, v in sorted(status.items())}, "error_rate_4xx_pct": round(r4, 1), "error_rate_5xx_pct": round(r5, 1),
            "methods": dict(methods.most_common()), "top_error_paths": [{"status": s, "path": p, "count": c} for (s, p), c in errs.most_common(8)],
            "top_clients": [{"ip": ip, "requests": c, "errors": ip_err.get(ip, 0)} for ip, c in ips.most_common(5)], "probing_clients": [{"ip": ip, "probe_requests": c} for ip, c in probes.most_common(5)],
            "megabytes_sent": round(sent / 1e6, 2), "findings": findings, "verdict": "Needs attention." if findings else "Nothing stands out in this sample.",
            "lesson": "The status mix is the quickest health reading of a web server: mostly 2xx and 3xx is healthy, a rise in 5xx is the server's fault, a rise in 4xx is broken links or scanning. Look at WHICH paths and WHICH clients produce the errors.",
            "limit": "Reads common and combined log formats only, on the lines you paste (first 60,000). A pattern match for probing is a lead, not proof of an attack; client addresses behind a proxy or CDN may all look the same."}


LOG_SAMPLE = "\n".join([
    '203.0.113.9 - - [12/Oct/2026:10:01:02 +0000] "GET /index.html HTTP/1.1" 200 5120 "-" "Mozilla/5.0"',
    '203.0.113.9 - - [12/Oct/2026:10:01:03 +0000] "GET /css/site.css HTTP/1.1" 200 2048 "-" "Mozilla/5.0"',
    '198.51.100.7 - - [12/Oct/2026:10:02:10 +0000] "GET /old-page HTTP/1.1" 404 512 "-" "Mozilla/5.0"',
    '198.51.100.7 - - [12/Oct/2026:10:02:11 +0000] "GET /old-page HTTP/1.1" 404 512 "-" "Mozilla/5.0"',
    '192.0.2.44 - - [12/Oct/2026:10:03:00 +0000] "GET /.env HTTP/1.1" 404 512 "-" "curl/8.0"',
    '192.0.2.44 - - [12/Oct/2026:10:03:01 +0000] "GET /wp-login.php HTTP/1.1" 404 512 "-" "curl/8.0"',
    '192.0.2.44 - - [12/Oct/2026:10:03:02 +0000] "GET /phpmyadmin/ HTTP/1.1" 404 512 "-" "curl/8.0"',
    '203.0.113.20 - - [12/Oct/2026:10:04:00 +0000] "POST /api/orders HTTP/1.1" 502 150 "-" "Mozilla/5.0"',
    '203.0.113.20 - - [12/Oct/2026:10:04:05 +0000] "POST /api/orders HTTP/1.1" 502 150 "-" "Mozilla/5.0"',
    '203.0.113.21 - - [12/Oct/2026:10:04:09 +0000] "GET /api/orders HTTP/1.1" 200 900 "-" "Mozilla/5.0"',
    '203.0.113.22 - - [12/Oct/2026:10:05:00 +0000] "GET /about HTTP/1.1" 301 0 "-" "Mozilla/5.0"',
    '203.0.113.22 - - [12/Oct/2026:10:05:01 +0000] "GET /about/ HTTP/1.1" 200 3100 "-" "Mozilla/5.0"'])


# ------------------------------------------------------------------ reference tables (checked against standards)
def reference() -> dict:
    return {
        "http": http_table(),
        "aaa": [{"item": "Port and transport", "radius": "UDP 1812 (authentication) and 1813 (accounting); older installs use 1645 and 1646", "tacacs": "TCP 49"},
                {"item": "AAA split", "radius": "Authentication and authorization combined; accounting separate", "tacacs": "Authentication, authorization and accounting are separate, so each can be handled differently"},
                {"item": "Encryption", "radius": "Only the password in the request is obscured; the rest is readable", "tacacs": "The whole packet body is encrypted"},
                {"item": "Typical use", "radius": "Network access: Wi-Fi (802.1X), VPN, remote access", "tacacs": "Administrator access to network devices, with per-command authorization"},
                {"item": "Standard", "radius": "IETF standard (RFC 2865)", "tacacs": "Cisco-originated; documented as informational RFC 8907 in 2020, not an IETF standards-track protocol"}],
        "kerberos": ["Client asks the Authentication Service (part of the KDC, port 88) for a Ticket-Granting Ticket (TGT), proving who it is with a key derived from the password.", "Client presents the TGT to the Ticket-Granting Service and asks for a ticket for one specific service.",
                     "Client presents that service ticket to the service, which trusts it because only the KDC could have issued it.", "Clocks must agree (Active Directory allows 5 minutes of skew by default) or authentication fails; TGTs last 10 hours by default."],
        "wifi": [{"protocol": "WEP", "status": "Broken. Do not use.", "why": "RC4 with a 24-bit IV sent in clear: IVs repeat after a few thousand packets and the key can be recovered in minutes."},
                 {"protocol": "WPA (TKIP)", "status": "Deprecated", "why": "A stop-gap on RC4 hardware."},
                 {"protocol": "WPA2-Personal", "status": "Acceptable with a long passphrase", "why": "AES-CCMP; the 4-way handshake can be captured and the passphrase guessed offline, so length matters."},
                 {"protocol": "WPA2/WPA3-Enterprise (802.1X)", "status": "Best for organizations", "why": "Per-user credentials or certificates through a RADIUS server; EAP-TLS uses certificates on both sides."},
                 {"protocol": "WPA3-Personal", "status": "Current", "why": "SAE replaces the pre-shared-key handshake, so a captured handshake cannot be guessed offline."},
                 {"protocol": "WPS PIN", "status": "Turn it off", "why": "An 8-digit PIN checked in two halves (and the last digit is a checksum) leaves at most 11,000 guesses."}],
        "802_1x": ["Three parties: the supplicant (the device), the authenticator (the switch or access point) and the authentication server (usually RADIUS).", "The port stays closed except for EAP traffic until the server approves; then the switch opens it, optionally into a particular VLAN.",
                   "EAP-TLS is the strongest common method: both the server and each client present certificates."],
        "crypto_sizes": [{"name": "DES", "size": "56-bit effective key (64 with parity)", "status": "Broken: a 1998 EFF machine cracked it in days"}, {"name": "3DES", "size": "168-bit nominal, about 112 effective", "status": "Retired"},
                         {"name": "AES", "size": "128, 192 or 256-bit key, 128-bit block", "status": "Standard"}, {"name": "RSA", "size": "2048-bit minimum today (3072 for long-term)", "status": "Standard, slower than elliptic curves"},
                         {"name": "ECC (P-256)", "size": "256-bit key, about as strong as RSA-3072", "status": "Standard"}, {"name": "MD5", "size": "128-bit digest", "status": "Collisions are easy: never for security"},
                         {"name": "SHA-1", "size": "160-bit digest", "status": "Practical collisions shown in 2017: avoid"}, {"name": "SHA-256", "size": "256-bit digest", "status": "Standard"},
                         {"name": "bcrypt, scrypt, Argon2", "size": "slow, salted password hashes", "status": "Use these to store passwords, not plain SHA-256"}],
        "ids": [{"type": "NIDS", "reads": "Copies of network traffic (from a mirror port or tap)", "acts": "Alerts only"}, {"type": "NIPS", "reads": "Traffic passing through it, in line", "acts": "Can block or drop"},
                {"type": "HIDS", "reads": "Activity on one host", "acts": "Alerts only"}, {"type": "HIPS", "reads": "Activity on one host", "acts": "Can block on that host"},
                {"type": "UTM", "reads": "One appliance bundling firewall, IPS, antivirus, web and mail filtering, VPN", "acts": "Both; convenient, but one box is one point of failure and every service shares its CPU"}],
        "printing": [{"item": "PCL", "note": "Hewlett-Packard language. The printer shares the rendering work, so output can differ between printers. Common in offices."},
                     {"item": "PostScript", "note": "Adobe language. The computer renders the page, so output is the same on any PostScript printer; common in publishing and on Macs."},
                     {"item": "Print server", "note": "One machine shares printers and drivers: Windows Print and Document Services, or CUPS on Linux (web page on port 631, uses IPP)."},
                     {"item": "Scan-to services", "note": "Scan to email (SMTP), to a share (SMB, port 445) or to the cloud. Use an authenticated account with minimal rights and no plain passwords in the device."},
                     {"item": "Printer security", "note": "Require sign-in or badge release so documents do not sit in the tray, change default admin passwords, keep firmware current, disable unused protocols, and keep audit logs."}],
        "slips": SLIPS_IT2,
        "not_built": ["Active Directory, GPMC, a real LDAP server or a Kerberos KDC: the Group Policy and LDIF tools model the rules only.", "Real RAID controllers, disks, backup software or restore tests.", "A real load balancer, web server or cloud service.",
                      "Network capture and IDS engines (Wireshark, Snort, Suricata): the Network track's capture reader covers reading, not capturing.", "Printer drivers and print servers."],
    }


SLIPS_IT2 = [
    "Hashing: the course says two different inputs should 'never' give the same output. That is impossible (there are more inputs than outputs). A good hash makes finding a collision computationally infeasible; MD5 and SHA-1 fail that test.",
    "Passwords: one lesson calls passwords 'the most secure common safeguards'. They are among the weakest single factors; they need length, uniqueness, a manager and a second factor.",
    "Disk encryption: it is described as giving confidentiality 'and integrity'. Full-disk encryption protects confidentiality; it does not by itself detect tampering. Secure Boot and measured boot protect the boot chain.",
    "802.1X reading: it lists WPA and WPA2 under 'shared key' methods and then says WPA 'enforces 802.1X'. Only the Enterprise modes use 802.1X; the Personal modes use a shared passphrase.",
    "TACACS+ is called an 'open standard released in 1993'. TACACS+ stayed Cisco-originated; it was published as informational RFC 8907 in 2020. The 1993 date belongs to the older TACACS (RFC 1492).",
    "WEP: the lesson says never to send plaintext and ciphertext together, but the real flaw is the short IV sent in clear with a reused RC4 key stream. Also 'roughly 5,000 packets until an IV repeats' is a birthday-bound estimate, not a guarantee.",
    "AES: 'the first and only public cipher approved for top secret information' is an unsourced absolute and dated. Check NSA's current CNSA suite.",
    "Counter-based tokens are called more secure than time-based ones for 'two reasons'. TOTP is the common standard and HOTP's weakness is counter drift; neither stops real-time phishing, which security keys (FIDO) do.",
    "Mobile and Wi-Fi coverage stops at WPA2: WPA3 and SAE are not mentioned, which makes it dated.",
    "Data destruction: 'low-level formatting' with consumer tools is described as a way to zero a drive. Modern drives cannot be low-level formatted outside the factory (zero-fill is an overwrite), multiple passes are not needed on modern drives (NIST SP 800-88 says one), and SSDs need a secure-erase or cryptographic-erase command, not overwriting. Degaussing does not work on SSDs or flash.",
    "FISMA is described as requiring data to be stored on US soil. FISMA itself does not say that; location rules come from agency policy and programs such as FedRAMP.",
    "Load balancers: 'Classic', 'Application', 'Network' and 'Gateway' load balancers are Amazon Web Services product names presented as general types, and the claim that an application load balancer guards against DDoS overstates it (that needs a WAF or DDoS service).",
    "Backups: incremental is defined as backing up 'only the data that's changed in files'. Incremental backs up what changed since the LAST backup of any kind, usually at file level; block-level change tracking is a separate feature.",
    "Group Policy lesson: precedence is explained as site, domain, OU, but the Local policy (applied first) and the Enforced and Block Inheritance options that can reverse the order are left out of that lesson.",
    "The document is pasted web pages (Wikipedia articles on RBAC, LDIF, RAID and HTTP status codes, a Microsoft documentation set) with menu text, 'needs more citations' banners and some sections repeated (LDIF twice, glossaries repeated). Treat those as reference dumps, not course text.",
]
