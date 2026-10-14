"""Data Analyst tools: a guided question builder, a pivot builder, A/B and survey statistics, and a saved analysis notebook.

The query builder writes plain SQL from your choices (never from free text), shows it, runs it read-only, and warns about the classic mistakes (averaging a ratio,
summing a count of distinct things). Everything runs on a dashboard or table you already loaded. Statistics are textbook formulas you can check by hand; a p-value is
not the chance the change is real, and the notes say so."""
from __future__ import annotations

import html
import json
import math
import re
from datetime import date, datetime

from app.services import biz_models, state, workspaces
from app.services.db import fetch_all, get_cursor

METRICS = {"count": "COUNT(*)", "sum": "SUM({c})", "avg": "AVG({c})", "min": "MIN({c})", "max": "MAX({c})", "median": "MEDIAN({c})", "count_distinct": "COUNT(DISTINCT {c})", "ratio": "SUM({c}) / NULLIF(SUM({d}), 0)"}
OPS = {"=": "=", "!=": "<>", ">": ">", ">=": ">=", "<": "<", "<=": "<=", "contains": "ILIKE", "is_null": "IS NULL", "not_null": "IS NOT NULL"}
RATIOISH = re.compile(r"(rate|pct|percent|ratio|margin|share|avg|average|per_)", re.I)
GRAINS = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}


class ToolError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _table(source: str) -> str:
    try:
        return biz_models._table_for(source)[0]
    except biz_models.ModelError as e:
        raise ToolError(str(e), getattr(e, "status", 400)) from None


def columns(source: str) -> list[dict]:
    t = _table(source)
    with get_cursor() as cur:
        rows = fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_name = ? AND table_schema = 'main' ORDER BY ordinal_position", [t])
    return rows


def _kind(typ: str) -> str:
    t = typ.upper()
    return "number" if any(x in t for x in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "REAL", "HUGEINT")) else "date" if any(x in t for x in ("DATE", "TIMESTAMP")) else "text"


def _q(name: str, cols: dict[str, str]) -> str:
    if name not in cols:
        raise ToolError(f"There is no column called '{name}'.")
    return '"' + name.replace('"', '""') + '"'


def run_query(source: str, metric: str, column: str | None = None, denominator: str | None = None, group_by: list[str] | None = None, grain: str | None = None,
              filters: list[dict] | None = None, order: str = "desc", limit: int = 50) -> dict:
    t = _table(source)
    cs = {c["name"]: _kind(c["type"]) for c in columns(source)}
    if metric not in METRICS:
        raise ToolError("metric must be one of: " + ", ".join(METRICS) + ".")
    notes: list[str] = []
    if metric == "count":
        expr = METRICS["count"]
    else:
        if not column:
            raise ToolError(f"{metric} needs a column.")
        qc = _q(column, cs)
        if metric in ("sum", "avg", "median", "ratio") and cs[column] != "number":
            raise ToolError(f"{metric} needs a number column, and '{column}' is {cs[column]}.")
        if metric == "ratio":
            if not denominator:
                raise ToolError("ratio needs a denominator column.")
            expr = METRICS["ratio"].format(c=qc, d=_q(denominator, cs))
            notes.append("Ratio is total of the top divided by total of the bottom, which is the correct overall rate.")
        else:
            expr = METRICS[metric].format(c=qc)
        if metric == "avg" and RATIOISH.search(column):
            notes.append(f"'{column}' looks like a rate or average already. Averaging it gives the average of the rows, which is not the overall rate. Use 'ratio' (total over total) for the overall figure.")
        if metric == "sum" and RATIOISH.search(column):
            notes.append(f"Adding up '{column}' may not make sense if it is a rate or an average.")
    gb = (group_by or [])[:2]
    sel, grp = [], []
    for g in gb:
        qg = _q(g, cs)
        if cs[g] == "date" and grain:
            if grain not in GRAINS:
                raise ToolError("grain must be one of: " + ", ".join(GRAINS) + ".")
            sel.append(f"CAST(DATE_TRUNC('{GRAINS[grain]}', {qg}) AS VARCHAR) AS \"{g}_{grain}\"")
            grp.append(str(len(sel)))
        else:
            sel.append(f"{qg} AS \"{g}\"")
            grp.append(str(len(sel)))
    where, params = [], []
    for f in filters or []:
        col, op = f.get("column"), f.get("op", "=")
        if op not in OPS:
            raise ToolError("filter op must be one of: " + ", ".join(OPS) + ".")
        qc = _q(col, cs)
        if op in ("is_null", "not_null"):
            where.append(f"{qc} {OPS[op]}")
            continue
        v = f.get("value")
        if v in (None, ""):
            raise ToolError(f"The filter on {col} needs a value.")
        if op == "contains":
            where.append(f"CAST({qc} AS VARCHAR) ILIKE ?")
            params.append(f"%{v}%")
        else:
            if cs[col] == "number":
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ToolError(f"{col} is a number; '{v}' is not.") from None
            where.append(f"{qc} {OPS[op]} ?")
            params.append(v)
    limit = max(1, min(int(limit or 50), 200))
    sql = f"SELECT {', '.join(sel + [expr + ' AS value'])} FROM {t}" + (f" WHERE {' AND '.join(where)}" if where else "") + (f" GROUP BY {', '.join(grp)}" if grp else "")
    sql += (f" ORDER BY {'1' if (gb and cs[gb[0]] == 'date' and grain) else str(len(sel) + 1)} {'ASC' if (order == 'asc' or (gb and cs[gb[0]] == 'date' and grain)) else 'DESC'}" if grp else "") + f" LIMIT {limit}"
    with get_cursor() as cur:
        res = cur.execute(sql, params)
        names = [d[0] for d in res.description]
        rows = [[(float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else (str(x) if x is not None else None)) for x in r] for r in res.fetchall()]
    shown = sql
    for p in params:
        shown = shown.replace("?", repr(p) if isinstance(p, str) else str(p), 1)
    if not gb and rows and rows[0][-1] is None:
        notes.append("The answer is empty (no rows matched, or the column is all blank).")
    return {"sql": shown, "columns": names, "rows": rows, "notes": notes, "chart": {"labels": [" / ".join(str(x) for x in r[:-1]) for r in rows], "values": [r[-1] for r in rows]} if gb else None,
            "caution": "The numbers are exactly what the SQL returns on the data loaded here. Check the filters and the definition before quoting them."}


