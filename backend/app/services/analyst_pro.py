"""Advanced analyst lab: cohorts, funnels, forecasts with ranges, finance maths, A/B test, Pareto, star schema, window-function recipes, DAX/Tableau map, dashboard review, metric and requirements templates.
Everything runs on this computer from what you paste or pick. Results are estimates to check, not answers."""
from __future__ import annotations

import math
import re
import statistics
from datetime import date, datetime

NOTE = "Check these against the source data before you put them in front of anyone."


class AnalystError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _num(v, name, lo=None, hi=None) -> float:
    try:
        x = float(str(v).replace(",", "").replace("$", "").replace("%", "").strip())
    except (TypeError, ValueError):
        raise AnalystError(f"{name} must be a number.") from None
    if math.isnan(x) or math.isinf(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        raise AnalystError(f"{name} is out of range.")
    return x


# ------------------------------------------------------------------ cohorts and funnels
def _month(s: str) -> tuple[int, int]:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(s[:19] if "%H" in fmt else s, fmt)
            return d.year, d.month
        except ValueError:
            continue
    raise AnalystError(f"Could not read the date '{s[:20]}'. Use 2026-09-15 or 2026-09.")


def cohort_pairs(pairs: list[tuple[str, tuple[int, int]]], max_cohorts: int = 24, max_periods: int = 12) -> dict:
    first: dict[str, int] = {}
    seen: dict[str, set[int]] = {}
    for uid, (y, m) in pairs:
        k = y * 12 + m
        seen.setdefault(uid, set()).add(k)
    for uid, ks in seen.items():
        first[uid] = min(ks)
    if not first:
        raise AnalystError("No rows to read. Give lines like: customer_id, 2026-03-14")
    last_all = max(max(ks) for ks in seen.values())
    cohorts: dict[int, list[str]] = {}
    for uid, k in first.items():
        cohorts.setdefault(k, []).append(uid)
    rows = []
    for k in sorted(cohorts)[-max_cohorts:]:
        users = cohorts[k]
        span = min(max_periods, last_all - k)
        ret = []
        for p in range(0, span + 1):
            n = sum(1 for u in users if (k + p) in seen[u])
            ret.append(round(100 * n / len(users), 1))
        rows.append({"cohort": f"{k // 12:04d}-{(k - 1) % 12 + 1:02d}", "size": len(users), "retention_pct": ret})
    avg = []
    for p in range(1, max_periods + 1):
        num = den = 0.0
        for r in rows:
            if len(r["retention_pct"]) > p:
                num += r["retention_pct"][p] * r["size"]
                den += r["size"]
        if den:
            avg.append(round(num / den, 1))
    return {"users": len(first), "cohorts": rows, "weighted_average_by_month": avg,
            "how_to_read": "Month 0 is the month a customer first appeared (always 100%). Each later number is the share of that group active again that many months later. Newer cohorts have fewer months to show.",
            "watch": ["A steep drop after month 1 usually points to onboarding or first-use problems.", "A curve that flattens means a loyal core; one that keeps falling means a leaky bucket.", "Compare cohorts, not just the average: an improving or worsening trend hides inside it."], "note": NOTE}


def cohort(text: str) -> dict:
    pairs = []
    for ln in str(text or "").splitlines():
        p = [x.strip() for x in re.split(r"[,\t;]", ln)]
        if len(p) < 2 or not p[0] or p[0].lower() in ("id", "user", "user_id", "customer_id", "customer"):
            continue
        pairs.append((p[0], _month(p[1])))
        if len(pairs) > 200000:
            raise AnalystError("Keep it under 200,000 rows.")
    return cohort_pairs(pairs)


def funnel(text: str) -> dict:
    steps = []
    for ln in str(text or "").splitlines():
        p = [x.strip() for x in ln.rsplit(",", 1)]
        if len(p) == 2 and p[0]:
            steps.append((p[0], _num(p[1], f"Count for {p[0]}", 0)))
    if len(steps) < 2:
        raise AnalystError("Give at least two steps, one per line: name, count (for example Visited, 1000).")
    rows, worst = [], None
    for i, (n, c) in enumerate(steps):
        prev = steps[i - 1][1] if i else None
        conv = None if prev is None else (round(100 * c / prev, 1) if prev else 0.0)
        rows.append({"step": n, "count": c, "from_previous_pct": conv, "overall_pct": round(100 * c / steps[0][1], 1) if steps[0][1] else 0.0})
        if conv is not None and (worst is None or conv < worst[1]):
            worst = (n, conv, steps[i - 1][0])
    out = {"steps": rows, "biggest_leak": {"between": f"{worst[2]} to {worst[0]}", "keeps_pct": worst[1]} if worst else None,
           "tips": ["Fix the biggest leak first, but check that its count is measured the same way as the step before.", "A step with more than the one before it means the steps are not a strict order or the data is mixed.", "Look at the funnel by segment (device, source, plan): the average can hide the real problem."], "note": NOTE}
    if any(rows[i]["count"] > rows[i - 1]["count"] for i in range(1, len(rows))):
        out["warning"] = "A step has more than the step before it. Check that every row counts the same people."
    return out


# ------------------------------------------------------------------ forecasting with a range
def _snaive(v: list[float], h: int, season: int) -> float:
    g_den = sum(v[-2 * season:-season])
    g = sum(v[-season:]) / g_den if g_den else 1.0
    return v[len(v) - season + ((h - 1) % season)] * (g ** ((h - 1) // season + 1))


def forecast(values, season=12, horizon=3, width=2) -> dict:
    if isinstance(values, str):
        toks = re.findall(r"-?\d[\d,]*\.?\d*", values.replace("\n", " "))
        values = [t.replace(",", "") for t in toks]
    v = [_num(x, "A value") for x in (values or [])]
    sn, h, w = int(_num(season, "Season length", 1, 366)), int(_num(horizon, "Months ahead", 1, 36)), _num(width, "Range width", 0.5, 4)
    if len(v) < 6:
        raise AnalystError("Give at least 6 values (one per period, oldest first).")
    seasonal = sn > 1 and len(v) >= 2 * sn + 1
    if seasonal:
        method = f"Seasonal naive: same period last cycle ({sn}) times the growth of the latest cycle over the one before."
        errs, naive = [], []
        for t in range(max(2 * sn, len(v) - 12), len(v)):
            errs.append(v[t] - _snaive(v[:t], 1, sn))
            naive.append(v[t] - v[t - 1])
        pts = [_snaive(v, k, sn) for k in range(1, h + 1)]
    else:
        n = len(v)
        xs = list(range(n))
        mx, my = statistics.fmean(xs), statistics.fmean(v)
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, v)) / sxx
        icpt = my - slope * mx
        method = "Straight-line trend (not enough history for a seasonal method: it needs more than two full cycles)."
        errs = [y - (icpt + slope * x) for x, y in zip(xs, v)]
        naive = [v[t] - v[t - 1] for t in range(1, n)]
        pts = [icpt + slope * (n - 1 + k) for k in range(1, h + 1)]
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    nrmse = math.sqrt(sum(e * e for e in naive) / len(naive)) if naive else None
    rows = [{"ahead": k, "forecast": round(p, 1), "low": round(p - w * rmse * math.sqrt(k), 1), "high": round(p + w * rmse * math.sqrt(k), 1)} for k, p in enumerate(pts, 1)]
    return {"method": method, "seasonal": seasonal, "points": len(v), "typical_error": round(rmse, 2), "repeat_last_value_error": round(nrmse, 2) if nrmse is not None else None,
            "beats_repeat_last_value": bool(nrmse is not None and rmse < nrmse), "forecast": rows,
            "how_range_works": f"Range = forecast plus or minus {w:g} typical errors, widened by the square root of the steps ahead (an assumption, not measured).",
            "caveats": ["The range reflects past error only. It does not cover a price change, promotion or shock.", "A short history gives a weak estimate of the seasonal shape.", "Test on the most recent periods before you trust it: hold them out and compare."], "note": NOTE}


# ------------------------------------------------------------------ finance
def breakeven(fixed_costs, price, variable_cost, target_profit=0) -> dict:
    f, p, c, t = _num(fixed_costs, "Fixed costs", 0), _num(price, "Price", 0), _num(variable_cost, "Variable cost per unit", 0), _num(target_profit, "Target profit", 0)
    if p <= c:
        raise AnalystError("Price must be higher than the variable cost per unit, or every sale loses money.")
    cm = p - c
    u = (f + t) / cm
    return {"contribution_per_unit": round(cm, 2), "contribution_margin_pct": round(100 * cm / p, 1), "units_needed": math.ceil(u), "revenue_needed": round(math.ceil(u) * p, 2),
            "note": "Break-even units = (fixed costs + target profit) / (price - variable cost). It assumes costs stay fixed and variable as stated."}


def unit_econ(monthly_revenue_per_customer, gross_margin_pct, monthly_churn_pct, cac) -> dict:
    a, g, ch, k = _num(monthly_revenue_per_customer, "Monthly revenue per customer", 0), _num(gross_margin_pct, "Gross margin %", 0, 100), _num(monthly_churn_pct, "Monthly churn %", 0.01, 100), _num(cac, "Cost to win a customer", 0)
    gm = a * g / 100
    life = 100 / ch
    ltv = gm * life
    pay = k / gm if gm else None
    ratio = ltv / k if k else None
    verdict = "Not enough to judge." if ratio is None else "Healthy: customers return well over what they cost to win." if ratio >= 3 else "Thin: under 3 times the cost, so growth is expensive." if ratio >= 1 else "Losing money on each customer over their lifetime."
    return {"gross_profit_per_month": round(gm, 2), "expected_lifetime_months": round(life, 1), "lifetime_value": round(ltv, 2), "ltv_to_cac": round(ratio, 2) if ratio is not None else None,
            "payback_months": round(pay, 1) if pay is not None else None, "verdict": verdict, "note": "Lifetime = 1 / churn. Rule of thumb: LTV at least 3x the cost to win a customer, payback under 12 months. Churn that is not steady makes this rough."}


def runway(cash, monthly_costs, monthly_income=0) -> dict:
    c, o, i = _num(cash, "Cash", 0), _num(monthly_costs, "Monthly costs", 0), _num(monthly_income, "Monthly income", 0)
    burn = o - i
    if burn <= 0:
        return {"net_monthly_burn": round(burn, 2), "runway_months": None, "verdict": "Income covers costs: no burn at these numbers.", "note": NOTE}
    m = c / burn
    return {"net_monthly_burn": round(burn, 2), "runway_months": round(m, 1), "verdict": "Under 3 months: act now." if m < 3 else "3 to 6 months: tight, plan the next move." if m < 6 else "Over 6 months of cover.", "note": "Cash / (costs - income). It assumes both stay flat."}


def cash_cycle(receivables, revenue, inventory, cogs, payables, days=365) -> dict:
    ar, rv, inv, cg, ap, d = _num(receivables, "Receivables", 0), _num(revenue, "Revenue", 0.01), _num(inventory, "Inventory", 0), _num(cogs, "Cost of goods", 0.01), _num(payables, "Payables", 0), _num(days, "Days in period", 1, 366)
    dso, dio, dpo = ar / rv * d, inv / cg * d, ap / cg * d
    return {"days_sales_outstanding": round(dso, 1), "days_inventory": round(dio, 1), "days_payables": round(dpo, 1), "cash_conversion_days": round(dso + dio - dpo, 1),
            "note": "Cash conversion = days to collect + days stock sits - days to pay suppliers. Lower is better; negative means suppliers fund the business."}


def npv_irr(rate, cashflows) -> dict:
    r = _num(rate, "Discount rate %", -50, 100) / 100
    cfs = [_num(x, "Cash flow") for x in re.split(r"[,\s;]+", str(cashflows).strip()) if x]
    if len(cfs) < 2:
        raise AnalystError("Give at least two cash flows, starting with the cost as a negative number: -10000, 3000, 4000, 5000")
    npv = sum(cf / (1 + r) ** i for i, cf in enumerate(cfs))
    irr = None
    if min(cfs) < 0 < max(cfs):
        lo, hi = -0.99, 10.0
        f = lambda x: sum(cf / (1 + x) ** i for i, cf in enumerate(cfs))  # noqa: E731
        if f(lo) * f(hi) < 0:
            for _ in range(200):
                mid = (lo + hi) / 2
                if f(lo) * f(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            irr = (lo + hi) / 2
    return {"npv": round(npv, 2), "irr_pct": round(irr * 100, 2) if irr is not None else None, "verdict": "Worth it at this rate (NPV above zero)." if npv > 0 else "Not worth it at this rate (NPV below zero).",
            "note": "NPV discounts each period's cash back to today. The first number is period 0. Rates and cash-flow guesses drive everything: try a cautious case."}


def margins(revenue, cogs, operating_costs=0) -> dict:
    r, c, o = _num(revenue, "Revenue", 0.01), _num(cogs, "Cost of goods", 0), _num(operating_costs, "Operating costs", 0)
    gp, op = r - c, r - c - o
    return {"gross_profit": round(gp, 2), "gross_margin_pct": round(100 * gp / r, 1), "operating_profit": round(op, 2), "operating_margin_pct": round(100 * op / r, 1), "markup_pct": round(100 * gp / c, 1) if c else None,
            "note": "Margin is profit as a share of price; markup is profit as a share of cost. A 50% markup is only a 33% margin."}


def ab_test(a_visitors, a_conversions, b_visitors, b_conversions) -> dict:
    n1, x1, n2, x2 = _num(a_visitors, "A visitors", 1), _num(a_conversions, "A conversions", 0), _num(b_visitors, "B visitors", 1), _num(b_conversions, "B conversions", 0)
    if x1 > n1 or x2 > n2:
        raise AnalystError("Conversions cannot be more than visitors.")
    p1, p2 = x1 / n1, x2 / n2
    pp = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2)) or 1e-12
    z = (p2 - p1) / se
    p = math.erfc(abs(z) / math.sqrt(2))
    se2 = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"a_rate_pct": round(100 * p1, 2), "b_rate_pct": round(100 * p2, 2), "lift_pct": round(100 * (p2 - p1) / p1, 1) if p1 else None, "p_value": round(p, 4),
            "difference_95ci_points": [round(100 * (p2 - p1 - 1.96 * se2), 2), round(100 * (p2 - p1 + 1.96 * se2), 2)],
            "verdict": "A real difference is likely (p below 0.05)." if p < 0.05 else "No clear difference yet: the gap could be chance.",
            "caveats": ["Decide the sample size before you start; stopping when it looks good inflates false wins.", "Check that visitors were split randomly and counted the same way.", "A small p-value says the gap is unlikely to be chance, not that it matters to the business."], "note": NOTE}


