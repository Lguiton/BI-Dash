"""Shared framework for the advanced labs: each field registers calculators and reference tabs here, and one generic page shows them.
Everything runs on this computer from what you type. Results are planning estimates to check, not answers."""
from __future__ import annotations

import math
import re

NOTE = "A planning estimate. Check it against the real data sheet, system or source before you rely on it."


class ProError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


_REG: dict[str, dict] = {}


def lab(track: str, title: str) -> None:
    _REG[track] = {"title": title, "tabs": []}


def tool(track: str, tid: str, label: str, help: str, fields: list[tuple], fn) -> None:
    """fields: (key, label, default) or (key, label, default, 'area') for a multi-line box."""
    _REG[track]["tabs"].append({"id": tid, "label": label, "kind": "tool", "help": help, "fn": fn,
                                "fields": [{"k": f[0], "label": f[1], "default": str(f[2]), "area": len(f) > 3} for f in fields]})


def ref(track: str, tid: str, label: str, sections: list[dict]) -> None:
    """sections: {'title', 'items': [str]} or {'title', 'head': [...], 'rows': [[...]]}."""
    _REG[track]["tabs"].append({"id": tid, "label": label, "kind": "ref", "sections": sections})


def tracks() -> list[str]:
    return [t for t, v in _REG.items() if v["tabs"]]


def spec(track: str) -> dict:
    v = _REG.get(track)
    if not v:
        raise ProError("No advanced lab for this field.", 404)
    return {"track": track, "title": v["title"], "tabs": [{k: x for k, x in t.items() if k != "fn"} for t in v["tabs"]], "note": NOTE}


def run(track: str, tid: str, args: dict) -> dict:
    v = _REG.get(track)
    t = next((x for x in (v or {}).get("tabs", []) if x["id"] == tid and x["kind"] == "tool"), None)
    if not t:
        raise ProError("Unknown tool.", 404)
    a = {f["k"]: ("" if args.get(f["k"]) is None else str(args.get(f["k"]))) for f in t["fields"]}
    for k, val in (args or {}).items():          # extra keys from agents pass through as text
        a.setdefault(k, str(val))
    try:
        out = t["fn"](a)
    except ProError:
        raise
    except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
        raise ProError("Check the numbers you entered: " + (str(e)[:120] or "a value is missing or out of range") + ".") from None
    out.setdefault("note", NOTE)
    return out


def attach(by_track: dict) -> None:
    """Make every calculator available to that field's agent as a tool (never replacing an existing tool)."""
    for track, v in _REG.items():
        reg = by_track.get(track)
        if reg is None:
            continue
        for t in v["tabs"]:
            if t["kind"] != "tool" or t["id"] in reg:
                continue
            usage = (t["help"] + " Fields: " + ", ".join(f["k"] for f in t["fields"]))[:300]
            reg[t["id"]] = (usage, (lambda tr, ti: lambda a: run(tr, ti, dict(a)))(track, t["id"]))


# ------------------------------------------------------------------ small helpers for the modules
def num(a: dict, k: str, name: str | None = None, lo: float | None = None, hi: float | None = None, strict: bool = False) -> float:
    nm = name or k.replace("_", " ")
    try:
        x = float(str(a.get(k, "")).replace(",", "").replace("$", "").replace("%", "").strip())
    except ValueError:
        raise ProError(f"{nm} must be a number.") from None
    if math.isnan(x) or math.isinf(x):
        raise ProError(f"{nm} must be a real number.")
    if lo is not None and (x <= lo if strict else x < lo):
        raise ProError(f"{nm} must be {'more than' if strict else 'at least'} {lo:g}.")
    if hi is not None and x > hi:
        raise ProError(f"{nm} must be at most {hi:g}.")
    return x


def txt(a: dict, k: str, name: str | None = None, required: bool = True, limit: int = 20000) -> str:
    s = str(a.get(k, "") or "").strip()
    if required and not s:
        raise ProError(f"Add {name or k.replace('_', ' ')}.")
    if len(s) > limit:
        raise ProError(f"Keep {name or k} under {limit:,} characters.")
    return s


def lines(a: dict, k: str, name: str | None = None, minimum: int = 1) -> list[list[str]]:
    rows = [[c.strip() for c in ln.split(",")] for ln in txt(a, k, name).splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(rows) < minimum:
        raise ProError(f"Give at least {minimum} line{'s' if minimum != 1 else ''} in {name or k}.")
    return rows


def r(x: float, d: int = 2) -> float:
    return round(x, d)