# ------------------------------------------------------------------ pivot


def pivot(source: str, rows: str, cols: str | None, value: str | None, agg: str = "sum", max_cols: int = 12) -> dict:
    t = _table(source)
    cs = {c["name"]: _kind(c["type"]) for c in columns(source)}
    if agg not in ("sum", "avg", "count", "min", "max"):
        raise ToolError("agg must be sum, avg, count, min or max.")
    qr = _q(rows, cs)
    if agg != "count":
        if not value:
            raise ToolError(f"{agg} needs a value column.")
        qv = _q(value, cs)
        if cs[value] != "number":
            raise ToolError(f"'{value}' is {cs[value]}; the value must be a number.")
        expr = f"{agg.upper()}({qv})"
    else:
        expr = "COUNT(*)"
    with get_cursor() as cur:
        if cols:
            qc = _q(cols, cs)
            top = [r[0] for r in cur.execute(f"SELECT CAST({qc} AS VARCHAR) FROM {t} GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT {max(1, min(max_cols, 20))}").fetchall()]
            data = cur.execute(f"SELECT CAST({qr} AS VARCHAR), CAST({qc} AS VARCHAR), {expr} FROM {t} GROUP BY 1, 2").fetchall()
            tot_r = dict(cur.execute(f"SELECT CAST({qr} AS VARCHAR), {expr} FROM {t} GROUP BY 1").fetchall())
            tot_c = dict(cur.execute(f"SELECT CAST({qc} AS VARCHAR), {expr} FROM {t} GROUP BY 1").fetchall())
            grand = cur.execute(f"SELECT {expr} FROM {t}").fetchone()[0]
        else:
            top = []
            data = []
            tot_r = dict(cur.execute(f"SELECT CAST({qr} AS VARCHAR), {expr} FROM {t} GROUP BY 1").fetchall())
            tot_c, grand = {}, cur.execute(f"SELECT {expr} FROM {t}").fetchone()[0]
    cell = {(r, c): v for r, c, v in data}
    rlabels = sorted(tot_r, key=lambda k: -(tot_r[k] or 0))[:100]
    f = lambda x: None if x is None else round(float(x), 4)
    matrix = [[f(cell.get((r, c))) for c in top] for r in rlabels]
    additive = agg in ("sum", "count")
    pct = [[None if (v is None or not grand or not additive) else round(100 * v / float(grand), 2) for v in row] for row in matrix] if cols else []
    notes = [] if additive else [f"Totals for '{agg}' are computed over all rows, not by adding the cells, and percent-of-total is only shown for sum and count."]
    if cols and len(tot_c) > len(top):
        notes.append(f"Showing the {len(top)} most common of {len(tot_c)} column values; the totals still include all of them.")
    return {"row_labels": rlabels, "col_labels": top, "matrix": matrix, "row_totals": [f(tot_r[r]) for r in rlabels], "col_totals": [f(tot_c.get(c)) for c in top], "grand_total": f(grand), "percent_of_total": pct, "notes": notes,
            "caution": "Percent of total is each cell over the grand total of all rows, so it adds to 100 only if every column value is shown."}


