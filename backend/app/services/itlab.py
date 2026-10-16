"""IT Specialist track: helpdesk tickets with SLA clocks, an asset inventory, a Windows event-log reader, onboarding/offboarding
checklists, capacity / availability / RAID calculators and command cheat sheets.

Honest limits
* The helpdesk and inventory are small personal trackers (what osTicket, GLPI or Snipe-IT do at company scale). No email intake,
  no user portal, no discovery agent: you type things in.
* SLA targets are simple elapsed hours by priority, not business hours.
* The event-log reader works on text or CSV you export from Windows Event Viewer. Event IDs are looked up in a fixed table of well-known
  IDs; anything else is shown as unknown. Findings are leads, not verdicts.
* Calculators are exact arithmetic with the assumptions printed next to the answer.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from app.services import state, workspaces


class ItError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


# ============================================================ helpdesk
CATEGORIES = {
    "hardware": ("Hardware", ["Ask what changed and when it last worked", "Check power, cables and indicator lights", "Try a known-good cable, port or power supply", "Check the device in Device Manager / system report", "Swap or repair; record the serial number"]),
    "software": ("Software or app", ["Get the exact error text or a screenshot", "Does it fail for other users or only this one?", "Restart the app, then the machine", "Check for recent updates or installs", "Repair or reinstall; test with a fresh profile"]),
    "network": ("Network or Wi-Fi", ["Can others on the same network connect?", "ipconfig /all: is there a valid address and gateway?", "Ping the gateway, then 8.8.8.8, then a name", "Is it DNS? IP works but names don't", "Try another cable, port or access point"]),
    "account": ("Account or password", ["Verify the person's identity first", "Check for a lockout or expired password", "Reset the password and require a change at next sign-in", "Confirm MFA works", "Look for repeated failures that suggest an attack"]),
    "email": ("Email", ["Webmail or desktop client only?", "Check storage quota and rules", "Check spam and quarantine", "Recreate the profile if only one client fails", "Check SPF, DKIM and DMARC if mail to outsiders bounces"]),
    "printer": ("Printer", ["Power, paper and toner", "Is the printer online and the right default?", "Clear the print queue and restart the spooler", "Reinstall the driver", "Try a direct IP port instead of a name"]),
    "other": ("Something else", ["Describe the problem in the user's words", "Reproduce it", "Find what changed", "Fix and confirm with the user", "Write down the fix"]),
}
PRIORITIES = {"urgent": 4, "high": 8, "medium": 24, "low": 72}          # target hours to resolve
STATUSES = ("open", "in_progress", "waiting", "resolved", "closed")


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _ticket(r: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    r["timeline"] = json.loads(r["timeline"] or "[]")
    r["checklist"] = json.loads(r["checklist"] or "[]")
    r["category_label"] = CATEGORIES.get(r["category"], (r["category"],))[0]
    r["sla_hours"] = PRIORITIES.get(r["priority"], 24)
    opened = _parse(r["opened_at"])
    end = _parse(r["resolved_at"]) if r["resolved_at"] else now
    hrs = (end - opened).total_seconds() / 3600
    r["age_hours"] = round(hrs, 1)
    r["is_open"] = r["status"] not in ("resolved", "closed")
    r["breached"] = hrs > r["sla_hours"]
    r["hours_left"] = round(r["sla_hours"] - hrs, 1) if r["is_open"] else None
    return r


def tickets(now: datetime | None = None) -> dict:
    rows = [_ticket(r, now) for r in state.rows("SELECT * FROM it_tickets WHERE workspace = ? ORDER BY id DESC", (_ws(),))]
    done = [r["age_hours"] for r in rows if not r["is_open"]]
    open_ = [r for r in rows if r["is_open"]]
    return {"tickets": rows,
            "stats": {"open": len(open_), "total": len(rows), "breached_open": sum(1 for r in open_ if r["breached"]),
                      "mean_hours_to_resolve": round(sum(done) / len(done), 1) if done else None,
                      "resolved_within_sla_pct": round(100 * sum(1 for r in rows if not r["is_open"] and not r["breached"]) / len(done)) if done else None,
                      "by_category": dict(Counter(r["category_label"] for r in rows))},
            "categories": [{"id": k, "label": v[0], "checklist": v[1]} for k, v in CATEGORIES.items()],
            "sla": PRIORITIES,
            "note": "SLA = elapsed hours to resolve by priority (urgent 4, high 8, medium 24, low 72). Business hours aren't modelled."}


def open_ticket(title: str, category: str, priority: str, requester: str = "", note: str = "") -> dict:
    title = (title or "").strip()[:140]
    if not title:
        raise ItError("Give the ticket a short title.")
    if category not in CATEGORIES:
        raise ItError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if priority not in PRIORITIES:
        raise ItError(f"Priority must be one of: {', '.join(PRIORITIES)}.")
    now = state.now()
    tl = [{"at": now, "text": "Opened." + (f" {note.strip()[:300]}" if note.strip() else "")}]
    cl = [{"text": t, "done": False} for t in CATEGORIES[category][1]]
    cur = state.run("INSERT INTO it_tickets (workspace, title, category, priority, status, requester, opened_at, timeline, checklist) VALUES (?,?,?,?,?,?,?,?,?)",
                    (_ws(), title, category, priority, "open", (requester or "").strip()[:80], now, json.dumps(tl), json.dumps(cl)))
    state.audit("it_ticket_open", f"{title} ({priority})")
    return get_ticket(int(cur.lastrowid))


def get_ticket(tid: int) -> dict:
    r = state.one("SELECT * FROM it_tickets WHERE id = ? AND workspace = ?", (tid, _ws()))
    if not r:
        raise ItError("No such ticket.", 404)
    return _ticket(r)


def update_ticket(tid: int, status: str | None = None, note: str | None = None, tick: dict | None = None, priority: str | None = None) -> dict:
    r = get_ticket(tid)
    tl, cl, now = r["timeline"], r["checklist"], state.now()
    sets, args = [], []
    if priority and priority != r["priority"]:
        if priority not in PRIORITIES:
            raise ItError(f"Priority must be one of: {', '.join(PRIORITIES)}.")
        tl.append({"at": now, "text": f"Priority changed to {priority}."})
        sets.append("priority = ?"); args.append(priority)
    if status and status != r["status"]:
        if status not in STATUSES:
            raise ItError(f"Status must be one of: {', '.join(STATUSES)}.")
        tl.append({"at": now, "text": f"Status: {status}."})
        sets.append("status = ?"); args.append(status)
        sets.append("resolved_at = ?"); args.append(now if status in ("resolved", "closed") else None)
    if note and note.strip():
        tl.append({"at": now, "text": note.strip()[:500]})
    if tick is not None:
        i = tick.get("index")
        if not isinstance(i, int) or not 0 <= i < len(cl):
            raise ItError("No such checklist item.")
        cl[i]["done"] = bool(tick.get("done"))
        sets.append("checklist = ?"); args.append(json.dumps(cl))
    sets.append("timeline = ?"); args.append(json.dumps(tl[-100:]))
    state.run(f"UPDATE it_tickets SET {', '.join(sets)} WHERE id = ?", (*args, tid))
    state.audit("it_ticket_update", f"#{tid} {status or ''}".strip())
    return get_ticket(tid)


def delete_ticket(tid: int) -> None:
    get_ticket(tid)
    state.run("DELETE FROM it_tickets WHERE id = ?", (tid,))


# ============================================================ inventory
KINDS = ("laptop", "desktop", "server", "phone", "printer", "network", "other")
ASSET_STATUS = ("in_use", "spare", "repair", "retired")


def _date(v, what: str) -> str | None:
    v = (v or "").strip() if isinstance(v, str) else v
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)).isoformat()
    except ValueError:
        raise ItError(f"{what} must be a date like 2026-03-31.") from None


def _asset(r: dict, today: date | None = None) -> dict:
    today = today or date.today()
    r["warranty_state"] = "unknown"
    if r["warranty_end"]:
        d = (date.fromisoformat(r["warranty_end"]) - today).days
        r["warranty_days_left"] = d
        r["warranty_state"] = "expired" if d < 0 else "expiring" if d <= 90 else "ok"
    else:
        r["warranty_days_left"] = None
    return r


def assets(today: date | None = None) -> dict:
    rows = [_asset(r, today) for r in state.rows("SELECT * FROM it_assets WHERE workspace = ? ORDER BY hostname COLLATE NOCASE", (_ws(),))]
    live = [r for r in rows if r["status"] != "retired"]
    return {"assets": rows, "kinds": list(KINDS), "statuses": list(ASSET_STATUS),
            "stats": {"total": len(rows), "in_use": sum(1 for r in rows if r["status"] == "in_use"), "warranty_expiring": sum(1 for r in live if r["warranty_state"] == "expiring"),
                      "warranty_expired": sum(1 for r in live if r["warranty_state"] == "expired"), "by_kind": dict(Counter(r["kind"] for r in rows)),
                      "by_os": dict(Counter((r["os"] or "unknown") for r in live))},
            "note": "A manual inventory. It only knows what you type in; there is no network discovery."}


def add_asset(hostname: str, kind: str, os_: str = "", owner: str = "", serial: str = "", purchased: str = "", warranty_end: str = "", status: str = "in_use", notes: str = "") -> dict:
    hostname = (hostname or "").strip()[:80]
    if not hostname:
        raise ItError("Give the asset a name.")
    if kind not in KINDS:
        raise ItError(f"Kind must be one of: {', '.join(KINDS)}.")
    if status not in ASSET_STATUS:
        raise ItError(f"Status must be one of: {', '.join(ASSET_STATUS)}.")
    if state.one("SELECT 1 FROM it_assets WHERE workspace = ? AND lower(hostname) = lower(?)", (_ws(), hostname)):
        raise ItError("An asset with that name already exists.", 409)
    cur = state.run("INSERT INTO it_assets (workspace, hostname, kind, os, owner, serial, purchased, warranty_end, status, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (_ws(), hostname, kind, (os_ or "")[:60], (owner or "")[:60], (serial or "")[:60], _date(purchased, "Purchase date"), _date(warranty_end, "Warranty end"),
                     status, (notes or "")[:300], state.now()))
    state.audit("it_asset_add", hostname)
    return _asset(state.one("SELECT * FROM it_assets WHERE id = ?", (cur.lastrowid,)))


def update_asset(aid: int, changes: dict) -> dict:
    r = state.one("SELECT * FROM it_assets WHERE id = ? AND workspace = ?", (aid, _ws()))
    if not r:
        raise ItError("No such asset.", 404)
    sets, args = [], []
    for k in ("os", "owner", "serial", "notes"):
        if k in changes and changes[k] is not None:
            sets.append(f"{k} = ?"); args.append(str(changes[k])[:300 if k == "notes" else 60])
    for k, label in (("purchased", "Purchase date"), ("warranty_end", "Warranty end")):
        if k in changes and changes[k] is not None:
            sets.append(f"{k} = ?"); args.append(_date(changes[k], label))
    if changes.get("status"):
        if changes["status"] not in ASSET_STATUS:
            raise ItError(f"Status must be one of: {', '.join(ASSET_STATUS)}.")
        sets.append("status = ?"); args.append(changes["status"])
    if sets:
        state.run(f"UPDATE it_assets SET {', '.join(sets)} WHERE id = ?", (*args, aid))
        state.audit("it_asset_update", r["hostname"])
    return _asset(state.one("SELECT * FROM it_assets WHERE id = ?", (aid,)))


def delete_asset(aid: int) -> None:
    if not state.one("SELECT 1 FROM it_assets WHERE id = ? AND workspace = ?", (aid, _ws())):
        raise ItError("No such asset.", 404)
    state.run("DELETE FROM it_assets WHERE id = ?", (aid,))


# ============================================================ Windows event log reader
EVENTS = {
    4624: ("Successful logon", "info"), 4625: ("Failed logon", "watch"), 4634: ("Logoff", "info"), 4648: ("Logon with explicit credentials", "watch"),
    4672: ("Special privileges assigned to a new logon", "watch"), 4688: ("A process was created", "info"), 4697: ("A service was installed", "watch"),
    4698: ("A scheduled task was created", "watch"), 4720: ("User account created", "watch"), 4722: ("User account enabled", "info"),
    4723: ("Password change attempted", "info"), 4724: ("Password reset attempted", "watch"), 4725: ("User account disabled", "info"),
    4726: ("User account deleted", "watch"), 4728: ("Member added to a global security group", "watch"), 4732: ("Member added to a local security group", "watch"),
    4740: ("Account locked out", "watch"), 4756: ("Member added to a universal security group", "watch"), 4768: ("Kerberos ticket (TGT) requested", "info"),
    4769: ("Kerberos service ticket requested", "info"), 4771: ("Kerberos pre-authentication failed", "watch"), 4776: ("NTLM credential validation", "info"),
    1102: ("Security audit log was cleared", "alert"), 104: ("An event log was cleared", "alert"), 7045: ("A service was installed (System log)", "watch"),
    7036: ("A service changed state", "info"), 41: ("Rebooted without a clean shutdown (Kernel-Power)", "watch"), 6005: ("Event log service started (boot)", "info"),
    6006: ("Event log service stopped (shutdown)", "info"), 6008: ("Previous shutdown was unexpected", "watch"), 1074: ("Shutdown or restart initiated", "info"),
    4104: ("PowerShell script block logged", "info"),
    # Routine Windows background events you will see thousands of times
    5379: ("Credential Manager credentials were read", "info"), 5382: ("Credentials were read from the Windows Vault", "info"),
    4798: ("A user's local group membership was enumerated", "info"), 4799: ("A local group's membership was enumerated", "info"),
    4797: ("An attempt was made to check for a blank password", "info"), 4738: ("A user account was changed", "watch"),
    5058: ("Key file operation (cryptographic key store)", "info"), 5059: ("Key migration operation", "info"), 5061: ("Cryptographic operation", "info"),
    5024: ("Windows Firewall service started", "info"), 5033: ("Windows Firewall driver started", "info"),
    4902: ("The per-user audit policy table was created", "info"), 4608: ("Windows is starting up", "info"), 4826: ("Boot configuration data was loaded", "info"),
    4696: ("A primary token was assigned to a process", "info"), 4616: ("The system time was changed", "info"), 4647: ("User-initiated logoff", "info"),
    4673: ("A privileged service was called", "info"), 4674: ("An operation was attempted on a privileged object", "info"), 4689: ("A process exited", "info"),
    4703: ("A token right was adjusted", "info"), 4719: ("System audit policy was changed", "watch"), 4729: ("Member removed from a global security group", "watch"),
    4733: ("Member removed from a local security group", "watch"), 4946: ("A Windows Firewall rule was added", "watch"), 4947: ("A Windows Firewall rule was modified", "watch"),
    5140: ("A network share was accessed", "info"), 5145: ("A network share object was checked for access", "info"),
    5156: ("The Filtering Platform permitted a connection", "info"), 5157: ("The Filtering Platform blocked a connection", "info"),
}
SAMPLE_EVENTS = """Date,Time,Id,Source,Account,Message
2026-10-08,09:00:01,4624,Microsoft-Windows-Security-Auditing,alice,An account was successfully logged on. Source Network Address: 192.0.2.20
2026-10-08,09:05:11,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:13,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:15,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:17,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:19,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:21,4625,Microsoft-Windows-Security-Auditing,bob,An account failed to log on. Source Network Address: 203.0.113.9
2026-10-08,09:05:23,4740,Microsoft-Windows-Security-Auditing,bob,A user account was locked out.
2026-10-08,09:07:02,4624,Microsoft-Windows-Security-Auditing,bob,An account was successfully logged on. Source Network Address: 203.0.113.9
2026-10-08,09:09:40,4720,Microsoft-Windows-Security-Auditing,bob,A user account was created. Account Name: svc_backup2
2026-10-08,09:10:02,4732,Microsoft-Windows-Security-Auditing,bob,A member was added to a security-enabled local group. Group: Administrators
2026-10-08,09:12:30,7045,Service Control Manager,SYSTEM,A service was installed in the system. Service Name: updater
2026-10-08,09:15:00,1102,Microsoft-Windows-Eventlog,bob,The audit log was cleared.
2026-10-08,12:00:00,6008,EventLog,SYSTEM,The previous system shutdown at 11:58:02 was unexpected.
"""
_ID_RE = re.compile(r"(?:event\s*id|eventid|\bid)\s*[:=]?\s*(\d{1,5})\b", re.I)
_IP_RE = re.compile(r"(?:source network address|ipaddress|client address)\s*[:=]\s*(\d+\.\d+\.\d+\.\d+)", re.I)
_ACCT_RE = re.compile(r"(?:account name|targetusername)\s*[:=]\s*([^\s,;]+)", re.I)


MAX_EVENT_ROWS = 200_000
MAX_EVENT_BYTES = 25 * 1024 * 1024


def decode_export(raw: bytes) -> str:
    """Windows exports are UTF-8 (often with a BOM) or UTF-16; try each."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8-sig", "replace")