def pareto(text: str) -> dict:
    rows = []
    for ln in str(text or "").splitlines():
        p = [x.strip() for x in ln.rsplit(",", 1)]
        if len(p) == 2 and p[0]:
            rows.append((p[0], _num(p[1], f"Value for {p[0]}", 0)))
    if len(rows) < 2:
        raise AnalystError("Give at least two lines: category, value (for example Late delivery, 42).")
    rows.sort(key=lambda r: -r[1])
    tot = sum(v for _, v in rows) or 1
    cum, out, cut = 0.0, [], None
    for n, v in rows:
        cum += v
        out.append({"category": n, "value": v, "share_pct": round(100 * v / tot, 1), "cumulative_pct": round(100 * cum / tot, 1)})
        if cut is None and cum / tot >= 0.8:
            cut = len(out)
    return {"rows": out, "vital_few": cut, "message": f"The top {cut} of {len(rows)} categories make up at least 80% of the total. Start there.", "note": NOTE}


# ------------------------------------------------------------------ modeling and SQL
MEASURE = re.compile(r"(amount|qty|quantity|price|revenue|cost|total|units|count|discount|tax|sales|profit|hours|weight|score|balance|fee|margin)", re.I)
DATEW = re.compile(r"(date|day|month|year|time|created|updated|_at$)", re.I)


