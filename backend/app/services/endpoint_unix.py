"""macOS and Linux hardening audit, in the same style as the Windows one: the app never touches a computer. It writes a READ-ONLY shell script (it only reads
settings and prints ID=VALUE lines), you run it on a machine you own, paste the output back, and it grades each line with the reason and the usual fix.
A short baseline of common checks, not a CIS benchmark. Some lines need administrator rights to read; those show as 'could not read'."""
from __future__ import annotations

import re

MAX_CHARS = 50_000


class UnixError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# id, title, severity (1-3), shell expression, rule, why, fix
MAC = [
    ("mac_filevault", "Disk encryption (FileVault) is on", 3, "fdesetup status 2>/dev/null | head -1", "contains:on", "A lost or stolen Mac should not give up its data.", "System Settings > Privacy & Security > FileVault > Turn on, and store the recovery key safely."),
    ("mac_firewall", "The built-in firewall is on", 2, "/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null", "contains:enabled", "Blocks unwanted incoming connections.", "System Settings > Network > Firewall > On."),
    ("mac_gatekeeper", "Gatekeeper is on", 2, "spctl --status 2>/dev/null", "contains:enabled", "Checks apps are from known developers before they run.", "sudo spctl --master-enable"),
    ("mac_sip", "System Integrity Protection is on", 3, "csrutil status 2>/dev/null", "contains:enabled", "Protects the system files from tampering, even by administrators.", "Restart into Recovery, open Terminal, run: csrutil enable."),
    ("mac_updates", "Automatic update checks are on", 2, "defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled 2>/dev/null", "eq:1", "Most break-ins use holes that already have a fix.", "System Settings > General > Software Update > Automatic updates."),
    ("mac_ssh", "Remote Login (SSH) is off", 2, "systemsetup -getremotelogin 2>/dev/null | head -1", "contains:off", "Remote Login lets others try to sign in over the network. Needs administrator rights to read.", "System Settings > General > Sharing > Remote Login > Off."),
    ("mac_guest", "The guest user is off", 1, "defaults read /Library/Preferences/com.apple.loginwindow GuestEnabled 2>/dev/null", "eq:0", "A guest session is one more way in.", "System Settings > Users & Groups > Guest User > Off."),
]
LINUX = [
    ("linux_firewall", "A firewall is active", 3, 'if command -v ufw >/dev/null 2>&1; then v=$(ufw status 2>/dev/null | head -1); echo "${v:-unknown}"; elif systemctl is-active firewalld >/dev/null 2>&1; then echo active; else echo none; fi', "firewall", "Closes ports that nothing needs open.", "sudo ufw default deny incoming; sudo ufw allow ssh; sudo ufw enable (or enable firewalld)."),
    ("linux_ssh_root", "SSH root login is disabled", 3, "v=$(grep -hiE '^[[:space:]]*PermitRootLogin' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | tail -1 | awk '{print tolower($2)}'); echo \"${v:-unset}\"", "sshroot", "Direct root login is the first thing attackers try.", "Set PermitRootLogin no in /etc/ssh/sshd_config and restart ssh."),
    ("linux_ssh_password", "SSH password login is disabled (keys only)", 2, "v=$(grep -hiE '^[[:space:]]*PasswordAuthentication' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | tail -1 | awk '{print tolower($2)}'); echo \"${v:-unset}\"", "sshpw", "Keys cannot be guessed the way passwords can.", "After keys work, set PasswordAuthentication no and restart ssh. Test in a second terminal first."),
    ("linux_updates", "Automatic security updates are set up", 2, "if dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii'; then echo installed; elif systemctl is-enabled dnf-automatic.timer >/dev/null 2>&1; then echo installed; else echo none; fi", "eq:installed", "Most break-ins use holes that already have a fix.", "sudo apt install unattended-upgrades (Debian/Ubuntu), or enable dnf-automatic (Fedora/RHEL)."),
    ("linux_sudo", "No passwordless sudo rules", 2, "grep -rhE 'NOPASSWD' /etc/sudoers /etc/sudoers.d 2>/dev/null | grep -vE '^[[:space:]]*#' | wc -l | tr -d ' '", "zero", "Passwordless sudo turns any stolen session into full control. Run with sudo to read all files.", "sudo visudo, and remove NOPASSWD entries you do not need."),
    ("linux_luks", "Disk encryption (LUKS) in use", 2, "lsblk -o TYPE 2>/dev/null | grep -c crypt", "luks", "A lost laptop should not give up its data.", "Choose encryption at install, or move sensitive data to an encrypted volume (LUKS)."),
    ("linux_listen", "Few listening network services", 1, "ss -tuln 2>/dev/null | grep -c LISTEN", "listen", "Every listening service is something to keep updated or close.", "Review with: ss -tulnp, and disable services you do not use."),
]
SETS = {"macos": MAC, "linux": LINUX}


