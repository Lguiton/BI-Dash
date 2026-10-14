"""Analytics-ready scorecard: is each table accurate, reliable, compliant and available to the people who use it?

The score (0 to 100) adds weighted checks per table. It is a guide to what to fix first, not a certificate: a high score
means the checks the app can run passed, nothing more. A weekly review keeps snapshots so you can see what got worse.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from app.services import state, workspaces
from app.services.datasets import q
from app.services.db import get_cursor

READY_AT = 80
KEEP = 26
# (id, label, weight, group). Groups follow the four words: accurate, reliable, compliant, accessible.
WEIGHTS = [("completeness", "Few missing values", 20, "accurate"), ("duplicates", "No duplicate rows", 15, "accurate"),
           ("fresh", "Recent data", 10, "reliable"), ("backup", "Recent verified backup", 10, "reliable"),
           ("pii", "Personal data protected", 15, "compliant"), ("classified", "Classified", 5, "compliant"),
           ("owner", "Has an owner and steward", 15, "accessible"), ("described", "Described in the catalog", 10, "accessible")]


def _freshness(cur, table: str, cols: list[dict]) -> int | None:
    d = next((c["name"] for c in cols if str(c.get("type", "")).upper() == "DATE" or str(c.get("type", "")).upper().startswith("TIMESTAMP")), None)
    if not d:
        return None
    try:
        newest = cur.execute(f"SELECT MAX({q(d)}) FROM {q(table)}").fetchone()[0]
    except Exception:  # noqa: BLE001
        return None
    if newest is None:
        return None
    nd = newest.date() if isinstance(newest, datetime) else newest
    return (date.today() - nd).days


def scorecard() -> dict:
    from app.services import dba, governance
    cat = governance.catalog()
    pii = governance.pii_scan()
    unprotected: dict[str, int] = {}
    for f in pii["findings"]:
        if not f["protected_from_ai"]:
            unprotected[f["table"]] = unprotected.get(f["table"], 0) + 1
    try:
        h = dba.health()
        age = h["backup"]["age_hours"]
        backup_ok = age is not None and age <= 24 * 7 and h["backup"]["count"] > 0
        backup_note = "no backup yet" if age is None else f"newest backup {age / 24:.1f} days old"
    except Exception:  # noqa: BLE001
        backup_ok, backup_note = False, "backup status unavailable"
    tables = []
    with get_cursor() as cur:
        for a in cat["assets"]:
            if a["system"] or a["kind"] != "table":
                continue
            days = _freshness(cur, a["name"], a["columns"])
            comp = a["completeness_pct"]
            dups = a["duplicate_rows"] or 0
            rows = a["rows"] or 0
            parts = {
                "completeness": 1.0 if comp is None else max(0.0, min(1.0, (comp - 50) / 50)),
                "duplicates": 1.0 if not rows else max(0.0, 1 - 4 * dups / rows),
                "fresh": 1.0 if days is None or days <= 35 else max(0.0, 1 - (days - 35) / 330),
                "backup": 1.0 if backup_ok else 0.0,
                "pii": 0.0 if unprotected.get(a["name"]) else 1.0,
                "classified": 1.0 if a["classification"] else 0.0,
                "owner": (0.5 if a["owner"] else 0.0) + (0.5 if a["steward"] else 0.0),
                "described": 1.0 if a["description"] else 0.0,
            }
            fix = []
            if parts["completeness"] < 1: fix.append(f"{100 - (comp or 100):.0f}% of values are missing")
            if parts["duplicates"] < 1: fix.append(f"{dups} duplicate rows")
            if parts["fresh"] < 1: fix.append(f"newest data is {days} days old")
            if parts["backup"] < 1: fix.append(f"no recent backup ({backup_note})")
            if parts["pii"] < 1: fix.append(f"{unprotected[a['name']]} personal column(s) not protected from AI")
            if parts["classified"] < 1: fix.append("not classified")
            if parts["owner"] < 1: fix.append("missing owner or steward")
            if parts["described"] < 1: fix.append("no description")
            score = round(sum(parts[i] * w for i, _, w, _ in WEIGHTS))
            groups = {}
            for i, _, w, g in WEIGHTS:
                gp = groups.setdefault(g, [0.0, 0])
                gp[0] += parts[i] * w
                gp[1] += w
            tables.append({"table": a["name"], "rows": rows, "score": score, "ready": score >= READY_AT,
                           "by_word": {g: round(100 * v[0] / v[1]) for g, v in groups.items()}, "fix": fix})
    tables.sort(key=lambda t: t["score"])
    overall = round(sum(t["score"] for t in tables) / len(tables)) if tables else None
    return {"workspace": workspaces.active(), "overall": overall, "ready_at": READY_AT, "ready_tables": sum(1 for t in tables if t["ready"]), "tables": tables,
            "backup": {"ok": backup_ok, "note": backup_note},
            "weights": [{"id": i, "label": lab, "weight": w, "word": g} for i, lab, w, g in WEIGHTS],
            "note": "A guide to what to fix first. The four words come from the data engineer's job: accurate, reliable, compliant with the rules that govern it, and accessible when needed. A high score means the checks this app can run passed, not that the data is right."}


def _key() -> str:
    return f"health_review:{workspaces.active()}"


def history() -> list[dict]:
    try:
        return json.loads(state.kv_get(_key()) or "[]")
    except ValueError:
        return []


def review_now(note: str = "") -> dict:
    """Score everything, compare with the previous review, and keep the result."""
    sc = scorecard()
    hist = history()
    prev = {t["table"]: t["score"] for t in hist[-1]["tables"]} if hist else {}
    now = {t["table"]: t["score"] for t in sc["tables"]}
    worse = [{"table": t, "was": prev[t], "now": s} for t, s in now.items() if t in prev and s < prev[t]]
    better = [{"table": t, "was": prev[t], "now": s} for t, s in now.items() if t in prev and s > prev[t]]
    new = [t for t in now if t not in prev] if prev else []
    gone = [t for t in prev if t not in now]
    todo = [f"{t['table']}: {t['fix'][0]}" for t in sc["tables"] if t["fix"]][:5]
    entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "overall": sc["overall"], "ready_tables": sc["ready_tables"], "table_count": len(sc["tables"]),
             "worse": worse, "better": better, "new_tables": new, "removed_tables": gone, "todo": todo, "note": note[:300],
             "tables": [{"table": t["table"], "score": t["score"]} for t in sc["tables"]]}
    state.kv_set(_key(), json.dumps((hist + [entry])[-KEEP:]))
    state.audit("health_review", f"overall {sc['overall']}, {len(worse)} worse, {len(better)} better")
    return {**entry, "first_review": not hist, "summary": summary_text(entry)}


def summary_text(e: dict) -> str:
    if e["overall"] is None:
        return "No tables to score yet."
    s = f"Overall {e['overall']}/100; {e['ready_tables']} of {e['table_count']} tables are analytics-ready."
    if e["worse"]:
        s += " Got worse: " + ", ".join(f"{w['table']} ({w['was']} to {w['now']})" for w in e["worse"][:5]) + "."
    if e["better"]:
        s += " Improved: " + ", ".join(f"{b['table']} ({b['was']} to {b['now']})" for b in e["better"][:5]) + "."
    if e["todo"]:
        s += " Fix first: " + "; ".join(e["todo"][:3]) + "."
    return s


def enabled() -> bool:
    return bool(state.setting_get(workspaces.active(), "health_review_enabled", True))


def due(days: int = 7) -> bool:
    if not enabled():
        return False
    h = history()
    if not h:
        return True
    last = datetime.strptime(h[-1]["at"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).days >= days


def set_enabled(on: bool) -> dict:
    state.setting_set(workspaces.active(), "health_review_enabled", bool(on))
    return {"enabled": bool(on)}


def tick() -> list[str]:
    try:
        if due():
            review_now()
            return ["health_review"]
    except Exception:  # noqa: BLE001
        pass
    return []