def star(columns: str, grain: str = "") -> dict:
    cols = [re.sub(r"[^a-z0-9_]+", "_", c.strip().lower()).strip("_") for c in re.split(r"[,\n;]+", str(columns or "")) if c.strip()]
    cols = [c for c in cols if c]
    if len(cols) < 3:
        raise AnalystError("List the columns of your flat table, separated by commas (at least 3).")
    facts, dims, dates, keys = [], {}, [], []
    for c in cols:
        if DATEW.search(c):
            dates.append(c)
        elif c.endswith("_id") or c == "id":
            keys.append(c)
        elif MEASURE.search(c):
            facts.append(c)
        else:
            stem = c.split("_")[0]
            dims.setdefault(stem if len(stem) > 2 else c, []).append(c)
    fk = [k for k in keys if k != "id"]
    sql = []
    if dates:
        sql.append("CREATE TABLE dim_date (date_key INT PRIMARY KEY, full_date DATE, year INT, quarter INT, month INT, month_name TEXT, weekday TEXT, is_weekend BOOLEAN);")
    for k in fk:
        sql.append(f"CREATE TABLE dim_{k[:-3]} ({k} INT PRIMARY KEY, name TEXT);  -- add the descriptive columns for this entity")
    for stem, cs in dims.items():
        sql.append(f"CREATE TABLE dim_{stem} ({stem}_key INT PRIMARY KEY, " + ", ".join(f"{c} TEXT" for c in cs) + ");")
    fact_cols = ["fact_id BIGINT PRIMARY KEY"] + (["date_key INT REFERENCES dim_date"] if dates else []) + [f"{k} INT REFERENCES dim_{k[:-3]}" for k in fk] + [f"{s}_key INT REFERENCES dim_{s}" for s in dims] + [f"{m} DECIMAL(18,2)" for m in facts]
    sql.append("CREATE TABLE fact (\n  " + ",\n  ".join(fact_cols) + "\n);")
    return {"grain": grain.strip() or "State the grain in one sentence: one row per ... (for example one row per order line).", "fact_measures": facts, "dimension_candidates": {**{"date": dates}, **{k: [k] for k in fk}, **dims}, "sql": "\n".join(sql),
            "rules": ["Pick the grain first, then only measures that exist at that grain.", "Measures you can add up (amount, quantity) go in the fact; descriptions go in dimensions.", "Use whole-number surrogate keys and keep a date dimension.", "Never mix grains in one fact table (order header and order line)."],
            "caveat": "A starting point from column names. Check each guess against what the column really holds.", "note": NOTE}


