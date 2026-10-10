"""Data quality rules: our own small take on tools like Great Expectations.

You attach rules to a table (no blanks here, this column is unique, values stay in a range, ...). Running them tells you which rule
failed, how many rows broke it and shows a few of them. Rules only ever read. The last result is kept so an alert can use it.
Suggested rules are based on how the data looks TODAY, so review them: a rule that fits a sample can be wrong for the real thing.
"""
from __future__ import annotations

import json
import time

from app.services import datasets, state, workflows
from app.services.db import get_cursor

q = datasets.q
KINDS = {
    "not_null": "No blanks in a column",
    "unique": "Every value in a column is different",
    "range": "Numbers stay between a minimum and a maximum",
    "in_set": "Values come from an allowed list",
    "matches": "Text matches a pattern (regular expression)",
    "row_count": "The table has a sensible number of rows",
    "fresh": "The newest date is recent enough",
}
MAX_RULES_PER_TABLE = 40
SAMPLE = 5


class DqError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def _cols(table: str) -> dict[str, str]:
    try:
        return workflows._columns(table)
    except workflows.WorkflowError as e:
        raise DqError(str(e), e.status) from e


def _num(v, what):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise DqError(f"{what} must be a number.") from None
    if f != f or abs(f) == float("inf"):
        raise DqError(f"{what} must be a finite number.")
    return f


def validate(table: str, kind: str, params: dict) -> dict:
    cols = _cols(table)
    if kind not in KINDS:
        raise DqError(f"Unknown rule type. Use one of: {', '.join(KINDS)}.")
    p: dict = {}
    if kind != "row_count":
        c = params.get("column")
        if c not in cols:
            raise DqError(f"Unknown column '{c}'. Available: {', '.join(cols)}.")
        p["column"] = c
    kind_of = datasets.kind_of(cols[p["column"]]) if "column" in p else None
    if kind == "range":
        if kind_of != "number":
            raise DqError(f"'{p['column']}' isn't a number column.")
        lo, hi = params.get("min"), params.get("max")
        if lo in (None, "") and hi in (None, ""):
            raise DqError("Give a minimum, a maximum, or both.")
        if lo not in (None, ""):
            p["min"] = _num(lo, "The minimum")
        if hi not in (None, ""):
            p["max"] = _num(hi, "The maximum")
        if "min" in p and "max" in p and p["min"] > p["max"]:
            raise DqError("The minimum is bigger than the maximum.")
    elif kind == "in_set":
        vals = params.get("values")
        if not isinstance(vals, list) or not vals or len(vals) > 200:
            raise DqError("Give 1 to 200 allowed values.")
        p["values"] = [str(v) for v in vals]
    elif kind == "matches":
        pat = str(params.get("pattern") or "")
        if not pat or len(pat) > 200:
            raise DqError("Give a pattern up to 200 characters.")
        with get_cursor() as cur:
            try:
                cur.execute("SELECT regexp_matches('x', ?)", [pat]).fetchone()
            except Exception as e:  # noqa: BLE001
                raise DqError(f"That pattern isn't valid: {str(e)[:120]}") from e
        p["pattern"] = pat
    elif kind == "row_count":
        lo, hi = params.get("min"), params.get("max")
        if lo in (None, "") and hi in (None, ""):
            raise DqError("Give a minimum, a maximum, or both.")
        if lo not in (None, ""):
            p["min"] = int(_num(lo, "The minimum"))
        if hi not in (None, ""):
            p["max"] = int(_num(hi, "The maximum"))
    elif kind == "fresh":
        if kind_of != "date":
            raise DqError(f"'{p['column']}' isn't a date column.")
        p["max_age_days"] = int(_num(params.get("max_age_days"), "Max age in days"))
        if p["max_age_days"] < 0:
            raise DqError("Max age can't be negative.")
    return p


def describe(kind: str, p: dict) -> str:
    c = p.get("column")
    return {"not_null": f"{c} has no blanks", "unique": f"{c} is unique",
            "range": f"{c} between {p.get('min', '-inf')} and {p.get('max', 'inf')}",
            "in_set": f"{c} is one of {', '.join(p.get('values', [])[:6])}{'...' if len(p.get('values', [])) > 6 else ''}",
            "matches": f"{c} matches /{p.get('pattern')}/", "row_count": f"row count between {p.get('min', 0)} and {p.get('max', 'inf')}",
            "fresh": f"newest {c} is at most {p.get('max_age_days')} day(s) old"}[kind]


def add_rule(table: str, kind: str, params: dict) -> dict:
    p = validate(table, kind, params)
    if len(list_rules(table)) >= MAX_RULES_PER_TABLE:
        raise DqError(f"A table can have at most {MAX_RULES_PER_TABLE} rules.")
    cur = state.run("INSERT INTO dq_rules (workspace, table_name, kind, params, created_at) VALUES (?,?,?,?,?)", (_ws(), table, kind, json.dumps(p), state.now()))
    return {"id": int(cur.lastrowid), "table": table, "kind": kind, "params": p, "text": describe(kind, p)}


