"""Cybersecurity track tools. Defensive and educational only.

What is here: a self-audit of this dashboard, a security-header check and a TLS certificate check for a PUBLIC website you name,
a port check of THIS computer only, a hash/integrity tool, a password-strength and passphrase tool, an authenticator-code (TOTP)
lab, and an incident tracker. What is NOT here, on purpose: anything that attacks, scans or probes systems you don't own.
Every network check refuses private, loopback and link-local addresses, so it cannot be pointed at your own network or a cloud
metadata service, and it connects to the exact address it resolved (no DNS tricks between the check and the connection).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import secrets
import socket
import ssl
import struct
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from app.services import state

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(__file__).resolve().parents[1] / "data"


class SecError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


# ============================================================ public-host guard
HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


def resolve_public(host: str, resolver=socket.getaddrinfo) -> str:
    """Return one public IP for `host`, or raise. Rejects IP literals that aren't public and any name that resolves to a non-public address."""
    host = (host or "").strip().lower().rstrip(".")
    try:
        lit = ipaddress.ip_address(host.strip("[]"))
        ips = [lit]
    except ValueError:
        if not HOST_RE.match(host):
            raise SecError("Enter a website name like example.com (no path, port or spaces).") from None
        try:
            infos = resolver(host, 443, type=socket.SOCK_STREAM)
        except OSError as e:
            raise SecError(f"Couldn't look up '{host}': {e}", 502) from e
        ips = [ipaddress.ip_address(i[4][0]) for i in infos]
    if not ips:
        raise SecError(f"'{host}' has no address.", 502)
    for ip in ips:
        if not ip.is_global:
            raise SecError(f"'{host}' points at a private or local address ({ip}). These checks only run against public websites, never your own network.", 400)
    return str(ips[0])


# ============================================================ security headers
def _header_findings(status: int, headers: dict[str, str], https: bool, cookies: list[str] | None = None) -> list[dict]:
    h = {k.lower(): v for k, v in headers.items()}
    out = []

    def add(hid, level, title, detail, fix):
        out.append({"id": hid, "level": level, "title": title, "detail": detail, "fix": fix})
    if not https:
        add("https", "fail", "Not served over HTTPS", "Anything sent over plain HTTP can be read or changed on the way.", "Serve the site over HTTPS and redirect HTTP to it.")
    hsts = h.get("strict-transport-security")
    if https:
        if not hsts:
            add("hsts", "warn", "No HSTS header", "Browsers may still try plain HTTP first.", "Send Strict-Transport-Security: max-age=31536000; includeSubDomains")
        else:
            m = re.search(r"max-age=(\d+)", hsts)
            add("hsts", "ok" if m and int(m.group(1)) >= 15552000 else "warn", "HSTS present", hsts, "Use max-age of at least 6 months (15552000)." if not m or int(m.group(1)) < 15552000 else "")
    csp = h.get("content-security-policy")
    if not csp:
        add("csp", "warn", "No Content-Security-Policy", "A CSP limits what scripts a page can run, which blunts cross-site scripting.", "Start with: default-src 'self' and loosen only what you need.")
    else:
        weak = "unsafe-inline" in csp or "unsafe-eval" in csp or re.search(r"(^|;)\s*(default|script)-src[^;]*\*", csp)
        add("csp", "warn" if weak else "ok", "Content-Security-Policy present" + (" but loose" if weak else ""), _clip(csp), "Remove 'unsafe-inline' / 'unsafe-eval' / wildcards where you can." if weak else "")
    if h.get("x-content-type-options", "").lower() != "nosniff":
        add("nosniff", "warn", "Missing X-Content-Type-Options: nosniff", "Browsers may guess a file's type and run something that wasn't meant to run.", "Send X-Content-Type-Options: nosniff")
    else:
        add("nosniff", "ok", "X-Content-Type-Options: nosniff", "", "")
    framing = h.get("x-frame-options") or ("frame-ancestors" in (csp or "") and "csp")
    add("framing", "ok" if framing else "warn", "Clickjacking protection" if framing else "Can be put inside another site's frame", "" if framing else "Another site could embed this page invisibly and trick clicks.",
        "" if framing else "Send X-Frame-Options: DENY or CSP frame-ancestors 'none'.")
    add("referrer", "ok" if "referrer-policy" in h else "info", "Referrer-Policy " + ("set" if "referrer-policy" in h else "not set"), h.get("referrer-policy", ""), "" if "referrer-policy" in h else "Send Referrer-Policy: strict-origin-when-cross-origin")
    add("permissions", "ok" if "permissions-policy" in h else "info", "Permissions-Policy " + ("set" if "permissions-policy" in h else "not set"), "", "" if "permissions-policy" in h else "Turn off browser features you don't use (camera, microphone, geolocation).")
    server = h.get("server", "")
    if re.search(r"\d+\.\d+", server) or h.get("x-powered-by"):
        add("disclosure", "warn", "Reveals software and version", f"{server} {h.get('x-powered-by', '')}".strip(), "Hide version numbers so attackers can't match you to known bugs quickly.")
    for c in (cookies or [])[:5]:
        name = c.split("=")[0]
        miss = [f for f, rx in (("Secure", r"(?i);\s*secure"), ("HttpOnly", r"(?i);\s*httponly"), ("SameSite", r"(?i);\s*samesite")) if not re.search(rx, c)]
        add(f"cookie:{name}", "warn" if miss else "ok", f"Cookie '{name}' " + (f"is missing {', '.join(miss)}" if miss else "has Secure, HttpOnly and SameSite"), "", "Add the missing attributes." if miss else "")
    return out