_SAMPLE = """CREATE TABLE sales AS SELECT * FROM (VALUES
 (1,'West','Ana',DATE '2026-01-15',1200),(2,'West','Ana',DATE '2026-02-10',900),(3,'West','Ben',DATE '2026-02-20',1500),(4,'West','Ben',DATE '2026-03-05',700),
 (5,'East','Cy',DATE '2026-01-22',800),(6,'East','Cy',DATE '2026-02-18',1100),(7,'East','Dee',DATE '2026-03-12',1300),(8,'East','Dee',DATE '2026-03-28',600),
 (9,'East','Cy',DATE '2026-03-30',1000),(10,'West','Ana',DATE '2026-03-31',1800)) t(id, region, rep, sold_on, amount)"""
RECIPES = [
    {"id": "running", "title": "Running total", "sql": "SELECT sold_on, amount, SUM(amount) OVER (ORDER BY sold_on) AS running_total FROM sales ORDER BY sold_on", "idea": "SUM() OVER (ORDER BY ...) adds up everything so far."},
    {"id": "rank", "title": "Rank within a group", "sql": "SELECT region, rep, amount, RANK() OVER (PARTITION BY region ORDER BY amount DESC) AS rank_in_region FROM sales ORDER BY region, rank_in_region", "idea": "PARTITION BY restarts the ranking for each region. Ties share a rank (use ROW_NUMBER to break ties)."},
    {"id": "top1", "title": "Top row per group", "sql": "SELECT * FROM (SELECT region, rep, amount, ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC) AS rn FROM sales) WHERE rn = 1", "idea": "ROW_NUMBER then filter rn = 1 gives the biggest sale in each region."},
    {"id": "lag", "title": "Change from the previous row", "sql": "SELECT sold_on, amount, amount - LAG(amount) OVER (ORDER BY sold_on) AS change_vs_previous FROM sales ORDER BY sold_on", "idea": "LAG looks one row back; LEAD looks forward. The first row has no previous, so it is NULL."},
    {"id": "movavg", "title": "Moving average (3 rows)", "sql": "SELECT sold_on, amount, ROUND(AVG(amount) OVER (ORDER BY sold_on ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3 FROM sales ORDER BY sold_on", "idea": "The frame ROWS BETWEEN 2 PRECEDING AND CURRENT ROW averages this row and the two before it."},
    {"id": "pct", "title": "Percent of total and of group", "sql": "SELECT region, rep, amount, ROUND(100.0 * amount / SUM(amount) OVER (), 1) AS pct_of_all, ROUND(100.0 * amount / SUM(amount) OVER (PARTITION BY region), 1) AS pct_of_region FROM sales ORDER BY region, amount DESC", "idea": "An empty OVER () is the whole table; PARTITION BY narrows it to the group."},
    {"id": "ntile", "title": "Split into quartiles", "sql": "SELECT id, amount, NTILE(4) OVER (ORDER BY amount) AS quartile FROM sales ORDER BY amount", "idea": "NTILE(n) puts rows into n equal-sized buckets, handy for top 25% customers."},
    {"id": "first", "title": "Compare to the first value", "sql": "SELECT rep, sold_on, amount, FIRST_VALUE(amount) OVER (PARTITION BY rep ORDER BY sold_on) AS first_sale, amount - FIRST_VALUE(amount) OVER (PARTITION BY rep ORDER BY sold_on) AS vs_first FROM sales ORDER BY rep, sold_on", "idea": "FIRST_VALUE pulls the first row of each group onto every row."},
    {"id": "dedupe", "title": "Keep the latest row per key", "sql": "SELECT rep, sold_on, amount FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY rep ORDER BY sold_on DESC) AS rn FROM sales) WHERE rn = 1 ORDER BY rep", "idea": "The standard way to dedupe: number rows per key newest first and keep rn = 1."},
    {"id": "monthly", "title": "Month over month with growth %", "sql": "WITH m AS (SELECT date_trunc('month', sold_on) AS month, SUM(amount) AS total FROM sales GROUP BY 1) SELECT month, total, ROUND(100.0 * (total - LAG(total) OVER (ORDER BY month)) / LAG(total) OVER (ORDER BY month), 1) AS growth_pct FROM m ORDER BY month", "idea": "Aggregate first in a CTE, then use LAG on the totals."},
]


