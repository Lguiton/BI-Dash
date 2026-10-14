"""Computer control (personal edition only): run a fixed list of Windows maintenance, settings, network, account and security
actions from the dashboard, with guard rails.

How it is kept safe
* Off unless the file `computer_control.enabled` exists in the project folder (or BI_COMPUTER_CONTROL=1). Other copies of the app
  that don't have that file show nothing and do nothing.
* Practice workspace = simulation: shows exactly what would run, runs nothing. Only the Real workspace executes.
* Real needs a PIN you set once. You arm it for 15 minutes; arming is a random token the browser must send with every action.
  Five wrong PINs lock it for five minutes.
* Only actions from the fixed catalogue (sysactions.py) can run. Parameters are validated and passed as environment variables.
* Before a change it records the prior state, so Undo works; risky ones auto-revert unless you press Keep; "Undo everything" replays them.
* Everything is written to the activity log. Passwords are never stored or logged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.config import BASE_DIR
from app.services import state, sysactions, sysscan, workspaces

MARKER = BASE_DIR.parent / "computer_control.enabled"
ARM_SECONDS = 15 * 60
MAX_TRIES, LOCK_SECONDS = 5, 300
UNDO_WINDOW_HOURS = 24
_lock = threading.RLock()
_armed: dict = {"token": None, "until": 0.0}
_fails: dict = {"n": 0, "locked_until": 0.0}
_jobs: dict[str, dict] = {}


class SysError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def enabled() -> bool:
    return os.environ.get("BI_COMPUTER_CONTROL") == "1" or MARKER.exists()


def need_enabled() -> None:
    if not enabled():
        raise SysError("Computer control isn't turned on in this copy of the app.", 404)


# ------------------------------------------------------------------ PIN and arming
def _hash(pin: str, salt: bytes) -> str:
    return hashlib.scrypt(pin.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def pin_is_set() -> bool:
    return bool(state.kv_get("sys_pin"))


def _verify(pin: str) -> bool:
    raw = state.kv_get("sys_pin")
    if not raw:
        return False
    d = json.loads(raw)
    return hmac.compare_digest(_hash(pin or "", bytes.fromhex(d["salt"])), d["hash"])


def _check_lock() -> None:
    if time.time() < _fails["locked_until"]:
        raise SysError(f"Too many wrong PINs. Try again in {int(_fails['locked_until'] - time.time())} seconds.", 429)


def _wrong() -> None:
    _fails["n"] += 1
    if _fails["n"] >= MAX_TRIES:
        _fails.update(n=0, locked_until=time.time() + LOCK_SECONDS)
        state.audit("computer_control_lock", "too many wrong PINs", ok=False)
    raise SysError("That PIN isn't right.", 403)


def set_pin(pin: str, current: str | None = None) -> dict:
    need_enabled()
    if not isinstance(pin, str) or not 6 <= len(pin) <= 64:
        raise SysError("Use a PIN of 6 to 64 characters.")
    if pin_is_set():
        _check_lock()
        if not _verify(current or ""):
            _wrong()
    salt = secrets.token_bytes(16)
    state.kv_set("sys_pin", json.dumps({"salt": salt.hex(), "hash": _hash(pin, salt)}))
    disarm()
    state.audit("computer_control_pin", "PIN set or changed")
    return {"pin_set": True}


def arm(pin: str) -> dict:
    need_enabled()
    if not pin_is_set():
        raise SysError("Set a PIN first.", 409)
    _check_lock()
    if not _verify(pin):
        _wrong()
    _fails["n"] = 0
    with _lock:
        _armed.update(token=secrets.token_urlsafe(32), until=time.time() + ARM_SECONDS)
    state.audit("computer_control_arm", f"armed for {ARM_SECONDS // 60} minutes")
    return {"token": _armed["token"], "seconds": ARM_SECONDS}


def disarm() -> None:
    with _lock:
        if _armed["token"]:
            state.audit("computer_control_disarm", "locked")
        _armed.update(token=None, until=0.0)


def seconds_left() -> int:
    return max(0, int(_armed["until"] - time.time())) if _armed["token"] else 0


def check_token(token: str | None) -> None:
    if not _armed["token"] or time.time() > _armed["until"]:
        raise SysError("Computer control is locked. Enter your PIN to arm it.", 403)
    if not token or not hmac.compare_digest(str(token), _armed["token"]):
        raise SysError("That session isn't armed. Enter your PIN again.", 403)


# ------------------------------------------------------------------ running PowerShell
def find_shell() -> str | None:
    for exe in ("powershell.exe", "pwsh.exe", "powershell", "pwsh"):
        p = shutil.which(exe)
        if p:
            return p
    return None


def run_script(script: str, env_extra: dict[str, str], timeout: int) -> dict:
    """Run one PowerShell script and return rc/out/err. Tests replace this function."""
    exe = find_shell()
    if not exe:
        raise SysError("PowerShell wasn't found. Computer control needs Windows (or WSL on Windows) with PowerShell.", 503)
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    env = os.environ.copy()
    env.update(env_extra)
    names = [k for k in env_extra if k.startswith("BI_")]
    if names:                                             # WSL only hands listed variables to Windows programs
        env["WSLENV"] = ":".join(names + ([env["WSLENV"]] if env.get("WSLENV") else []))
    t0 = time.time()
    try:
        p = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                           capture_output=True, env=env, timeout=timeout, stdin=subprocess.DEVNULL)
        out = p.stdout.decode("utf-8", "replace").replace("\x00", "")[:300_000]
        err = p.stderr.decode("utf-8", "replace").replace("\x00", "")[:20_000]
        return {"rc": p.returncode, "out": out, "err": err, "seconds": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "out": "", "err": f"Timed out after {timeout} seconds.", "seconds": float(timeout)}


# ------------------------------------------------------------------ catalogue and status
def catalog() -> dict:
    return {"categories": [{"id": i, "label": l} for i, l in sysactions.CATEGORIES], "actions": [sysactions.public(a) for a in sysactions.ACTIONS]}


def status() -> dict:
    exe = find_shell() if enabled() else None
    return {"enabled": enabled(), "workspace": workspaces.active(), "live": workspaces.active() == "real", "pin_set": pin_is_set() if enabled() else False,
            "armed_seconds": seconds_left(), "shell": bool(exe), "platform": platform.system() + (" (WSL)" if "microsoft" in platform.release().lower() else ""),
            "pending": pending_reverts(), "arm_minutes": ARM_SECONDS // 60}


def _get(action_id: str) -> dict:
    a = sysactions.BY_ID.get(action_id)
    if not a:
        raise SysError("That action doesn't exist.", 404)
    return a


def clean(a: dict, raw: dict | None) -> dict[str, str]:
    raw = raw or {}
    out = {}
    try:
        for spec in a["params"]:
            out[spec["name"]] = sysactions.validate(spec, raw.get(spec["name"]))
    except sysactions.ParamError as e:
        raise SysError(str(e)) from None
    return out


def _env(params: dict[str, str]) -> dict[str, str]:
    return {f"BI_P_{k}": v for k, v in params.items()}


def _shown(a: dict, params: dict) -> dict:
    sec = {s["name"] for s in a["params"] if s.get("secret")}
    return {k: ("***" if k in sec else v) for k, v in params.items()}


def preview(action_id: str, raw: dict | None) -> dict:
    need_enabled()
    a = _get(action_id)
    params = clean(a, raw) if raw is not None else {}
    return {"id": a["id"], "title": a["title"], "risk": a["risk"], "script": a["script"].strip(), "capture": (a["capture"] or "").strip() or None,
            "restore": (a["restore"] or "").strip() or None, "params": _shown(a, params), "admin": a["admin"], "revert_after": a["revert_after"],
            "note": "The script reads its inputs from environment variables (BI_P_...), so a value can never become code."}


# ------------------------------------------------------------------ changes (history, undo)
def _row(cid: int) -> dict:
    r = state.one("SELECT * FROM sys_changes WHERE id = ?", (cid,))
    if not r:
        raise SysError("That change isn't in the history.", 404)
    return r


def history(limit: int = 60) -> list[dict]:
    rows = state.rows("SELECT id, at, action, title, risk, params, status, output, undone_at, revert_at, kept, (undo_data IS NOT NULL) AS undoable FROM sys_changes ORDER BY id DESC LIMIT ?", (limit,))
    now = time.time()
    for r in rows:
        r["params"] = json.loads(r["params"] or "{}")
        r["undoable"] = bool(r["undoable"]) and r["status"] == "ok" and not r["undone_at"]
        r["revert_in"] = max(0, int(r["revert_at"] - now)) if r["revert_at"] and not r["kept"] and not r["undone_at"] else None
    return rows


def pending_reverts() -> list[dict]:
    return [r for r in history(20) if r["revert_in"] is not None]


def _run_restore(row: dict) -> dict:
    a = _get(row["action"])
    if not a["restore"] or row["undo_data"] is None:
        raise SysError("That change can't be undone from here.", 409)
    res = run_script(a["restore"], {"BI_UNDO": row["undo_data"]}, 300)
    return res


def undo(cid: int, token: str | None) -> dict:
    need_enabled()
    if workspaces.active() != "real":
        raise SysError("Undo runs on your computer, so it only works in the Real workspace.", 409)
    check_token(token)
    row = _row(cid)
    if row["status"] != "ok" or row["undone_at"] or row["undo_data"] is None:
        raise SysError("That change can't be undone (already undone, failed, or not reversible).", 409)
    res = _run_restore(row)
    if res["rc"] != 0:
        state.audit("computer_control_undo", f"#{cid} {row['action']}: {res['err'][:200]}", ok=False)
        raise SysError(f"The undo failed: {res['err'].strip()[:300] or res['out'].strip()[:300]}", 500)
    state.run("UPDATE sys_changes SET undone_at = ?, revert_at = NULL WHERE id = ?", (state.now(), cid))
    state.audit("computer_control_undo", f"#{cid} {row['action']} undone")
    return {"undone": cid, "output": res["out"].strip()[:2000]}


def keep(cid: int) -> dict:
    need_enabled()
    row = _row(cid)
    state.run("UPDATE sys_changes SET kept = 1, revert_at = NULL WHERE id = ?", (cid,))
    state.audit("computer_control_keep", f"#{cid} {row['action']} kept")
    return {"kept": cid}


def undo_all(token: str | None) -> dict:
    need_enabled()
    if workspaces.active() != "real":
        raise SysError("Undo runs on your computer, so it only works in the Real workspace.", 409)
    check_token(token)
    since = (datetime.now(timezone.utc) - timedelta(hours=UNDO_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    rows = state.rows("SELECT * FROM sys_changes WHERE status = 'ok' AND undo_data IS NOT NULL AND undone_at IS NULL AND at >= ? ORDER BY id DESC", (since,))
    done, failed = [], []
    for r in rows:
        try:
            res = _run_restore(r)
            if res["rc"] == 0:
                state.run("UPDATE sys_changes SET undone_at = ?, revert_at = NULL WHERE id = ?", (state.now(), r["id"]))
                done.append(r["id"])
            else:
                failed.append({"id": r["id"], "why": (res["err"] or res["out"]).strip()[:200]})
        except SysError as e:
            failed.append({"id": r["id"], "why": e.message})
    state.audit("computer_control_undo_all", f"undone {len(done)}, failed {len(failed)}", ok=not failed)
    return {"undone": done, "failed": failed, "window_hours": UNDO_WINDOW_HOURS}


def _auto_revert(cid: int) -> None:
    """Puts things back when the Keep button wasn't pressed in time. Safe to run without the PIN: it only restores the prior state."""
    try:
        row = state.one("SELECT * FROM sys_changes WHERE id = ?", (cid,))
        if not row or row["kept"] or row["undone_at"] or row["status"] != "ok" or not row["revert_at"] or row["undo_data"] is None:
            return
        res = _run_restore(row)
        ok = res["rc"] == 0
        if ok:
            state.run("UPDATE sys_changes SET undone_at = ?, revert_at = NULL, output = output || ? WHERE id = ?", (state.now(), "\n[auto-reverted]", cid))
        state.audit("computer_control_auto_revert", f"#{cid} {row['action']} {'reverted' if ok else 'FAILED to revert: ' + res['err'][:150]}", ok=ok)
    except Exception as e:  # noqa: BLE001
        state.audit("computer_control_auto_revert", f"#{cid} error {e}", ok=False)


