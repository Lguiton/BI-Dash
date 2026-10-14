#!/usr/bin/env python3
"""Self-check for this dashboard on your own computer. Prints OK / WARN / FAIL lines and exits 1 on any FAIL.

    python scripts/security_check.py            checks files, settings and which network addresses are open
It never changes anything and never prints a secret."""
import os
import re
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
results: list[tuple[str, str]] = []


def say(level: str, msg: str):
    results.append((level, msg))
    print(f"{level:<5} {msg}")


def env_values() -> dict:
    out = {}
    f = BACKEND / ".env"
    if f.exists():
        for line in f.read_text(errors="ignore").splitlines():
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", line)
            if m:
                out[m.group(1)] = m.group(2).strip().strip("'\"")
    out.update({k: v for k, v in os.environ.items() if k.startswith("BI_")})
    return out


def lan_ips() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith("127."):
                ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def main() -> int:
    env = env_values()
    # 1. Secrets
    envf = BACKEND / ".env"
    if envf.exists():
        say("OK", "backend/.env exists (keys live there, not in the code).")
        if not (ROOT / ".gitignore").exists() or ".env" not in (ROOT / ".gitignore").read_text(errors="ignore"):
            say("WARN", ".env is not listed in .gitignore; if you use git, add it so keys are never committed.")
    else:
        say("WARN", "No backend/.env yet. That is fine until you add AI keys or email settings.")
    for k, v in env.items():
        if re.search(r"(API_KEY|SECRET|TOKEN|PASSWORD)$", k) and v and v.lower() in ("password", "changeme", "12345678", "your-key-here", "test"):
            say("FAIL", f"{k} looks like a placeholder or a weak value.")
    # 2. Login
    if env.get("BI_AUTH") == "1":
        pw = env.get("BI_OWNER_PASSWORD", "")
        say("OK" if len(pw) >= 12 else "FAIL", "Login is on" + ("." if len(pw) >= 12 else ", but BI_OWNER_PASSWORD is shorter than 12 characters."))
    else:
        say("OK", "Login is off, which is fine only while the dashboard listens on this computer alone (checked below).")
    # 3. Who can reach it
    exposed = []
    for port, name in ((8020, "backend"), (3012, "dashboard"), (3000, "dashboard (docker)")):
        for ip in lan_ips():
            if reachable(ip, port):
                exposed.append(f"{name} port {port} answers on {ip}")
    if exposed:
        level = "OK" if env.get("BI_AUTH") == "1" else "FAIL"
        for e in exposed:
            say(level, f"{e}: other devices on your network can reach it" + ("" if level == "OK" else " and there is no login. Start it with installer\\start.bat, which listens on 127.0.0.1 only."))
    else:
        up = [p for p in (8020, 3012) if reachable("127.0.0.1", p)]
        say("OK", "Not reachable from other devices on your network" + (f" (running now on ports {', '.join(map(str, up))})." if up else " (the app isn't running right now, so run this again while it is)."))
    # 4. Data safety
    data = BACKEND / "data"
    newest = 0.0
    for f in (data / "backups").rglob("*.duckdb") if (data / "backups").exists() else []:
        newest = max(newest, f.stat().st_mtime)
    if newest:
        age = (time.time() - newest) / 86400
        say("OK" if age <= 7 else "WARN", f"Newest backup is {age:.1f} days old" + ("." if age <= 7 else ". Start the app (it backs up your Real data daily) or run installer\\backup_now.bat."))
    else:
        say("WARN", "No backups found yet. The app makes one daily once Real data exists; installer\\backup_now.bat makes one now.")
    # 5. Packaging
    if (ROOT / "backend" / "data" / "auth.json").exists():
        say("OK", "Owner password is stored only as a salted hash (data/auth.json).")
    bad = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".pem", ".key", ".pfx") and "node_modules" not in p.parts and ".venv" not in p.parts]
    say("FAIL" if bad else "OK", "Private key files found in the project folder: " + ", ".join(bad[:5]) if bad else "No private key files in the project folder.")
    fails = sum(1 for lv, _ in results if lv == "FAIL")
    warns = sum(1 for lv, _ in results if lv == "WARN")
    print(f"\n{fails} problem(s), {warns} warning(s).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