# ------------------------------------------------------------------ A/B tests and surveys


def _z(p: float) -> float:
    from scipy.stats import norm
    return float(norm.ppf(p))


def ab_proportions(a_success: int, a_n: int, b_success: int, b_n: int, alpha: float = 0.05) -> dict:
    from scipy.stats import norm
    for nm, v in (("a_n", a_n), ("b_n", b_n)):
        if int(v) < 1:
            raise ToolError(f"{nm} must be at least 1.")
    if not (0 <= a_success <= a_n and 0 <= b_success <= b_n):
        raise ToolError("Successes cannot be negative or more than the group size.")
    if not 0.001 <= alpha <= 0.2:
        raise ToolError("alpha must be between 0.001 and 0.2.")
    pa, pb = a_success / a_n, b_success / b_n
    pp = (a_success + b_success) / (a_n + b_n)
    se_pool = math.sqrt(pp * (1 - pp) * (1 / a_n + 1 / b_n))
    z = (pb - pa) / se_pool if se_pool else 0.0
    p = float(2 * (1 - norm.cdf(abs(z))))
    se = math.sqrt(pa * (1 - pa) / a_n + pb * (1 - pb) / b_n)
    zc = _z(1 - alpha / 2)
    diff = pb - pa
    ci = [diff - zc * se, diff + zc * se]
    small = min(a_success, a_n - a_success, b_success, b_n - b_success) < 5
    sig = p < alpha
    return {"a": {"rate": round(pa, 5), "n": a_n}, "b": {"rate": round(pb, 5), "n": b_n}, "difference": round(diff, 5), "relative_lift_pct": round(100 * diff / pa, 2) if pa else None, "z": round(z, 4), "p_value": round(p, 5),
            "confidence_interval": [round(ci[0], 5), round(ci[1], 5)], "significant": sig,
            "arithmetic": [f"A rate = {a_success}/{a_n} = {pa:.4f}; B rate = {b_success}/{b_n} = {pb:.4f}", f"Pooled rate = {a_success + b_success}/{a_n + b_n} = {pp:.4f}", f"z = ({pb:.4f} - {pa:.4f}) / {se_pool:.5f} = {z:.3f}",
                           f"Difference {diff:+.4f}, {100 * (1 - alpha):.0f}% interval {ci[0]:+.4f} to {ci[1]:+.4f}"],
            "says": (f"The difference of {diff:+.2%} is bigger than chance alone would usually produce (p = {p:.3f})." if sig else f"The difference of {diff:+.2%} is within what chance alone could produce (p = {p:.3f}). Not enough evidence of a real change.")
                    + (" Some counts are very small, so this normal-approximation result is unreliable." if small else ""),
            "caution": "A p-value is the chance of seeing a difference this big if nothing really changed, not the chance the change is real. Decide the sample size before the test; stopping early when it looks good inflates false wins."}


