"""Paste a client's message and get a suggested job: client, title, field, due date and a draft quote from your price list.
Rules only (no AI call, no tokens). It suggests; you confirm before anything is created, and nothing is sent to anyone."""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.services import jobfield, service_catalog

MAX = 6000
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_STOP = set("the a an and or to of for my our your is are with on in at it i we you me please need help can could would this that have has be from by".split())
_GROUP_OF_FIELD = {"itsupport": "it", "network": "net", "security": "sec", "analyst": "bi", "scientist": "ds", "ml": "ds", "ai": "ai",
                   "cpe": "cpe", "engineering": "data", "fullstack": "fs", "pm": "pm", "sysanalyst": "bi"}


def _client(text: str) -> str:
    m = re.search(r"^\s*from:\s*\"?([^<\n\"@]+?)\"?\s*(?:<|$)", text, re.I | re.M)
    if m and len(m.group(1).strip()) > 1:
        return m.group(1).strip()[:80]
    m = re.search(r"\b(?:this is|i am|i'm|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if m:
        return m.group(1).strip()
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    if lines and re.fullmatch(r"[-~—]*\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", lines[-1]) and len(lines) > 1:
        return lines[-1].lstrip("-~— ").strip()
    return ""


def _due(text: str, today: date) -> str | None:
    t = text.lower()
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        y = int(m.group(3)) if m.group(3) else today.year
        y += 2000 if y < 100 else 0
        try:
            d = date(y, int(m.group(1)), int(m.group(2)))
            if not m.group(3) and d < today:
                d = date(y + 1, d.month, d.day)
            return d.isoformat()
        except ValueError:
            pass
    if re.search(r"\b(today|asap|right away)\b", t):
        return today.isoformat()
    if "tomorrow" in t:
        return (today + timedelta(days=1)).isoformat()
    m = re.search(r"\b(?:in|within)\s+(\d{1,2})\s+days?\b", t)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()
    if "next week" in t:
        return (today + timedelta(days=7)).isoformat()
    for i, name in enumerate(_DAYS):
        if re.search(rf"\b(?:by|on|before|this|next)?\s*{name}\b", t):
            ahead = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=ahead)).isoformat()
    return None


def _title(text: str) -> str:
    m = re.search(r"^\s*subject:\s*(.+)$", text, re.I | re.M)
    if m:
        return re.sub(r"^(re|fwd?):\s*", "", m.group(1).strip(), flags=re.I)[:120]
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or re.match(r"^(hi|hello|hey|good (morning|afternoon|evening)|dear)\b[^.?!]{0,30}[,!]?$", ln, re.I) or re.match(r"^(from|to|date|cc):", ln, re.I):
            continue
        ln = re.sub(r"^(hi|hello|hey)[^,]*,\s*", "", ln, flags=re.I)
        first = re.split(r"(?<=[.!?])\s", ln)[0]
        return first.strip().rstrip(".")[:120]
    return ""


def _quote(text: str, field: str | None) -> dict | None:
    words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 2}
    grp = _GROUP_OF_FIELD.get(field or "")
    best, score = None, 0
    for s in service_catalog.SERVICES:
        bag = {w for w in re.findall(r"[a-z0-9]+", (s["name"] + " " + s["deliverable"]).lower()) if w not in _STOP and len(w) > 2}
        n = len(words & bag) + (1 if s["group"] == grp else 0) * 0.5
        if n > score:
            best, score = s, n
    if not best or score < 1:
        return None
    rate = service_catalog.rates()[best["group"]]
    lo, hi = best["hours"]
    return {"service": best["name"], "hours": [lo, hi], "rate": rate, "low": round(lo * rate, 2), "high": round(hi * rate, 2),
            "suggested": round((lo + hi) / 2 * rate, 2), "note": "A starting range from your price list. Check it against the real work before you send any quote."}


def read(text: str, today: date | None = None) -> dict:
    text = (text or "").strip()
    if len(text) < 5:
        raise ValueError("Paste the client's message first.")
    text = text[:MAX]
    today = today or date.today()
    title = _title(text)
    field = jobfield.guess(title + " " + text[:600])
    return {"client": _client(text), "title": title, "field": jobfield.info(field), "due": _due(text, today), "quote": _quote(text, field),
            "note": "Suggestions from rules, no AI used. Fix anything wrong, then start the job. Nothing is sent to the client."}
