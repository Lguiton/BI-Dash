"""What the AI Lab is allowed to see in the active workspace.

Modes (set per workspace in Settings):
  off        no questions are sent to any AI provider
  aggregate  the model may only run summary queries (SUM/COUNT/AVG... ) and sees at most 20 rows back
  full       the model may run any read-only SELECT (up to 40 rows come back)
Blocked columns are hidden from the schema the model sees and rejected in its queries and results.

This is a guardrail, not a vault. It stops the model from reading what you told it not to through the normal tools, and
it stops accidents. It does not make a leak impossible: anything the model is allowed to see is sent to the provider you
chose. For data you can't share at all, keep the mode off.
"""
import re

from app.services import workspaces

AGG_ROWS = 20
AGG_FN = re.compile(r"\b(sum|avg|mean|count|min|max|median|stddev\w*|var_\w+|variance|quantile\w*|mode|approx_count_distinct|string_agg|list)\s*\(", re.I)
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class PolicyError(Exception):
    pass


def current() -> dict:
    ws = workspaces.active()
    s = workspaces.settings(ws)
    return {"workspace": ws, "mode": s["ai_mode"], "blocked_columns": list(s["blocked_columns"])}


def describe() -> dict:
    p = current()
    p["allowed"] = p["mode"] != "off"
    return p


def check_sql(sql: str) -> None:
    p = current()
    if p["mode"] == "off":
        raise PolicyError("AI access to this workspace is switched off in Settings.")
    if p["blocked_columns"]:
        words = {w.lower() for w in WORD.findall(sql)}
        hit = sorted(words & set(p["blocked_columns"]))
        if hit:
            raise PolicyError(f"Column(s) {', '.join(hit)} are blocked from the AI in Settings. Leave them out of the query.")
    if p["mode"] == "aggregate" and not AGG_FN.search(sql):
        raise PolicyError("This workspace only allows summary queries for the AI: use SUM, COUNT, AVG, MIN or MAX (with GROUP BY) instead of listing rows.")


def check_result(columns: list[str], rows: list[list]) -> list[list]:
    """Final check on what is about to be shown to the model; returns the rows it may see."""
    p = current()
    if p["blocked_columns"]:
        bad = sorted({c for c in columns if c.lower() in set(p["blocked_columns"])})
        if bad:
            raise PolicyError(f"The result includes blocked column(s) {', '.join(bad)}. Select only the columns you need.")
        for r in rows[:200]:
            for v in r:
                if isinstance(v, str) and v[:1] in "{[(" and any(f"'{b}'" in v.lower() or f'"{b}"' in v.lower() for b in p["blocked_columns"]):
                    raise PolicyError("The result contains a whole row with a blocked column in it. Select plain columns instead.")
    if p["mode"] == "aggregate":
        return rows[:AGG_ROWS]
    return rows


def mask_schema(objs: list[dict]) -> list[dict]:
    p = current()
    blocked = set(p["blocked_columns"])
    if not blocked:
        return objs
    return [{**o, "columns": [c for c in o["columns"] if c["name"].lower() not in blocked]} for o in objs]
