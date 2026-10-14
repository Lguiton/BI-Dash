"""A scored, read-only health check of this dashboard (AIDA-style). Changes nothing and never shows a secret."""
from __future__ import annotations

import os
from datetime import datetime

from app.services import auth, backups, state, workspaces


LAPTOP_KEYS = ("encrypted", "locks", "findmy", "windows_signin")
LAPTOP_TEXT = {
    "encrypted": ("Disk encryption (BitLocker or Device Encryption) is on", "Settings, Privacy & security, Device encryption or BitLocker. Without it, a lost laptop exposes your clients' data."),
    "locks": ("The laptop locks itself after a few minutes", "Windows Settings, Accounts, Sign-in options, and set a short screen timeout."),
    "findmy": ("Find my device is on", "Windows Settings, Privacy & security, Find my device, so you can lock or wipe it if it is stolen."),
    "windows_signin": ("Windows needs a password or PIN to sign in", "A laptop with no sign-in lets anyone who picks it up open the dashboard."),
}


def laptop() -> dict:
    d = state.setting_get("real", "laptop", None) or {}
    return {"laptop": bool(d.get("laptop")), **{k: bool(d.get(k)) for k in LAPTOP_KEYS}, "text": {k: {"label": v[0], "how": v[1]} for k, v in LAPTOP_TEXT.items()}}


def set_laptop(body: dict) -> dict:
    cur = laptop()
    new = {"laptop": bool(body.get("laptop", cur["laptop"])), **{k: bool(body.get(k, cur[k])) for k in LAPTOP_KEYS}}
    state.setting_set("real", "laptop", new)
    state.audit("laptop_safety", ", ".join(f"{k}={v}" for k, v in new.items()))
    return laptop()


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    checks: list[dict] = []

    def add(name: str, level: str, detail: str, fix: str = ""):
        checks.append({"name": name, "level": level, "detail": detail, "fix": fix})

    # Login
    if auth.enabled():
        add("Login", "ok", "Sign-in is turned on.")
    else:
        extra = {h for h in os.environ.get("BI_ALLOWED_HOSTS", "").split(",") if h.strip()}
        if extra:
            add("Login", "bad", "Login is off but extra host names are allowed, so others may reach it.", "Set BI_AUTH=1 and BI_OWNER_PASSWORD in backend/.env.")
        else:
            add("Login", "ok", "Login is off, which is fine because only this computer can reach the dashboard.")
    pw = os.environ.get("BI_OWNER_PASSWORD", "")
    if auth.enabled():
        add("Password strength", "ok" if len(pw) >= 12 else "warn", "Password is long enough." if len(pw) >= 12 else "The owner password is shorter than 12 characters.", "Use a longer passphrase.")
    # Hosts
    add("Allowed host names", "ok" if not os.environ.get("BI_ALLOWED_HOSTS") else "warn",
        "Only this computer's names are served." if not os.environ.get("BI_ALLOWED_HOSTS") else "Extra host names are allowed (hosted setup).", "Remove BI_ALLOWED_HOSTS unless you host it online.")
    # Backups
    try:
        b = backups.list_backups("real")
    except Exception:  # noqa: BLE001
        b = []
    if not b:
        add("Backups", "warn", "No backup of the Real workspace yet.", "Run backup_now.bat or use the Backups page.")
    else:
        age = (now - datetime.strptime(b[0]["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 86400
        add("Backups", "ok" if age <= 2 else "warn", f"Newest backup is {age:.1f} day(s) old.", "" if age <= 2 else "Open the dashboard once a day or run backup_now.bat.")
    # Audit chain
    v = state.audit_verify()
    add("Activity log seal", "ok" if v["ok"] else "bad", v["message"], "" if v["ok"] else "Someone or something edited the history. Restore from a backup and check the machine.")
    # Failed logins in the last 24 h
    try:
        fails = state.one("SELECT COUNT(*) AS n FROM audit WHERE action='login_failed' AND at >= ?", ((now.astimezone() if now.tzinfo else now).strftime("%Y-%m-%d %H:%M:%S")[:10],))["n"]
    except Exception:  # noqa: BLE001
        fails = 0
    add("Failed sign-ins today", "ok" if fails == 0 else ("warn" if fails < 5 else "bad"), f"{fails} failed sign-in(s) today.", "" if fails == 0 else "If it was not you, change the password and sign out everywhere.")
    lp = laptop()
    if lp["laptop"]:
        for k in LAPTOP_KEYS:
            add("Laptop: " + LAPTOP_TEXT[k][0], "ok" if lp[k] else "bad", "Confirmed." if lp[k] else "Not confirmed yet.", "" if lp[k] else LAPTOP_TEXT[k][1])
        add("Laptop: sign-in to the dashboard", "ok" if auth.enabled() else "bad", "Dashboard sign-in is on." if auth.enabled() else "Dashboard sign-in is off.", "" if auth.enabled() else "Set BI_AUTH=1 and BI_OWNER_PASSWORD in backend/.env, then restart.")
        cf = backups.copy_folder()
        good = bool(cf["folder"]) and cf["last"].endswith(" ok")
        add("Laptop: backup copy off the disk", "ok" if good else "warn", f"Copies go to {cf['folder']}." if good else ("No backup copy folder is set." if not cf["folder"] else "The last copy to the folder failed: " + cf["last"]),
            "" if good else "In Settings, set a USB drive or a OneDrive or Google Drive folder under Laptop and travel.")
    add("Workspace", "ok", f"Active workspace: {workspaces.active()}.")
    weight = {"ok": 0, "warn": 10, "bad": 30}
    score = max(0, 100 - sum(weight[c["level"]] for c in checks))
    needs = [c for c in checks if c["level"] != "ok"]
    return {"score": score, "grade": "Good" if score >= 90 else ("Fair" if score >= 70 else "Needs attention"), "checks": checks, "needs_attention": needs}
