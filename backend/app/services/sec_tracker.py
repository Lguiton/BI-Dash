"""Per-client security records you keep up to date: report history and re-check comparison, backup restore tests, an account inventory, a device inventory with
end-of-support dates, and an incident timeline. Stored per workspace in the state file (Practice and Real never mix), tied to a client from the Clients page.

Dates for end of support come from a short built-in table of widely published dates, or from a date you type. Always confirm with the vendor's own page: vendors
change dates, and the table does not cover everything. Nothing here contacts any outside service."""
from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta

from app.services import clients, state, workspaces

COLL = {
    "backups": {"system": ("text", True, None), "date": ("date", False, None), "result": ("choice", True, ("ok", "fail")), "note": ("text", False, None), "every_days": ("int", False, (7, 365))},
    "accounts": {"name": ("text", True, None), "kind": ("choice", False, ("email", "money", "cloud", "social", "website", "other")), "owner": ("text", False, None), "mfa": ("choice", False, ("app", "key", "sms", "none", "unknown")),
                 "recovery_stored": ("bool", False, None), "shared": ("bool", False, None), "last_review": ("date", False, None), "note": ("text", False, None)},
    "devices": {"name": ("text", True, None), "kind": ("choice", False, ("pc", "laptop", "phone", "server", "router", "camera", "printer", "other")), "os": ("text", False, None), "os_version": ("text", False, None),
                "eol_date": ("date", False, None), "last_seen": ("date", False, None), "note": ("text", False, None)},
    "timeline": {"at": ("datetime", False, None), "kind": ("choice", True, ("detected", "action", "contact", "evidence", "recovery", "note")), "what": ("text", True, None), "who": ("text", False, None), "incident": ("text", False, None)},
}
# Widely published end-of-support dates (confirm with the vendor). Matched on the OS text you type.
EOL = [("windows 7", "2020-01-14"), ("windows 8.1", "2023-01-10"), ("windows 8", "2016-01-12"), ("windows 10", "2025-10-14"), ("server 2012 r2", "2023-10-10"), ("server 2012", "2023-10-10"), ("server 2016", "2027-01-12"),
       ("server 2019", "2029-01-09"), ("server 2022", "2031-10-14"), ("ubuntu 18.04", "2023-05-31"), ("ubuntu 20.04", "2025-05-31"), ("ubuntu 22.04", "2027-06-01"), ("ubuntu 24.04", "2029-05-31"),
       ("windows xp", "2014-04-08"), ("windows vista", "2017-04-11")]
EOL_NOTE = "Dates come from a short built-in list of widely published dates, or the date you entered. Confirm on the vendor's page; paid extended-update programmes can change the real picture."


class TrackError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key() -> str:
    return f"sectrack:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    d = json.loads(raw) if raw else {}
    for k in ("reports", *COLL):
        d.setdefault(k, [])
    d.setdefault("next", {})
    return d


def _save(d: dict) -> None:
    state.kv_set(_key(), json.dumps(d))


def _client(cid) -> int:
    try:
        cid = int(cid)
        d = clients._load()
        clients._find(d, "clients", cid)
        return cid
    except (TypeError, ValueError):
        raise TrackError("client_id is required.") from None
    except clients.ClientError:
        raise TrackError("That client doesn't exist.", 404) from None


def _field(spec, v, name):
    typ, req, extra = spec
    if v in (None, ""):
        if req:
            raise TrackError(f"{name} is required.")
        return None if typ in ("date", "datetime") else (False if typ == "bool" else ("" if typ in ("text", "choice") else None))
    if typ == "text":
        return re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v)).strip()[:300]
    if typ == "choice":
        if v not in extra:
            raise TrackError(f"{name} must be one of: {', '.join(extra)}.")
        return v
    if typ == "bool":
        return bool(v)
    if typ == "int":
        try:
            x = int(v)
        except (TypeError, ValueError):
            raise TrackError(f"{name} must be a whole number.") from None
        if not extra[0] <= x <= extra[1]:
            raise TrackError(f"{name} must be between {extra[0]} and {extra[1]}.")
        return x
    try:
        return (datetime.strptime(str(v)[:10], "%Y-%m-%d").date().isoformat() if typ == "date" else datetime.fromisoformat(str(v)[:19]).isoformat(timespec="minutes"))
    except ValueError:
        raise TrackError(f"{name} must be a valid {'date like 2026-10-31' if typ == 'date' else 'date and time like 2026-10-31T14:30'}.") from None