def _event_rows(text: str) -> list[dict]:
    lines = [l for l in text.splitlines() if l.strip()]
    out: list[dict] = []
    if not lines:
        return out
    first = lines[0]
    delim = "\t" if first.count("\t") >= 2 else ";" if first.count(";") > first.count(",") else ","
    head = [h.strip().lower() for h in next(csv.reader([first], delimiter=delim))]
    id_col = next((i for i, h in enumerate(head) if h.replace("_", " ").replace("-", " ") in ("id", "eventid", "event id")), None)
    if id_col is not None:
        acct = next((i for i, h in enumerate(head) if h in ("account", "user", "username", "account name")), None)
        for row in csv.reader(lines[1:], delimiter=delim):
            if len(row) <= id_col or not row[id_col].strip().isdigit():
                continue
            blob = ",".join(row)
            ip = _IP_RE.search(blob)
            out.append({"id": int(row[id_col]), "account": (row[acct].strip() if acct is not None and acct < len(row) else (_ACCT_RE.search(blob) or [None, ""])[1]) or None,
                        "ip": ip.group(1) if ip else None, "line": blob[:200]})
            if len(out) >= MAX_EVENT_ROWS:
                break
        return out
    for l in lines:
        m = _ID_RE.search(l)
        if m:
            event_id = int(m.group(1))
        else:
            # Event Viewer's list copied as text: "Audit Success<TAB>10/10/2026 8:49:36 AM<TAB>Source<TAB>4799<TAB>Category"
            parts = [p.strip() for p in re.split(r"\t+|\s{2,}", l.strip()) if p.strip()]
            hit = next((p for i, p in enumerate(parts) if i >= 2 and p.isdigit() and len(p) <= 5), None)
            if hit is None:
                continue
            event_id = int(hit)
        a, ip = _ACCT_RE.search(l), _IP_RE.search(l)
        out.append({"id": event_id, "account": a.group(1) if a else None, "ip": ip.group(1) if ip else None, "line": l[:200]})
        if len(out) >= MAX_EVENT_ROWS:
            break
    return out