def recipes() -> dict:
    return {"sample_table": "sales(id, region, rep, sold_on, amount): 10 made-up rows", "recipes": [{k: r[k] for k in ("id", "title", "idea", "sql")} for r in RECIPES]}


def run_recipe(rid: str) -> dict:
    r = next((x for x in RECIPES if x["id"] == rid), None)
    if not r:
        raise AnalystError("Unknown recipe.", 404)
    import duckdb
    con = duckdb.connect(":memory:")
    try:
        con.execute(_SAMPLE)
        cur = con.execute(r["sql"])
        cols = [d[0] for d in cur.description]
        rows = [[str(v) if isinstance(v, (date, datetime)) else v for v in row] for row in cur.fetchall()]
    finally:
        con.close()
    return {"id": rid, "title": r["title"], "sql": r["sql"], "columns": cols, "rows": rows, "idea": r["idea"], "note": "Runs on a built-in made-up table in memory. Your data is not touched."}


MAP = [
    ("Running total", "SUM(amount) OVER (ORDER BY d)", "CALCULATE(SUM(T[Amount]), FILTER(ALL(T[Date]), T[Date] <= MAX(T[Date])))", "RUNNING_SUM(SUM([Amount]))", "=SUM($B$2:B2)"),
    ("Year to date", "SUM(amount) WHERE d >= start of year", "TOTALYTD(SUM(T[Amount]), Dates[Date])", "RUNNING_SUM(SUM([Amount])) (restart every year)", "=SUMIFS(B:B, A:A, \">=\"&DATE(YEAR(TODAY()),1,1))"),
    ("Same period last year", "LAG(total, 12) OVER (ORDER BY month)", "CALCULATE(SUM(T[Amount]), SAMEPERIODLASTYEAR(Dates[Date]))", "LOOKUP(SUM([Amount]), -12)", "=B14/B2-1 (12 rows apart)"),
    ("Percent of total", "amount / SUM(amount) OVER ()", "DIVIDE(SUM(T[Amount]), CALCULATE(SUM(T[Amount]), ALL(T)))", "SUM([Amount]) / TOTAL(SUM([Amount]))", "=B2/SUM(B:B)"),
    ("Rank", "RANK() OVER (ORDER BY amount DESC)", "RANKX(ALL(T[Rep]), [Total], , DESC)", "RANK(SUM([Amount]))", "=RANK(B2,B:B)"),
    ("Distinct count", "COUNT(DISTINCT customer_id)", "DISTINCTCOUNT(T[CustomerID])", "COUNTD([Customer ID])", "=SUMPRODUCT(1/COUNTIF(A:A,A:A))"),
    ("Fixed-level total (ignore filters)", "SUM(amount) OVER (PARTITION BY region)", "CALCULATE(SUM(T[Amount]), ALLEXCEPT(T, T[Region]))", "{FIXED [Region]: SUM([Amount])}", "=SUMIFS(B:B, A:A, A2)"),
    ("Conditional sum", "SUM(CASE WHEN status='Won' THEN amount END)", "CALCULATE(SUM(T[Amount]), T[Status] = \"Won\")", "SUM(IF [Status]='Won' THEN [Amount] END)", "=SUMIFS(B:B, C:C, \"Won\")"),
    ("Moving average (3)", "AVG(amount) OVER (ORDER BY d ROWS 2 PRECEDING)", "AVERAGEX(DATESINPERIOD(Dates[Date], MAX(Dates[Date]), -3, MONTH), [Total])", "WINDOW_AVG(SUM([Amount]), -2, 0)", "=AVERAGE(B2:B4)"),
    ("Safe divide", "amount / NULLIF(units, 0)", "DIVIDE([Amount], [Units])", "ZN([Amount]) / ZN([Units])", "=IFERROR(B2/C2, 0)"),
]


