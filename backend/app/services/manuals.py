"""Step-by-step how-to manuals, one per discipline.

The steps live in app/content/manuals/<track>.json (edit them there, or with scripts/content.py); this module
loads them and keeps the progress ticks.

Each manual is an ordered playbook: what to do, how, which tool to open, how you know you're done, and the mistakes
beginners make. The text is guidance written for this app's real features. Ticking a step is your own record; the app
doesn't verify it (the Company page is where progress is detected from data).

`tab` names the tab inside the discipline's dashboard that a step opens. VALID_TABS lists the real ones, and a test
fails if a manual points at a tab or page that doesn't exist.
"""
from __future__ import annotations

import json

from app.services import content, state

VALID_TABS = {
    "pm": {"board", "prio", "sprint", "flow", "schedule", "evm", "risk", "okr", "product", "time", "calendar", "rules"},
    "sysanalyst": {"req", "dict", "process", "calc", "feas", "sot"},
    "fullstack": {"api", "scaffold", "code", "stack", "se"},
    "security": {"report", "fix", "records", "phish", "unix", "audit", "logs", "web", "ports", "crypto", "incident", "honeypot", "endpoint", "frame", "tools"},
    "network": {"subnet", "config", "capture", "diag", "calc", "ref", "gen", "design", "sim", "pcap"},
    "cpe": {"numbers", "logic", "circuits", "arch", "wiring", "ev", "sim", "veh", "systems"},
    "itsupport": {"tickets", "assets", "backup", "events", "checklists", "capacity", "cheats", "software", "virt", "aplus", "fund", "infra", "coach"},
    "engineering": {"lab", "pipeline", "dba", "design", "gov", "gov/catalog", "gov/pii", "gov/lineage", "gov/controls", "gov/access"},
}


def S(sid, title, what, how, tool=None, done="", mistakes=(), ask=""):
    """tool = (label, href, tab|None). href is a top-level page or None (stay on this dashboard)."""
    t = None
    if tool:
        t = {"label": tool[0], "href": tool[1], "tab": tool[2] if len(tool) > 2 else None}
    return {"id": sid, "title": title, "what": what, "how": list(how), "tool": t, "done_when": done, "mistakes": list(mistakes), "ask": ask}


MANUALS: dict[str, dict] = content.load_manuals()   # content/manuals/<track>.json, checked when loaded


def manual_for(track: str) -> dict | None:
    return MANUALS.get(track)


def _all_done() -> dict[str, list[str]]:
    raw = state.kv_get("manual_done")
    return json.loads(raw) if raw else {}


def get(track: str) -> dict | None:
    m = MANUALS.get(track)
    if not m:
        return None
    return {"track": track, **m, "done": _all_done().get(track, [])}


def set_done(track: str, step: str, done: bool) -> dict | None:
    m = MANUALS.get(track)
    if not m or step not in {s["id"] for s in m["steps"]}:
        return None
    allv = _all_done()
    cur = set(allv.get(track, []))
    (cur.add if done else cur.discard)(step)
    allv[track] = sorted(cur)
    state.kv_set("manual_done", json.dumps(allv))
    return get(track)