def process_due_reverts() -> int:
    """Called by the scheduler so a revert still happens if the app was restarted while a timer was running."""
    if not enabled():
        return 0
    n = 0
    for r in state.rows("SELECT id FROM sys_changes WHERE revert_at IS NOT NULL AND revert_at <= ? AND kept = 0 AND undone_at IS NULL", (time.time(),)):
        _auto_revert(r["id"])
        n += 1
    return n


# ------------------------------------------------------------------ running actions
SAMPLE = {
    "scan_startup": [{"where": "HKCU Run", "name": "ExampleSync", "command": "C:\\Users\\you\\AppData\\Local\\Temp\\sync.exe", "exe": "C:\\Users\\you\\AppData\\Local\\Temp\\sync.exe", "sig": "NotSigned", "publisher": ""},
                     {"where": "HKCU Run", "name": "OneDrive", "command": "C:\\Program Files\\Microsoft OneDrive\\OneDrive.exe", "exe": "C:\\Program Files\\Microsoft OneDrive\\OneDrive.exe", "sig": "Valid", "publisher": "CN=Microsoft Corporation"}],
    "scan_processes": [{"name": "notepad", "path": "C:\\Windows\\System32\\notepad.exe", "sig": "Valid", "publisher": "CN=Microsoft Windows", "count": 1}],
    "scan_network": [{"state": "Listen", "laddr": "0.0.0.0", "lport": 8888, "raddr": "0.0.0.0", "rport": 0, "pid": 4242, "proc": "examplesrv", "path": "C:\\Tools\\examplesrv.exe"},
                     {"state": "Established", "laddr": "192.168.1.20", "lport": 50111, "raddr": "93.184.216.34", "rport": 443, "pid": 100, "proc": "chrome", "path": "C:\\Program Files\\Google\\Chrome\\chrome.exe"}],
    "scan_remote": {"processes": [], "apps": [{"DisplayName": "ExampleDesk Remote", "DisplayVersion": "1.0", "Publisher": "Example Inc"}], "rdp_enabled": True, "services": [], "shares": []},
    "scan_privacy": [{"capability": "microphone", "app": "C:#Tools#recorder.exe", "start": 133700000000000000, "stop": 0, "nonpackaged": True}],
    "scan_accounts": {"users": [{"name": "you", "enabled": True, "password_required": True}, {"name": "Guest", "enabled": True, "password_required": False}], "admins": [{"name": "PC\\you", "cls": "User", "source": "Local"}]},
    "scan_system": {"defender": {"antivirus": True, "realtime": True, "signature_age_days": 12, "quick_scan_end": ""}, "threats": [], "firewall": [{"name": "Public", "enabled": "False"}],
                    "hosts": ["0.0.0.0 ads.example.com"], "proxy_enabled": False, "proxy_server": "", "proxy_script": "", "uac_enabled": True},
}