def list_rules(table: str | None = None) -> list[dict]:
    rows = state.rows("SELECT id, table_name, kind, params FROM dq_rules WHERE workspace = ?" + (" AND table_name = ?" if table else "") + " ORDER BY id",
                      (_ws(), table) if table else (_ws(),))
    out = []
    for r in rows:
        p = json.loads(r["params"])
        out.append({"id": r["id"], "table": r["table_name"], "kind": r["kind"], "params": p, "text": describe(r["kind"], p)})
    return out


def delete_rule(rid: int) -> None:
    if not state.one("SELECT id FROM dq_rules WHERE id = ? AND workspace = ?", (rid, _ws())):
        raise DqError("No such rule.", 404)
    state.run("DELETE FROM dq_rules WHERE id = ?", (rid,))


def _rows(cur, sql, params=()):
    res = cur.execute(sql, list(params))
    names = [d[0] for d in res.description]
    return [{n: datasets._json(v) for n, v in zip(names, r)} for r in res.fetchall()]


def _check(cur, table: str, rule: dict) -> dict:
    k, p, t = rule["kind"], rule["params"], q(table)
    c = q(p["column"]) if "column" in p else None
    total = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    sample: list = []
    if k == "not_null":
        bad_where = f"{c} IS NULL"
    elif k == "unique":
        n = cur.execute(f"SELECT COUNT(*) FROM (SELECT {c} FROM {t} WHERE {c} IS NOT NULL GROUP BY {c} HAVING COUNT(*) > 1)").fetchone()[0]
        sample = _rows(cur, f"SELECT {c} AS value, COUNT(*) AS copies FROM {t} WHERE {c} IS NOT NULL GROUP BY {c} HAVING COUNT(*) > 1 ORDER BY copies DESC LIMIT {SAMPLE}")
        return {"failing": n, "total": total, "sample": sample, "unit": "repeated values"}
    elif k == "range":
        conds = ([f"{c} < ?"] if "min" in p else []) + ([f"{c} > ?"] if "max" in p else [])
        args = ([p["min"]] if "min" in p else []) + ([p["max"]] if "max" in p else [])
        bad_where = "(" + " OR ".join(conds) + ")"
        n = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {bad_where}", args).fetchone()[0]
        return {"failing": n, "total": total, "unit": "rows",
                "sample": _rows(cur, f"SELECT * FROM {t} WHERE {bad_where} LIMIT {SAMPLE}", args)}
    elif k == "in_set":
        marks = ", ".join("?" for _ in p["values"])
        bad_where = f"{c} IS NOT NULL AND CAST({c} AS VARCHAR) NOT IN ({marks})"
        n = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {bad_where}", p["values"]).fetchone()[0]
        return {"failing": n, "total": total, "unit": "rows",
                "sample": _rows(cur, f"SELECT * FROM {t} WHERE {bad_where} LIMIT {SAMPLE}", p["values"])}
    elif k == "matches":
        bad_where = f"{c} IS NOT NULL AND NOT regexp_matches(CAST({c} AS VARCHAR), ?)"
        n = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {bad_where}", [p["pattern"]]).fetchone()[0]
        return {"failing": n, "total": total, "unit": "rows",
                "sample": _rows(cur, f"SELECT * FROM {t} WHERE {bad_where} LIMIT {SAMPLE}", [p["pattern"]])}
    elif k == "row_count":
        bad = (("min" in p and total < p["min"]) or ("max" in p and total > p["max"]))
        return {"failing": 1 if bad else 0, "total": total, "unit": "table", "sample": [{"rows": total}] if bad else []}
    else:   # fresh
        mx = cur.execute(f"SELECT MAX({c}) FROM {t}").fetchone()[0]
        if mx is None:
            return {"failing": 1, "total": total, "unit": "table", "sample": [{"newest": None}]}
        from datetime import date, datetime
        d = mx.date() if isinstance(mx, datetime) else mx
        age = (date.today() - d).days
        bad = age > p["max_age_days"]
        return {"failing": 1 if bad else 0, "total": total, "unit": "table", "sample": [{"newest": str(d), "age_days": age}] if bad else []}
    n = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {bad_where}").fetchone()[0]
    return {"failing": n, "total": total, "unit": "rows", "sample": _rows(cur, f"SELECT * FROM {t} WHERE {bad_where} LIMIT {SAMPLE}")}


