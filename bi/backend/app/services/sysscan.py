"""Turns the raw output of the security scans into leads.

Honest limits: this is not an antivirus and it can't see malware that hides well. Every item is a lead to look at, not a verdict.
An unsigned program is not necessarily bad (plenty of honest hobby software is unsigned) and a signed one is not necessarily safe.
For real malware detection use Microsoft Defender (the app can start a scan and read its detections) and a second-opinion scanner.
"""
from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timedelta, timezone

CAVEAT = ("Leads, not verdicts. This is not an antivirus. Unsigned does not mean malicious and signed does not mean safe. "
          "Use Microsoft Defender for detection and treat anything surprising as a question to answer, not a conclusion.")
ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
RISKY_DIRS = re.compile(r"\\(temp|downloads|users\\public|appdata\\local\\temp|\$recycle\.bin)\\", re.I)
USER_WRITABLE = re.compile(r"\\(appdata|programdata|users\\public|temp|downloads)\\", re.I)
BAD_SIG = {"NotSigned", "HashMismatch", "NotTrusted", "UnknownError"}
SYSTEM_LISTENERS = {"system", "svchost", "lsass", "services", "wininit", "spoolsv", "dns", "msmpeng", "mdnsresponder", "idle"}


def _f(sev: str, title: str, detail: str, advice: str, evidence: list[str] | None = None) -> dict:
    return {"severity": sev, "title": title, "detail": detail, "advice": advice, "evidence": (evidence or [])[:8]}