def dax_map() -> dict:
    return {"columns": ["Idea", "SQL", "Power BI (DAX)", "Tableau", "Excel"], "rows": [list(r) for r in MAP],
            "tips": ["Build a proper date table in Power BI and mark it as the date table: time-intelligence functions need it.", "In DAX, a measure runs in the filter context of each cell; a calculated column runs per row. Prefer measures for totals.", "Tableau level-of-detail (FIXED, INCLUDE, EXCLUDE) controls the grain of a calculation independent of the view."], "note": "Patterns to adapt: check names and ranges against your own model."}


# ------------------------------------------------------------------ design review, metrics, requirements
DASH_RULES = [
    (r"(?i)\bpie|donut", r"(?i)(\d{2,})\s*(slices|segments|categories)|more than (5|five|6|six)", "A pie or donut with many slices.", "Use a sorted bar chart: people cannot compare more than about 5 angles."),
    (r"(?i)\b3-?d\b|three.?dimensional", None, "3D charts.", "Use flat charts: 3D distorts size and hides values."),
    (r"(?i)dual.?axis|two y.?axes|secondary axis", None, "A dual-axis chart.", "Use two small charts one above the other, or index both to 100: two scales invite false stories."),
    (r"(?i)rainbow|many colou?rs|every colou?r", None, "Many colors with no meaning.", "Use one color, and a second only to highlight what matters."),
    (r"(?i)truncat|axis (does not|doesn't|not) start at (0|zero)|starts at \d", None, "A bar chart axis that does not start at zero.", "Bars must start at zero. A line chart can zoom, but label it."),
    (r"(?i)(\d{2,})\s*(kpis?|tiles|cards|metrics)", None, "Lots of KPI tiles.", "Keep 3 to 6 top-level numbers. Put the rest one click down."),
    (r"(?i)(\d{2,})\s*(charts|visuals|visualizations|widgets)", None, "Many charts on one page.", "Aim for 4 to 7 visuals per page, each answering one question."),
    (r"(?i)no (title|labels?|legend|date|filter)|unlabel", None, "Missing titles, labels or dates.", "Every chart needs a title that says the point, units, and the date range."),
    (r"(?i)scroll(ing)?|long page", None, "A long scrolling page.", "Put the answer at the top and details below; split by audience."),
    (r"(?i)red.?green|red and green", None, "Red and green as the only signal.", "Add an icon or label: 1 in 12 men cannot tell them apart."),
]
GOOD = ["Start from the decision the reader makes, then pick the numbers.", "One headline number or message at the top left.", "Compare to something: target, last period, or peers.", "Sort bars; label directly instead of a legend where possible.", "Show the date the data was last refreshed.", "Test with the real reader: can they say the point in 5 seconds?"]
CHARTS = [("compare categories", "Sorted bar chart", "Pie with many slices, 3D"), ("change over time", "Line chart (bars for few periods)", "Stacked areas with many series"), ("part of a whole (2 to 5 parts)", "Stacked bar or a single stacked bar; a pie only for 2 to 3 slices", "Donuts with many slices"),
          ("relationship of two numbers", "Scatter plot", "Dual axis lines"), ("distribution", "Histogram or box plot", "Averages alone"), ("ranking with change", "Slope chart or bar with arrows", "Rank tables with no context"), ("progress to target", "Bullet chart or a bar with a target line", "Gauges"),
          ("flow or steps", "Funnel as bars, or a Sankey for flows", "Pie"), ("a few exact numbers", "A small table with the key number in bold", "A chart for 3 values")]