def add(kind: str, b: dict) -> dict:
    spec = COLL[kind]
    cid = _client(b.get("client_id"))
    d = _load()
    d["next"][kind] = d["next"].get(kind, 0) + 1
    rec = {"id": d["next"][kind], "client_id": cid, **{k: _field(v, b.get(k), k) for k, v in spec.items()}}
    if kind == "backups":
        rec["date"] = rec["date"] or date.today().isoformat()
        rec["every_days"] = rec["every_days"] or 30
    if kind == "timeline":
        rec["at"] = rec["at"] or datetime.now().isoformat(timespec="minutes")
    d[kind].append(rec)
    _save(d)
    state.audit(f"sec.{kind}.add", f"client {cid}")
    return rec


def update(kind: str, rid: int, b: dict) -> dict:
    d = _load()
    rec = next((r for r in d[kind] if r["id"] == rid), None)
    if not rec:
        raise TrackError("Not found.", 404)
    for k, v in COLL[kind].items():
        if k in b:
            rec[k] = _field(v, b[k], k)
    _save(d)
    return rec


def remove(kind: str, rid: int) -> dict:
    d = _load()
    if not any(r["id"] == rid for r in d[kind]):
        raise TrackError("Not found.", 404)
    d[kind] = [r for r in d[kind] if r["id"] != rid]
    _save(d)
    return {"deleted": rid}


def rows(kind: str, cid: int) -> list[dict]:
    return [r for r in _load()[kind] if r["client_id"] == cid]


# ------------------------------------------------------------------ 1. report history and comparison


def _norm(s: str) -> str:
    return re.sub(r"\d+", "#", s.lower()).strip()


def _k(i: dict) -> str:
    return f"{i['source'].lower()}|{_norm(i['title'])}"


def save_report(cid, report: dict) -> dict:
    cid = _client(cid)
    d = _load()
    d["next"]["reports"] = d["next"].get("reports", 0) + 1
    rec = {"id": d["next"]["reports"], "client_id": cid, "date": date.today().isoformat(), "band": report["band"], "counts": report["counts"], "sample": report.get("sample", False),
           "items": [{"key": _k(i), "severity": i["severity"], "title": i["title"], "source": i["source"], "fix_id": i.get("fix_id")} for i in report["items"]]}
    d["reports"].append(rec)
    _save(d)
    state.audit("sec.report.save", f"client {cid}")
    return {k: rec[k] for k in ("id", "date", "band", "counts")}


def history(cid: int) -> list[dict]:
    return [{k: r[k] for k in ("id", "date", "band", "counts")} for r in _load()["reports"] if r["client_id"] == cid]


def compare(cid: int, a: int | None = None, b: int | None = None) -> dict:
    """Newest report against the one before it (or two you pick): what was fixed, what is new, what is still open."""
    rs = [r for r in _load()["reports"] if r["client_id"] == cid]
    byid = {r["id"]: r for r in rs}
    if a and b:
        if a not in byid or b not in byid:
            raise TrackError("Report not found.", 404)
        old, new = byid[a], byid[b]
    else:
        if len(rs) < 2:
            raise TrackError("Save at least two checkup reports for this client to compare them.")
        old, new = rs[-2], rs[-1]
    ok, nk = {i["key"]: i for i in old["items"]}, {i["key"]: i for i in new["items"]}
    fixed = [ok[k] for k in ok if k not in nk]
    fresh = [nk[k] for k in nk if k not in ok]
    still = [nk[k] for k in nk if k in ok]
    order = {"high": 0, "medium": 1, "low": 2}
    for lst in (fixed, fresh, still):
        lst.sort(key=lambda i: order[i["severity"]])
    worse = [nk[k] for k in nk if k in ok and order[nk[k]["severity"]] < order[ok[k]["severity"]]]
    return {"from": {"id": old["id"], "date": old["date"], "band": old["band"], "counts": old["counts"]}, "to": {"id": new["id"], "date": new["date"], "band": new["band"], "counts": new["counts"]},
            "fixed": fixed, "new": fresh, "still_open": still, "got_worse": worse,
            "says": f"Between {old['date']} and {new['date']}: {len(fixed)} fixed, {len(fresh)} new, {len(still)} still open.",
            "caution": "Findings are matched by their source and title, so a reworded finding can show as one fixed and one new. Different inputs between two reports (a PC added or left out) also change the result."}


# ------------------------------------------------------------------ 2. backups