def read_events(text: str, limit: int = 400_000) -> dict:
    if not (text or "").strip():
        raise ItError("Paste an event-log export first.")
    if len(text) > limit:
        raise ItError("That export is over 400 KB. Paste a smaller slice, or use Open file.")
    rows = _event_rows(text)
    if not rows:
        raise ItError("No event IDs found. Export from Event Viewer as CSV (Save All Events As), or paste lines that contain 'Event ID: 4625' or an Event ID column. A .evtx file is binary and can't be read here.")
    counts = Counter(r["id"] for r in rows)
    table = [{"id": i, "count": n, "meaning": EVENTS.get(i, ("Not in this app's table of well-known IDs", "unknown"))[0],
              "level": EVENTS.get(i, ("", "unknown"))[1]} for i, n in counts.most_common()]
    f = []

    def add(sev, title, detail, advice, ev):
        f.append({"severity": sev, "title": title, "detail": detail, "advice": advice, "evidence": ev[:5]})

    fails = [r for r in rows if r["id"] == 4625]
    if len(fails) >= 5:
        by = Counter((r["ip"] or "unknown") for r in fails)
        who = Counter((r["account"] or "unknown") for r in fails)
        add("medium", f"{len(fails)} failed logons", f"Most from {by.most_common(1)[0][0]} against {who.most_common(1)[0][0]}.",
            "Check the source. Many failures then a success from the same address is a classic takeover pattern.", [r["line"] for r in fails])
        ok_after = [r for r in rows if r["id"] == 4624 and r["ip"] in by and r["ip"]]
        if ok_after:
            add("high", "A successful logon came from an address that had failed logons", f"{ok_after[0]['ip']} logged on successfully.", "Treat the account as compromised until proven otherwise: reset it, check what it did afterwards.", [r["line"] for r in ok_after])
    for eid, sev, title, advice in ((1102, "high", "The security audit log was cleared", "Clearing logs is a classic way to hide activity. Find who did it and why."),
                                    (104, "high", "An event log was cleared", "Find who cleared it and why."),
                                    (4740, "medium", "Account lockouts", "Find the source of the failed attempts (an old password on a phone is common)."),
                                    (4720, "medium", "New user account created", "Was this expected? Check who created it."),
                                    (4732, "medium", "Member added to a local group", "If the group is Administrators, confirm it was approved."),
                                    (4728, "medium", "Member added to a global group", "Confirm it was approved."),
                                    (7045, "medium", "A new service was installed", "Unexpected services are a persistence technique; verify the file and publisher."),
                                    (4698, "medium", "Scheduled task created", "Check the action it runs."),
                                    (6008, "low", "Unexpected shutdown", "Check power, hardware and recent updates."), (41, "low", "Rebooted without a clean shutdown", "Check power, hardware and drivers.")):
        hit = [r for r in rows if r["id"] == eid]
        if hit:
            add(sev, f"{title} ({len(hit)})", EVENTS[eid][0], advice, [r["line"] for r in hit])
    order = {"high": 0, "medium": 1, "low": 2}
    f.sort(key=lambda x: order[x["severity"]])
    return {"events": len(rows), "distinct_ids": len(counts), "table": table, "findings": f,
            "caveat": "Leads, not verdicts. Only well-known IDs are named; an unknown ID isn't necessarily harmless. Event Viewer remains the source of truth."}