def dashboard_review(text: str) -> dict:
    t = str(text or "")
    if len(t.strip()) < 10:
        raise AnalystError("Describe the dashboard in a few sentences: what charts, how many numbers, colors, axes, who reads it.")
    finds = []
    for pat, extra, problem, fix in DASH_RULES:
        if re.search(pat, t) and (extra is None or re.search(extra, t)):
            finds.append({"problem": problem, "fix": fix})
    return {"findings": finds, "charts": [{"question": q, "use": u, "avoid": a} for q, u, a in CHARTS], "good_practice": GOOD,
            "caveat": "Pattern matching on your description: it catches common mistakes, not whether the dashboard answers the right question.", "note": NOTE}


def metric_card(name="", formula="", owner="", source="", grain="", caveats="") -> dict:
    n = (name or "").strip()
    if not n:
        raise AnalystError("Give the metric a name.")
    miss = [k for k, v in (("formula", formula), ("owner", owner), ("source", source), ("grain", grain)) if not (v or "").strip()]
    text = (f"METRIC: {n}\nDefinition: {formula.strip() or 'TO FILL: exact formula in plain words and in SQL'}\nOwner: {owner.strip() or 'TO FILL: one named person'}\nSource: {source.strip() or 'TO FILL: system and table'}\n"
            f"Grain and refresh: {grain.strip() or 'TO FILL: one row per what; how often updated'}\nIncluded / excluded: TO FILL (for example refunds, test accounts, internal users)\nKnown caveats: {caveats.strip() or 'none known'}\nLast reviewed: TO FILL\nVersion: 1")
    return {"text": text, "missing": miss, "rules": ["One definition per metric, in one place, with a named owner.", "Change a definition with a version and a note, never silently.", "Show the metric's definition one click from every chart that uses it.", "Two dashboards showing different numbers for the same name is a governance failure: find the source of the difference first."], "note": NOTE}