def _record(a: dict, params: dict, status_: str) -> int:
    cur = state.run("INSERT INTO sys_changes (at, workspace, action, title, risk, params, status, output, kept) VALUES (?,?,?,?,?,?,?,?,0)",
                    (state.now(), workspaces.active(), a["id"], a["title"], a["risk"], json.dumps(_shown(a, params)), status_, ""))
    return int(cur.lastrowid)


def _finish(job: dict, **kw) -> None:
    with _lock:
        job.update(kw)


def _analyse(a: dict, out: str) -> dict:
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        return {"parsed": False}
    res = {"parsed": True, "analysis": sysscan.analyze(a["id"], data)}
    if isinstance(data, list):
        res["rows"] = data[:300]
    elif isinstance(data, dict):
        res["data"] = data
    return res


def _work(job: dict, a: dict, params: dict, cid: int | None) -> None:
    env = _env(params)
    undo_data = None
    try:
        if a["restore_point"] and workspaces.active() == "real":
            rp = run_script(sysactions.BY_ID["restore_point"]["script"], {}, 300)
            _finish(job, restore_point="created" if rp["rc"] == 0 else f"skipped ({(rp['err'] or rp['out']).strip()[:120]})")
        if a["capture"]:
            cap = run_script(a["capture"], env, 120)
            if cap["rc"] != 0:
                raise SysError(f"Nothing was changed: couldn't record the current state first ({(cap['err'] or cap['out']).strip()[:200]}).", 500)
            undo_data = cap["out"].strip() or "{}"
        res = run_script(a["script"], env, a["timeout"])
        ok = res["rc"] == 0
        out = (res["out"] + (("\n" + res["err"]) if res["err"].strip() else "")).strip()
        extra = _analyse(a, res["out"]) if (ok and (a["scan"] or a["read"])) else {}
        final = {"output": out[:20000], "seconds": res["seconds"], **extra}
        if cid:
            ra = a["revert_after"]
            if a["id"] == "firewall_set" and params.get("state") == "on":
                ra = None
            revert_at = (time.time() + ra) if (ok and ra and undo_data is not None) else None
            state.run("UPDATE sys_changes SET status = ?, output = ?, undo_data = ?, revert_at = ? WHERE id = ?",
                      ("ok" if ok else "failed", out[:4000], undo_data if ok else None, revert_at, cid))
            final["change_id"] = cid
            if revert_at:
                final["revert_in"] = ra
                t = threading.Timer(ra + 1, _auto_revert, args=(cid,))
                t.daemon = True
                t.start()
        state.audit("computer_control", f"{a['id']} {json.dumps(_shown(a, params))} -> {'ok' if ok else 'failed'}", ok=ok)
        _finish(job, status="ok" if ok else "failed", **final)
        return
    except SysError as e:
        _finish(job, status="failed", output=e.message)
        if cid:
            state.run("UPDATE sys_changes SET status = 'failed', output = ? WHERE id = ?", (e.message, cid))
        state.audit("computer_control", f"{a['id']} refused: {e.message}", ok=False)
    except Exception as e:  # noqa: BLE001
        _finish(job, status="failed", output=f"Unexpected error: {e}")
        if cid:
            state.run("UPDATE sys_changes SET status = 'failed', output = ? WHERE id = ?", (f"Unexpected error: {e}", cid))