# ============================================================ onboarding / offboarding
CHECKLISTS = {
    "onboard": ("Onboard a new person", ["Create the account with a unique name and a temporary password", "Add to the right groups (least privilege)", "Enrol multi-factor sign-in", "Create the mailbox and add to distribution lists",
                                          "Assign and image a device; record it in the inventory", "Install the standard software", "Give access to the shared drives and apps they need", "Walk through password manager, VPN and how to ask for help",
                                          "Record who approved the access"]),
    "offboard": ("Offboard someone who is leaving", ["Disable the account (don't delete yet)", "Reset the password and sign out every session", "Revoke MFA devices, tokens and keys", "Remove from groups and shared drives",
                                                      "Forward or archive the mailbox as policy says", "Collect and wipe the devices; mark them in the inventory", "Transfer ownership of files and shared resources",
                                                      "Cancel licences and remove from vendor portals", "Delete the account after the retention period"]),
    "new_pc": ("Set up a new computer", ["Update the firmware and OS", "Turn on full-disk encryption and store the recovery key safely", "Create a standard user plus a separate admin account", "Install the endpoint protection and the standard apps",
                                         "Turn on the firewall and automatic updates", "Join the domain or management system", "Set the backup", "Label it and add it to the inventory"]),
    "malware": ("SOHO malware removal (A+ 2.6)", ["Investigate and verify the symptoms", "Quarantine the infected system (unplug it from the network)", "Disable System Restore in Windows Home (so infected restore points are not kept)", "Remediate: remove the malware with updated tools, in safe mode or a rescue environment if needed",
                                                  "Update the anti-malware software", "Scan again and use removal techniques (safe mode, pre-installation environment)", "Reimage or reinstall if the system can't be trusted", "Schedule scans and run updates",
                                                  "Turn System Restore back on and create a new restore point", "Educate the user about how it happened"]),
    "change": ("Make a change safely (A+ 4.2)", ["Write the purpose and scope of the change", "Say which systems and people are affected", "Pick the type: standard, normal or emergency", "Assess the risk and give it a level", "Write the rollback plan and take a backup",
                                                "Test it in a sandbox or on a spare machine", "Get approval (change board for normal changes) and pick a window outside any change freeze", "Implement it, with a second person reviewing if you can", "Get end-user acceptance", "Record the outcome"]),
    "disposal": ("Retire a drive or device safely (A+ 2.9)", ["Confirm what data it held and who owns it", "Check retention and legal requirements before destroying anything", "Back up anything still needed", "Wipe it: overwrite or secure erase (SSDs: use the drive's secure erase)", "If the data is sensitive, destroy the drive: shred, drill, degauss (magnetic disks only) or incinerate",
                                                    "Use a vendor that gives a certificate of destruction or recycling", "Dispose of batteries and toner as hazardous waste", "Update the inventory and keep the certificate"]),
    "method": ("Troubleshooting method (A+)", ["Identify the problem: ask questions, find what changed, back up first", "Establish a theory of probable cause (question the obvious)", "Test the theory to confirm the cause, or form a new theory", "Plan the fix, including any side effects, and implement it", "Verify the whole system works and add preventive measures", "Document the findings, actions and outcome"]),
    "fwapp": ("An app can't reach the network: is Windows Firewall blocking it?", ["Confirm the symptom is that one program fails while the browser and ping work, and note the exact program path", "Check you are an administrator; on a work PC, ask whether Group Policy manages the firewall, because it overrides local rules",
                                                                                    "Open wf.msc, then Outbound Rules, and search for a Block rule naming the program; also check Inbound Rules if the program listens for connections", "Look at the profile's default outbound action (Windows Defender Firewall Properties): block by default means every program needs an allow rule",
                                                                                    "Prefer deleting or disabling a stray Block rule: a Block rule beats an Allow rule, so adding an allow does nothing", "If you add an Allow rule, scope it to the program path and only the profiles it needs; do not tick Public on a laptop that uses cafe Wi-Fi unless required",
                                                                                    "Never switch the whole firewall off to test; a security product from another vendor may also be filtering, so check that too", "Re-test the program, record what you changed and who approved it, and remove temporary rules"]),
    "footprint": ("Check your digital footprint (personal)", ["Search your name plus city, and your name plus email, in a private window; list what you find", "Check your email addresses at haveibeenpwned.com (enter the address only, never a password) and change passwords for anything listed",
                                                                "Review privacy settings on each social account and limit who sees posts and old photos", "Delete (not just deactivate) accounts you no longer use; a deactivated account still holds your data",
                                                                "Ask data broker sites to remove you; each has its own opt-out form and they re-list people, so repeat twice a year", "Review app permissions for location, contacts, microphone and camera; remove what the app does not need",
                                                                "Turn on two-factor sign-in and use a password manager with a unique password per account", "Consider a credit freeze if identity theft is a worry, and set an alert for your name; set a reminder to repeat this in six months"]),
    "print": ("Fix a printing problem (work from the job to the paper)", ["Ask who is affected: one user, one printer, everyone", "Check the printer itself: power, paper, jam, toner, a display error, and a test page from its own menu", "Check the connection: network cable or wi-fi, and ping the printer's IP address", "Check the queue on the print server or PC: clear a stuck job, then restart the print spooler (Windows) or CUPS (Linux)", "Check the driver and port: right model, the printer's IP not a changed one (use a DHCP reservation or a static address)", "Print a test page from a different PC to decide whether it is the device or the user's PC", "Record the cause and fix in the ticket"]),
    "destroy": ("Sanitise storage media (NIST 800-88: clear, purge, destroy)", ["Classify the data on the media and note who owns it and any retention rule", "Pick the level: Clear (overwrite, for reuse inside the organisation), Purge (cryptographic erase, secure erase or degauss, for reuse outside), Destroy (shred, disintegrate, incinerate)", "Match the method to the media: overwriting is unreliable on SSDs and flash because of wear levelling; use the drive's secure erase, crypto-erase or destroy it", "Degaussing works on magnetic disks and tape only, and ruins them", "Record the asset, serial number, method, date, person and witness", "Verify: attempt to read the media, or check the tool's report", "Keep the certificate of destruction from any third party, and file it"]),
    "byod": ("Allow a personal device (BYOD) safely", ["Write the policy: which data and apps are allowed and what the company may do to the device", "Require a screen lock, device encryption and an up-to-date OS", "Enrol the device in management (MDM) or use app protection so only work data can be wiped", "Separate work and personal data (a work profile or managed apps)", "Require multi-factor sign-in and block rooted or jailbroken devices", "Agree what happens when the person leaves or the device is lost: remote wipe of work data and who to call", "Review the list of enrolled devices every quarter"]),
    "dr": ("Test a disaster recovery plan", ["List systems in order of importance and give each an RTO and an RPO", "Confirm backups run at least as often as the RPO and that one copy is off site and offline or immutable", "Write the restore steps in order (infrastructure, directory, databases, applications), with who does each", "Check the contact list, credentials and licence keys are available when the network is down", "Restore one system to a spare machine and time it against its RTO", "Test an application, not just a file: log in and run a normal task", "Write down what failed, fix it, and schedule the next test (at least twice a year)"]),
    "gpochg": ("Change a Group Policy safely", ["Write what the change is for and the setting's exact path", "Check which OU and which security group it will reach, and whether anything is Enforced or blocks it", "Test on a pilot OU with one machine first", "Use gpresult /r or Group Policy Modeling to confirm the winning policy", "Back up the GPO before editing", "Link it for everyone only after the pilot, and tell users what will change", "Keep a rollback: unlink or disable the GPO, then gpupdate /force"]),
    "harden": ("Harden a Windows endpoint (one change at a time)", ["Pick one risk (for example SMB1, exposed RDP, local admin rights) and write down why it matters here", "Judge likelihood and impact so the order is deliberate", "Write the exact configuration change and who owns it",
                                                                   "Test it on one machine and verify the thing you worry about still works (printers, shares, line-of-business apps)", "Deploy in phases (pilot group, then everyone) with a written backout plan", "Tell users beforehand what will change and who to call",
                                                                   "Document the change and every exception with a reason and a review date", "Monitor that the setting holds (a drift check or the Endpoint hardening audit) and re-run it after major updates"]),
    "vendor": ("Run a vendor through its life cycle", ["Pre-contract: check the vendor's business and security record and call references", "Read the contract for price, term, SLA, data ownership and how you leave", "Agree a communication plan with named contacts and check-in dates",
                                                      "Delivery: track what was promised against what arrived, in writing", "Keep the relationship healthy: raise problems early, and review benefits for both sides", "Post-contract: get your data back and revoke the vendor's access",
                                                      "Record lessons learned before renewing or replacing"]),
    "outage": ("Handle a service outage", ["Confirm it's real and how many people it affects", "Post a short status message", "Check what changed recently", "Check the dependencies: power, network, DNS, storage, certificates",
                                           "Roll back the last change if it fits", "Restore service first, find the cause second", "Tell people when it's fixed", "Write a short post-incident note"]),
}