def _clip(s: str, n=160) -> str:
    return s if len(s) <= n else s[:n] + "…"


def _score(findings: list[dict]) -> dict:
    scored = [f for f in findings if f["level"] in ("ok", "warn", "fail")]
    ok = sum(1 for f in scored if f["level"] == "ok")
    return {"passed": ok, "total": len(scored), "pct": round(100 * ok / len(scored)) if scored else 0}


def fetch_https(host: str, path: str = "/", ip: str | None = None, timeout: float = 8.0) -> tuple[int, dict, str]:
    """One GET over TLS to the resolved IP. No redirects are followed. Returns (status, headers, location_or_empty)."""
    ip = ip or resolve_public(host)
    ctx = ssl.create_default_context()
    with socket.create_connection((ip, 443), timeout=timeout) as raw, ctx.wrap_socket(raw, server_hostname=host) as tls:
        tls.settimeout(timeout)
        tls.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: bi-dashboard-security-check/1\r\nAccept: */*\r\nConnection: close\r\n\r\n".encode())
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 65536:
            chunk = tls.recv(4096)
            if not chunk:
                break
            buf += chunk
    head = buf.split(b"\r\n\r\n", 1)[0].decode("latin-1", "replace").split("\r\n")
    m = re.match(r"HTTP/\d\.?\d? (\d{3})", head[0])
    if not m:
        raise SecError("The server didn't answer like a web server.", 502)
    headers: dict[str, str] = {}
    for line in head[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            if k.lower() == "set-cookie":
                headers[f"set-cookie-{len(headers)}"] = v.strip()
            else:
                headers[k.strip().lower()] = v.strip()
    return int(m.group(1)), headers, headers.get("location", "")


def check_headers(host: str, fetcher=fetch_https) -> dict:
    host = host.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    resolve_public(host)                                      # refuse private targets even with a custom fetcher
    try:
        status, headers, loc = fetcher(host)
    except SecError:
        raise
    except (OSError, ssl.SSLError) as e:
        raise SecError(f"Couldn't make a secure connection to {host}: {e}", 502) from e
    cookies = [v for k, v in headers.items() if k.startswith("set-cookie")]
    plain = {k: v for k, v in headers.items() if not k.startswith("set-cookie")}
    findings = _header_findings(status, plain, True, cookies)
    return {"host": host, "status": status, "redirect_to": loc or None, "findings": findings, "score": _score(findings),
            "note": "One request to the front page, no redirects followed. A good header score doesn't mean the site is secure; it means one class of easy mistakes is absent."}


# ============================================================ TLS certificate
def fetch_cert(host: str, ip: str | None = None, timeout: float = 8.0) -> dict:
    ip = ip or resolve_public(host)
    ctx = ssl.create_default_context()
    with socket.create_connection((ip, 443), timeout=timeout) as raw, ctx.wrap_socket(raw, server_hostname=host) as tls:
        return {"cert": tls.getpeercert(), "version": tls.version(), "cipher": tls.cipher()[0] if tls.cipher() else None}


def cert_report(host: str, info: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cert = info["cert"]
    na = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    nb = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days = (na - now).days
    issuer = ", ".join(v for rdn in cert.get("issuer", ()) for k, v in rdn if k in ("organizationName", "commonName"))
    names = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
    out = []
    out.append({"id": "expiry", "level": "fail" if days < 0 else "warn" if days < 21 else "ok", "title": f"Expires in {days} day(s)" if days >= 0 else f"Expired {-days} day(s) ago",
                "fix": "Renew it now." if days < 21 else ""})
    ver = info.get("version") or ""
    out.append({"id": "tls", "level": "ok" if ver in ("TLSv1.3", "TLSv1.2") else "fail", "title": f"Negotiated {ver}", "fix": "" if ver in ("TLSv1.3", "TLSv1.2") else "Disable TLS 1.0/1.1 and SSLv3."})
    out.append({"id": "names", "level": "ok", "title": f"Covers {len(names)} name(s)", "fix": ""})
    return {"host": host, "issuer": issuer, "valid_from": nb.date().isoformat(), "valid_until": na.date().isoformat(), "days_left": days, "names": names[:12],
            "tls_version": ver, "cipher": info.get("cipher"), "findings": out, "score": _score(out),
            "note": "The connection was verified against your system's trusted certificate authorities: if it had failed verification you'd see an error instead of this report."}


def check_cert(host: str, fetcher=fetch_cert) -> dict:
    host = host.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    resolve_public(host)
    try:
        return cert_report(host, fetcher(host))
    except ssl.SSLCertVerificationError as e:
        return {"host": host, "error": f"The certificate FAILED verification: {e.verify_message}", "findings": [{"id": "verify", "level": "fail", "title": "Certificate not trusted", "fix": "Don't enter passwords on this site until it's fixed."}],
                "score": {"passed": 0, "total": 1, "pct": 0}}
    except (OSError, ssl.SSLError) as e:
        raise SecError(f"Couldn't connect to {host}:443 ({e}).", 502) from e


# ============================================================ local port check (this computer only)
PORTS = {
    21: ("FTP", "Sends passwords in clear text. Rarely needed."), 22: ("SSH", "Remote login. Fine if keys or MFA are used."),
    23: ("Telnet", "Clear-text remote login. Should be off."), 25: ("SMTP", "Mail server."), 53: ("DNS", "Name server."), 80: ("HTTP", "Web, unencrypted."),
    111: ("RPC", "Often unnecessary."), 135: ("Windows RPC", "Windows service."), 139: ("NetBIOS", "Windows file sharing, legacy."), 443: ("HTTPS", "Web, encrypted."),
    445: ("SMB", "Windows file sharing. A common attack target."), 631: ("CUPS", "Printing."), 1433: ("SQL Server", "Database."), 3000: ("This dashboard (frontend)", "Expected if you run it."),
    3306: ("MySQL", "Database."), 3389: ("Remote Desktop", "Remote login. Needs MFA and a VPN."), 5432: ("PostgreSQL", "Database."),
    5433: ("PostgreSQL (practice)", "The practice database from docker-compose."), 5900: ("VNC", "Remote screen."), 6379: ("Redis", "Often has no password by default."),
    8020: ("This dashboard (backend)", "Expected if you run it."), 8080: ("Alt HTTP", "Dev servers."), 8888: ("Jupyter", "Runs code. Needs its token."),
    9200: ("Elasticsearch", "Search database."), 27017: ("MongoDB", "Database."),
}


def check_ports(timeout: float = 0.25) -> dict:
    """Connect to a fixed list of common ports on 127.0.0.1 only. The list is not user-supplied, so this can't be aimed elsewhere."""
    found = []
    for port, (name, note) in PORTS.items():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                found.append({"port": port, "service": name, "note": note})
        except OSError:
            pass
        finally:
            s.close()
    return {"checked": len(PORTS), "open": found,
            "explain": "These ports accept connections on 127.0.0.1 (this machine). Whether they are reachable from OTHER machines depends on the address the program listens on: 127.0.0.1 is private, 0.0.0.0 is everyone. "
                       "Check with 'ss -tlnp' (Linux) or 'netstat -ano' (Windows). If this backend runs in a container or the cloud, this shows that environment, not your laptop."}


# ============================================================ hashing
ALGOS = {"sha256": "SHA-256", "sha512": "SHA-512", "sha3_256": "SHA3-256", "blake2b": "BLAKE2b", "sha1": "SHA-1 (legacy)", "md5": "MD5 (legacy)"}
MAX_HASH_BYTES = 50 * 1024 * 1024


def hash_bytes(data: bytes, algos: list[str] | None = None) -> dict:
    if len(data) > MAX_HASH_BYTES:
        raise SecError(f"That's over {MAX_HASH_BYTES // (1024 * 1024)} MB.", 413)
    algos = algos or ["sha256"]
    out = {}
    for a in algos:
        if a not in ALGOS:
            raise SecError(f"Unknown algorithm. Use one of: {', '.join(ALGOS)}.")
        out[a] = hashlib.new(a, data).hexdigest()
    return {"bytes": len(data), "hashes": out,
            "note": "A hash is a fingerprint: any change to the data gives a completely different value. MD5 and SHA-1 are fine for spotting accidental corruption but broken for security. Hashing is not encryption and can't be reversed."}


def verify_hash(data: bytes, expected: str, algo: str = "sha256") -> dict:
    exp = re.sub(r"\s+", "", expected or "").lower()
    if algo not in ALGOS or not re.fullmatch(r"[0-9a-f]+", exp or "x"):
        raise SecError("Paste the expected hash as hexadecimal characters and pick a valid algorithm.")
    got = hash_bytes(data, [algo])["hashes"][algo]
    return {"match": hmac.compare_digest(got, exp), "algorithm": algo, "computed": got,
            "advice": "Matches: the file is identical to what the publisher hashed." if hmac.compare_digest(got, exp) else "DOES NOT MATCH: the file is damaged or different. Don't run or install it; download it again from the original source."}


# ============================================================ passwords
COMMON = set("""123456 password 12345678 qwerty 123456789 12345 1234 111111 1234567 dragon 123123 baseball abc123 football monkey letmein shadow master 666666 qwertyuiop 123321
mustang 1234567890 michael 654321 superman 1qaz2wsx 7777777 121212 000000 qazwsx 123qwe killer trustno1 jordan jennifer zxcvbnm asdfgh hunter buster soccer harley batman
andrew tigger sunshine iloveyou 2000 charlie robert thomas hockey ranger daniel starwars klaster 112233 george computer michelle jessica pepper 1111 zxcvbn 555555 11111111
131313 freedom 777777 pass maggie 159753 aaaaaa ginger princess joshua cheese amanda summer love ashley nicole chelsea biteme matthew access yankees 987654321 dallas austin
thunder taylor matrix welcome admin administrator passw0rd password1 password123 letmein1 qwerty123 welcome1 changeme""".split())
SEQ = ["abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiop", "asdfghjkl", "zxcvbnm"]
GUESSES_PER_SECOND = 1e10          # a fast offline attack on an unsalted fast hash; stated so the number isn't magic


def _pool(pw: str) -> int:
    pool = 0
    if re.search(r"[a-z]", pw): pool += 26
    if re.search(r"[A-Z]", pw): pool += 26
    if re.search(r"\d", pw): pool += 10
    if re.search(r"[^A-Za-z0-9]", pw): pool += 33
    return pool


def _human(sec: float) -> str:
    for limit, unit in ((60, "seconds"), (3600, "minutes"), (86400, "hours"), (86400 * 365, "days"), (86400 * 365 * 1000, "years"), (86400 * 365 * 1e6, "thousand years"), (86400 * 365 * 1e9, "million years")):
        if sec < limit:
            div = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400, "years": 86400 * 365, "thousand years": 86400 * 365 * 1000, "million years": 86400 * 365 * 1e6}[unit]
            return f"{sec / div:.0f} {unit}" if sec / div >= 1 or unit == "seconds" else f"under 1 {unit.rstrip('s')}"
    return "billions of years"


def password_strength(pw: str) -> dict:
    if not isinstance(pw, str) or not pw:
        raise SecError("Type a password to check.")
    if len(pw) > 200:
        raise SecError("Up to 200 characters.")
    low = pw.lower()
    issues, bits = [], len(pw) * math.log2(max(_pool(pw), 2))
    if low in COMMON or re.sub(r"[\d!@#$%^&*]+$", "", low) in COMMON:
        issues.append("It's one of the most common passwords (or a common one with digits added). Attackers try these first.")
        bits = min(bits, 12)
    if len(set(pw)) <= max(2, len(pw) // 4):
        issues.append("Too many repeated characters.")
        bits *= 0.4
    for seq in SEQ:
        for i in range(len(seq) - 3):
            if seq[i:i + 4] in low or seq[i:i + 4][::-1] in low:
                issues.append("Contains an easy run of keys or letters (like abcd, 1234 or qwer).")
                bits -= 10
                break
        else:
            continue
        break
    if re.search(r"(19|20)\d{2}", pw):
        issues.append("Contains a year, which is easy to guess.")
        bits -= 6
    if len(pw) < 12:
        issues.append("Under 12 characters. Length matters more than symbols.")
    bits = max(bits, 0)
    guesses = 2 ** bits
    sec = guesses / GUESSES_PER_SECOND / 2
    score = 0 if bits < 28 else 1 if bits < 45 else 2 if bits < 60 else 3 if bits < 80 else 4
    return {"length": len(pw), "entropy_bits": round(bits, 1), "score": score, "label": ["very weak", "weak", "fair", "good", "strong"][score],
            "crack_time": _human(sec), "issues": issues,
            "assumption": f"Estimated at {GUESSES_PER_SECOND:.0e} guesses per second (a fast offline attack on a stolen, weakly hashed password file). This is a rough estimate that assumes the password was picked randomly from the characters it uses; real passwords made of words, names or patterns are weaker than the number says.",
            "advice": "Use a password manager with a unique random password per site, and turn on MFA. Never type a password you actually use into any tool you don't fully trust, including this one (it is checked on your own machine and never logged or stored)."}


def _words() -> list[str]:
    return [w for w in (DATA / "wordlist.txt").read_text().split() if w]


def generate(kind: str = "passphrase", length: int = 6) -> dict:
    if kind == "passphrase":
        words = _words()
        if not 4 <= length <= 12:
            raise SecError("Use 4 to 12 words.")
        phrase = "-".join(secrets.choice(words) for _ in range(length))
        bits = length * math.log2(len(words))
        return {"kind": kind, "value": phrase, "entropy_bits": round(bits, 1), "wordlist_size": len(words),
                "note": f"{length} words from a {len(words):,}-word list is about {bits:.0f} bits, if the words are picked at random (they are, by your computer's secure random generator). Aim for 60+ bits for something you must memorise, more for anything valuable."}
    if kind == "password":
        if not 12 <= length <= 64:
            raise SecError("Use 12 to 64 characters.")
        alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*-_=+"      # no look-alikes (l, 1, I, O, 0)
        while True:
            pw = "".join(secrets.choice(alphabet) for _ in range(length))
            if re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw) and re.search(r"\d", pw) and re.search(r"[^A-Za-z0-9]", pw):
                break
        return {"kind": kind, "value": pw, "entropy_bits": round(length * math.log2(len(alphabet)), 1), "wordlist_size": None,
                "note": "Random characters from your computer's secure generator. Store it in a password manager; don't try to memorise it."}
    raise SecError("kind must be passphrase or password.")


# ============================================================ TOTP lab (RFC 6238, the maths behind authenticator apps)
def new_secret() -> dict:
    s = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    return {"secret": s, "uri": f"otpauth://totp/BI%20Dashboard:demo?secret={s}&issuer=BI%20Dashboard",
            "note": "This is a practice secret for learning. Never reuse a practice secret for a real account."}


def totp(secret: str, at: float | None = None, digits: int = 6, step: int = 30, algo: str = "sha1") -> str:
    key = base64.b32decode(re.sub(r"\s+", "", secret).upper() + "=" * (-len(re.sub(r"\s+", "", secret)) % 8), casefold=True)
    counter = int((time.time() if at is None else at) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), getattr(hashlib, algo)).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_lab(secret: str, code: str | None = None, at: float | None = None) -> dict:
    try:
        now = at if at is not None else time.time()
        cur = totp(secret, now)
    except Exception:  # noqa: BLE001
        raise SecError("That isn't a valid secret. Use letters A-Z and digits 2-7 (base32).") from None
    out = {"code": cur, "seconds_left": 30 - int(now % 30), "explain": [
        "1. The secret is shared once (the QR code) and stored by the server and your phone.",
        "2. Both sides compute the time step = floor(unix time / 30).",
        "3. HMAC-SHA1(secret, step) gives 20 bytes; 4 of them, picked by the last nibble, become a number.",
        "4. The last 6 digits of that number are the code. It changes every 30 seconds and can't be reused later."]}
    if code is not None:
        c = re.sub(r"\s+", "", str(code))
        match = [d for d in (-1, 0, 1) if hmac.compare_digest(totp(secret, now + 30 * d), c)]
        out["verified"] = bool(match)
        out["note"] = ("Accepted (servers allow one step either side for clock drift)." if match else "Rejected: wrong code or the clocks differ by more than 30 seconds.")
    return out


# ============================================================ incident tracker (a small SOAR-style playbook)
CATEGORIES = {
    "phishing": ("Phishing email", ["Don't click or open anything else from the message", "Report it and keep the original email", "Check who clicked or replied", "Reset passwords for anyone who entered credentials", "Block the sender and the link domain", "Tell people what to look for"]),
    "credential": ("Leaked or guessed password", ["Reset the password and sign out all sessions", "Turn on MFA for the account", "Check the account's recent logins and changes", "Check whether the password was reused elsewhere and reset those", "Find how it leaked (phishing, breach, shared)"]),
    "malware": ("Malware on a device", ["Disconnect the device from the network (don't power off if you need evidence)", "Identify the malware and what it can reach", "Reset passwords used on that device from another device", "Wipe and rebuild rather than 'clean'", "Restore data from a backup you trust", "Find how it got in"]),
    "lost_device": ("Lost or stolen device", ["Lock or remotely wipe it", "Revoke its sessions and keys", "Check whether the disk was encrypted", "List what data was on it", "Decide whether anyone must be told (customers, regulators)"]),
    "data_exposure": ("Data exposed by mistake", ["Remove public access immediately", "Work out what was exposed and for how long", "Check access logs for who saw it", "Rotate any secrets that were exposed", "Decide whether anyone must be told", "Add a check so it can't recur"]),
    "other": ("Something else", ["Describe what happened and when it was noticed", "Contain it so it can't spread or continue", "Find the cause", "Fix and recover", "Write down what you'd change"]),
}
SEVERITIES = ("low", "medium", "high", "critical")
STATUSES = ("open", "investigating", "contained", "resolved")


def _incident(r: dict) -> dict:
    r["timeline"] = json.loads(r["timeline"] or "[]")
    r["checklist"] = json.loads(r["checklist"] or "[]")
    r["category_label"] = CATEGORIES.get(r["category"], (r["category"],))[0]
    if r["resolved_at"] and r["detected_at"]:
        try:
            hrs = (datetime.fromisoformat(r["resolved_at"].replace(" ", "T")) - datetime.fromisoformat(r["detected_at"].replace(" ", "T"))).total_seconds() / 3600
            r["hours_to_resolve"] = round(hrs, 1)
        except ValueError:
            r["hours_to_resolve"] = None
    else:
        r["hours_to_resolve"] = None
    return r


def incidents() -> dict:
    rows = [_incident(r) for r in state.rows("SELECT * FROM incidents WHERE workspace = ? ORDER BY id DESC", (_ws(),))]
    done = [r["hours_to_resolve"] for r in rows if r["hours_to_resolve"] is not None]
    return {"incidents": rows, "stats": {"open": sum(1 for r in rows if r["status"] != "resolved"), "total": len(rows),
                                         "mean_hours_to_resolve": round(sum(done) / len(done), 1) if done else None},
            "categories": [{"id": k, "label": v[0], "checklist": v[1]} for k, v in CATEGORIES.items()]}


def open_incident(title: str, category: str, severity: str, note: str = "") -> dict:
    title = (title or "").strip()[:140]
    if not title:
        raise SecError("Give the incident a short title.")
    if category not in CATEGORIES:
        raise SecError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if severity not in SEVERITIES:
        raise SecError(f"Severity must be one of: {', '.join(SEVERITIES)}.")
    now = state.now()
    tl = [{"at": now, "text": f"Opened ({severity})." + (f" {note.strip()[:300]}" if note.strip() else "")}]
    cl = [{"text": t, "done": False} for t in CATEGORIES[category][1]]
    cur = state.run("INSERT INTO incidents (workspace, title, category, severity, status, detected_at, timeline, checklist, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (_ws(), title, category, severity, "open", now, json.dumps(tl), json.dumps(cl), now))
    state.audit("incident_open", f"{title} ({severity})")
    return get_incident(int(cur.lastrowid))


def get_incident(iid: int) -> dict:
    r = state.one("SELECT * FROM incidents WHERE id = ? AND workspace = ?", (iid, _ws()))
    if not r:
        raise SecError("No such incident.", 404)
    return _incident(r)


def update_incident(iid: int, status: str | None = None, note: str | None = None, tick: dict | None = None, severity: str | None = None) -> dict:
    r = get_incident(iid)
    tl, cl, now = r["timeline"], r["checklist"], state.now()
    sets, args = [], []
    if severity and severity != r["severity"]:
        if severity not in SEVERITIES:
            raise SecError(f"Severity must be one of: {', '.join(SEVERITIES)}.")
        tl.append({"at": now, "text": f"Severity changed to {severity}."})
        sets.append("severity = ?"); args.append(severity)
    if status and status != r["status"]:
        if status not in STATUSES:
            raise SecError(f"Status must be one of: {', '.join(STATUSES)}.")
        tl.append({"at": now, "text": f"Status: {status}."})
        sets.append("status = ?"); args.append(status)
        sets.append("resolved_at = ?"); args.append(now if status == "resolved" else None)
    if note and note.strip():
        tl.append({"at": now, "text": note.strip()[:500]})
    if tick is not None:
        i = tick.get("index")
        if not isinstance(i, int) or not 0 <= i < len(cl):
            raise SecError("No such checklist item.")
        cl[i]["done"] = bool(tick.get("done"))
        sets.append("checklist = ?"); args.append(json.dumps(cl))
    sets.append("timeline = ?"); args.append(json.dumps(tl[-100:]))
    state.run(f"UPDATE incidents SET {', '.join(sets)} WHERE id = ?", (*args, iid))
    state.audit("incident_update", f"#{iid} {status or ''}".strip())
    return get_incident(iid)


def delete_incident(iid: int) -> None:
    get_incident(iid)
    state.run("DELETE FROM incidents WHERE id = ?", (iid,))