ROLES = {
    "executive": ["What decision will this help you make, and how often?", "Which 3 numbers would you check first each morning?", "What would make you act, and what is the threshold?", "Who else sees this, and what do they care about?"],
    "manager": ["What do you do now to get these numbers, and how long does it take?", "Which breakdowns do you need (team, product, region, week)?", "What questions do you get from your boss that you can't answer today?", "What would you change in your team if the number moved?"],
    "finance": ["Which definition of revenue or cost is the official one?", "What is the cut-off for closing the period?", "Which reports must tie to the ledger, and by how much tolerance?", "Who signs off?"],
    "operations": ["What is the unit of work (order, ticket, shipment)?", "What counts as late, and who sets that?", "How fresh must the data be: real time, hourly, daily?", "What goes wrong when the data is wrong?"],
}


def requirements(role="manager", audience="", decisions="", metrics="", refresh="daily") -> dict:
    r = (role or "manager").lower()
    if r not in ROLES:
        raise AnalystError("Role must be executive, manager, finance or operations.")
    doc = (f"DASHBOARD REQUIREMENTS\nAudience: {audience.strip() or 'TO FILL'}\nDecisions it supports: {decisions.strip() or 'TO FILL'}\nKey metrics (with owner and definition): {metrics.strip() or 'TO FILL'}\nRefresh: {refresh}\n"
           "Breakdowns needed: TO FILL\nSources and access: TO FILL\nOut of scope: TO FILL\nSuccess measure (how we will know it helps): TO FILL\nSign-off: TO FILL")
    return {"questions": ROLES[r], "document": doc, "tips": ["Ask what decision it supports before what chart they want.", "Show a quick sketch or a draft early: people react better than they specify.", "Write down what is out of scope so the project can finish."], "note": NOTE}


QA = ["Totals tie to the source system or ledger (with a stated tolerance).", "Filters and date range are shown, and the default is what the reader expects.", "Every metric has a definition one click away.", "Spot-check three numbers by hand against the raw data.", "Duplicates, nulls and test records are handled and documented.", "Time zone and period boundaries are correct (month end, fiscal year).", "Numbers format correctly (units, rounding, currency).",
      "Drill-downs and filters give the same totals as the headline.", "Loads fast enough, and the refresh time is displayed.", "Someone other than the author has reviewed it.", "Access follows who is allowed to see what (personal and financial data).", "A named owner, a change log and a contact for questions."]
ROLLOUT = ["Pick one team and one question, not the whole company.", "Certify a small set of trusted datasets and label them.", "Give a 30-minute training and a one-page guide.", "Set up a place to ask questions and a person who answers.", "Review the most-used reports every quarter and retire the unused ones.", "Track adoption: who opens it, how often, and what they do next."]


def reference() -> dict:
    return {"qa": QA, "rollout": ROLLOUT, "roles": list(ROLES), "good_practice": GOOD, "note": NOTE}


def cohort_table(table: str, id_col: str, date_col: str) -> dict:
    """The same cohort view, straight from a table you imported (up to 200,000 rows)."""
    from app.services import datasets
    cols = {c["name"]: c for c in datasets.table_columns(table)}
    for n in (id_col, date_col):
        if n not in cols:
            raise AnalystError(f"The table has no column called '{n}'.")
    with datasets.get_cursor() as cur:
        rows = datasets.fetch_all(cur, f"SELECT CAST({datasets.q(id_col)} AS VARCHAR) AS i, strftime(CAST({datasets.q(date_col)} AS DATE), '%Y-%m') AS m FROM {datasets.q(table)} WHERE {datasets.q(id_col)} IS NOT NULL AND {datasets.q(date_col)} IS NOT NULL LIMIT 200000")
    return cohort_pairs([(r["i"], _month(r["m"])) for r in rows])
