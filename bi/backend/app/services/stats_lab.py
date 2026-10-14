"""Analysis Lab: probability, time-series, filtering and regression on your own tables.

Everything is computed here with plain numpy/scipy. Nothing is estimated by an LLM, and every
user-chosen column or operator is checked against a whitelist (values are bound parameters).

Sources: "operations" (the flat operations view) or any table imported in My data.
Findings are leads, not verdicts: a probability from history is not a promise, a trend can end,
and a regression shows association, not cause.
"""
from __future__ import annotations

import math
import statistics
from datetime import date, datetime, timedelta

import numpy as np
from scipy import stats as sps

from app.services import datasets
from app.services.datasets import DataError, q
from app.services.db import fetch_all, get_cursor

OPS = "operations"
OPS_VIEW = "v_operations_flat"
OPS_COLS = [
    ("record_date", "date"), ("year", "number"), ("quarter", "number"), ("month", "number"), ("month_name", "text"),
    ("day_name", "text"), ("is_weekend", "bool"), ("entity_id", "text"), ("entity_name", "text"), ("category", "text"),
    ("cost_budget_per_record", "number"), ("revenue", "number"), ("operational_cost", "number"), ("profit", "number"),
    ("margin", "number"), ("units_processed", "number"), ("duration_minutes", "number"), ("status", "text"),
]
OPS_LABEL = "Operations (the main dashboard data)"
MAX_FILTERS = 12
MAX_ROWS = 100_000
MAX_GROUPS = 20
OPS_SET = {"eq", "ne", "gt", "gte", "lt", "lte", "between", "in", "contains", "is_null", "not_null"}
SQL_OP = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
OP_WORDS = {"eq": "is", "ne": "is not", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "between": "between", "in": "is one of",
            "contains": "contains", "is_null": "is empty", "not_null": "is not empty"}