def sample_size(base_rate: float, min_effect: float, alpha: float = 0.05, power: float = 0.8) -> dict:
    if not 0 < base_rate < 1:
        raise ToolError("base_rate must be between 0 and 1 (for example 0.12 for 12%).")
    if min_effect <= 0 or base_rate + min_effect >= 1:
        raise ToolError("min_effect must be positive, with base_rate + min_effect below 1.")
    p1, p2 = base_rate, base_rate + min_effect
    za, zb = _z(1 - alpha / 2), _z(power)
    n = ((za * math.sqrt(2 * (p1 + p2) / 2 * (1 - (p1 + p2) / 2)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (p2 - p1) ** 2
    return {"per_group": math.ceil(n), "total": 2 * math.ceil(n), "says": f"To detect a move from {p1:.1%} to {p2:.1%} with {power:.0%} power at {alpha:.0%} significance, you need about {math.ceil(n):,} people in each group.",
            "caution": "Smaller effects need far more people. Halving the effect roughly quadruples the sample."}


def ab_means(a: list[float], b: list[float], alpha: float = 0.05) -> dict:
    from scipy import stats
    if len(a) < 2 or len(b) < 2:
        raise ToolError("Each group needs at least 2 numbers.")
    r = stats.ttest_ind(b, a, equal_var=False)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    se = math.sqrt(_var(a) / len(a) + _var(b) / len(b))
    df = r.df if hasattr(r, "df") else len(a) + len(b) - 2
    tc = float(stats.t.ppf(1 - alpha / 2, df))
    d = mb - ma
    sp = math.sqrt(((len(a) - 1) * _var(a) + (len(b) - 1) * _var(b)) / (len(a) + len(b) - 2))
    p = float(r.pvalue)
    return {"a": {"mean": round(ma, 4), "n": len(a)}, "b": {"mean": round(mb, 4), "n": len(b)}, "difference": round(d, 4), "confidence_interval": [round(d - tc * se, 4), round(d + tc * se, 4)], "t": round(float(r.statistic), 4),
            "p_value": round(p, 5), "effect_size_d": round(d / sp, 3) if sp else None, "significant": p < alpha,
            "says": f"Group B's average is {d:+.3f} compared with A (p = {p:.3f}). " + ("That is larger than chance would usually produce." if p < alpha else "That is within normal chance variation."),
            "caution": "Welch's t-test assumes the averages are meaningful and the samples are independent. Heavy outliers or tiny samples weaken it."}


def _var(x: list[float]) -> float:
    m = sum(x) / len(x)
    return sum((v - m) ** 2 for v in x) / (len(x) - 1)


def survey(source: str, column: str, group: str | None = None) -> dict:
    t = _table(source)
    cs = {c["name"]: _kind(c["type"]) for c in columns(source)}
    qc = _q(column, cs)
    with get_cursor() as cur:
        rows = cur.execute(f"SELECT CAST({qc} AS VARCHAR), COUNT(*) FROM {t} WHERE {qc} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 40").fetchall()
        total = sum(r[1] for r in rows)
        blank = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {qc} IS NULL").fetchone()[0]
    if not total:
        raise ToolError("That column has no answers.")
    out = []
    for lab, n in rows:
        p = n / total
        z = 1.96
        den = 1 + z * z / total
        centre = (p + z * z / (2 * total)) / den
        half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
        out.append({"answer": lab, "count": n, "pct": round(100 * p, 1), "low": round(100 * (centre - half), 1), "high": round(100 * (centre + half), 1)})
    return {"column": column, "answers": total, "blank": int(blank), "options": out, "says": f"{total:,} answers; '{out[0]['answer']}' is most common at {out[0]['pct']}%.",
            "caution": "The ranges are 95% Wilson intervals and assume the answers are a fair sample. If only keen customers replied, the range understates the real uncertainty."}


# ------------------------------------------------------------------ analysis notebook


def _key() -> str:
    return f"analystnb:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    d = json.loads(raw) if raw else {}
    d.setdefault("entries", [])
    d.setdefault("next", 0)
    return d


def _txt(v, limit):
    return re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v or "")).strip()[:limit]


def nb_save(b: dict) -> dict:
    title = _txt(b.get("title"), 120)
    if not title:
        raise ToolError("Give the analysis a title.")
    d = _load()
    d["next"] += 1
    res = b.get("result") or {}
    e = {"id": d["next"], "title": title, "question": _txt(b.get("question"), 500), "sql": _txt(b.get("sql"), 4000), "columns": [str(c) for c in (res.get("columns") or [])][:12],
         "rows": [[(None if x is None else x) for x in r[:12]] for r in (res.get("rows") or [])[:50]], "finding": _txt(b.get("finding"), 1500), "caveats": _txt(b.get("caveats"), 1500), "created": date.today().isoformat()}
    d["entries"].append(e)
    d["entries"] = d["entries"][-100:]
    state.kv_set(_key(), json.dumps(d))
    return {"id": e["id"], "title": title}


def nb_list() -> list[dict]:
    return [{k: e[k] for k in ("id", "title", "question", "created")} for e in _load()["entries"]]


def nb_delete(i: int) -> dict:
    d = _load()
    d["entries"] = [e for e in d["entries"] if e["id"] != i]
    state.kv_set(_key(), json.dumps(d))
    return {"deleted": i}


def nb_html(i: int) -> str:
    e = next((x for x in _load()["entries"] if x["id"] == i), None)
    if not e:
        raise ToolError("Not found.", 404)
    h = html.escape
    head = "".join(f"<th>{h(str(c))}</th>" for c in e["columns"])
    body = "".join("<tr>" + "".join(f"<td>{h('' if x is None else str(x))}</td>" for x in r) + "</tr>" for r in e["rows"])
    banner = "<p style='background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600'>SAMPLE: from the Practice workspace, not a client deliverable.</p>" if workspaces.active() != "real" else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{h(e['title'])}</title><style>body{{font:15px/1.5 system-ui,Arial,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}td,th{{padding:.35rem .5rem;border-bottom:1px solid #ddd;text-align:left}}pre{{background:#f3f4f3;padding:.6rem;overflow:auto}}h2{{border-bottom:2px solid #0f6b4a}}</style></head><body>{banner}
<h1>{h(e['title'])}</h1><p>{h(e['created'])}</p><h2>Question</h2><p>{h(e['question'])}</p><h2>Finding</h2><p>{h(e['finding'])}</p><h2>Method</h2><pre>{h(e['sql'])}</pre>
<h2>Result</h2><table><tr>{head}</tr>{body}</table><h2>Caveats</h2><p>{h(e['caveats'] or 'None noted.')}</p></body></html>"""
