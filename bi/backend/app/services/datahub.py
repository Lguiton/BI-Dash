"""Dataset hub: for every table you imported, a plain-language health check, your own notes and tags, and ideas for what to do next.

Nothing here changes data. The checks are simple on purpose so you can see why each one fired.
"""
from __future__ import annotations

import json
import re

from app.services import datasets, state
from app.services.db import get_cursor

MAX_NOTE = 4000
MAX_TAGS = 8


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def get_notes(table: str) -> dict:
    r = state.one("SELECT note, tags, updated_at FROM dataset_notes WHERE workspace = ? AND table_name = ?", (_ws(), table))
    if not r:
        return {"note": "", "tags": [], "updated_at": None}
    return {"note": r["note"] or "", "tags": json.loads(r["tags"] or "[]"), "updated_at": r["updated_at"]}


def set_notes(table: str, note: str, tags: list[str]) -> dict:
    datasets.table_columns(table)          # raises 404 unless it's one of our tables
    clean = []
    for t in tags:
        t = re.sub(r"[^a-z0-9 _-]", "", t.strip().lower())[:24].strip()
        if t and t not in clean:
            clean.append(t)
    if len(clean) > MAX_TAGS:
        raise datasets.DataError(f"Use at most {MAX_TAGS} tags.")
    state.run("INSERT INTO dataset_notes (workspace, table_name, note, tags, updated_at) VALUES (?,?,?,?,?) "
              "ON CONFLICT(workspace, table_name) DO UPDATE SET note = excluded.note, tags = excluded.tags, updated_at = excluded.updated_at",
              (_ws(), table, note.strip()[:MAX_NOTE], json.dumps(clean), state.now()))
    return get_notes(table)


def list_hub() -> list[dict]:
    notes = {r["table_name"]: r for r in state.rows("SELECT table_name, note, tags FROM dataset_notes WHERE workspace = ?", (_ws(),))}
    out = []
    for t in datasets.list_tables():
        n = notes.get(t["table_name"])
        out.append({"table": t["table_name"], "label": t["label"], "source": t["source"], "rows": t["rows_count"],
                    "columns": len(t["columns"]), "updated_at": t["updated_at"],
                    "tags": json.loads(n["tags"] or "[]") if n else [], "has_note": bool(n and n["note"])})
    return out


def _checks(table: str, prof: dict) -> list[dict]:
    """Each check: level (info|warn), what we saw, and why it matters."""
    rows = prof["rows"]
    out: list[dict] = []
    if rows == 0:
        return [{"level": "warn", "title": "The table is empty", "why": "There is nothing to analyse yet."}]
    if rows < 30:
        out.append({"level": "warn", "title": f"Only {rows} rows", "why": "Averages and charts on so few rows swing wildly. Treat any pattern as a guess."})
    for c in prof["columns"]:
        nulls = c["nulls"] or 0
        pct = nulls / rows
        if pct >= 0.5:
            out.append({"level": "warn", "title": f"'{c['name']}' is {pct:.0%} empty", "why": "A column that is mostly blank rarely helps. Fix the source or drop it."})
        elif pct >= 0.05:
            out.append({"level": "info", "title": f"'{c['name']}' has {nulls:,} blanks ({pct:.0%})", "why": "Decide whether blank means zero, unknown or an error before averaging it."})
        if c["distinct_count"] == 1 and rows > 1:
            out.append({"level": "info", "title": f"'{c['name']}' never changes", "why": "A constant column carries no information for charts or models."})
        if c["kind"] == "text" and rows >= 20 and c["distinct_count"] >= 0.9 * rows and nulls < rows:
            out.append({"level": "info", "title": f"'{c['name']}' looks like an ID or free text", "why": "Nearly every value is different, so grouping by it is useless. Good as a key, poor as a category."})
        if c["kind"] == "number" and c.get("min") is not None and c.get("max") is not None and c.get("mean") is not None and c.get("median") is not None:
            span = (c["max"] - c["min"]) or 0
            if span and abs(c["mean"] - c["median"]) > 0.25 * span:
                out.append({"level": "info", "title": f"'{c['name']}' is skewed (mean {c['mean']:.4g} vs median {c['median']:.4g})",
                            "why": "A few extreme values pull the average. Report the median too, and look at a histogram."})
    with get_cursor() as cur:
        dup = cur.execute(f"SELECT COUNT(*) - COUNT(DISTINCT ROW(*COLUMNS(*))) FROM {datasets.q(table)}").fetchone()[0] if len(prof["columns"]) <= 40 else 0
    if dup:
        out.append({"level": "warn", "title": f"{dup:,} duplicate rows", "why": "Exact copies double-count in totals. Confirm they are real repeats before keeping them."})
    return out


def _ideas(prof: dict) -> list[str]:
    kinds = {}
    for c in prof["columns"]:
        kinds.setdefault(c["kind"], []).append(c["name"])
    ideas = []
    nums, dates, texts = kinds.get("number", []), kinds.get("date", []), kinds.get("text", [])
    if dates and nums:
        ideas.append(f"Trend: chart {nums[0]} over {dates[0]} (My data → chart, bucket by month).")
    if texts and nums:
        ideas.append(f"Breakdown: total {nums[0]} by {texts[0]}, then ask which group is the outlier and why.")
    if len(nums) >= 2:
        ideas.append(f"Relationship: scatter {nums[0]} against {nums[1]}. Correlation is a hint, not a cause.")
    if nums:
        ideas.append(f"Distribution: histogram of {nums[0]} to spot skew and outliers before averaging.")
    ideas.append("Build a repeatable path from this table in the Workflow builder (filter, group, sort), then save it.")
    return ideas[:5]


def summary(table: str) -> dict:
    prof = datasets.profile(table)       # raises DataError 404 for a table that isn't ours
    checks = _checks(table, prof)
    warn = sum(1 for c in checks if c["level"] == "warn")
    return {"table": table, "rows": prof["rows"], "columns": prof["columns"], "checks": checks,
            "grade": "needs attention" if warn else ("fine, with notes" if checks else "looks clean"),
            "ideas": _ideas(prof), **get_notes(table)}