# ------------------------------------------------------------------ helpers
def _f(x, d: int = 6):
    """JSON-safe float: NaN/inf become None."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, d) if math.isfinite(x) else None


def _with_distinct(ident: str, cols: list[dict]) -> list[dict]:
    """Add how many different values each category column has, so the page can default to useful groupings (not an ID column)."""
    cats = [c["name"] for c in cols if c["kind"] in ("text", "bool")][:30]
    if cats:
        try:
            row = _rows("SELECT " + ", ".join(f"COUNT(DISTINCT {q(c)}) AS d{i}" for i, c in enumerate(cats)) + f" FROM {q(ident)}", [])[0]
            for i, c in enumerate(cats):
                next(x for x in cols if x["name"] == c)["distinct"] = int(row[f"d{i}"])
        except Exception:  # a hint only; never block the page
            pass
    return cols


def sources() -> list[dict]:
    out = [{"id": OPS, "label": OPS_LABEL, "rows": _count(OPS_VIEW), "columns": _with_distinct(OPS_VIEW, [{"name": n, "kind": k} for n, k in OPS_COLS])}]
    for t in datasets.list_tables():
        try:
            cols = [{"name": c["name"], "kind": datasets.kind_of(c["type"])} for c in datasets.table_columns(t["table_name"])]
        except DataError:
            continue
        out.append({"id": t["table_name"], "label": t.get("label") or t["table_name"], "rows": t.get("rows_count"), "columns": _with_distinct(t["table_name"], cols)})
    return out


def _count(ident: str) -> int:
    with get_cursor() as cur:
        return int(cur.execute(f"SELECT COUNT(*) FROM {q(ident)}").fetchone()[0])


def resolve(source: str) -> tuple[str, dict[str, str]]:
    """(SQL identifier, {column: kind}). Raises DataError for anything that is not ours."""
    if source == OPS:
        return OPS_VIEW, dict(OPS_COLS)
    cols = datasets.table_columns(source)
    return source, {c["name"]: datasets.kind_of(c["type"]) for c in cols}


def _need(cols: dict[str, str], name: str | None, kinds: tuple[str, ...] | None = None, what: str = "column") -> str:
    if not name or name not in cols:
        raise DataError(f"Pick a valid {what}" + (f" ('{name}' is not in this table)." if name else "."))
    if kinds and cols[name] not in kinds:
        raise DataError(f"The {what} '{name}' is a {cols[name]} column; this needs {' or '.join(kinds)}.")
    return name


def _typed(kind: str, v):
    if kind == "number":
        try:
            x = float(str(v).replace(",", "").replace("$", "").strip())
        except (TypeError, ValueError) as e:
            raise DataError(f"'{v}' is not a number.") from e
        if not math.isfinite(x):
            raise DataError(f"'{v}' is not a usable number.")
        return x
    if kind == "date":
        s = str(v).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise DataError(f"'{v}' is not a date (use YYYY-MM-DD).")
    if kind == "bool":
        s = str(v).strip().lower()
        if s in ("true", "1", "yes", "y", "t"):
            return True
        if s in ("false", "0", "no", "n", "f"):
            return False
        raise DataError(f"'{v}' is not true/false.")
    return str(v)


def cond_sql(cols: dict[str, str], c: dict) -> tuple[str, list, str]:
    """One condition -> (SQL fragment, params, plain-English text)."""
    col = _need(cols, c.get("column"), what="filter column")
    op = c.get("op", "eq")
    if op not in OPS_SET:
        raise DataError(f"Unknown operator '{op}'.")
    kind = cols[col]
    qc = q(col)
    if op == "is_null":
        return f"{qc} IS NULL", [], f"{col} is empty"
    if op == "not_null":
        return f"{qc} IS NOT NULL", [], f"{col} is not empty"
    if op in ("gt", "gte", "lt", "lte") and kind in ("text", "bool"):
        raise DataError(f"'{OP_WORDS[op]}' needs a number or date column; '{col}' is {kind}.")
    if op == "contains":
        if kind != "text":
            raise DataError(f"'contains' works on text columns; '{col}' is {kind}.")
        s = str(c.get("value", ""))
        if not s:
            raise DataError("'contains' needs some text.")
        return f"LOWER({qc}) LIKE ?", [f"%{s.lower().replace('%', '').replace('_', '')}%"], f"{col} contains '{s}'"
    if op == "between":
        lo, hi = _typed(kind, c.get("value")), _typed(kind, c.get("value2"))
        if kind in ("text", "bool"):
            raise DataError("'between' needs a number or date column.")
        return f"{qc} BETWEEN ? AND ?", [lo, hi], f"{col} between {lo} and {hi}"
    if op == "in":
        raw = c.get("value")
        items = [x.strip() for x in str(raw).split(",") if x.strip()] if not isinstance(raw, list) else [str(x) for x in raw]
        if not items:
            raise DataError("'is one of' needs at least one value (comma-separated).")
        if len(items) > 50:
            raise DataError("'is one of' accepts up to 50 values.")
        vals = [_typed(kind, x) for x in items]
        return f"{qc} IN ({', '.join('?' for _ in vals)})", vals, f"{col} is one of {', '.join(items)}"
    v = _typed(kind, c.get("value"))
    return f"{qc} {SQL_OP[op]} ?", [v], f"{col} {OP_WORDS[op]} {v}"


def where_clause(cols: dict[str, str], filters: list[dict] | None, mode: str = "and", extra: list[str] | None = None) -> tuple[str, list, list[str]]:
    filters = filters or []
    if len(filters) > MAX_FILTERS:
        raise DataError(f"Use at most {MAX_FILTERS} filters.")
    if mode not in ("and", "or"):
        raise DataError("Combine filters with 'and' or 'or'.")
    parts, params, words = [], [], []
    for c in filters:
        s, p, w = cond_sql(cols, c)
        parts.append(f"({s})")
        params += p
        words.append(w)
    joined = f" {mode.upper()} ".join(parts)
    clauses = []
    if joined:
        clauses.append(f"({joined})")
    clauses += extra or []
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params, words


def _rows(sql: str, params: list) -> list[dict]:
    with get_cursor() as cur:
        return fetch_all(cur, sql, params)


# ------------------------------------------------------------------ filtering
def filter_report(source: str, filters: list[dict], mode: str = "and", preview: int = 15) -> dict:
    ident, cols = resolve(source)
    total = _count(ident)
    w, params, words = where_clause(cols, filters, mode)
    kept = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    funnel = []
    cum_params: list = []
    cum_parts: list[str] = []
    for c, text in zip(filters, words):
        s, p, _ = cond_sql(cols, c)
        alone = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)} WHERE {s}", p)[0]["n"])
        cum_parts.append(f"({s})")
        cum_params += p
        joiner = " AND " if mode == "and" else " OR "
        after = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)} WHERE " + joiner.join(cum_parts), cum_params)[0]["n"])
        funnel.append({"filter": text, "matches_alone": alone, "rows_after": after})
    num_cols = [c for c, k in cols.items() if k == "number"][:6]
    summary = []
    if num_cols:
        sel = ", ".join(f"AVG({q(c)}) AS a{i}, MIN({q(c)}) AS lo{i}, MAX({q(c)}) AS hi{i}" for i, c in enumerate(num_cols))
        allr = _rows(f"SELECT {sel} FROM {q(ident)}", [])[0]
        keptr = _rows(f"SELECT {sel} FROM {q(ident)}{w}", params)[0] if kept else {}
        for i, c in enumerate(num_cols):
            summary.append({"column": c, "mean_all": _f(allr.get(f"a{i}"), 3), "mean_kept": _f(keptr.get(f"a{i}"), 3),
                            "min_kept": _f(keptr.get(f"lo{i}"), 3), "max_kept": _f(keptr.get(f"hi{i}"), 3)})
    shown = [c for c in cols if c != "fact_id"][:12]
    prev = _rows(f"SELECT {', '.join(q(c) for c in shown)} FROM {q(ident)}{w} LIMIT {int(max(1, min(preview, 50)))}", params)
    for r in prev:
        for k, v in list(r.items()):
            if isinstance(v, (date, datetime)):
                r[k] = v.isoformat()[:10]
            elif isinstance(v, float):
                r[k] = _f(v, 4)
    sql = f"SELECT * FROM {q(ident)}{w}"
    return {
        "total": total, "kept": kept, "removed": total - kept, "kept_pct": _f(kept / total * 100, 1) if total else None,
        "mode": mode, "funnel": funnel, "summary": summary, "columns": shown, "preview": prev,
        "sql": sql, "params": [str(p) for p in params],
        "lesson": ("Filtering isolates the rows that matter before you analyze them. Always compare 'kept' with 'total': a filter that "
                   "removes most of your data can make results look sharper than they are."),
    }


# ------------------------------------------------------------------ probability
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def probability(source: str, event: dict, filters: list[dict] | None = None, mode: str = "and", group_by: str | None = None,
                given: dict | None = None, entity_col: str | None = None) -> dict:
    ident, cols = resolve(source)
    if not event or not event.get("column"):
        raise DataError("Describe the event first (for example: status is Delayed).")
    ev_sql, ev_p, ev_words = cond_sql(cols, event)
    ev_col = event["column"]
    null_guard = [f"{q(ev_col)} IS NOT NULL"] if event.get("op") not in ("is_null", "not_null") else []
    w, params, fwords = where_clause(cols, filters, mode, null_guard)
    n_all = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}", [])[0]["n"])
    base = _rows(f"SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN {ev_sql} THEN 1 ELSE 0 END), 0) AS k FROM {q(ident)}{w}", ev_p + params)[0]
    n, k = int(base["n"]), int(base["k"])
    if n == 0:
        raise DataError("No rows are left to measure (check the filters, or the event column may be empty).")
    lo, hi = wilson(k, n)
    out: dict = {
        "event": ev_words, "filters": fwords, "rows_total": n_all, "rows_used": n, "events": k,
        "p": _f(k / n), "ci_low": _f(lo), "ci_high": _f(hi),
        "sentences": [f"In {n:,} rows, '{ev_words}' happened {k:,} times: P(event) = {k / n:.1%} (95% range {lo:.1%} to {hi:.1%})."],
        "warnings": [],
    }
    if n < 30:
        out["warnings"].append(f"Only {n} rows: a probability from so little history is shaky.")
    if k == 0 or k == n:
        out["warnings"].append("The event never or always happened here, so the estimate is 0% or 100%. That is the data, not a guarantee.")
    # conditional probability by group
    if group_by:
        _need(cols, group_by, what="group column")
        if cols[group_by] == "number":
            distinct = int(_rows(f"SELECT COUNT(DISTINCT {q(group_by)}) AS n FROM {q(ident)}", [])[0]["n"])
            if distinct > 30:
                raise DataError(f"'{group_by}' has {distinct} different numbers; group by a category column, or filter first.")
        rows = _rows(
            f"SELECT CAST({q(group_by)} AS VARCHAR) AS g, COUNT(*) AS n, SUM(CASE WHEN {ev_sql} THEN 1 ELSE 0 END) AS k "
            f"FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(group_by)} IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT {MAX_GROUPS}", ev_p + params)
        groups = []
        for r in rows:
            gn, gk = int(r["n"]), int(r["k"] or 0)
            glo, ghi = wilson(gk, gn)
            groups.append({"group": r["g"], "n": gn, "events": gk, "p": _f(gk / gn), "ci_low": _f(glo), "ci_high": _f(ghi),
                           "lift": _f((gk / gn) / (k / n)) if k else None, "small": gn < 30})
        out["groups"] = groups
        out["group_by"] = group_by
        if len(groups) >= 2:
            ranked = sorted(groups, key=lambda g: g["p"] or 0, reverse=True)
            a, b = ranked[0], ranked[-1]
            out["sentences"].append(f"By {group_by}: highest is '{a['group']}' at {a['p']:.1%}, lowest is '{b['group']}' at {b['p']:.1%}.")
            # chi-square test of independence between group and event
            table = np.array([[g["events"], g["n"] - g["events"]] for g in groups if g["n"] > 0], dtype=float)
            if table.shape[0] >= 2 and (table.sum(axis=0) > 0).all():
                try:
                    chi2, p, _, _ = sps.chi2_contingency(table)
                    out["independence_p"] = _f(p, 6)
                    out["sentences"].append(
                        ("The difference between groups is unlikely to be luck" if p < 0.05 else "The difference between groups could easily be luck")
                        + f" (chi-square p = {p:.3g}).")
                except ValueError:
                    pass
    # Bayes: P(A|B)
    if given and given.get("column"):
        b_sql, b_p, b_words = cond_sql(cols, given)
        r = _rows(
            f"SELECT COUNT(*) AS n, SUM(CASE WHEN {ev_sql} THEN 1 ELSE 0 END) AS a, SUM(CASE WHEN {b_sql} THEN 1 ELSE 0 END) AS b, "
            f"SUM(CASE WHEN ({ev_sql}) AND ({b_sql}) THEN 1 ELSE 0 END) AS ab FROM {q(ident)}{w}",
            ev_p + b_p + ev_p + b_p + params)[0]
        N, A, B, AB = int(r["n"]), int(r["a"] or 0), int(r["b"] or 0), int(r["ab"] or 0)
        bayes = {"given": b_words, "p_a": _f(A / N), "p_b": _f(B / N) if N else None, "p_a_and_b": _f(AB / N),
                 "p_a_given_b": _f(AB / B) if B else None, "p_b_given_a": _f(AB / A) if A else None,
                 "p_a_given_not_b": _f((A - AB) / (N - B)) if N - B else None,
                 "lift": _f((AB / B) / (A / N)) if B and A else None, "counts": {"n": N, "a": A, "b": B, "ab": AB}}
        if B and A and N - B > 0 and N - A > 0:
            tbl = np.array([[AB, B - AB], [A - AB, N - A - (B - AB)]], dtype=float)
            if (tbl >= 0).all() and (tbl.sum(axis=0) > 0).all() and (tbl.sum(axis=1) > 0).all():
                bayes["independence_p"] = _f(sps.chi2_contingency(tbl)[1], 6)
        out["bayes"] = bayes
        if bayes["p_a_given_b"] is not None:
            out["sentences"].append(f"P(event | {b_words}) = {bayes['p_a_given_b']:.1%}, compared with {bayes['p_a']:.1%} overall.")
    # repeat behaviour per entity (e.g. does a customer who did it once do it again?)
    if entity_col:
        _need(cols, entity_col, what="who/what column")
        er = _rows(
            f"SELECT n_events, COUNT(*) AS entities FROM (SELECT {q(entity_col)} AS e, COUNT(*) AS n_events FROM {q(ident)}"
            f"{w}{' AND' if w else ' WHERE'} ({ev_sql}) AND {q(entity_col)} IS NOT NULL GROUP BY 1) GROUP BY 1 ORDER BY 1", params + ev_p)
        once = sum(int(r["entities"]) for r in er)
        again = sum(int(r["entities"]) for r in er if int(r["n_events"]) >= 2)
        rlo, rhi = wilson(again, once)
        out["repeat"] = {"entity_col": entity_col, "entities_with_event": once, "entities_repeating": again,
                         "p_repeat": _f(again / once) if once else None, "ci_low": _f(rlo), "ci_high": _f(rhi),
                         "distribution": [{"times": int(r["n_events"]), "entities": int(r["entities"])} for r in er[:15]]}
        if once:
            out["sentences"].append(f"Of {once:,} {entity_col} values that had the event at least once, {again:,} ({again / once:.1%}) had it again.")
    out["lesson"] = ("Probability from history = (times it happened) / (times it could have). A conditional probability P(A | B) only counts rows "
                     "where B is true. A big 'lift' on a tiny group is often noise; check the sample size and the range.")
    return out


# ------------------------------------------------------------------ time series
BUCKETS = {"day": 7, "week": 4, "month": 3}
AGGS = {"sum": "SUM", "avg": "AVG", "count": "COUNT", "min": "MIN", "max": "MAX"}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _step(t: date, bucket: str) -> date:
    if bucket == "day":
        return t + timedelta(days=1)
    if bucket == "week":
        return t + timedelta(days=7)
    return date(t.year + (t.month == 12), t.month % 12 + 1, 1)


def _load_series(ident: str, date_col: str, expr: str, agg: str, bucket: str, w: str, params: list, min_points: int = 8):
    """Bucketed series with gaps filled. Returns (dates, values, filled_count) or a reason string when there is too little data."""
    rows = _rows(f"SELECT CAST(DATE_TRUNC('{bucket}', {q(date_col)}) AS DATE) AS t, {expr} AS v FROM {q(ident)}{w} GROUP BY 1 ORDER BY 1", params)
    rows = [r for r in rows if r["t"] is not None]
    if len(rows) < min_points:
        return f"Need at least {min_points} {bucket}s of data; this selection has {len(rows)}."
    if len(rows) > 5000:
        raise DataError(f"{len(rows):,} {bucket}s is too many to analyze at once; use a wider bucket or filter the dates.")
    have = {r["t"]: r["v"] for r in rows}
    ts, t, end = [], rows[0]["t"], rows[-1]["t"]
    while t <= end and len(ts) < 6000:
        ts.append(t)
        t = _step(t, bucket)
    vals = np.array([float(have[t]) if have.get(t) is not None else (0.0 if agg in ("sum", "count") else np.nan) for t in ts])
    filled = int(np.isnan(vals).sum())
    if filled:
        idx = np.arange(len(vals))
        good = ~np.isnan(vals)
        vals = np.interp(idx, idx[good], vals[good])
    return ts, vals, filled


def timeseries(source: str, date_col: str, value_col: str | None, agg: str = "sum", bucket: str = "day",
               filters: list[dict] | None = None, mode: str = "and", window: int | None = None, horizon: int = 0) -> dict:
    ident, cols = resolve(source)
    horizon = max(0, min(int(horizon or 0), 60))
    _need(cols, date_col, ("date",), "date column")
    if agg not in AGGS:
        raise DataError("Pick sum, avg, count, min or max.")
    if bucket not in BUCKETS:
        raise DataError("Pick day, week or month.")
    if agg != "count":
        _need(cols, value_col, ("number",), "value column")
        expr = f"{AGGS[agg]}({q(value_col)})"
    else:
        expr = "COUNT(*)"
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(date_col)} IS NOT NULL"])
    loaded = _load_series(ident, date_col, expr, agg, bucket, w, params)
    if isinstance(loaded, str):
        return {"available": False, "reason": loaded, "filters": fwords}
    ts, vals, filled = loaded
    n = len(vals)
    x = np.arange(n, dtype=float)
    win = int(window or BUCKETS[bucket])
    win = max(2, min(win, max(2, n // 2)))
    ma = [None] * (win - 1) + [float(v) for v in np.convolve(vals, np.ones(win) / win, mode="valid")]
    lr = sps.linregress(x, vals)
    trend = lr.intercept + lr.slope * x
    resid = vals - trend
    # seasonality
    period = 7 if bucket == "day" else 12 if bucket == "month" else 0
    season = np.zeros(n)
    seas: dict | None = None
    if period and n >= 2 * period:
        phase = np.array([t.weekday() if bucket == "day" else t.month - 1 for t in ts])
        idxs = range(7) if bucket == "day" else range(12)
        means = {i: float(resid[phase == i].mean()) for i in idxs if (phase == i).any()}
        centre = statistics.fmean(means.values())
        means = {i: m - centre for i, m in means.items()}
        season = np.array([means.get(int(p), 0.0) for p in phase])
        before, after = float(np.var(resid)), float(np.var(resid - season))
        strength = max(0.0, 1 - after / before) if before > 0 else 0.0
        names = DAY_NAMES if bucket == "day" else MONTH_NAMES
        best = max(means, key=means.get)
        worst = min(means, key=means.get)
        seas = {"kind": "weekday" if bucket == "day" else "month", "strength": _f(strength, 3),
                "pattern": [{"label": names[i], "effect": _f(m, 3)} for i, m in sorted(means.items())],
                "high": names[best], "low": names[worst]}
    expected = trend + season
    r2 = resid - season
    med = float(np.median(r2))
    mad = float(np.median(np.abs(r2 - med)))
    if mad > 0:
        z = 0.6745 * (r2 - med) / mad
    else:
        sd = float(np.std(r2))
        z = (r2 - med) / sd if sd > 0 else np.zeros(n)
    flag = np.abs(z) > 3.5
    series = []
    start_i = max(0, n - 2000)
    for i in range(start_i, n):
        series.append({"t": ts[i].isoformat(), "v": _f(vals[i], 4), "ma": _f(ma[i], 4) if ma[i] is not None else None,
                       "trend": _f(trend[i], 4), "expected": _f(expected[i], 4), "anomaly": bool(flag[i])})
    anomalies = sorted(
        ({"t": ts[i].isoformat(), "value": _f(vals[i], 4), "expected": _f(expected[i], 4), "z": _f(z[i], 2),
          "direction": "high" if z[i] > 0 else "low"} for i in range(n) if flag[i]), key=lambda a: -abs(a["z"] or 0))[:15]
    mean_v = float(vals.mean())
    last, prev = vals[-win:], vals[-2 * win:-win]
    change = (float(last.mean()) - float(prev.mean())) / abs(float(prev.mean())) * 100 if len(prev) == win and float(prev.mean()) != 0 else None
    sig = lr.pvalue < 0.05
    direction = "flat" if not sig else ("up" if lr.slope > 0 else "down")
    per = (lr.slope / abs(mean_v) * 100) if mean_v else None
    sentences = [
        (f"The trend is {direction}: about {lr.slope:+,.2f} per {bucket}"
         + (f" ({per:+.2f}% of the average)" if per is not None else "")
         + f", R² = {lr.rvalue ** 2:.2f}, " + ("a real trend (p < 0.05)." if sig else "not clearly different from flat (p ≥ 0.05)."))
    ]
    if seas and (seas["strength"] or 0) >= 0.1:
        sentences.append(f"There is a repeating {seas['kind']} pattern (strength {seas['strength']:.0%}): {seas['high']} runs highest and {seas['low']} lowest.")
    elif seas:
        sentences.append("No clear repeating pattern was found.")
    if anomalies:
        sentences.append(f"{len(anomalies)} unusual {bucket}(s) stand out; the biggest is {anomalies[0]['t']} ({anomalies[0]['direction']}).")
    if change is not None:
        sentences.append(f"The last {win} {bucket}s average {change:+.1f}% versus the {win} before.")
    fc = []
    effects = {e["label"]: e["effect"] or 0.0 for e in seas["pattern"]} if seas else {}
    if horizon:
        sd = float(np.std(r2, ddof=1)) if n > 2 else 0.0
        tt = ts[-1]
        for j in range(1, horizon + 1):
            tt = _step(tt, bucket)
            lab = (DAY_NAMES[tt.weekday()] if bucket == "day" else MONTH_NAMES[tt.month - 1]) if seas else None
            sea = effects.get(lab, 0.0) if seas else 0.0
            v = lr.intercept + lr.slope * (n - 1 + j) + (sea or 0.0)
            lo_, hi_ = v - 1.96 * sd, v + 1.96 * sd
            if agg in ("sum", "count"):
                v, lo_ = max(0.0, v), max(0.0, lo_)
            fc.append({"t": tt.isoformat(), "v": _f(v, 4), "low": _f(lo_, 4), "high": _f(hi_, 4)})
        if fc:
            sentences.append(f"Projecting the trend{' and repeating pattern' if seas and (seas['strength'] or 0) >= 0.1 else ''} forward {horizon} {bucket}(s) "
                             f"gives about {fc[-1]['v']:,.4g} at the end (95% range {fc[-1]['low']:,.4g} to {fc[-1]['high']:,.4g}). It assumes the past pattern continues.")
    return {
        "available": True, "bucket": bucket, "agg": agg, "value_col": value_col, "date_col": date_col, "filters": fwords,
        "points": n, "filled_gaps": filled, "window": win, "series": series, "forecast": fc,
        "trend": {"slope": _f(lr.slope, 6), "intercept": _f(lr.intercept, 4), "r2": _f(lr.rvalue ** 2, 4), "p": _f(lr.pvalue, 6),
                  "direction": direction, "pct_of_mean": _f(per, 3)},
        "seasonality": seas, "anomalies": anomalies, "recent_change_pct": _f(change, 2), "sentences": sentences,
        "lesson": ("A time series = trend (long-run direction) + seasonality (repeating pattern) + noise. Unusual points are the ones far from "
                   "what trend and season predict (a robust z-score above 3.5). The past pattern is not a promise; for a forecast use the Dashboard's forecast."),
    }


# ------------------------------------------------------------------ regression
MAX_LEVELS = 12


def _design(rows: list[dict], y: str, xn: list[str], xc: list[str]):
    ys, cols, names, kinds = [], [], [], []
    levels: dict[str, list[str]] = {}
    for c in xc:
        cnt: dict[str, int] = {}
        for r in rows:
            if r[c] is not None:
                cnt[str(r[c])] = cnt.get(str(r[c]), 0) + 1
        if len(cnt) > MAX_LEVELS:
            raise DataError(f"'{c}' has {len(cnt)} different values; use a column with at most {MAX_LEVELS}, or filter first.")
        if len(cnt) < 2:
            raise DataError(f"'{c}' has only one value in this selection, so it cannot explain anything.")
        order = sorted(cnt, key=lambda k: (-cnt[k], k))
        levels[c] = order
    keep = [r for r in rows if r[y] is not None and all(r[c] is not None for c in xn + xc)]
    for r in keep:
        ys.append(float(r[y]))
    X = [np.ones(len(keep))]
    names.append("(intercept)")
    kinds.append(("intercept", ""))
    for c in xn:
        X.append(np.array([float(r[c]) for r in keep]))
        names.append(c)
        kinds.append(("num", c))
    for c in xc:
        ref = levels[c][0]
        for lv in levels[c][1:]:
            X.append(np.array([1.0 if str(r[c]) == lv else 0.0 for r in keep]))
            names.append(f"{c} = {lv}")
            kinds.append(("cat", f"{c}|{ref}"))
    return np.column_stack(X), np.array(ys), names, kinds, levels, len(rows) - len(keep)


def regression(source: str, y: str, x_numeric: list[str] | None = None, x_categorical: list[str] | None = None,
               filters: list[dict] | None = None, mode: str = "and", predict: dict | None = None) -> dict:
    ident, cols = resolve(source)
    xn, xc = list(dict.fromkeys(x_numeric or [])), list(dict.fromkeys(x_categorical or []))
    _need(cols, y, ("number",), "column to explain")
    for c in xn:
        _need(cols, c, ("number",), "numeric input")
    for c in xc:
        _need(cols, c, ("text", "bool"), "category input")
    if y in xn:
        raise DataError("The column you explain can't also be an input.")
    if not xn and not xc:
        raise DataError("Pick at least one input column.")
    if len(xn) + len(xc) > 8:
        raise DataError("Use at most 8 input columns.")
    sel = list(dict.fromkeys([y] + xn + xc))
    w, params, fwords = where_clause(cols, filters, mode)
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    rows = _rows(f"SELECT {', '.join(q(c) for c in sel)} FROM {q(ident)}{w} LIMIT {MAX_ROWS}", params)
    X, Y, names, kinds, levels, dropped = _design(rows, y, xn, xc)
    n, p = X.shape
    if n < p + 10:
        raise DataError(f"{n} usable rows is too few for {p} parameters; need at least {p + 10}. Remove inputs or loosen the filters.")
    if np.linalg.matrix_rank(X) < p:
        raise DataError("Two or more inputs carry the same information (perfect overlap, such as a total and its parts). Remove one.")
    if float(np.std(Y)) == 0:
        raise DataError(f"'{y}' never changes in this selection, so there is nothing to explain.")
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ Y
    fitted = X @ beta
    resid = Y - fitted
    dof = n - p
    rss = float(resid @ resid)
    tss = float(((Y - Y.mean()) ** 2).sum())
    sigma2 = rss / dof
    se = np.sqrt(np.maximum(np.diag(XtX_inv) * sigma2, 0))
    t = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    pv = 2 * sps.t.sf(np.abs(t), dof)
    tcrit = float(sps.t.ppf(0.975, dof))
    r2 = 1 - rss / tss
    adj = 1 - (1 - r2) * (n - 1) / dof
    fstat = ((tss - rss) / (p - 1)) / sigma2 if p > 1 else None
    fp = float(sps.f.sf(fstat, p - 1, dof)) if fstat is not None else None
    sdy = float(np.std(Y, ddof=1))
    coefs, sentences = [], []
    for i, nm in enumerate(names):
        kind, info = kinds[i]
        std = None
        if kind == "num" and sdy > 0:
            std = beta[i] * float(np.std(X[:, i], ddof=1)) / sdy
        row = {"term": nm, "coef": _f(beta[i], 6), "se": _f(se[i], 6), "t": _f(t[i], 3), "p": _f(pv[i], 6),
               "ci_low": _f(beta[i] - tcrit * se[i], 6), "ci_high": _f(beta[i] + tcrit * se[i], 6), "std_coef": _f(std, 3),
               "significant": bool(pv[i] < 0.05) if kind != "intercept" else None}
        coefs.append(row)
        if kind == "num":
            sig = "a reliable link" if pv[i] < 0.05 else "not clearly different from zero"
            sentences.append(f"Each +1 in {nm} goes with {beta[i]:+,.4g} in {y}, other inputs held fixed ({sig}, p = {pv[i]:.3g}).")
        elif kind == "cat":
            col, ref = info.split("|", 1)
            sig = "a reliable difference" if pv[i] < 0.05 else "not clearly different"
            sentences.append(f"{nm} vs {col} = {ref}: {beta[i]:+,.4g} in {y} ({sig}, p = {pv[i]:.3g}).")
    # multicollinearity (VIF on numeric inputs)
    vif = []
    num_idx = [i for i, (k, _) in enumerate(kinds) if k == "num"]
    if len(num_idx) >= 2:
        for i in num_idx:
            others = [j for j in range(1, p) if j != i]
            Xo = X[:, [0] + others]
            b = np.linalg.lstsq(Xo, X[:, i], rcond=None)[0]
            res = X[:, i] - Xo @ b
            sst = float(((X[:, i] - X[:, i].mean()) ** 2).sum())
            r2i = 1 - float(res @ res) / sst if sst > 0 else 0.0
            vif.append({"term": names[i], "vif": _f(1 / (1 - r2i) if r2i < 0.999999 else float("inf"), 2)})
    warnings = []
    if any((v["vif"] or 0) > 5 for v in vif) or any(v["vif"] is None for v in vif):
        warnings.append("Some numeric inputs overlap strongly (VIF above 5), so their individual coefficients are unreliable even if the model fits well.")
    if len(rows) >= MAX_ROWS and total > MAX_ROWS:
        warnings.append(f"Used the first {MAX_ROWS:,} of {total:,} rows.")
    if dropped:
        warnings.append(f"{dropped:,} rows with an empty value in one of the chosen columns were left out.")
    if n < 30:
        warnings.append(f"Only {n} rows; treat the numbers as rough.")
    het = float(np.corrcoef(np.abs(resid), fitted)[0, 1]) if np.std(fitted) > 0 and np.std(np.abs(resid)) > 0 else 0.0
    if abs(het) > 0.3:
        warnings.append("Errors grow with the predicted value (a 'fan' shape), so the confidence ranges are optimistic.")
    # honest check: fit on 80%, score on the other 20%
    holdout = None
    if n >= 50:
        rng = np.random.default_rng(7)
        idx = rng.permutation(n)
        cut = int(n * 0.8)
        tr, te = idx[:cut], idx[cut:]
        try:
            bt = np.linalg.lstsq(X[tr], Y[tr], rcond=None)[0]
            pr = X[te] @ bt
            sst_te = float(((Y[te] - Y[te].mean()) ** 2).sum())
            holdout = {"r2": _f(1 - float(((Y[te] - pr) ** 2).sum()) / sst_te, 4) if sst_te > 0 else None, "rows": int(len(te))}
            if holdout["r2"] is not None and r2 - holdout["r2"] > 0.1:
                warnings.append("It scores clearly worse on rows it didn't learn from than on the rows it did: it may be over-fitting.")
        except np.linalg.LinAlgError:
            pass
    # chart data
    sample = np.random.default_rng(3).permutation(n)[:400]
    chart: dict
    if len(xn) == 1 and not xc:
        xi = names.index(xn[0])
        xs = X[:, xi]
        chart = {"kind": "scatter", "x": xn[0], "y": y, "points": [{"x": _f(xs[i], 4), "y": _f(Y[i], 4)} for i in sample],
                 "line": [{"x": _f(xs.min(), 4), "y": _f(beta[0] + beta[xi] * xs.min(), 4)}, {"x": _f(xs.max(), 4), "y": _f(beta[0] + beta[xi] * xs.max(), 4)}]}
    else:
        lo, hi = float(min(Y.min(), fitted.min())), float(max(Y.max(), fitted.max()))
        chart = {"kind": "fit", "x": "predicted", "y": "actual", "points": [{"x": _f(fitted[i], 4), "y": _f(Y[i], 4)} for i in sample],
                 "line": [{"x": _f(lo, 4), "y": _f(lo, 4)}, {"x": _f(hi, 4), "y": _f(hi, 4)}]}
    resid_pts = [{"x": _f(fitted[i], 4), "y": _f(resid[i], 4)} for i in sample]
    # what-if
    what_if = None
    if predict:
        x0 = [1.0]
        used = []
        for c in xn:
            if c not in predict or predict[c] in (None, ""):
                raise DataError(f"For a what-if, give a value for '{c}'.")
            x0.append(float(_typed("number", predict[c])))
            used.append(f"{c}={predict[c]}")
        for c in xc:
            val = str(predict.get(c, levels[c][0]))
            if val not in levels[c]:
                raise DataError(f"'{val}' isn't a value of {c}. Choose one of: {', '.join(levels[c])}.")
            x0 += [1.0 if val == lv else 0.0 for lv in levels[c][1:]]
            used.append(f"{c}={val}")
        x0a = np.array(x0)
        pred = float(x0a @ beta)
        hw = tcrit * math.sqrt(sigma2 * (1 + float(x0a @ XtX_inv @ x0a)))
        what_if = {"inputs": used, "prediction": _f(pred, 4), "low": _f(pred - hw, 4), "high": _f(pred + hw, 4)}
    sentences.insert(0, f"These inputs explain {r2:.0%} of the ups and downs in {y} (adjusted {adj:.0%}); typical miss is about {math.sqrt(sigma2):,.4g}.")
    return {
        "y": y, "x_numeric": xn, "x_categorical": xc, "filters": fwords, "n": n, "params": p, "dof": dof,
        "y_mean": _f(float(Y.mean()), 6), "x_ranges": {c: [_f(float(X[:, names.index(c)].min()), 6), _f(float(X[:, names.index(c)].max()), 6)] for c in xn},
        "r2": _f(r2, 4), "adj_r2": _f(adj, 4), "rmse": _f(math.sqrt(rss / n), 4), "mae": _f(float(np.abs(resid).mean()), 4),
        "f_stat": _f(fstat, 3), "f_p": _f(fp, 8), "coefficients": coefs, "vif": vif, "holdout": holdout,
        "reference": {c: levels[c][0] for c in xc}, "x_means": {c: _f(float(np.mean(X[:, names.index(c)])), 6) for c in xn}, "chart": chart, "residuals": resid_pts, "what_if": what_if,
        "warnings": warnings, "sentences": sentences,
        "lesson": ("Linear regression fits y = intercept + b1*x1 + b2*x2 ... by least squares. A coefficient is the average change in y for +1 in that "
                   "input with the others held fixed. R² is the share of variation explained. It shows association, not cause: a link can come from "
                   "something you didn't measure."),
    }


# ------------------------------------------------------------------ descriptive: what happened
def describe(source: str, filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    w, params, fwords = where_clause(cols, filters, mode)
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    if total == 0:
        raise DataError("No rows match. Loosen the filters.")
    nums, texts, dates = [], [], []
    for c, k in cols.items():
        if c == "fact_id":
            continue
        if k == "number":
            r = _rows(f"SELECT COUNT({q(c)}) AS n, AVG({q(c)}) AS mean, MEDIAN({q(c)}) AS median, STDDEV_SAMP({q(c)}) AS sd, MIN({q(c)}) AS lo, "
                      f"QUANTILE_CONT({q(c)}, 0.25) AS q1, QUANTILE_CONT({q(c)}, 0.75) AS q3, MAX({q(c)}) AS hi, SUM({q(c)}) AS total "
                      f"FROM {q(ident)}{w}", params)[0]
            sd, mean = r["sd"], r["mean"]
            nums.append({"column": c, "count": int(r["n"]), "missing": total - int(r["n"]), "mean": _f(mean, 4), "median": _f(r["median"], 4),
                         "sd": _f(sd, 4), "min": _f(r["lo"], 4), "q1": _f(r["q1"], 4), "q3": _f(r["q3"], 4), "max": _f(r["hi"], 4), "sum": _f(r["total"], 2),
                         "skew_note": ("mean is well above the median: a few large values pull it up" if mean is not None and r["median"] is not None and sd and (mean - r["median"]) > 0.25 * sd
                                       else "mean is well below the median: a few small values pull it down" if mean is not None and r["median"] is not None and sd and (r["median"] - mean) > 0.25 * sd else "")})
        elif k in ("text", "bool"):
            dist = int(_rows(f"SELECT COUNT(DISTINCT {q(c)}) AS n FROM {q(ident)}{w}", params)[0]["n"])
            top = _rows(f"SELECT CAST({q(c)} AS VARCHAR) AS v, COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(c)} IS NOT NULL GROUP BY 1 ORDER BY n DESC, v LIMIT 5", params)
            miss = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(c)} IS NULL", params)[0]["n"])
            texts.append({"column": c, "distinct": dist, "missing": miss, "top": [{"value": r["v"], "n": int(r["n"]), "pct": _f(int(r["n"]) / total * 100, 1)} for r in top]})
        elif k == "date":
            r = _rows(f"SELECT MIN({q(c)}) AS lo, MAX({q(c)}) AS hi, COUNT({q(c)}) AS n FROM {q(ident)}{w}", params)[0]
            dates.append({"column": c, "from": str(r["lo"])[:10] if r["lo"] else None, "to": str(r["hi"])[:10] if r["hi"] else None, "missing": total - int(r["n"])})
    sentences = [f"{total:,} rows, {len(nums)} number column(s), {len(texts)} category column(s), {len(dates)} date column(s)."]
    for d in dates[:1]:
        if d["from"]:
            sentences.append(f"{d['column']} runs from {d['from']} to {d['to']}.")
    return {"rows": total, "filters": fwords, "numbers": nums, "categories": texts, "dates": dates, "sentences": sentences,
            "lesson": "Descriptive analytics answers 'what happened?' with counts, averages, ranges and top values. Compare mean and median: a big gap means a few extreme values."}


# ------------------------------------------------------------------ diagnostic: why
def diagnose(source: str, y: str, group_col: str | None = None, date_col: str | None = None, split: str | None = None,
             filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, y, ("number",), "metric to explain")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(y)} IS NOT NULL"])
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    if total < 10:
        raise DataError("Need at least 10 rows to look for drivers.")
    out: dict = {"y": y, "rows": total, "filters": fwords, "sentences": [], "drivers": [], "change": None}
    # which columns move with y
    for c, k in cols.items():
        if c in (y, "fact_id"):
            continue
        if k == "number":
            r = _rows(f"SELECT CORR({q(c)}, {q(y)}) AS r, COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(c)} IS NOT NULL", params)[0]
            if r["r"] is not None and math.isfinite(r["r"]):
                rr = float(r["r"])
                out["drivers"].append({"column": c, "kind": "number", "strength": _f(abs(rr), 3), "detail": f"correlation {rr:+.2f}", "n": int(r["n"])})
        elif k in ("text", "bool"):
            d = int(_rows(f"SELECT COUNT(DISTINCT {q(c)}) AS n FROM {q(ident)}{w}", params)[0]["n"])
            if 2 <= d <= 30:
                r = _rows(
                    f"WITH g AS (SELECT {q(c)} AS k, COUNT(*) AS n, AVG({q(y)}) AS m FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(c)} IS NOT NULL GROUP BY 1), "
                    f"t AS (SELECT AVG({q(y)}) AS m, VAR_POP({q(y)}) AS v, COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(c)} IS NOT NULL) "
                    f"SELECT SUM(g.n * (g.m - t.m) * (g.m - t.m)) / NULLIF(MAX(t.v) * MAX(t.n), 0) AS eta2 FROM g, t", params + params)[0]
                if r["eta2"] is not None and math.isfinite(r["eta2"]):
                    out["drivers"].append({"column": c, "kind": "category", "strength": _f(max(0.0, min(1.0, float(r["eta2"]))), 3),
                                           "detail": f"{d} groups explain {max(0.0, float(r['eta2'])):.0%} of the variation", "n": total})
    out["drivers"].sort(key=lambda d: -(d["strength"] or 0))
    out["drivers"] = out["drivers"][:12]
    if out["drivers"]:
        top = out["drivers"][0]
        out["sentences"].append(f"Most associated with {y}: '{top['column']}' ({top['detail']}). Association is a lead to investigate, not proof of cause.")
    # what changed between two periods, and where
    if date_col:
        _need(cols, date_col, ("date",), "date column")
        rng = _rows(f"SELECT MIN({q(date_col)}) AS lo, MAX({q(date_col)}) AS hi FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(date_col)} IS NOT NULL", params)[0]
        if rng["lo"] and rng["hi"] and rng["lo"] != rng["hi"]:
            lo, hi = rng["lo"], rng["hi"]
            lo = lo.date() if isinstance(lo, datetime) else lo
            hi = hi.date() if isinstance(hi, datetime) else hi
            cut = _typed("date", split) if split else lo + (hi - lo) / 2
            if not (lo < cut <= hi):
                raise DataError(f"The split date must fall between {lo} and {hi}.")
            gsel = f"CAST({q(group_col)} AS VARCHAR)" if group_col else "'All rows'"
            if group_col:
                _need(cols, group_col, ("text", "bool"), "group column")
            rows = _rows(
                f"SELECT {gsel} AS g, SUM(CASE WHEN {q(date_col)} < ? THEN {q(y)} ELSE 0 END) AS a, SUM(CASE WHEN {q(date_col)} >= ? THEN {q(y)} ELSE 0 END) AS b, "
                f"SUM(CASE WHEN {q(date_col)} < ? THEN 1 ELSE 0 END) AS na, SUM(CASE WHEN {q(date_col)} >= ? THEN 1 ELSE 0 END) AS nb "
                f"FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(date_col)} IS NOT NULL GROUP BY 1", [cut, cut, cut, cut] + params)
            ta, tb = sum(float(r["a"] or 0) for r in rows), sum(float(r["b"] or 0) for r in rows)
            parts = sorted(({"group": r["g"], "before": _f(r["a"], 2), "after": _f(r["b"], 2), "change": _f(float(r["b"] or 0) - float(r["a"] or 0), 2),
                             "share_of_change": _f((float(r["b"] or 0) - float(r["a"] or 0)) / (tb - ta) * 100, 1) if tb != ta else None,
                             "rows_before": int(r["na"] or 0), "rows_after": int(r["nb"] or 0)} for r in rows), key=lambda p: -abs(p["change"] or 0))[:20]
            out["change"] = {"split": cut.isoformat(), "from": lo.isoformat(), "to": hi.isoformat(), "total_before": _f(ta, 2), "total_after": _f(tb, 2),
                             "change": _f(tb - ta, 2), "change_pct": _f((tb - ta) / abs(ta) * 100, 1) if ta else None, "group_col": group_col, "parts": parts}
            line = f"Total {y}: {ta:,.2f} before {cut} and {tb:,.2f} from then on ({tb - ta:+,.2f}"
            line += f", {(tb - ta) / abs(ta):+.1%})." if ta else ")."
            out["sentences"].append(line)
            if group_col and parts and parts[0]["change"]:
                out["sentences"].append(f"Biggest mover: '{parts[0]['group']}' ({parts[0]['change']:+,.2f}). Different period lengths or row counts can drive the gap, so check rows before and after.")
            if (cut - lo).days and abs((cut - lo).days - (hi - cut).days) > 1:
                out["sentences"].append("The two periods are different lengths, so compare rates, not totals.")
    out["lesson"] = ("Diagnostic analytics asks 'why did it happen?'. Two steps: (1) find what moves with the metric (drivers), (2) split the change between "
                     "two periods by group to see where it came from. Then test the lead with Regression or Probability.")
    return out


# ------------------------------------------------------------------ prescriptive: what to do
def opportunities(source: str, value_col: str, group_col: str, higher_is_better: bool = True, benchmark: str = "median",
                  min_rows: int = 5, filters: list[dict] | None = None, mode: str = "and", levers_y: str | None = None,
                  levers: list[str] | None = None) -> dict:
    ident, cols = resolve(source)
    _need(cols, value_col, ("number",), "metric")
    _need(cols, group_col, ("text", "bool"), "group column")
    if benchmark not in ("median", "top_quartile", "best"):
        raise DataError("Benchmark must be median, top_quartile or best.")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(value_col)} IS NOT NULL", f"{q(group_col)} IS NOT NULL"])
    rows = _rows(f"SELECT CAST({q(group_col)} AS VARCHAR) AS g, COUNT(*) AS n, AVG({q(value_col)}) AS m FROM {q(ident)}{w} GROUP BY 1", params)
    rows = [r for r in rows if int(r["n"]) >= max(1, min_rows)]
    if len(rows) < 3:
        raise DataError(f"Need at least 3 groups with {min_rows}+ rows each; found {len(rows)}. Lower the minimum rows or pick another group column.")
    vals = [float(r["m"]) for r in rows]
    if benchmark == "best":
        bench = max(vals) if higher_is_better else min(vals)
    elif benchmark == "median":
        bench = float(np.median(vals))
    else:  # top quartile: the value only a quarter of groups beat
        bench = float(np.percentile(vals, 75 if higher_is_better else 25))
    acts = []
    for r in rows:
        m, n = float(r["m"]), int(r["n"])
        gap = (bench - m) if higher_is_better else (m - bench)
        if gap > 0:
            acts.append({"group": r["g"], "rows": n, "average": _f(m, 4), "benchmark": _f(bench, 4), "gap_per_row": _f(gap, 4),
                         "estimated_gain": _f(gap * n, 2), "action": f"Study what '{r['g']}' does differently from the better groups and close part of the {gap:,.4g}-per-row gap."})
    acts.sort(key=lambda a: -(a["estimated_gain"] or 0))
    best = max(rows, key=lambda r: float(r["m"]) if higher_is_better else -float(r["m"]))
    out: dict = {"metric": value_col, "group_col": group_col, "higher_is_better": higher_is_better, "benchmark_kind": benchmark, "benchmark": _f(bench, 4),
                 "groups": len(rows), "filters": fwords, "opportunities": acts[:15], "best_group": best["g"],
                 "sentences": [], "levers": None}
    if acts:
        tot = sum(a["estimated_gain"] or 0 for a in acts)
        out["sentences"].append(f"If every group below the {benchmark.replace('_', ' ')} ({bench:,.4g}) reached it, {value_col} would improve by about {tot:,.2f} in total. "
                                f"Largest single opportunity: '{acts[0]['group']}' (about {acts[0]['estimated_gain']:,.2f}).")
    else:
        out["sentences"].append("Every group is already at or past the benchmark.")
    out["sentences"].append("These are sized from past averages and assume other groups' practices transfer. Treat each as a thing to test, not a promise.")
    # levers from a regression
    if levers_y and levers:
        reg = regression(source, levers_y, x_numeric=[c for c in levers if cols.get(c) == "number"], filters=filters, mode=mode)
        ls = []
        for c in reg["coefficients"]:
            mean = reg["x_means"].get(c["term"])
            if mean is None or c["coef"] is None:
                continue
            ls.append({"lever": c["term"], "coef": c["coef"], "effect_of_plus_10pct": _f(c["coef"] * 0.10 * mean, 4), "reliable": bool(c["significant"]),
                       "std_coef": c["std_coef"]})
        ls.sort(key=lambda x: -abs(x["std_coef"] or 0))
        out["levers"] = {"y": levers_y, "r2": reg["r2"], "items": ls,
                         "note": f"Estimated change in {levers_y} from a 10% rise in each input, others fixed. A link is not a guarantee that pulling the lever works."}
    out["lesson"] = ("Prescriptive analytics answers 'what should we do?'. Here: rank groups by the gap to a benchmark times their volume (where effort pays most), "
                     "and rank levers by how strongly they move the result. It suggests where to test, using the past; it can't promise outcomes.")
    return out


# ------------------------------------------------------------------ quantitative future: ARIMA-style forecast
def _fit_ar(w: np.ndarray, p: int):
    """OLS fit of w_t = c + sum phi_i w_{t-i} + e. Returns (const, phi, sigma2, aic, n_used)."""
    n = len(w)
    rows = n - p
    X = np.column_stack([np.ones(rows)] + [w[p - i - 1:n - i - 1] for i in range(p)]) if p else np.ones((rows, 1))
    y = w[p:]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    rss = float(res @ res)
    sigma2 = rss / rows
    aic = rows * math.log(max(sigma2, 1e-12)) + 2 * (p + 2)
    return float(beta[0]), beta[1:], sigma2, aic, rows


def _arima_forecast(y: np.ndarray, d: int, h: int, max_p: int = 7):
    """ARIMA(p, d, 0): AR terms on the (differenced) series, p picked by AIC. Returns the fit and h-step forecasts with 95% bands."""
    w = np.diff(y) if d else y.copy()
    best = None
    for p in range(0, max_p + 1):
        if len(w) - p < max(12, 3 * (p + 2)):
            break
        c, phi, s2, aic, _ = _fit_ar(w, p)
        if best is None or aic < best[0] - 1e-9:
            best = (aic, p, c, phi, s2)
    if best is None:
        raise DataError("Not enough history for an ARIMA-style fit (need about 15 points).")
    aic, p, c, phi, s2 = best
    hist = list(w[-p:]) if p else []
    wf = []
    for _ in range(h):
        nxt = c + sum(phi[i] * hist[-1 - i] for i in range(p)) if p else c
        wf.append(nxt)
        hist.append(nxt)
    fc = np.cumsum(wf) + y[-1] if d else np.array(wf)
    # forecast-error variance from the psi weights of the full AR polynomial (1 - phi(B)) (1 - B)^d
    poly = np.zeros(p + d + 1)
    poly[0] = 1.0
    for i in range(p):
        poly[i + 1] -= phi[i]
    if d:
        poly = np.convolve(poly, [1.0, -1.0])
    ar = -poly[1:]
    psi = [1.0]
    for j in range(1, h):
        psi.append(sum(ar[i] * psi[j - 1 - i] for i in range(min(j, len(ar)))))
    var = s2 * np.cumsum(np.square(psi))
    half = 1.96 * np.sqrt(var)
    return {"p": p, "d": d, "c": c, "phi": [float(x) for x in phi], "sigma2": s2, "aic": aic}, fc, fc - half, fc + half


def arima_forecast(source: str, date_col: str, value_col: str | None, agg: str = "sum", bucket: str = "day", horizon: int = 14,
                   d: int = 1, filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, date_col, ("date",), "date column")
    if agg not in AGGS or bucket not in BUCKETS:
        raise DataError("Pick a valid measure and period.")
    if d not in (0, 1):
        raise DataError("Differencing must be 0 or 1.")
    horizon = max(1, min(int(horizon), 60))
    if agg != "count":
        _need(cols, value_col, ("number",), "value column")
        expr = f"{AGGS[agg]}({q(value_col)})"
    else:
        expr = "COUNT(*)"
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(date_col)} IS NOT NULL"])
    loaded = _load_series(ident, date_col, expr, agg, bucket, w, params, min_points=20)
    if isinstance(loaded, str):
        return {"available": False, "reason": loaded.replace("at least 20", "at least 20 (ARIMA needs more history than a trend line)"), "filters": fwords}
    ts, y, filled = loaded
    n = len(y)
    order, fc, lo, hi = _arima_forecast(y, d, horizon)
    if agg in ("sum", "count"):
        fc, lo, hi = np.maximum(fc, 0), np.maximum(lo, 0), np.maximum(hi, 0)
    # honest check: fit on all but the last k points, forecast them, compare with "same as last value"
    k = max(3, min(14, n // 5))
    backtest = None
    try:
        _, bf, _, _ = _arima_forecast(y[:-k], d, k)
        actual = y[-k:]
        mae = float(np.mean(np.abs(actual - bf)))
        naive = float(np.mean(np.abs(actual - y[-k - 1])))
        nz = actual != 0
        backtest = {"points": k, "mae": _f(mae, 4), "naive_mae": _f(naive, 4), "better_than_naive": bool(mae < naive),
                    "mape": _f(float(np.mean(np.abs((actual[nz] - bf[nz]) / actual[nz])) * 100), 2) if nz.any() else None}
    except DataError:
        pass
    tt, fcl = ts[-1], []
    for j in range(horizon):
        tt = _step(tt, bucket)
        fcl.append({"t": tt.isoformat(), "v": _f(fc[j], 4), "low": _f(lo[j], 4), "high": _f(hi[j], 4)})
    series = [{"t": ts[i].isoformat(), "v": _f(y[i], 4)} for i in range(max(0, n - 1500), n)]
    name = f"ARIMA({order['p']},{order['d']},0)"
    sentences = [f"Best fit by AIC: {name}. It predicts each change from the previous {order['p'] or 'no'} change(s)" + (" (differenced once, so it models change rather than level)." if d else ".") if order["p"] else
                 f"Best fit by AIC: {name}: no useful memory beyond the average " + ("change (a random walk with drift)." if d else "level.")]
    if backtest:
        sentences.append(f"Test on the last {backtest['points']} {bucket}s it hadn't seen: average miss {backtest['mae']:,.4g} vs {backtest['naive_mae']:,.4g} for 'same as last time'"
                         + (" (better than the simple guess)." if backtest["better_than_naive"] else " (NOT better than the simple guess, so don't lean on it)."))
    sentences.append(f"Forecast {horizon} {bucket}(s) out: about {fcl[-1]['v']:,.4g} (95% range {fcl[-1]['low']:,.4g} to {fcl[-1]['high']:,.4g}). The range widens with distance.")
    return {"available": True, "method": "arima", "name": name, "order": order, "bucket": bucket, "agg": agg, "points": n, "filled_gaps": filled, "filters": fwords,
            "series": series, "forecast": fcl, "backtest": backtest, "sentences": sentences,
            "note": "This is ARIMA(p, d, 0): the autoregressive and differencing parts, fitted by least squares. Full ARIMA with moving-average terms and seasonal parts lives in statsmodels (see the Python lab).",
            "lesson": ("ARIMA forecasts from the series' own past: AR = each value depends on recent values, I = difference the series to remove drift, MA = depends on recent errors "
                       "(not included here). Always compare with the naive 'same as last time' guess; a fancy model that can't beat it is not adding anything.")}


# ------------------------------------------------------------------ quantitative past: business metrics
def business_metrics(source: str, date_col: str, revenue_col: str, cost_col: str | None = None, entity_col: str | None = None,
                     cash: float | None = None, filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, date_col, ("date",), "date column")
    _need(cols, revenue_col, ("number",), "revenue column")
    if cost_col:
        _need(cols, cost_col, ("number",), "cost column")
    if entity_col:
        _need(cols, entity_col, ("text", "bool", "number"), "customer/entity column")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(date_col)} IS NOT NULL"])
    cost_sql = f"COALESCE(SUM({q(cost_col)}), 0)" if cost_col else "0"
    rows = _rows(f"SELECT CAST(DATE_TRUNC('month', {q(date_col)}) AS DATE) AS m, COALESCE(SUM({q(revenue_col)}), 0) AS rev, {cost_sql} AS cost, COUNT(*) AS n, "
                 f"MIN({q(date_col)}) AS d0, MAX({q(date_col)}) AS d1 FROM {q(ident)}{w} GROUP BY 1 ORDER BY 1", params)
    if len(rows) < 2:
        raise DataError("Need at least 2 months of data for month-over-month metrics.")
    if len(rows) > 600:
        raise DataError("Too many months to show; filter the dates.")
    last_row = rows[-1]
    last_d1 = last_row["d1"].date() if isinstance(last_row["d1"], datetime) else last_row["d1"]
    nxt = _step(last_row["m"], "month")
    partial = last_d1 < nxt - timedelta(days=1)
    first_d0 = rows[0]["d0"].date() if isinstance(rows[0]["d0"], datetime) else rows[0]["d0"]
    lead_partial = first_d0 > rows[0]["m"]
    entities: dict = {}
    churn_note = None
    if entity_col:
        pairs = _rows(f"SELECT CAST(DATE_TRUNC('month', {q(date_col)}) AS DATE) AS m, CAST({q(entity_col)} AS VARCHAR) AS e FROM {q(ident)}{w}"
                      f"{' AND' if w else ' WHERE'} {q(entity_col)} IS NOT NULL GROUP BY 1, 2", params)
        if len(pairs) > 2_000_000:
            raise DataError("Too many customer-month pairs; filter the data first.")
        for r in pairs:
            entities.setdefault(r["m"], set()).add(r["e"])
    out_rows, seen, prev_set, prev_rev = [], set(), None, None
    for r in rows:
        rev, cost = float(r["rev"]), float(r["cost"])
        gp = rev - cost
        row = {"month": r["m"].isoformat()[:7], "revenue": _f(rev, 2), "cost": _f(cost, 2) if cost_col else None, "profit": _f(gp, 2) if cost_col else None,
               "margin_pct": _f(gp / rev * 100, 2) if cost_col and rev else None, "growth_pct": _f((rev - prev_rev) / abs(prev_rev) * 100, 2) if prev_rev else None,
               "net_burn": _f(max(0.0, -gp), 2) if cost_col else None, "rows": int(r["n"])}
        if entity_col:
            cur = entities.get(r["m"], set())
            new = len(cur - seen)
            lost = len(prev_set - cur) if prev_set is not None else None
            row.update({"active": len(cur), "new": new, "lost": lost,
                        "churn_pct": _f(lost / len(prev_set) * 100, 2) if prev_set else None})
            seen |= cur
            prev_set = cur
        prev_rev = rev
        out_rows.append(row)
    done = out_rows[:-1] if partial and len(out_rows) > 2 else out_rows
    head = done[-1]
    mrr = head["revenue"]
    recent = [r for r in done[-3:] if r["net_burn"] is not None]
    avg_burn = sum(r["net_burn"] for r in recent) / len(recent) if recent else None
    runway = None
    if cash is not None and avg_burn is not None:
        runway = None if avg_burn <= 0 else _f(cash / avg_burn, 1)
    revs = [r["revenue"] for r in done if r["revenue"]]
    cmgr = _f(((revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1) * 100, 2) if len(revs) >= 2 and revs[0] > 0 and revs[-1] > 0 else None
    churns = [r["churn_pct"] for r in done if r.get("churn_pct") is not None]
    tot_rev = sum(r["revenue"] or 0 for r in out_rows)
    tot_cost = sum(r["cost"] or 0 for r in out_rows) if cost_col else None
    headline = {"latest_month": head["month"], "mrr": mrr, "arr": _f(mrr * 12, 2) if mrr is not None else None, "growth_pct": head["growth_pct"], "margin_pct": head["margin_pct"],
                "avg_net_burn_3m": _f(avg_burn, 2) if avg_burn is not None else None, "runway_months": runway, "cmgr_pct": cmgr,
                "avg_churn_pct": _f(sum(churns) / len(churns), 2) if churns else None,
                "overall_margin_pct": _f((tot_rev - tot_cost) / tot_rev * 100, 2) if tot_cost is not None and tot_rev else None}
    sentences = [f"Latest full month ({head['month']}): revenue {mrr:,.2f}" + (f", margin {head['margin_pct']}%" if head["margin_pct"] is not None else "") + "."]
    if headline["cmgr_pct"] is not None:
        sentences.append(f"Revenue grew about {cmgr}% a month on average over {len(revs)} months.")
    if cost_col:
        if avg_burn and avg_burn > 0:
            sentences.append(f"Spending exceeded revenue: net burn about {avg_burn:,.2f} a month over the last {len(recent)} months."
                             + (f" With {cash:,.0f} in cash that is about {runway} months of runway." if runway else " Enter your cash balance to see runway."))
        else:
            sentences.append("Revenue covered cost in the recent months, so there is no net burn.")
    if churns:
        sentences.append(f"On average {headline['avg_churn_pct']}% of the previous month's customers did not come back the next month.")
    notes = ["'MRR' here means revenue in the month. True MRR counts only recurring subscription revenue; if your file mixes one-off sales, it will overstate.",
             "Churn here = customers active last month and absent this month. In non-subscription data, a skipped month is not necessarily a cancellation."]
    if partial:
        notes.append(f"{last_row['m'].isoformat()[:7]} is incomplete (data ends {last_d1}), so headline numbers use the month before.")
    if lead_partial:
        notes.append(f"{rows[0]['m'].isoformat()[:7]} starts on {first_d0}, so its first-month growth/churn figures are understated.")
    return {"date_col": date_col, "months": out_rows, "headline": headline, "partial_last_month": partial, "filters": fwords, "sentences": sentences, "notes": notes,
            "lesson": ("Quantitative past analysis crunches what the numbers already say: margin = profit / revenue, growth = change from last month, burn = spending above revenue, "
                       "runway = cash / burn, churn = customers lost / customers at the start. Sum the parts first, then divide; never average percentages.")}