def run(table: str, trigger: str = "manual") -> dict:
    cols = _cols(table)                          # the table must exist and be allowed
    rules = list_rules(table)
    if not rules:
        raise DqError("This table has no rules yet. Add some, or use the suggested ones.")
    results, t0 = [], time.perf_counter()
    with get_cursor() as cur:
        for r in rules:
            try:
                if "column" in r["params"] and r["params"]["column"] not in cols:
                    raise DqError(f"column '{r['params']['column']}' no longer exists")
                res = _check(cur, table, r)
                results.append({"id": r["id"], "kind": r["kind"], "text": r["text"], "passed": res["failing"] == 0, **res})
            except Exception as e:  # noqa: BLE001  a broken rule is a finding, not a crash
                results.append({"id": r["id"], "kind": r["kind"], "text": r["text"], "passed": False, "failing": None, "total": None,
                                "unit": "error", "sample": [], "error": str(e)[:160]})
    failed = sum(1 for x in results if not x["passed"])
    out = {"table": table, "rules": len(results), "failed": failed, "passed": len(results) - failed, "results": results,
           "seconds": round(time.perf_counter() - t0, 2), "at": state.now()}
    state.run("INSERT INTO dq_runs (workspace, at, table_name, total, failed, detail, trigger) VALUES (?,?,?,?,?,?,?)",
              (_ws(), out["at"], table, len(results), failed, json.dumps([{k: x[k] for k in ("text", "passed", "failing", "unit")} for x in results]), trigger))
    state.run("DELETE FROM dq_runs WHERE id NOT IN (SELECT id FROM dq_runs ORDER BY id DESC LIMIT 1000)")
    return out


def history(table: str | None = None, limit: int = 30) -> list[dict]:
    rows = state.rows("SELECT id, at, table_name, total, failed, trigger FROM dq_runs WHERE workspace = ?" + (" AND table_name = ?" if table else "") + " ORDER BY id DESC LIMIT ?",
                      (_ws(), table, limit) if table else (_ws(), limit))
    return rows


def latest_failures() -> list[dict]:
    """The most recent run of each table that still has failing rules (used by alerts; it never re-runs anything)."""
    out = []
    for t in {r["table_name"] for r in state.rows("SELECT DISTINCT table_name FROM dq_runs WHERE workspace = ?", (_ws(),))}:
        r = state.one("SELECT at, table_name, total, failed, detail FROM dq_runs WHERE workspace = ? AND table_name = ? ORDER BY id DESC LIMIT 1", (_ws(), t))
        if r and r["failed"]:
            bad = [d["text"] for d in json.loads(r["detail"]) if not d["passed"]]
            out.append({"table": t, "failed": r["failed"], "total": r["total"], "at": r["at"], "rules": bad})
    return out


def suggest(table: str) -> dict:
    """Rules that would pass today. A starting point to review, not a verdict on what 'good' means."""
    prof = datasets.profile(table) if table not in workflows.BUILTIN else _builtin_profile(table)
    have = {(r["kind"], r["params"].get("column")) for r in list_rules(table)}
    out = []
    for c in prof["columns"]:
        n = prof["rows"]
        if n and not c["nulls"] and ("not_null", c["name"]) not in have:
            out.append({"kind": "not_null", "params": {"column": c["name"]}, "text": f"{c['name']} has no blanks", "why": "It has none right now."})
        if n >= 20 and c["distinct_count"] == n and not c["nulls"] and ("unique", c["name"]) not in have:
            out.append({"kind": "unique", "params": {"column": c["name"]}, "text": f"{c['name']} is unique", "why": "Every value is different right now."})
        if c["kind"] == "number" and c.get("min") is not None and ("range", c["name"]) not in have:
            span = (c["max"] - c["min"]) or abs(c["max"]) or 1
            lo = 0 if c["min"] >= 0 else c["min"] - span * 0.5
            out.append({"kind": "range", "params": {"column": c["name"], "min": lo, "max": c["max"] + span * 0.5},
                        "text": f"{c['name']} between {lo:.4g} and {c['max'] + span * 0.5:.4g}",
                        "why": "Today's min and max with 50% headroom. Tighten or loosen it to match what is realistic."})
    return {"table": table, "suggestions": out[:25], "caution": "Suggested from today's data. Check each one makes business sense before saving it."}


def _builtin_profile(table: str) -> dict:
    cols = _cols(table)
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]
        out = []
        for name, typ in cols.items():
            c, k = q(name), datasets.kind_of(typ)
            r = cur.execute(f"SELECT COUNT(*) - COUNT({c}), COUNT(DISTINCT {c})" + (f", MIN({c}), MAX({c})" if k == "number" else "") + f" FROM {q(table)}").fetchone()
            item = {"name": name, "type": typ, "kind": k, "nulls": r[0], "distinct_count": r[1]}
            if k == "number":
                item.update({"min": float(r[2]) if r[2] is not None else None, "max": float(r[3]) if r[3] is not None else None})
            out.append(item)
    return {"table": table, "rows": total, "columns": out}