def _arr(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
        return a.is_global
    except ValueError:
        return False


def _filetime(v) -> datetime | None:
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=v // 10)


def _name_of(consent_key: str) -> str:
    return consent_key.replace("#", "\\")


def startup(data) -> list[dict]:
    f = []
    items = _arr(data)
    for i in items:
        sig, exe = i.get("sig", ""), i.get("exe") or ""
        label = f"{i.get('name')} ({i.get('where')})"
        if sig == "HashMismatch":
            f.append(_f("high", f"A startup item's file was changed after signing: {i.get('name')}", f"{exe}", "The signature no longer matches the file. Treat it as tampered with until you can explain why.", [label]))
        elif sig == "Missing":
            f.append(_f("low", f"A startup entry points to a file that isn't there: {i.get('name')}", exe, "Usually a leftover from an uninstall. Safe to remove, but make sure you recognise the name.", [label]))
        elif sig in BAD_SIG:
            sev = "medium" if RISKY_DIRS.search(exe or "") else "low"
            f.append(_f(sev, f"Unsigned program starts with Windows: {i.get('name')}", exe, "Do you recognise it? Look the file name up and check its folder. Programs that start from Temp or Downloads deserve a closer look.", [label]))
        elif RISKY_DIRS.search(exe or ""):
            f.append(_f("medium", f"A startup item runs from a temporary or Downloads folder: {i.get('name')}", exe, "Legitimate programs rarely start from there.", [label]))
    return f


def processes(data) -> list[dict]:
    f = []
    for p in _arr(data):
        path, sig = p.get("path") or "", p.get("sig", "")
        if sig == "HashMismatch":
            f.append(_f("high", f"A running program's file fails its signature check: {p.get('name')}", path, "The file was modified after it was signed. Find out why.", [path]))
        elif RISKY_DIRS.search(path) and sig in BAD_SIG | {"Missing"}:
            f.append(_f("medium", f"An unsigned program is running from a temporary or Downloads folder: {p.get('name')}", path, "Do you recognise it? If not, scan it with Defender.", [path]))
        elif sig in BAD_SIG and USER_WRITABLE.search(path):
            f.append(_f("low", f"Unsigned program running from your user data folder: {p.get('name')}", path, "Common for small tools and some games. Worth knowing what it is.", [path]))
    return f


def network(data) -> list[dict]:
    f = []
    rows = _arr(data)
    listen_all = [r for r in rows if r.get("state") == "Listen" and r.get("laddr") in ("0.0.0.0", "::") and str(r.get("proc") or "").lower() not in SYSTEM_LISTENERS]
    if listen_all:
        names = sorted({f"{r.get('proc')}:{r.get('lport')}" for r in listen_all})
        f.append(_f("low", f"{len(names)} program(s) accept connections on every network interface", ", ".join(names[:12]), "Fine for servers you run on purpose. A program you don't recognise listening to the world is worth investigating.", names))
    outbound = [r for r in rows if r.get("state") == "Established" and _is_public(str(r.get("raddr") or ""))]
    risky = [r for r in outbound if RISKY_DIRS.search(str(r.get("path") or "")) or (USER_WRITABLE.search(str(r.get("path") or "")) and "\\appdata\\local\\programs" not in str(r.get("path") or "").lower() and "\\appdata\\local\\microsoft" not in str(r.get("path") or "").lower())]
    if risky:
        ev = sorted({f"{r.get('proc')} -> {r.get('raddr')}:{r.get('rport')}" for r in risky})
        f.append(_f("medium", f"{len(ev)} internet connection(s) made by programs in temporary or user-data folders", "; ".join(ev[:6]), "Many browsers and chat apps live in AppData, so check each name. Programs from Temp or Downloads that talk to the internet are the ones to look at.", ev))
    f.append(_f("info", f"{len(outbound)} established internet connections", f"{len({r.get('proc') for r in outbound})} different programs", "A snapshot only. Run it again later to see what changes.", sorted({str(r.get('proc')) for r in outbound})))
    return f


def remote(data) -> list[dict]:
    d = data or {}
    f = []
    procs, apps = _arr(d.get("processes")), _arr(d.get("apps"))
    for p in procs:
        f.append(_f("medium", f"A remote-control program is running: {p.get('Name')}", str(p.get("Path") or ""), "Expected if you use it. If you didn't install it, someone else may have remote access.", [str(p.get("Path") or "")]))
    for a in apps:
        f.append(_f("low", f"Remote-access software is installed: {a.get('DisplayName')}", f"{a.get('Publisher') or ''} {a.get('DisplayVersion') or ''}".strip(), "Expected if you installed it. Remove it if you don't use it; unused remote tools are an easy way in.", [str(a.get("DisplayName"))]))
    if d.get("rdp_enabled"):
        f.append(_f("medium", "Remote Desktop is turned on", "This computer accepts Remote Desktop connections.", "Turn it off if you don't use it. If you do, keep it behind a VPN and never forward its port on your router."))
    for s in _arr(d.get("services")):
        if s.get("status") == "Running" and s.get("name") in ("WinRM", "sshd"):
            f.append(_f("low", f"{s.get('name')} is running", "A remote management service is accepting connections.", "Fine if you use it on purpose; otherwise stop it and set it to Manual.", [str(s.get("name"))]))
    sh = _arr(d.get("shares"))
    if sh:
        f.append(_f("low", f"{len(sh)} shared folder(s)", ", ".join(str(x.get("Name")) for x in sh), "Make sure each is meant to be shared and who can open it.", [f"{x.get('Name')} = {x.get('Path')}" for x in sh]))
    return f


def privacy(data, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    f = []
    live, recent = [], []
    for r in _arr(data):
        start, stop = _filetime(r.get("start")), _filetime(r.get("stop"))
        label = f"{r.get('capability')}: {_name_of(str(r.get('app')))}"
        if start and not stop:
            live.append(label)
        elif stop and now - stop < timedelta(hours=24):
            recent.append(f"{label} (used {stop.astimezone().strftime('%Y-%m-%d %H:%M')})")
    for l in live:
        f.append(_f("medium", f"In use right now - {l}", "Windows says this program is currently using the device.", "If you didn't expect your camera, microphone or location to be in use, find the program and close it. The camera light normally comes on with the webcam."))
    if recent:
        f.append(_f("info", f"{len(recent)} use(s) of camera, microphone or location in the last 24 hours", "; ".join(recent[:6]), "Check each is a program you used.", recent))
    return f


def accounts(data) -> list[dict]:
    d = data or {}
    f = []
    users, admins = _arr(d.get("users")), _arr(d.get("admins"))
    for u in users:
        if u.get("name", "").lower() == "guest" and u.get("enabled"):
            f.append(_f("medium", "The Guest account is enabled", "", "Disable it unless you need it."))
        elif u.get("enabled") and not u.get("password_required"):
            f.append(_f("medium", f"{u.get('name')} can sign in without a password", "", "Give the account a password or disable it.", [str(u.get("name"))]))
    if len(admins) > 2:
        f.append(_f("low", f"{len(admins)} accounts are administrators", ", ".join(str(a.get("name")) for a in admins), "Everyday accounts should be standard users. Keep one administrator for changes.", [str(a.get("name")) for a in admins]))
    f.append(_f("info", f"{len(users)} local account(s), {sum(1 for u in users if u.get('enabled'))} enabled", ", ".join(str(u.get("name")) for u in users), "Disable accounts nobody uses."))
    return f


def system(data) -> list[dict]:
    d = data or {}
    f = []
    de = d.get("defender")
    if not de:
        f.append(_f("medium", "Couldn't read Microsoft Defender's status", "Another security product may be managing protection, or the scan needs administrator rights.", "Check Windows Security to confirm something is protecting this computer."))
    else:
        if not de.get("antivirus") or not de.get("realtime"):
            f.append(_f("high", "Antivirus real-time protection is off", "", "Turn it on in Windows Security unless another security product is doing the job."))
        if (de.get("signature_age_days") or 0) > 7:
            f.append(_f("medium", f"Antivirus definitions are {de.get('signature_age_days')} days old", "", "Run 'Update Defender signatures'."))
    for t in _arr(d.get("threats")):
        f.append(_f("high", f"Defender detected a threat (ID {t.get('id')})", f"{t.get('at')} by {t.get('process') or 'unknown'}", "Open Windows Security, Protection history, and follow what it recommends.", [str(r) for r in _arr(t.get("resources"))]))
    for p in _arr(d.get("firewall")):
        if str(p.get("enabled")).lower() in ("false", "0"):
            f.append(_f("medium", f"The {p.get('name')} firewall profile is off", "", "Turn it on unless you turned it off deliberately."))
    hosts = [h for h in _arr(d.get("hosts")) if not re.match(r"^\s*(127\.0\.0\.1|::1|0\.0\.0\.0)\s+(localhost)\s*$", str(h))]
    if hosts:
        f.append(_f("medium", f"{len(hosts)} custom entr{'y' if len(hosts) == 1 else 'ies'} in the hosts file", "; ".join(str(h).strip() for h in hosts[:4]), "Each line overrides DNS. Make sure you added every one: unknown entries can redirect banking or update sites.", [str(h).strip() for h in hosts]))
    if d.get("proxy_enabled") or d.get("proxy_script"):
        f.append(_f("medium", "A web proxy is configured", d.get("proxy_server") or d.get("proxy_script") or "", "Expected on some work networks. Unexpected proxies can intercept your traffic.", [str(d.get("proxy_server") or d.get("proxy_script"))]))
    if d.get("uac_enabled") is False:
        f.append(_f("high", "User Account Control is off", "", "Turn it back on in Windows settings; it blocks silent changes."))
    return f


ANALYZERS = {"scan_startup": startup, "scan_processes": processes, "scan_network": network, "scan_remote": remote, "scan_privacy": privacy,
             "scan_accounts": accounts, "scan_system": system}


def analyze(action_id: str, data) -> dict:
    fn = ANALYZERS[action_id]
    findings = sorted(fn(data), key=lambda x: ORDER[x["severity"]])
    return {"findings": findings, "counts": {k: sum(1 for x in findings if x["severity"] == k) for k in ORDER}, "caveat": CAVEAT}


def combine(parts: dict[str, dict]) -> dict:
    allf = []
    for aid, r in parts.items():
        for x in r.get("findings", []):
            allf.append({**x, "source": aid})
    allf.sort(key=lambda x: ORDER[x["severity"]])
    return {"findings": allf, "counts": {k: sum(1 for x in allf if x["severity"] == k) for k in ORDER}, "scans": list(parts), "caveat": CAVEAT}