def backup_status(cid: int, today: date | None = None) -> dict:
    t = today or date.today()
    tests = rows("backups", cid)
    systems: dict[str, list[dict]] = {}
    for r in tests:
        systems.setdefault(r["system"].lower(), []).append(r)
    out = []
    for name, rs in systems.items():
        rs.sort(key=lambda r: r["date"])
        last, ok = rs[-1], [r for r in rs if r["result"] == "ok"]
        days = (t - date.fromisoformat(last["date"])).days
        last_ok = ok[-1]["date"] if ok else None
        due = date.fromisoformat(last["date"]) + timedelta(days=last["every_days"])
        flag = "failed" if last["result"] == "fail" else "overdue" if t > due else "ok"
        out.append({"system": rs[-1]["system"], "last_test": last["date"], "days_since": days, "last_result": last["result"], "last_success": last_ok, "next_due": due.isoformat(), "status": flag, "tests": len(rs)})
    out.sort(key=lambda r: {"failed": 0, "overdue": 1, "ok": 2}[r["status"]])
    return {"systems": out, "needs_attention": [s for s in out if s["status"] != "ok"], "fix_id": "restore-test",
            "caution": "A passing test proves the file you restored was good, not that every file in the backup is."}


# ------------------------------------------------------------------ 3. accounts


def account_review(cid: int, today: date | None = None) -> dict:
    t = today or date.today()
    flags = []
    for a in rows("accounts", cid):
        why = []
        if a["mfa"] in ("none", "unknown", ""):
            why.append("no two-step sign-in" if a["mfa"] == "none" else "two-step sign-in status unknown")
        if a["mfa"] == "sms":
            why.append("text-message codes can be stolen; prefer an authenticator app")
        if not a["recovery_stored"]:
            why.append("recovery codes not stored")
        if a["shared"]:
            why.append("shared login")
        if not a["last_review"] or (t - date.fromisoformat(a["last_review"])).days > 180:
            why.append("not reviewed in 180 days")
        if why:
            sev = "high" if a["kind"] in ("email", "money") and a["mfa"] in ("none", "unknown", "") else "medium" if a["mfa"] in ("none", "sms", "unknown", "") else "low"
            flags.append({"account": a["name"], "kind": a["kind"], "severity": sev, "reasons": why, "id": a["id"]})
    flags.sort(key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]])
    return {"flags": flags, "accounts": len(rows("accounts", cid)), "fix_id": "account-review"}


# ------------------------------------------------------------------ 7. devices


def eol_for(os_text: str) -> str | None:
    t = (os_text or "").lower()
    for k, v in EOL:
        if k in t:
            return v
    return None


def device_status(cid: int, today: date | None = None) -> dict:
    t = today or date.today()
    out = []
    for dv in rows("devices", cid):
        eol = dv["eol_date"] or eol_for(f"{dv['os']} {dv['os_version']}")
        if not eol:
            st, days = "unknown", None
        else:
            days = (date.fromisoformat(eol) - t).days
            st = "expired" if days < 0 else "soon" if days <= 180 else "ok"
        out.append({**dv, "eol": eol, "eol_source": "entered" if dv["eol_date"] else ("built-in list" if eol else None), "days_to_eol": days, "status": st})
    out.sort(key=lambda r: {"expired": 0, "soon": 1, "unknown": 2, "ok": 3}[r["status"]])
    return {"devices": out, "attention": [x for x in out if x["status"] in ("expired", "soon")], "note": EOL_NOTE, "fix_id": "device-eol"}


# ------------------------------------------------------------------ 8. timeline


def timeline_html(cid: int, incident: str = "") -> str:
    d = _load()
    c = clients._find(clients._load(), "clients", cid)
    ev = sorted([e for e in d["timeline"] if e["client_id"] == cid and (not incident or e["incident"] == incident)], key=lambda e: e["at"])
    e_ = html.escape
    sample = workspaces.active() != "real"
    rows_ = "".join(f"<tr><td>{e_(x['at'].replace('T', ' '))}</td><td>{e_(x['kind'])}</td><td>{e_(x['what'])}</td><td>{e_(x['who'])}</td></tr>" for x in ev)
    banner = "<p style='background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600'>SAMPLE: Practice workspace, not a real incident record.</p>" if sample else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Incident timeline</title><style>body{{font:15px/1.5 system-ui,Arial,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:.4rem .5rem;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}.n{{color:#555;font-size:.85rem}}</style></head><body>{banner}
<h1>Incident timeline</h1><p class=n>{e_(c['name'])}{(' · ' + e_(incident)) if incident else ''} · exported {date.today().isoformat()}</p>
<table><tr><th>When</th><th>Type</th><th>What happened or was done</th><th>Who</th></tr>{rows_}</table>
<p class=n>Entries are as the person recorded them. Times are as entered and may be approximate. This is a record of events, not a finding of cause or fault.</p></body></html>"""
