"""Log analysis with defensive detections: our own small take on a SIEM (Splunk / Elastic) for one pasted or uploaded log file.

It reads text you give it and never contacts anything. It understands three common shapes (Linux auth/syslog lines, web server
access logs in the usual "combined" format, and generic timestamped lines with a level) and looks for patterns that deserve a
human's attention. A detection is a lead, not a verdict: a rule can fire on innocent traffic and miss a careful attacker.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

MAX_BYTES = 5 * 1024 * 1024
MAX_LINES = 100_000
BRUTE_N, BRUTE_WINDOW = 5, timedelta(minutes=10)
ENUM_USERS = 5
SCAN_4XX = 10

SYSLOG = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<proc>[\w./-]+)(?:\[\d+\])?:\s+(?P<msg>.*)$")
FAIL = re.compile(r"Failed (?:password|publickey|keyboard-interactive/pam) for (?:invalid user )?(?P<user>\S+) from (?P<ip>[0-9a-fA-F:.]+)")
INVALID = re.compile(r"Invalid user (?P<user>\S*) from (?P<ip>[0-9a-fA-F:.]+)")
OK = re.compile(r"Accepted (?:password|publickey|keyboard-interactive/pam) for (?P<user>\S+) from (?P<ip>[0-9a-fA-F:.]+)")
ACCESS = re.compile(r'^(?P<ip>[0-9a-fA-F:.]+)\s+\S+\s+(?P<user>\S+)\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>[A-Z]+)\s+(?P<path>\S+)[^"]*"\s+(?P<status>\d{3})\s+(?P<size>\S+)')
GENERIC = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*[-\[|]?\s*(?P<level>TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRIT(?:ICAL)?|FATAL|ALERT)\b[\]\s:|-]*(?P<msg>.*)$", re.I)
MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}

SENSITIVE = re.compile(r"(/\.env\b|/\.git(/|$)|/wp-login|/wp-admin|/xmlrpc\.php|/phpmyadmin|/etc/passwd|/etc/shadow|/admin(/|$)|/\.aws|/id_rsa|/config\.php|/backup\.(zip|sql|tar))", re.I)
PATTERNS = [
    ("sqli", "SQL injection pattern", re.compile(r"(union(\s|%20|\+)+select|(\'|%27)(\s|%20|\+)*or(\s|%20|\+)*(\'?1\'?=\'?1|true)|sleep\s*\(|information_schema|benchmark\s*\(|;\s*drop\s+table)", re.I)),
    ("xss", "Cross-site scripting pattern", re.compile(r"(<script|%3cscript|onerror\s*=|javascript:|<img[^>]+onerror)", re.I)),
    ("traversal", "Path traversal pattern", re.compile(r"(\.\./|\.\.%2f|%2e%2e[/%]|\.\.\\)", re.I)),
    ("cmdi", "Command injection pattern", re.compile(r"(;|\||%7c|`|\$\()\s*(cat|ls|wget|curl|nc|bash|sh|id|whoami)\b", re.I)),
]


def _ts_access(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.split()[0], "%d/%b/%Y:%H:%M:%S")
    except (ValueError, IndexError):
        return None


def parse(text: str, year: int | None = None) -> tuple[list[dict], dict]:
    year = year or datetime.now().year
    events, kinds = [], Counter()
    lines = text.splitlines()
    truncated = len(lines) > MAX_LINES
    for raw in lines[:MAX_LINES]:
        line = raw.strip()
        if not line:
            continue
        ev = None
        m = SYSLOG.match(line)
        if m:
            try:
                ts = datetime.strptime(f"{year} {m['mon']} {int(m['day'])} {m['time']}", "%Y %b %d %H:%M:%S")
            except ValueError:
                ts = None
            msg = m["msg"]
            f, i, o = FAIL.search(msg), INVALID.search(msg), OK.search(msg)
            if f:
                ev = {"kind": "auth_fail", "ts": ts, "ip": f["ip"], "user": f["user"], "invalid": "invalid user" in msg.lower(), "line": line}
            elif i:
                ev = {"kind": "auth_fail", "ts": ts, "ip": i["ip"], "user": i["user"], "invalid": True, "line": line, "probe": True}
            elif o:
                ev = {"kind": "auth_ok", "ts": ts, "ip": o["ip"], "user": o["user"], "line": line}
            else:
                lvl = "ERROR" if re.search(r"\b(error|failed|failure|denied)\b", msg, re.I) else "INFO"
                ev = {"kind": "generic", "ts": ts, "level": lvl, "line": line}
        if ev is None:
            m = ACCESS.match(line)
            if m:
                ev = {"kind": "http", "ts": _ts_access(m["ts"]), "ip": m["ip"], "user": None if m["user"] == "-" else m["user"], "method": m["method"],
                      "path": m["path"], "status": int(m["status"]), "line": line}
        if ev is None:
            m = GENERIC.match(line)
            if m:
                try:
                    ts = datetime.fromisoformat(m["ts"].replace(" ", "T"))
                except ValueError:
                    ts = None
                lvl = m["level"].upper()
                lvl = {"WARNING": "WARN", "CRITICAL": "CRIT"}.get(lvl, lvl)
                ev = {"kind": "generic", "ts": ts, "level": lvl, "line": line}
        if ev is None:
            ev = {"kind": "unparsed", "ts": None, "line": line}
        kinds[ev["kind"]] += 1
        events.append(ev)
    info = {"lines": min(len(lines), MAX_LINES), "truncated": truncated, "kinds": dict(kinds)}
    return events, info


def _short(s: str, n=160) -> str:
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    return s if len(s) <= n else s[:n] + "…"


def _window_hits(times: list[datetime], n: int, window: timedelta) -> tuple[bool, datetime | None]:
    ts = sorted(t for t in times if t)
    for i in range(len(ts) - n + 1):
        if ts[i + n - 1] - ts[i] <= window:
            return True, ts[i]
    return False, None


def analyze(text: str, year: int | None = None) -> dict:
    if len(text.encode("utf-8", "ignore")) > MAX_BYTES:
        raise ValueError(f"That log is over {MAX_BYTES // (1024 * 1024)} MB. Paste or upload a smaller slice.")
    events, info = parse(text, year)
    if not events:
        raise ValueError("The log is empty.")
    findings: list[dict] = []
    fails, oks = defaultdict(list), defaultdict(list)
    users_by_ip, http_by_ip = defaultdict(set), defaultdict(list)
    for e in events:
        if e["kind"] == "auth_fail":
            fails[e["ip"]].append(e)
            users_by_ip[e["ip"]].add(e["user"])
        elif e["kind"] == "auth_ok":
            oks[e["ip"]].append(e)
        elif e["kind"] == "http":
            http_by_ip[e["ip"]].append(e)

    # 1. brute force (and the worse case: a success afterwards)
    for ip, evs in fails.items():
        hit, start = _window_hits([x["ts"] for x in evs], BRUTE_N, BRUTE_WINDOW)
        if hit or (len(evs) >= BRUTE_N and not any(x["ts"] for x in evs)):
            later_ok = [o for o in oks.get(ip, []) if o["ts"] and start and o["ts"] >= start]
            if later_ok:
                findings.append({"id": f"brute-success:{ip}", "severity": "critical", "title": f"Possible account takeover from {ip}",
                                 "detail": f"{len(evs)} failed logins from {ip}, then a successful login as '{later_ok[0]['user']}'.",
                                 "evidence": [_short(x["line"]) for x in evs[:3]] + [_short(later_ok[0]["line"])],
                                 "advice": "Treat the account as compromised: force a password reset, revoke sessions and keys, and review what that login did. Block the address."})
            else:
                findings.append({"id": f"brute:{ip}", "severity": "high", "title": f"Password guessing from {ip}",
                                 "detail": f"{len(evs)} failed logins from {ip} (at least {BRUTE_N} inside {int(BRUTE_WINDOW.total_seconds() // 60)} minutes).",
                                 "evidence": [_short(x["line"]) for x in evs[:3]],
                                 "advice": "Block or rate-limit the address, require key-based login or MFA, and confirm none of the targeted accounts logged in."})
    # 2. user enumeration
    for ip, users in users_by_ip.items():
        if len(users) >= ENUM_USERS:
            findings.append({"id": f"enum:{ip}", "severity": "medium", "title": f"{ip} tried {len(users)} different usernames",
                             "detail": "Trying many names (admin, root, test, ...) is how attackers look for accounts that exist.",
                             "evidence": [", ".join(sorted(u for u in users if u)[:10])],
                             "advice": "Disable logins for accounts that don't need them, and avoid default account names."})
    # 3. scanning / probing
    for ip, evs in http_by_ip.items():
        errs = [x for x in evs if 400 <= x["status"] < 500]
        sens = [x for x in evs if SENSITIVE.search(x["path"])]
        if len(errs) >= SCAN_4XX or len({x["path"] for x in sens}) >= 3:
            findings.append({"id": f"scan:{ip}", "severity": "medium", "title": f"Probing from {ip}",
                             "detail": f"{len(errs)} client errors and {len({x['path'] for x in sens})} requests for sensitive paths (e.g. /.env, /wp-login, /admin).",
                             "evidence": [_short(f"{x['method']} {x['path']} -> {x['status']}") for x in (sens or errs)[:4]],
                             "advice": "Make sure none of those paths exist or are public, keep software patched, and rate-limit or block the address."})
        elif sens:
            findings.append({"id": f"sensitive:{ip}", "severity": "low", "title": f"{ip} asked for a sensitive path",
                             "detail": f"{len(sens)} request(s) such as {sens[0]['path']}.", "evidence": [_short(f"{x['method']} {x['path']} -> {x['status']}") for x in sens[:3]],
                             "advice": "A 404 is fine. A 200 on one of these paths means something sensitive is exposed: fix it now."})
    # 4. attack strings in requests
    for code, label, rx in PATTERNS:
        hits = [x for x in events if x["kind"] == "http" and rx.search(x["path"])]
        if hits:
            ok = [x for x in hits if x["status"] < 400]
            findings.append({"id": f"{code}", "severity": "high" if ok else "medium", "title": f"{label} in {len(hits)} request(s)",
                             "detail": f"From {len({x['ip'] for x in hits})} address(es). {len(ok)} of them got a success response (status below 400), which is the worrying part.",
                             "evidence": [_short(f"{x['ip']} {x['method']} {x['path']} -> {x['status']}") for x in hits[:3]],
                             "advice": "Check the code behind those URLs uses parameterised queries and output encoding, and add a web application firewall rule if you run one."})
    # 5. server errors
    by_hour = defaultdict(lambda: [0, 0])
    for e in events:
        if e["kind"] == "http" and e["ts"]:
            h = e["ts"].replace(minute=0, second=0)
            by_hour[h][0] += 1
            by_hour[h][1] += e["status"] >= 500
    for h, (tot, bad) in by_hour.items():
        if tot >= 20 and bad / tot >= 0.2:
            findings.append({"id": f"5xx:{h.isoformat()}", "severity": "medium", "title": f"{bad} of {tot} requests failed with a server error around {h:%Y-%m-%d %H:00}",
                             "detail": "A burst of 5xx can be a bug, an overload or someone breaking the app on purpose.", "evidence": [],
                             "advice": "Look at the application error log for the same hour."})
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: order[f["severity"]])

    # summary
    times = [e["ts"] for e in events if e["ts"]]
    tl: dict[datetime, dict] = defaultdict(lambda: {"events": 0, "problems": 0})
    levels, status_classes = Counter(), Counter()
    for e in events:
        if e.get("level"):
            levels[e["level"]] += 1
        if e["kind"] == "http":
            status_classes[f"{e['status'] // 100}xx"] += 1
        if e["ts"]:
            h = e["ts"].replace(minute=0, second=0)
            tl[h]["events"] += 1
            tl[h]["problems"] += (e["kind"] == "auth_fail") or (e["kind"] == "http" and e["status"] >= 400) or e.get("level") in ("ERROR", "CRIT", "FATAL", "ALERT")
    ip_counter = Counter(e["ip"] for e in events if e.get("ip"))
    return {"info": info, "range": [min(times).isoformat(), max(times).isoformat()] if times else None,
            "levels": dict(levels), "status_classes": dict(status_classes),
            "top_ips": [{"ip": ip, "events": n, "failed_logins": len(fails.get(ip, []))} for ip, n in ip_counter.most_common(10)],
            "timeline": [{"hour": h.isoformat(), **v} for h, v in sorted(tl.items())][:500],
            "findings": findings, "caveat": "Detections are leads, not verdicts. Rules can fire on innocent traffic and miss careful attackers."}


def search(text: str, query: str = "", level: str = "", ip: str = "", limit: int = 100, year: int | None = None) -> dict:
    events, info = parse(text, year)
    q = query.lower().strip()
    out = []
    for e in events:
        if q and q not in e["line"].lower():
            continue
        if level and e.get("level") != level.upper():
            continue
        if ip and e.get("ip") != ip:
            continue
        out.append({"ts": e["ts"].isoformat() if e["ts"] else None, "kind": e["kind"], "ip": e.get("ip"), "line": _short(e["line"], 400)})
        if len(out) >= max(1, min(limit, 500)):
            break
    return {"matches": out, "info": info}


def sample_log() -> str:
    """A small made-up auth log (documentation-range addresses) with a brute-force that ends in a success, plus some probing."""
    out = []
    for i in range(8):
        out.append(f"Oct 10 03:1{i}:0{i} web1 sshd[41{i}]: Failed password for root from 203.0.113.50 port 5{i}022 ssh2")
    out.append("Oct 10 03:19:30 web1 sshd[420]: Accepted password for root from 203.0.113.50 port 55111 ssh2")
    for u in ("admin", "test", "oracle", "postgres", "guest", "ubuntu"):
        out.append(f"Oct 10 04:02:11 web1 sshd[430]: Invalid user {u} from 198.51.100.7 port 40001")
    out.append("Oct 10 05:00:00 web1 sshd[440]: Accepted publickey for deploy from 192.0.2.10 port 50000 ssh2")
    out += ['198.51.100.7 - - [10/Oct/2026:06:00:0%d +0000] "GET /wp-login.php HTTP/1.1" 404 12' % i for i in range(3)]
    out.append('198.51.100.7 - - [10/Oct/2026:06:01:00 +0000] "GET /search?q=1%27%20OR%201=1 HTTP/1.1" 200 512')
    return "\n".join(out) + "\n"
