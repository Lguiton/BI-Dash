"""Lead tracker: where each lead came from, what you quoted, and whether you won it, so you can see which sources pay.

A lead is someone who has not become a client yet. Winning one creates the client and a job in your Clients page. Nothing is sent
anywhere. Win rates need a few finished leads before they mean anything, and the page says so."""
from __future__ import annotations

import json
from datetime import date

from app.services import clients as cl
from app.services import state, workspaces
from app.services.clients import ClientError, _date, _find, _nid, _num, _txt

STATUS = ("new", "contacted", "quoted", "won", "lost")
SOURCES = ("referral", "nextdoor", "facebook", "google", "marketing dashboard", "walk-in", "repeat client", "other")
MIN_DECIDED = 5          # finished leads needed before a "best source" is named


def _key() -> str:
    return f"leads:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    d.setdefault("leads", [])
    d.setdefault("next", {})
    return d


def _save(d: dict) -> None:
    state.kv_set(_key(), json.dumps(d))


def _check_status(v: str) -> str:
    if v not in STATUS:
        raise ClientError("status must be one of: " + ", ".join(STATUS) + ".")
    return v


def add(b: dict) -> dict:
    d = _load()
    lead = {"id": _nid(d, "lead"), "name": _txt(b.get("name"), "name", 80, True), "source": _txt(b.get("source") or "other", "source", 40).lower() or "other",
            "contact": _txt(b.get("contact"), "contact", 120), "what": _txt(b.get("what"), "what they need", 200), "value": _num(b.get("value"), "value"),
            "status": _check_status(b.get("status") or "new"), "next_step": _txt(b.get("next_step"), "next step", 160), "next_date": _date(b.get("next_date"), "next date"),
            "note": _txt(b.get("note"), "note", 600), "created": date.today().isoformat(), "quoted_on": None, "closed_on": None, "lost_reason": "", "client_id": None, "job_id": None}
    if lead["status"] in ("quoted", "won"):
        lead["quoted_on"] = lead["created"]
    d["leads"].append(lead)
    _save(d)
    return lead


def update(lid: int, b: dict) -> dict:
    d = _load()
    lead = _find(d, "leads", lid)
    for k, lim in (("name", 80), ("source", 40), ("contact", 120), ("what", 200), ("next_step", 160), ("note", 600), ("lost_reason", 160)):
        if k in b:
            lead[k] = _txt(b[k], k, lim, k == "name")
            if k == "source":
                lead[k] = lead[k].lower() or "other"
    if "value" in b:
        lead["value"] = _num(b["value"], "value")
    if "next_date" in b:
        lead["next_date"] = _date(b["next_date"], "next date")
    if "status" in b:
        st = _check_status(b["status"])
        if st == "won" and lead["status"] != "won":
            raise ClientError("Use Win to turn a lead into a client and job.", 400)
        if st == "quoted" and not lead["quoted_on"]:
            lead["quoted_on"] = date.today().isoformat()
        if st == "lost" and lead["status"] != "lost":
            lead["closed_on"] = date.today().isoformat()
        lead["status"] = st
    _save(d)
    return lead


def delete(lid: int) -> dict:
    d = _load()
    _find(d, "leads", lid)
    d["leads"] = [x for x in d["leads"] if x["id"] != lid]
    _save(d)
    return {"deleted": lid}


def win(lid: int, b: dict | None = None) -> dict:
    """The lead said yes: make the client (unless one exists) and a job holding the quote, and mark the lead won."""
    b = b or {}
    d = _load()
    lead = _find(d, "leads", lid)
    if lead["status"] == "won":
        raise ClientError("This lead is already won.", 409)
    cid = b.get("client_id") or lead["client_id"]
    if cid:
        _find(cl._load(), "clients", int(cid))
    else:
        cid = cl.add_client({"name": lead["name"], "contact": lead["contact"] if "@" not in lead["contact"] else "", "email": lead["contact"] if "@" in lead["contact"] else "", "notes": f"From lead ({lead['source']})."})["id"]
    value = _num(b.get("value", lead["value"]), "value")
    job = cl.add_job({"client_id": int(cid), "title": _txt(b.get("title") or lead["what"] or f"Work for {lead['name']}", "title", 120), "quote": value, "status": "active",
                      "notes": f"From lead ({lead['source']})."})
    d = _load()
    lead = _find(d, "leads", lid)
    lead.update(status="won", value=value, client_id=int(cid), job_id=job["id"], closed_on=date.today().isoformat(), quoted_on=lead["quoted_on"] or date.today().isoformat())
    _save(d)
    state.audit("lead.win", f"lead {lid}")
    return {"lead": lead, "client_id": int(cid), "job_id": job["id"]}


def listing(today: date | None = None) -> dict:
    t = (today or date.today()).isoformat()
    d = _load()
    rows = sorted(d["leads"], key=lambda x: (x["status"] in ("won", "lost"), x["next_date"] or "9999", x["id"]))
    return {"leads": [{**x, "due": bool(x["next_date"] and x["next_date"] <= t and x["status"] not in ("won", "lost"))} for x in rows], "statuses": list(STATUS), "sources": list(SOURCES), "sample": cl.sample()}


def due(today: date | None = None) -> list[dict]:
    return [x for x in listing(today)["leads"] if x["due"]]


def stats() -> dict:
    d = _load()
    by: dict[str, dict] = {}
    for x in d["leads"]:
        s = by.setdefault(x["source"], {"source": x["source"], "leads": 0, "quoted": 0, "won": 0, "lost": 0, "open": 0, "won_value": 0.0, "open_value": 0.0})
        s["leads"] += 1
        s["quoted"] += 1 if (x["quoted_on"] or x["status"] in ("quoted", "won")) else 0
        if x["status"] == "won":
            s["won"] += 1
            s["won_value"] += x["value"]
        elif x["status"] == "lost":
            s["lost"] += 1
        else:
            s["open"] += 1
            s["open_value"] += x["value"]
    rows = []
    for s in by.values():
        done = s["won"] + s["lost"]
        rows.append({**s, "won_value": round(s["won_value"], 2), "open_value": round(s["open_value"], 2), "win_rate": round(100 * s["won"] / done) if done else None, "decided": done})
    rows.sort(key=lambda r: (-r["won_value"], -r["leads"]))
    decided = sum(r["decided"] for r in rows)
    if decided >= MIN_DECIDED and rows and rows[0]["won_value"] > 0:
        msg = f"So far {rows[0]['source']} has brought the most won work (${rows[0]['won_value']:,.0f}). This is from {decided} finished leads, so treat it as a hint."
    else:
        msg = f"Not enough finished leads yet: {decided} won or lost, and about {MIN_DECIDED} are needed before a pattern means anything."
    return {"sources": rows, "decided": decided, "message": msg, "totals": {"leads": len(d["leads"]), "open": sum(r["open"] for r in rows), "open_value": round(sum(r["open_value"] for r in rows), 2), "won_value": round(sum(r["won_value"] for r in rows), 2)}}