def script(os_name: str) -> str:
    if os_name not in SETS:
        raise UnixError("os must be macos or linux.")
    head = ["#!/bin/sh", "# Read-only hardening check. It reads settings and prints ID=VALUE lines. It changes nothing.",
            "# Run in Terminal on a machine you own. Running with sudo gives fuller results." if os_name == "macos" else "# Run in a terminal on a machine you own. Running with sudo gives fuller results (firewall, sudoers).",
            "# Paste the whole output back into the Endpoint hardening tab."]
    return "\n".join(head + [f'echo "{c[0]}=$({c[3]})"' for c in SETS[os_name]]) + "\n"


def _int(v):
    try:
        return int(v.strip())
    except (ValueError, AttributeError):
        return None


def _judge(rule: str, v: str):
    low = v.strip().lower()
    if not low or "not permitted" in low or "error" in low or "unknown" in low or "no such" in low:
        return "unknown", "Could not read this (try running with sudo, or it does not apply to this system)."
    if rule.startswith("contains:"):
        w = rule.split(":", 1)[1]
        if w == "on":
            return ("pass", "on") if re.search(r"\bon\b", low) else ("fail", "off")
        if w == "off":
            return ("pass", "off") if re.search(r"\boff\b", low) else ("fail", "on")
        return ("pass", w) if w in low else ("fail", f"not {w}")
    if rule.startswith("eq:"):
        return ("pass", "set") if low == rule.split(":", 1)[1] else ("fail", f"value {v.strip()}")
    if rule == "firewall":
        return ("pass", "active") if "status: active" in low or low == "active" else (("fail", "none found or inactive"))
    if rule == "sshroot":
        return ("pass", "disabled") if low == "no" else (("warn", "keys only (prohibit-password); fine, but 'no' is stricter") if low in ("prohibit-password", "without-password") else (("fail", "root login allowed") if low == "yes" else ("warn", "no explicit setting: the default depends on the version")))
    if rule == "sshpw":
        return ("pass", "keys only") if low == "no" else (("warn", "passwords allowed: turn off once keys work") if low in ("yes", "unset") else ("unknown", f"value {v.strip()}"))
    if rule == "zero":
        n = _int(v)
        return ("pass", "none found") if n == 0 else (("fail", f"{n} rule(s)") if n else ("unknown", f"value {v.strip()}"))
    if rule == "luks":
        n = _int(v)
        return ("pass", f"{n} encrypted volume(s)") if n else (("warn", "none seen: fine only if nothing sensitive is stored, or it is encrypted another way") if n == 0 else ("unknown", f"value {v.strip()}"))
    if rule == "listen":
        n = _int(v)
        return ("pass", f"{n} listening") if n is not None and n <= 10 else (("warn", f"{n} listening: review them") if n is not None else ("unknown", f"value {v.strip()}"))
    return "unknown", "no rule"


def grade(text: str, os_name: str) -> dict:
    if os_name not in SETS:
        raise UnixError("os must be macos or linux.")
    if not isinstance(text, str) or not text.strip():
        raise UnixError("Paste the output of the script first.")
    if len(text) > MAX_CHARS:
        raise UnixError("That is over 50,000 characters; paste only the script's output.", 413)
    ids = {c[0] for c in SETS[os_name]}
    found: dict[str, str] = {}
    for raw in text.splitlines():
        m = re.match(r"^\s*([a-z0-9_]+)\s*=\s*(.*?)\s*$", raw, re.I)
        if m and m.group(1).lower() in ids:
            found[m.group(1).lower()] = m.group(2)
    if not found:
        raise UnixError(f"I found no result lines for {os_name}. The script prints lines like {SETS[os_name][0][0]}=...; paste its output as it appeared.")
    rows, got, total = [], 0.0, 0
    for cid, title, sev, _e, rule, why, fix in SETS[os_name]:
        if cid not in found:
            rows.append({"id": cid, "title": title, "severity": sev, "status": "missing", "value": None, "note": "Not in the pasted output.", "why": why, "fix": fix})
            continue
        status, note = _judge(rule, found[cid])
        if status != "unknown":
            total += sev
            got += sev if status == "pass" else (sev * 0.5 if status == "warn" else 0)
        rows.append({"id": cid, "title": title, "severity": sev, "status": status, "value": found[cid], "note": note, "why": why, "fix": fix})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("pass", "warn", "fail", "unknown", "missing")}
    order = {"fail": 0, "warn": 1}
    todo = sorted((r for r in rows if r["status"] in order), key=lambda r: (order[r["status"]], -r["severity"]))[:5]
    return {"os": os_name, "score_pct": round(100 * got / total) if total else None, "counts": counts, "rows": rows, "start_with": [{"id": r["id"], "title": r["title"], "status": r["status"], "fix": r["fix"]} for r in todo],
            "fix_id": "mac-hardening" if os_name == "macos" else "linux-hardening",
            "limit": "A short baseline of common settings from one machine, not a CIS benchmark. It cannot see malware, other machines, or settings it does not read, and a pass is not a guarantee."}
