"""Prescriptive analytics: recommend an action to reach a goal.

Two tools, both transparent about their assumptions:
  goal_seek            how far must each lever move (others held fixed) for the average of a number to reach a target? (from a regression)
  optimize_allocation  how to split a limited budget across groups to maximize the total return (a linear program, solved with scipy)
Both rest on patterns in past data. They say what the data implies, not what is guaranteed to work.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

from app.services import stats_lab
from app.services.datasets import DataError, q
from app.services.stats_lab import _f, _need, _rows, resolve, where_clause


def goal_seek(source: str, y: str, target: float, levers: list[str], filters=None, mode: str = "and") -> dict:
    levers = list(dict.fromkeys(levers or []))
    if not levers:
        raise DataError("Pick at least one lever (a number you can change).")
    reg = stats_lab.regression(source, y, x_numeric=levers, filters=filters, mode=mode)
    cur = float(reg["y_mean"])
    gap = target - cur
    coef = {c["term"]: c for c in reg["coefficients"]}
    means = {}
    ident, cols = resolve(source)
    w, params, _ = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in [y] + levers])
    row = _rows(f"SELECT {', '.join(f'AVG({q(c)}) AS m{i}' for i, c in enumerate(levers))} FROM {q(ident)}{w}", params)[0]
    for i, c in enumerate(levers):
        means[c] = float(row[f"m{i}"])
    opts = []
    for c in levers:
        b = coef[c]
        if not b["coef"] or abs(b["coef"]) < 1e-12:
            continue
        need = gap / b["coef"]
        new = means[c] + need
        lo, hi = reg["x_ranges"][c]
        inside = lo <= new <= hi
        opts.append({"lever": c, "effect_per_unit": _f(b["coef"], 6), "reliable": bool(b["significant"]), "current_average": _f(means[c], 4),
                     "change_needed": _f(need, 4), "needed_value": _f(new, 4), "change_pct": _f(need / abs(means[c]) * 100, 1) if means[c] else None,
                     "inside_observed_range": bool(inside), "observed_range": [lo, hi]})
    opts.sort(key=lambda o: (not o["reliable"], not o["inside_observed_range"], abs(o["change_pct"]) if o["change_pct"] is not None else 1e18))
    # one balanced plan: move every reliable lever by the same percentage
    rel = [c for c in levers if coef[c]["significant"] and means[c]]
    plan = None
    denom = sum(coef[c]["coef"] * means[c] for c in rel)
    if rel and abs(denom) > 1e-12:
        t = gap / denom
        plan = {"pct_each": _f(t * 100, 2), "levers": [{"lever": c, "from": _f(means[c], 4), "to": _f(means[c] * (1 + t), 4)} for c in rel],
                "all_inside_range": all(reg["x_ranges"][c][0] <= means[c] * (1 + t) <= reg["x_ranges"][c][1] for c in rel)}
    sentences = [f"Average {y} is {cur:,.4g} now; the target is {target:,.4g} (a gap of {gap:+,.4g})."]
    if gap == 0:
        sentences.append("You are already at the target on average.")
    elif opts and opts[0]["reliable"]:
        o = opts[0]
        sentences.append(f"Easiest single lever: move {o['lever']} from {o['current_average']:,.4g} to about {o['needed_value']:,.4g} ({o['change_pct']:+}%), other inputs unchanged.")
    elif opts:
        sentences.append("None of the levers has a reliable link to this number, so any plan below is weak.")
    if plan:
        sentences.append(f"Or move every reliable lever by about {plan['pct_each']:+}% together.")
    warn = ["This assumes the past relationship holds if you change the lever, which is a big 'if': a link in the data is not proof that pushing the lever causes the result."]
    if reg["r2"] < 0.2:
        warn.append(f"The inputs explain only {reg['r2']:.0%} of {y}, so the plan is a rough guide at best.")
    if any(not o["inside_observed_range"] for o in opts):
        warn.append("Some needed values fall outside anything seen in your data; that is extrapolation, so trust it least.")
    return {"y": y, "target": target, "current": _f(cur, 6), "gap": _f(gap, 6), "r2": reg["r2"], "options": opts, "plan": plan, "filters": reg["filters"],
            "sentences": sentences, "warnings": warn,
            "lesson": ("Goal seeking runs a regression backwards: if +1 in a lever moves the result by b, then closing a gap needs gap / b of movement. It is only as good as "
                       "the regression (check R² and 'reliable') and only valid inside the range of values you have actually seen.")}


def optimize_allocation(source: str, group_col: str, return_col: str, effort_col: str, budget: float | None = None, min_mult: float = 0.5,
                        max_mult: float = 1.5, min_rows: int = 10, filters=None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, group_col, ("text", "bool"), "group column")
    _need(cols, return_col, ("number",), "return column")
    _need(cols, effort_col, ("number",), "effort/budget column")
    if return_col == effort_col:
        raise DataError("The return and the effort must be different columns.")
    if not (0 <= min_mult <= 1 <= max_mult <= 5):
        raise DataError("Minimum must be between 0 and 1 and maximum between 1 and 5 times the current level.")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in (group_col, return_col, effort_col)])
    rows = _rows(f"SELECT CAST({q(group_col)} AS VARCHAR) AS g, SUM({q(return_col)}) AS r, SUM({q(effort_col)}) AS e, COUNT(*) AS n FROM {q(ident)}{w} "
                 f"GROUP BY 1 HAVING SUM({q(effort_col)}) > 0 ORDER BY e DESC LIMIT 50", params)
    if len(rows) < 2:
        raise DataError("Need at least 2 groups with positive effort to compare.")
    g = [r["g"] for r in rows]
    R, E, N = (np.array([float(r[k]) for r in rows]) for k in ("r", "e", "n"))
    rate = R / E
    total = float(E.sum())
    B = total if budget is None else float(budget)
    if B <= 0:
        raise DataError("The budget must be above zero.")
    lo, hi = E * min_mult, E * max_mult
    if lo.sum() > B + 1e-9:
        raise DataError(f"The minimum levels already cost {lo.sum():,.2f}, more than the budget {B:,.2f}. Lower the minimum or raise the budget.")
    sol = linprog(c=-rate, A_ub=np.ones((1, len(g))), b_ub=[B], bounds=list(zip(lo, hi)), method="highs")
    if not sol.success:
        raise DataError("No allocation satisfies those limits. Loosen the minimum/maximum or change the budget.")
    x = sol.x
    now_ret, new_ret = float((rate * E).sum()), float((rate * x).sum())
    table = [{"group": g[i], "rows": int(N[i]), "return_per_unit": _f(rate[i], 4), "current": _f(E[i], 2), "recommended": _f(x[i], 2), "change": _f(x[i] - E[i], 2),
              "change_pct": _f((x[i] - E[i]) / E[i] * 100, 1), "return_now": _f(rate[i] * E[i], 2), "return_new": _f(rate[i] * x[i], 2), "thin": bool(N[i] < min_rows)}
             for i in range(len(g))]
    table.sort(key=lambda t: -(t["change"] or 0))
    up = [t for t in table if (t["change"] or 0) > 0.005]
    down = [t for t in table if (t["change"] or 0) < -0.005]
    gain = new_ret - now_ret
    sentences = [f"With {B:,.2f} to spend across {len(g)} groups, the best split returns {new_ret:,.2f} versus {now_ret:,.2f} now ({gain:+,.2f}, {gain / now_ret * 100:+.1f}%)." if now_ret else
                 f"With {B:,.2f} to spend, the best split returns {new_ret:,.2f}."]
    if up:
        sentences.append("Put more into " + ", ".join(f"{t['group']} ({t['change_pct']:+}%)" for t in up[:3]) + (" and less into " + ", ".join(f"{t['group']} ({t['change_pct']:+}%)" for t in down[:3]) if down else "") + ".")
    else:
        sentences.append("The current split is already the best within these limits.")
    warn = [f"Assumes each group keeps earning the same return per unit when you raise or lower its spend. Real returns usually shrink as spend grows, so the limits ({min_mult:g}x to {max_mult:g}x) keep the plan modest. Test a small shift first."]
    thin = [t["group"] for t in table if t["thin"]]
    if thin:
        warn.append(f"Return per unit for {', '.join(thin[:5])} rests on fewer than {min_rows} rows, so it may be luck.")
    if budget is not None and budget > total * max_mult:
        warn.append("The budget is larger than the groups can absorb at the maximum levels; some budget goes unspent.")
    return {"group_col": group_col, "return_col": return_col, "effort_col": effort_col, "budget": _f(B, 2), "current_total": _f(total, 2), "spent": _f(float(x.sum()), 2),
            "return_now": _f(now_ret, 2), "return_new": _f(new_ret, 2), "gain": _f(gain, 2), "gain_pct": _f(gain / now_ret * 100, 2) if now_ret else None,
            "allocation": table, "filters": fwords, "sentences": sentences, "warnings": warn,
            "lesson": ("Optimization picks the best option under limits: maximize return, subject to a budget and per-group minimums and maximums. This is a linear program: "
                       "it fills the best return-per-unit group first until its limit, then the next. The answer is only as realistic as its assumptions, so read the warnings.")}


def brief(source: str, metric: str, group_col: str | None = None, date_col: str | None = None, higher_is_better: bool = True,
          filters=None, mode: str = "and") -> dict:
    """One page that runs the four kinds of analytics in order: what happened, why, what next, what to do. Each part is optional and fails softly."""
    ident, cols = resolve(source)
    _need(cols, metric, ("number",), "metric")
    sections, notes = [], []

    def add(kind: str, title: str, lines: list[str], detail: dict | None = None):
        sections.append({"kind": kind, "title": title, "lines": [x for x in lines if x], "detail": detail or {}})

    # 1. descriptive
    try:
        d = stats_lab.describe(source, filters, mode)
        m = next((n for n in d["numbers"] if n["column"] == metric), None)
        lines = [f"{d['rows']:,} rows."]
        if m:
            lines.append(f"{metric}: average {m['mean']:,.4g}, middle value {m['median']:,.4g}, from {m['min']:,.4g} to {m['max']:,.4g}.")
            if m["skew_note"]:
                lines.append(m["skew_note"].capitalize() + ".")
        if group_col:
            top = next((c for c in d["categories"] if c["column"] == group_col), None)
            if top and top["top"]:
                lines.append(f"Most common {group_col}: {top['top'][0]['value']} ({top['top'][0]['pct']}% of rows).")
        add("descriptive", "What happened", lines)
    except DataError as e:
        notes.append(f"Descriptive step skipped: {e.message}")
    # trend over time (descriptive) and forecast (predictive)
    fc = None
    if date_col:
        try:
            fc = stats_lab.timeseries(source, date_col, metric, "sum", "week" if _span_days(ident, cols, date_col, filters, mode) > 120 else "day", filters, mode, None, 7)
            if fc.get("available"):
                add("descriptive", "Trend", fc["sentences"][:2])
            else:
                notes.append(f"Trend step skipped: {fc.get('reason')}")
        except DataError as e:
            notes.append(f"Trend step skipped: {e.message}")
    # 2. diagnostic
    try:
        g = stats_lab.diagnose(source, metric, group_col, date_col, None, filters, mode)
        add("diagnostic", "Why", g["sentences"][:3], {"drivers": g["drivers"][:4]})
    except DataError as e:
        notes.append(f"Diagnostic step skipped: {e.message}")
    # 3. predictive
    if fc and fc.get("available") and fc.get("forecast"):
        lines = [x for x in fc["sentences"] if x.startswith("Projecting")]
        add("predictive", "What is likely next", lines or ["No forecast sentence available."])
    # 4. prescriptive
    if group_col:
        try:
            o = stats_lab.opportunities(source, metric, group_col, higher_is_better, "median", 5, filters, mode)
            add("prescriptive", "What to do", o["sentences"][:2] + ([o["opportunities"][0]["action"]] if o["opportunities"] else []), {"opportunities": o["opportunities"][:3]})
        except DataError as e:
            notes.append(f"Prescriptive step skipped: {e.message}")
    else:
        notes.append("Pick a group column (such as region or product) to get ranked recommendations.")
    if not sections:
        raise DataError("Nothing could be computed for this metric. Check the data and filters.")
    return {"metric": metric, "group_col": group_col, "date_col": date_col, "sections": sections, "notes": notes,
            "lesson": ("Prescriptive analytics draws on the other three: descriptive shows what the numbers did, diagnostic finds why, predictive projects what comes next, and "
                       "only then can you choose an action. Treat the recommendation as the next thing to test, with the earlier steps as its evidence.")}


def _span_days(ident, cols, date_col, filters, mode) -> int:
    w, params, _ = where_clause(cols, filters, mode, [f"{q(date_col)} IS NOT NULL"])
    r = _rows(f"SELECT DATE_DIFF('day', MIN({q(date_col)}), MAX({q(date_col)})) AS d FROM {q(ident)}{w}", params)[0]
    return int(r["d"] or 0)


# ------------------------------------------------------------------ are the inputs fit to act on?
def input_check(source: str, columns: list[str], date_col: str | None = None, group_col: str | None = None, filters=None, mode: str = "and") -> dict:
    """A pre-flight check before acting on a recommendation: enough rows, few gaps, fresh data, no wild values, groups big enough."""
    ident, cols = resolve(source)
    columns = [c for c in dict.fromkeys(columns or []) if c]
    if not columns:
        raise DataError("Pick the columns the recommendation relies on.")
    for c in columns:
        _need(cols, c, None, "column")
    w, params, fwords = where_clause(cols, filters, mode)
    n = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    checks: list[dict] = []

    def add(name: str, level: str, detail: str):
        checks.append({"check": name, "level": level, "detail": detail})

    if n == 0:
        raise DataError("No rows match the filters, so there is nothing to check.")
    add("Enough rows", "ok" if n >= 100 else "warn" if n >= 30 else "bad", f"{n:,} rows" + ("" if n >= 100 else ". Under 100 rows, results swing a lot; under 30 they are mostly luck."))
    for c in columns:
        r = _rows(f"SELECT COUNT(*) - COUNT({q(c)}) AS miss, COUNT(DISTINCT {q(c)}) AS d FROM {q(ident)}{w}", params)[0]
        miss = int(r["miss"]) / n * 100
        add(f"Gaps in {c}", "ok" if miss < 5 else "warn" if miss < 20 else "bad", f"{miss:.1f}% empty" + ("" if miss < 5 else ". Empty values are skipped, which can bias the result."))
        if int(r["d"]) <= 1:
            add(f"{c} never changes", "bad", "One value only, so it cannot explain or predict anything.")
        if cols[c] == "number":
            s = _rows(f"SELECT QUANTILE_CONT({q(c)}, 0.25) AS q1, QUANTILE_CONT({q(c)}, 0.75) AS q3, MIN({q(c)}) AS lo, MAX({q(c)}) AS hi, "
                      f"SUM(CASE WHEN {q(c)} < 0 THEN 1 ELSE 0 END) AS neg FROM {q(ident)}{w}", params)[0]
            if s["q1"] is not None and s["q3"] is not None and s["q3"] > s["q1"]:
                iqr = float(s["q3"]) - float(s["q1"])
                far = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} ({q(c)} < ? OR {q(c)} > ?)", params + [float(s["q1"]) - 3 * iqr, float(s["q3"]) + 3 * iqr])[0]["n"])
                if far:
                    add(f"Extreme values in {c}", "warn", f"{far:,} row(s) lie far outside the normal range (beyond 3x the middle spread). Check they are real, not typos or unit mix-ups.")
            if s["neg"] and ("cost" in c.lower() or "revenue" in c.lower() or "qty" in c.lower() or "units" in c.lower()):
                add(f"Negative values in {c}", "warn", f"{int(s['neg']):,} negative value(s) in a column that is usually positive: refunds, or errors?")
    if date_col:
        _need(cols, date_col, ("date",), "date column")
        r = _rows(f"SELECT MAX({q(date_col)}) AS hi, MIN({q(date_col)}) AS lo FROM {q(ident)}{w}", params)[0]
        if r["hi"]:
            hi = r["hi"].date() if hasattr(r["hi"], "date") else r["hi"]
            from datetime import date as _d
            age = (_d.today() - hi).days
            add("Fresh data", "ok" if age <= 14 else "warn" if age <= 60 else "bad", f"Latest record is {hi} ({age} days ago)" + ("" if age <= 14 else ". Advice from old data may no longer fit today."))
    if group_col:
        _need(cols, group_col, ("text", "bool"), "group column")
        g = _rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}{' AND' if w else ' WHERE'} {q(group_col)} IS NOT NULL GROUP BY {q(group_col)}", params)
        small = sum(1 for x in g if int(x["n"]) < 10)
        add(f"Group sizes in {group_col}", "ok" if small == 0 else "warn", f"{len(g)} groups, {small} with fewer than 10 rows" + ("" if small == 0 else ". Their averages are unreliable."))
    levels = [c["level"] for c in checks]
    verdict = "red" if "bad" in levels else "amber" if "warn" in levels else "green"
    msg = {"green": "Inputs look sound. You can use the recommendations as a starting point, then monitor the result.",
           "amber": "Usable with care. Fix or note the warnings before acting on anything big.",
           "red": "Don't act on these results yet. Fix the problems marked red first."}[verdict]
    return {"rows": n, "verdict": verdict, "message": msg, "checks": checks, "filters": fwords,
            "reminders": ["A recommendation is only as good as its inputs: wrong, stale or biased data produces a confident wrong answer.",
                          "Models usually need testing on data they haven't seen and re-tuning; a first result is a draft.",
                          "Start with a small, reversible change and track the result (see 'Track the result'); conditions change and surprises happen."]}


# ------------------------------------------------------------------ keep watching the result
MAX_TRACKED = 50


def _tkey() -> str:
    from app.services import workspaces
    return f"prescribe_track:{workspaces.active()}"


def _tload() -> list[dict]:
    import json
    from app.services import state
    try:
        v = json.loads(state.kv_get(_tkey(), "[]") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def _tsave(items: list[dict]) -> None:
    import json
    from app.services import state
    state.kv_set(_tkey(), json.dumps(items))


def _avg_since(source: str, metric: str, date_col: str, since, until, filters, mode):
    ident, cols = resolve(source)
    extra = [f"{q(date_col)} >= ?", f"{q(metric)} IS NOT NULL"] + ([f"{q(date_col)} <= ?"] if until else [])
    w, params, _ = where_clause(cols, filters, mode, extra)
    r = _rows(f"SELECT AVG({q(metric)}) AS m, STDDEV_SAMP({q(metric)}) AS sd, COUNT(*) AS n FROM {q(ident)}{w}", _ordered(params, filters, since, until))[0]
    return (float(r["m"]) if r["m"] is not None else None), (float(r["sd"]) if r["sd"] is not None else None), int(r["n"])


def _ordered(params, filters, since, until):
    # where_clause puts filter params first, then the extras in order: date >= since, [date <= until]
    return list(params) + [since] + ([until] if until else [])


def track_add(title: str, source: str, metric: str, date_col: str, action: str, target: float | None = None, baseline_days: int = 30,
              filters=None, mode: str = "and") -> dict:
    from datetime import date, timedelta
    import uuid
    from app.services import state
    title, action = (title or "").strip()[:140], (action or "").strip()[:500]
    if not title:
        raise DataError("Give the decision a title.")
    ident, cols = resolve(source)
    _need(cols, metric, ("number",), "metric")
    _need(cols, date_col, ("date",), "date column")
    if not 7 <= baseline_days <= 365:
        raise DataError("The baseline period must be 7 to 365 days.")
    w, params, _ = where_clause(cols, filters, mode, [f"{q(date_col)} IS NOT NULL"])
    last = _rows(f"SELECT MAX({q(date_col)}) AS d FROM {q(ident)}{w}", params)[0]["d"]
    if not last:
        raise DataError("No dated rows to measure a baseline from.")
    last = last.date() if hasattr(last, "date") else last
    since = last - timedelta(days=baseline_days - 1)
    m, sd, n = _avg_since(source, metric, date_col, since, last, filters, mode)
    if m is None or n < 5:
        raise DataError(f"Only {n} rows in the last {baseline_days} days of data; a baseline needs at least 5.")
    items = _tload()
    if len(items) >= MAX_TRACKED:
        raise DataError(f"You are tracking {MAX_TRACKED} decisions already; delete some first.")
    it = {"id": uuid.uuid4().hex[:10], "title": title, "action": action, "source": source, "metric": metric, "date_col": date_col, "filters": filters or [], "mode": mode,
          "baseline": round(m, 6), "baseline_sd": round(sd or 0.0, 6), "baseline_n": n, "baseline_from": since.isoformat(), "baseline_to": last.isoformat(),
          "start": (last + timedelta(days=1)).isoformat(), "target": target, "created": state.now()}
    items.append(it)
    _tsave(items)
    state.audit("prescribe.track", title)
    return track_check_one(it)


def track_check_one(it: dict) -> dict:
    from datetime import date
    try:
        m, sd, n = _avg_since(it["source"], it["metric"], it["date_col"], date.fromisoformat(it["start"]), None, it["filters"], it["mode"])
    except DataError as e:
        return {**it, "status": "unavailable", "message": e.message, "current": None, "rows_since": 0}
    base, bsd = it["baseline"], it["baseline_sd"]
    out = {**it, "current": None if m is None else round(m, 6), "rows_since": n}
    if m is None or n < 5:
        return {**out, "status": "waiting", "message": f"Only {n} row(s) dated since {it['start']}. Load newer data to see the effect (need at least 5)."}
    change = m - base
    out["change"] = round(change, 6)
    out["change_pct"] = round(change / abs(base) * 100, 2) if base else None
    # is the move bigger than ordinary day-to-day noise around the baseline? (standard error of the new average)
    se = (bsd / (n ** 0.5)) if bsd else 0.0
    out["unusual"] = bool(se and abs(change) > 3 * se)
    tgt = it.get("target")
    if tgt is not None and tgt != base:
        prog = change / (tgt - base)
        out["progress_pct"] = round(prog * 100, 1)
        status = "on target" if prog >= 1 else "moving the right way" if prog > 0.1 else "no clear effect" if prog > -0.1 else "moving the wrong way"
    else:
        status = "changed" if out["unusual"] else "no clear change"
    out["status"] = status
    out["message"] = (f"Average {it['metric']} since {it['start']} is {m:,.4g} versus a baseline of {base:,.4g} ({change:+,.4g}"
                      + (f", {out['change_pct']:+}%" if out["change_pct"] is not None else "") + ")."
                      + (" That is bigger than normal noise." if out["unusual"] else " That is within normal noise, so it may be chance.")
                      + (" Something else may be driving it; check before crediting or blaming your change." if out["unusual"] and tgt is None else ""))
    return out


def track_list() -> list[dict]:
    return [track_check_one(it) for it in sorted(_tload(), key=lambda i: i["created"], reverse=True)]


def track_delete(item_id: str) -> dict:
    items = _tload()
    keep = [i for i in items if i["id"] != item_id]
    if len(keep) == len(items):
        raise DataError("That tracked decision no longer exists.", 404)
    _tsave(keep)
    return {"deleted": item_id}