def _new_job(a: dict, params: dict, simulated: bool) -> dict:
    job = {"id": uuid.uuid4().hex[:12], "action": a["id"], "title": a["title"], "status": "running", "output": "", "simulated": simulated,
           "started": state.now(), "params": _shown(a, params)}
    with _lock:
        _jobs[job["id"]] = job
        for k in list(_jobs)[:-40]:
            _jobs.pop(k, None)
    return job


def run(action_id: str, raw: dict | None, token: str | None, confirm_word: str | None = None) -> dict:
    need_enabled()
    a = _get(action_id)
    params = clean(a, raw)
    live = workspaces.active() == "real"
    if live:
        check_token(token)
        if a["typed"] and (confirm_word or "").strip().upper() != "CONFIRM":
            raise SysError("This is a high-risk action. Type CONFIRM to go ahead.", 400)
        if not find_shell():
            raise SysError("PowerShell wasn't found. Computer control needs Windows (or WSL on Windows) with PowerShell.", 503)
    job = _new_job(a, params, simulated=not live)
    if not live:
        sample = SAMPLE.get(a["id"])
        extra = {}
        if sample is not None:
            extra = {"analysis": sysscan.analyze(a["id"], sample), "parsed": True}
        _finish(job, status="ok", seconds=0.0, output="PRACTICE MODE: nothing was run on your computer.\n\nThis is what would run in the Real workspace:\n\n" + a["script"].strip()
                + ("\n\n(The results below use made-up example data.)" if sample is not None else ""), **extra)
        state.audit("computer_control_simulated", f"{a['id']} {json.dumps(_shown(a, params))}")
        return job
    cid = None if a["read"] else _record(a, params, "running")
    threading.Thread(target=_work, args=(job, a, params, cid), daemon=True).start()
    return job