def checklists() -> dict:
    raw = state.kv_get(f"it_checklists:{_ws()}")
    ticks = json.loads(raw) if raw else {}
    return {"lists": [{"id": k, "title": v[0], "items": [{"text": t, "done": i in ticks.get(k, [])} for i, t in enumerate(v[1])]} for k, v in CHECKLISTS.items()]}


def tick_checklist(list_id: str, index: int | None, done: bool = True, reset: bool = False) -> dict:
    if list_id not in CHECKLISTS:
        raise ItError("No such checklist.", 404)
    raw = state.kv_get(f"it_checklists:{_ws()}")
    ticks = json.loads(raw) if raw else {}
    if reset:
        ticks[list_id] = []
    else:
        if not isinstance(index, int) or not 0 <= index < len(CHECKLISTS[list_id][1]):
            raise ItError("No such checklist item.")
        cur = set(ticks.get(list_id, []))
        (cur.add if done else cur.discard)(index)
        ticks[list_id] = sorted(cur)
    state.kv_set(f"it_checklists:{_ws()}", json.dumps(ticks))
    return checklists()


# ============================================================ calculators
def _num(v, name, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise ItError(f"{name} must be a number from {lo:g} to {hi:g}.")
    return float(v)


def capacity(used_gb: float, total_gb: float, growth_gb_per_month: float, warn_pct: float = 80.0, today: date | None = None) -> dict:
    used, total = _num(used_gb, "Used", 0, 1e9), _num(total_gb, "Total", 1, 1e9)
    g, w = _num(growth_gb_per_month, "Growth", 0, 1e9), _num(warn_pct, "Warning level", 1, 100)
    if used > total:
        raise ItError("Used can't be more than total.")
    today = today or date.today()

    def when(target_gb):
        if used >= target_gb:
            return {"months": 0.0, "date": today.isoformat()}
        if g <= 0:
            return None
        m = (target_gb - used) / g
        return {"months": round(m, 1), "date": (today + timedelta(days=round(m * 30.44))).isoformat()}
    return {"used_pct": round(100 * used / total, 1), "free_gb": round(total - used, 1), "warn_at_pct": w, "reach_warning": when(total * w / 100), "reach_full": when(total),
            "advice": "Order storage before the warning date, not the full date: purchasing and migrating take weeks." if g > 0 else "No growth entered, so no date can be predicted.",
            "note": "Straight-line growth. Real growth is lumpier (new projects, backups); re-measure every month."}


def availability(pct: float) -> dict:
    p = _num(pct, "Availability", 0, 100)
    down = 1 - p / 100
    return {"availability_pct": p, "per_day_seconds": round(86400 * down, 1), "per_month_minutes": round(30.44 * 1440 * down, 1), "per_year_hours": round(8766 * down, 2),
            "nines": ("none" if p < 90 else f"about {min(int(round(-math.log10(max(down, 1e-9)), 6)), 9)} nine(s)"),
            "note": "Downtime allowed at that availability. 99.9% is about 8.8 hours a year; 99.99% is about 53 minutes."}


def raid(level: str, disks: int, size_tb: float) -> dict:
    level = str(level).lower().replace("raid", "").strip()
    n, s = int(_num(disks, "Disks", 1, 64)), _num(size_tb, "Disk size", 0.001, 1000)
    rules = {"0": (2, lambda n: n * s, "none: one disk failing loses everything", "Speed only. Never for data you care about."),
             "1": (2, lambda n: s, "n-1 disks (all copies but one)", "Mirror. Simple and safe, half the capacity at 2 disks."),
             "5": (3, lambda n: (n - 1) * s, "1 disk", "Rebuilds on big disks take long and a second failure during rebuild loses the array."),
             "6": (4, lambda n: (n - 2) * s, "2 disks", "Safer for large disks."),
             "10": (4, lambda n: (n // 2) * s, "1 per mirror pair (not any 2 disks)", "Fast and resilient; half the capacity.")}
    if level not in rules:
        raise ItError("Level must be 0, 1, 5, 6 or 10.")
    need, cap, tol, note = rules[level]
    if n < need or (level == "10" and n % 2):
        raise ItError(f"RAID {level} needs at least {need} disks" + (" and an even number." if level == "10" else "."))
    return {"level": level, "disks": n, "raw_tb": round(n * s, 2), "usable_tb": round(cap(n), 2), "efficiency_pct": round(100 * cap(n) / (n * s)), "tolerates": tol, "note": note,
            "caveat": "RAID is availability, not backup: it won't save you from deletion, ransomware or a fire. Keep a separate backup (3-2-1)."}


# ============================================================ cheat sheets
CHEATS = {
    "Windows and PowerShell": [
        ("Get-Service | Where Status -eq Stopped", "Services that are stopped"), ("Restart-Service Spooler", "Restart the print spooler"), ("Get-EventLog -LogName System -Newest 50", "Recent system events"),
        ("Get-Process | Sort CPU -Desc | Select -First 10", "Top CPU users"), ("Get-Volume", "Disk space per volume"), ("gpupdate /force", "Pull Group Policy now"), ("gpresult /r", "Which policies apply to this user and computer"),
        ("sfc /scannow", "Repair protected system files"), ("DISM /Online /Cleanup-Image /RestoreHealth", "Repair the component store"), ("whoami /groups", "Which groups the current user is in"),
        ("net user <name> /domain", "Look up a domain account"), ("systeminfo", "OS version, hotfixes, uptime"), ("winget upgrade --all", "Update installed apps"),
    ],
    "Active Directory (on-premises)": [
        ("Get-ADUser <name> -Properties *", "Everything about a user"), ("Unlock-ADAccount <name>", "Unlock an account"), ("Set-ADAccountPassword <name> -Reset", "Reset a password"),
        ("Get-ADGroupMember <group>", "Who is in a group"), ("Search-ADAccount -LockedOut", "All locked-out accounts"), ("Search-ADAccount -AccountDisabled", "All disabled accounts"),
        ("dcdiag", "Domain controller health"), ("repadmin /replsummary", "Replication health between controllers"),
    ],
    "Linux administration": [
        ("systemctl status <service>", "State and recent log lines of a service"), ("journalctl -u <service> -n 100", "Last 100 log lines for a service"), ("df -h && du -sh /var/*", "Disk space, then what is using it"),
        ("top  /  htop", "Live processes"), ("free -h", "Memory"), ("last -n 20", "Recent logins"), ("sudo apt update && sudo apt upgrade", "Update Debian/Ubuntu"),
        ("chmod 640 file && chown user:group file", "Permissions and ownership"), ("crontab -l", "Scheduled jobs for this user"), ("ssh-keygen -t ed25519", "Make an SSH key pair"),
    ],
    "Disks and partitions (read first, write second)": [
        ("lsblk -f  /  sudo blkid", "Disks, partitions, file systems and UUIDs"), ("sudo fdisk -l /dev/sdX", "Print a partition table without changing it"), ("sudo parted /dev/sdX print", "Same with parted (MBR or GPT)"),
        ("sudo fdisk /dev/sdX   (p, n, w)", "Interactive editor; nothing is saved until w, q discards"), ("sudo parted /dev/sdX mklabel gpt", "Replace the whole partition table. Live at once and destroys the old layout"),
        ("sudo mkfs.ext4 /dev/sdX1", "Make a file system. Erases that partition"), ("sudo resize2fs /dev/sdX1", "Grow an ext4 file system after growing the partition"), ("sudo mount /dev/sdX1 /mnt  &&  df -h", "Mount and check"),
    ],
    "Windows Firewall": [
        ("wf.msc", "Open Windows Defender Firewall with Advanced Security (Win+R)"), ("Get-NetFirewallRule -DisplayName \"*Chrome*\" | Format-Table DisplayName,Direction,Action,Enabled", "Find rules for a program"),
        ("Get-NetFirewallProfile | Format-Table Name,Enabled,DefaultInboundAction,DefaultOutboundAction", "Defaults per profile"), ("Disable-NetFirewallRule -DisplayName \"<rule>\"", "Switch one rule off (reversible). Do not disable the whole firewall"),
        ("netsh advfirewall show allprofiles", "Older command for the same profile view"),
    ],
    "Printing": [
        ("Get-Printer | Format-Table Name,PortName,DriverName", "List printers with their port and driver"), ("Get-PrintJob -PrinterName <name>", "Jobs waiting in a queue"), ("Restart-Service Spooler", "Restart the Windows print spooler"),
        ("lpstat -p -d", "Linux (CUPS): printers and the default"), ("lpstat -o", "Linux (CUPS): jobs waiting"), ("cancel -a <printer>", "Linux (CUPS): clear all jobs for a printer"),
        ("ping <printer-ip>", "Is the printer reachable at all"), ("http://localhost:631", "CUPS admin page on a Linux machine"),
    ],
    "Directory and LDAP": [
        ("ldapsearch -x -H ldap://host -b dc=example,dc=com '(uid=jdoe)'", "Find an entry (read-only)"), ("ldapadd -x -D cn=admin,dc=example,dc=com -W -f new.ldif", "Add entries from an LDIF file (back up first)"),
        ("ldapmodify -x -D cn=admin,dc=example,dc=com -W -f change.ldif", "Change entries from an LDIF file"), ("slappasswd -h {SSHA}", "Make a salted password hash for userPassword"),
        ("Get-ADUser -Identity jdoe -Properties MemberOf", "Windows: a user and their groups"), ("Get-ADGroupMember 'Group name'", "Windows: group members"), ("dsquery user -name jdoe*", "Windows: find users by name"),
    ],
    "Linux services and run levels": [
        ("systemctl get-default", "The default target (the modern run level)"), ("sudo systemctl set-default multi-user.target", "Boot to text mode by default (graphical.target for a desktop)"),
        ("systemctl isolate rescue.target", "Single-user maintenance mode. On a remote machine this ends your SSH session"), ("runlevel", "SysV: previous and current level (N 5 means no previous, level 5)"),
        ("systemctl status ssh", "Is a service running, and its last log lines"), ("sudo systemctl enable --now ssh", "Start now and at every boot"), ("journalctl -u ssh -n 50", "Last 50 log lines for a service"),
        ("systemctl list-units --failed", "Services that failed to start"),
    ],
    "Microsoft Defender Antivirus (PowerShell)": [
        ("Get-MpComputerStatus", "Protection state, signature age, last scan times"), ("Start-MpScan -ScanType QuickScan", "Quick scan (FullScan and CustomScan with -ScanPath also exist)"),
        ("Update-MpSignature", "Fetch the latest definitions"), ("Get-MpThreatDetection", "Recent detections"), ("Start-MpWDOScan", "Microsoft Defender Offline scan: restarts into the recovery environment"),
        ("Get-MpPreference | Select ExclusionPath", "Review exclusions; each one is a blind spot, keep them few and documented"), ("Add-MpPreference -ExclusionPath C:\\Tools\\build", "Exclude a folder (needs admin)"),
    ],
    "Group Policy": [
        ("gpupdate /force", "Pull policy now"), ("gpresult /r", "Policies applied to this user and computer"), ("gpresult /h report.html", "Full HTML report of what applied and which GPO won"),
        ("Get-GPO -All", "List every GPO in the domain"), ("Backup-GPO -All -Path D:\\gpo", "Back up all GPOs"), ("Get-GPInheritance -Target 'OU=Sales,DC=example,DC=com'", "Links and inheritance on an OU"),
    ],
    "Web and site triage": [
        ("nslookup example.com", "Does the name resolve"), ("curl -I https://example.com", "Just the response headers and status code"), ("curl -v https://example.com", "Show the connection, TLS and request steps"),
        ("openssl s_client -connect example.com:443 -servername example.com", "Inspect the certificate and TLS handshake"), ("Test-NetConnection example.com -Port 443", "Windows: can I reach the port"), ("nc -vz example.com 443", "Linux: can I reach the port"),
    ],
    "DHCP and DNS server (dnsmasq)": [
        ("dnsmasq --test", "Check the config for errors before restarting"), ("sudo systemctl restart dnsmasq", "Apply a change"), ("sudo journalctl -u dnsmasq -f", "Watch DISCOVER, OFFER, REQUEST and ACK live"),
        ("sudo ss -ulpn | grep -E ':(53|67)'", "Who is listening on the DNS and DHCP ports"), ("dig @192.168.50.1 example.com", "Ask a specific DNS server"), ("cat /var/lib/misc/dnsmasq.leases", "Current leases: expiry, MAC, IP, name"),
        ("sudo dhclient -r && sudo dhclient -v eth0", "On a test client: release then ask again"), ("resolvectl status", "What DNS this Linux machine is using (systemd-resolved)"),
    ],
    "Backups and recovery": [
        ("3-2-1 rule", "3 copies, 2 different media, 1 off-site (and test a restore)"), ("RPO", "How much data you can afford to lose, as time"), ("RTO", "How long you can afford to be down"),
        ("robocopy S:\\ D:\\backup /MIR /R:1 /W:1", "Mirror a folder on Windows (MIR deletes at the destination: test first)"), ("rsync -avh --dry-run src/ dest/", "Preview a Linux copy before running it"),
    ],
}


def cheats() -> dict:
    return {"groups": {k: [{"cmd": c, "what": w} for c, w in v] for k, v in CHEATS.items()},
            "method": ["Ask what changed and when it last worked.", "Reproduce the problem yourself if you can.", "Check the simplest, cheapest explanation first (power, cable, restart, typo).",
                       "Change one thing at a time and write it down.", "Confirm the fix with the person, then document it so the next person finds it."]}