def run_scan_all(token: str | None) -> dict:
    need_enabled()
    live = workspaces.active() == "real"
    fake = {"id": "scan_all", "title": "Full security scan", "risk": "low"}
    job = {"id": uuid.uuid4().hex[:12], "action": "scan_all", "title": fake["title"], "status": "running", "output": "", "simulated": not live, "started": state.now(), "params": {}}
    with _lock:
        _jobs[job["id"]] = job
    if not live:
        parts = {i: sysscan.analyze(i, SAMPLE[i]) for i in sysactions.SCAN_ORDER}
        _finish(job, status="ok", output="PRACTICE MODE: made-up example data, nothing was read from your computer.", analysis=sysscan.combine(parts), parsed=True)
        return job
    check_token(token)
    if not find_shell():
        raise SysError("PowerShell wasn't found. Computer control needs Windows (or WSL on Windows) with PowerShell.", 503)

    def work():
        parts, notes = {}, []
        for i in sysactions.SCAN_ORDER:
            a = sysactions.BY_ID[i]
            _finish(job, output=f"Running {a['title']}...")
            try:
                r = run_script(a["script"], {}, a["timeout"])
                if r["rc"] != 0:
                    notes.append(f"{a['title']}: {(r['err'] or r['out']).strip()[:150]}")
                    continue
                data = json.loads(r["out"]) if r["out"].strip() else None
                parts[i] = sysscan.analyze(i, data)
            except Exception as e:  # noqa: BLE001
                notes.append(f"{a['title']}: {e}")
        res = sysscan.combine(parts)
        res["skipped"] = notes
        _finish(job, status="ok", output="Done." + (f" {len(notes)} scan(s) couldn't run (some need administrator rights)." if notes else ""), analysis=res, parsed=True)
        state.audit("computer_control_scan", f"full scan: {res['counts']}")

    threading.Thread(target=work, daemon=True).start()
    return job


def job(job_id: str) -> dict:
    j = _jobs.get(job_id)
    if not j:
        raise SysError("That job isn't known (it may have finished a while ago).", 404)
    return j
