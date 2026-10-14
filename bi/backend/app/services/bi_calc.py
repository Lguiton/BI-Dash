"""BI calculators: forecast method backtest, budget variance, scenarios and distribution tools. Pure arithmetic, nothing estimated by an LLM."""
from __future__ import annotations

import math
import statistics

import numpy as np
from scipy import stats as st


class CalcError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _series(values, lo=8, hi=500, name="values") -> list[float]:
    if isinstance(values, str):
        values = [v for v in values.replace("\n", ",").replace(";", ",").replace("\t", ",").split(",") if v.strip()]
    if not isinstance(values, list) or isinstance(values, bool):
        raise CalcError(f"Send {name} as a list of numbers.")
    out = []
    for v in values:
        try:
            x = float(str(v).strip().replace(" ", "")) if not isinstance(v, (int, float)) or isinstance(v, bool) else float(v)
        except ValueError:
            raise CalcError(f"'{v}' isn't a number.") from None
        if not math.isfinite(x):
            raise CalcError("Numbers only, please (no infinity or NaN).")
        out.append(x)
    if not lo <= len(out) <= hi:
        raise CalcError(f"Give between {lo} and {hi} {name} (you gave {len(out)}).")
    return out


# ------------------------------------------------------------------ forecast methods
def _ses_fit(y, alpha):
    lvl, sse = y[0], 0.0
    for v in y[1:]:
        sse += (v - lvl) ** 2
        lvl = alpha * v + (1 - alpha) * lvl
    return lvl, sse


def _best_alpha(y):
    return min((a / 20 for a in range(1, 20)), key=lambda a: _ses_fit(y, a)[1])


def _holt(y, a, b):
    lvl, tr, sse = y[0], y[1] - y[0], 0.0
    for v in y[1:]:
        f = lvl + tr
        sse += (v - f) ** 2
        new = a * v + (1 - a) * f
        tr = b * (new - lvl) + (1 - b) * tr
        lvl = new
    return lvl, tr, sse


def _methods(tr: list[float], k: int, season: int, alpha: float | None):
    n = len(tr)
    out = {}
    out["naive"] = [tr[-1]] * k
    out["average"] = [statistics.fmean(tr)] * k
    out["moving_average_3"] = [statistics.fmean(tr[-3:])] * k
    a = alpha if alpha else _best_alpha(tr)
    out["exp_smoothing"] = [_ses_fit(tr, a)[0]] * k
    ab = min(((x / 10, z / 10) for x in range(1, 10, 2) for z in range(1, 10, 2)), key=lambda p: _holt(tr, *p)[2])
    lvl, trd, _ = _holt(tr, *ab)
    out["holt_trend"] = [lvl + trd * (i + 1) for i in range(k)]
    t = np.arange(n)
    slope, icpt = np.polyfit(t, tr, 1)
    out["linear_trend"] = [float(icpt + slope * (n + i)) for i in range(k)]
    chg = [(tr[i] - tr[i - 1]) / abs(tr[i - 1]) for i in range(1, n) if tr[i - 1] != 0]
    g = statistics.fmean(chg) if chg else 0.0
    out["growth_rate"] = [tr[-1] * (1 + g) ** (i + 1) for i in range(k)] if g > -0.99 else [tr[-1]] * k
    if season >= 2 and n >= season:
        out["seasonal_naive"] = [tr[n - season + (i % season)] for i in range(k)]
    return out, a, ab


LABELS = {"naive": "Naive (repeat the last value)", "average": "Historical average", "moving_average_3": "Moving average (last 3)", "exp_smoothing": "Exponential smoothing",
          "holt_trend": "Holt (smoothing with trend)", "linear_trend": "Linear trend (a + b x time)", "growth_rate": "Growth rate (average % change)", "seasonal_naive": "Seasonal naive (same period last cycle)"}


def _metrics(actual, fc):
    err = [a - f for a, f in zip(actual, fc)]
    mae = statistics.fmean(abs(e) for e in err)
    rmse = math.sqrt(statistics.fmean(e * e for e in err))
    pe = [abs(e / a) for e, a in zip(err, actual) if a != 0]
    return {"mae": round(mae, 3), "rmse": round(rmse, 3), "mape": round(100 * statistics.fmean(pe), 2) if pe else None, "bias": round(statistics.fmean(err), 3)}


def forecast_compare(values, horizon: int = 6, holdout: int | None = None, season: int = 0, alpha: float | None = None) -> dict:
    y = _series(values, 8, 500, "values")
    n = len(y)
    if not 1 <= int(horizon) <= 60:
        raise CalcError("Horizon must be between 1 and 60 periods.")
    horizon = int(horizon)
    h = int(holdout) if holdout else min(12, max(3, n // 4))
    if not 2 <= h <= n - 4:
        raise CalcError(f"Hold out between 2 and {n - 4} periods for testing.")
    if season and (int(season) < 2 or int(season) * 2 > n):
        raise CalcError("A season length needs at least two full cycles of data (for monthly data, 12 and 24+ values).")
    if alpha is not None and not 0 < float(alpha) < 1:
        raise CalcError("Alpha must be between 0 and 1.")
    train, test = y[:-h], y[-h:]
    fcs, a, ab = _methods(train, h, int(season or 0), alpha)
    rows = []
    for key, f in fcs.items():
        rows.append({"id": key, "label": LABELS[key], **_metrics(test, f), "holdout_forecast": [round(v, 2) for v in f]})
    rows.sort(key=lambda r: r["rmse"])
    naive = next(r for r in rows if r["id"] == "naive")
    for r in rows:
        r["beats_naive"] = r["rmse"] < naive["rmse"]
    best = rows[0]
    full, _, _ = _methods(y, horizon, int(season or 0), alpha)
    t = np.arange(n)
    slope, _ = np.polyfit(t, y, 1)
    r_trend = abs(float(np.corrcoef(t, y)[0, 1])) if np.std(y) > 0 else 0.0
    warn = []
    if r_trend > 0.8 and best["id"] in ("average", "moving_average_3", "exp_smoothing", "naive"):
        warn.append("The series trends, yet the best method is flat. Flat methods (average, moving average, simple smoothing, naive) always lag behind a steady rise or fall; check the holdout is long enough and try the trend methods.")
    if r_trend > 0.8:
        warn.append(f"The series climbs or falls by about {slope:,.2f} per period. A moving average of past values can't extrapolate that: it forecasts roughly where the series was, not where it is heading.")
    if best["mape"] is None:
        warn.append("MAPE is undefined because some actual values are zero.")
    if h < 4:
        warn.append("The test window is short; the ranking may change with different data.")
    warn.append("A backtest ranks methods on past data. It does not promise the future; re-run it as new actuals arrive.")
    return {"n": n, "train": len(train), "holdout": h, "actual_holdout": [round(v, 2) for v in test], "methods": rows, "best": best["id"], "best_label": best["label"],
            "forecast": [round(v, 2) for v in full[best["id"]]], "horizon": horizon, "alpha_used": round(a, 2), "holt_alpha_beta": ab, "warnings": warn,
            "metrics_help": {"MAE": "average size of the miss, in the data's own units", "RMSE": "like MAE but punishes big misses; same units", "MAPE": "average miss as a percent of the actual; breaks at zero and favours under-forecasts", "Bias": "average (actual - forecast): positive means the forecast runs low"},
            "limit": "Eight classical methods on one series. No ARIMA or Prophet here (use the Python practice scripts), no outside factors such as promotions, and no confidence interval."}


INFOGRAPHIC_SERIES = [20000, 22000, 24000, 26000, 28000, 30000, 32000, 34000, 36000, 38000]


# ------------------------------------------------------------------ variance
def _money(v, name):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise CalcError(f"{name} must be a number.") from None
    if not math.isfinite(x):
        raise CalcError(f"{name} must be a finite number.")
    return x


def variance(rows: list[dict], threshold_pct: float = 10.0) -> dict:
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise CalcError("Send 1 to 100 lines with item, kind, budget and actual.")
    thr = _money(threshold_pct, "Threshold")
    if not 0 <= thr <= 1000:
        raise CalcError("Threshold must be 0 to 1000 percent.")
    out, rev_b = [], 0.0
    tot = {"revenue": [0.0, 0.0], "cost": [0.0, 0.0]}
    for i, r in enumerate(rows, 1):
        item = str(r.get("item", "")).strip()[:60]
        kind = str(r.get("kind", "")).strip().lower()
        if not item:
            raise CalcError(f"Line {i} needs an item name.")
        if kind not in tot:
            raise CalcError(f"Line {i} ({item}): kind must be revenue or cost.")
        b, a = _money(r.get("budget"), f"Line {i} budget"), _money(r.get("actual"), f"Line {i} actual")
        var = a - b
        pct = None if b == 0 else 100 * var / abs(b)
        fav = (var >= 0) if kind == "revenue" else (var <= 0)
        tot[kind][0] += b
        tot[kind][1] += a
        out.append({"item": item, "kind": kind, "budget": round(b, 2), "actual": round(a, 2), "variance": round(var, 2), "pct": None if pct is None else round(pct, 1),
                    "favourable": fav if var != 0 else None, "flag": bool(pct is None and var != 0 or (pct is not None and abs(pct) >= thr))})
    pb, pa = tot["revenue"][0] - tot["cost"][0], tot["revenue"][1] - tot["cost"][1]
    drivers = sorted((o for o in out if o["variance"] != 0), key=lambda o: -abs(o["variance"]))[:5]
    unfav = sorted((o for o in out if o["favourable"] is False), key=lambda o: -abs(o["variance"]))
    msg = []
    if unfav:
        msg.append(f"Biggest unfavourable gap: {unfav[0]['item']} ({unfav[0]['variance']:+,.2f}).")
    flagged = [o["item"] for o in out if o["flag"]]
    if flagged:
        msg.append(f"{len(flagged)} line(s) are beyond the {thr:g}% threshold: {', '.join(flagged[:6])}.")
    return {"lines": out, "revenue": {"budget": round(tot["revenue"][0], 2), "actual": round(tot["revenue"][1], 2), "variance": round(tot["revenue"][1] - tot["revenue"][0], 2)},
            "cost": {"budget": round(tot["cost"][0], 2), "actual": round(tot["cost"][1], 2), "variance": round(tot["cost"][1] - tot["cost"][0], 2)},
            "profit": {"budget": round(pb, 2), "actual": round(pa, 2), "variance": round(pa - pb, 2)},
            "margin_pct": {"budget": None if tot["revenue"][0] == 0 else round(100 * pb / tot["revenue"][0], 1), "actual": None if tot["revenue"][1] == 0 else round(100 * pa / tot["revenue"][1], 1)},
            "top_gaps": [{"item": o["item"], "variance": o["variance"], "favourable": o["favourable"]} for o in drivers], "summary": msg,
            "lesson": "Variance = actual - budget. For revenue, above budget is favourable; for a cost, above budget is unfavourable. Percent variance is the gap divided by the budget. Profit variance is revenue variance minus cost variance.",
            "limit": "Arithmetic on the lines you enter. It says how far you are from budget, not why; the reasons need a person who knows the business."}


# ------------------------------------------------------------------ scenarios
def _profit(price, vol, ucost, fixed):
    rev = price * vol
    cost = ucost * vol + fixed
    return rev, cost, rev - cost


def scenario(price: float, volume: float, unit_cost: float, fixed_cost: float, scenarios: list[dict] | None = None, shock_pct: float = 10.0) -> dict:
    p, v, u, f = (_money(price, "Price"), _money(volume, "Volume"), _money(unit_cost, "Unit cost"), _money(fixed_cost, "Fixed cost"))
    if min(p, v, u, f) < 0:
        raise CalcError("Price, volume and costs can't be negative.")
    shock = _money(shock_pct, "Sensitivity step")
    if not 1 <= shock <= 50:
        raise CalcError("Sensitivity step must be 1 to 50 percent.")
    sc = scenarios if scenarios is not None else [{"name": "Worst", "price_pct": -5, "volume_pct": -20, "cost_pct": 10}, {"name": "Base", "price_pct": 0, "volume_pct": 0, "cost_pct": 0}, {"name": "Best", "price_pct": 5, "volume_pct": 15, "cost_pct": -5}]
    if not isinstance(sc, list) or not 1 <= len(sc) <= 8:
        raise CalcError("Use 1 to 8 scenarios.")
    rows = []
    for s_ in sc:
        nm = str(s_.get("name", "")).strip()[:30] or "Scenario"
        pp, vp, cp = (_money(s_.get(k, 0), k) for k in ("price_pct", "volume_pct", "cost_pct"))
        if min(pp, vp, cp) < -100:
            raise CalcError(f"{nm}: a change can't be below -100%.")
        rev, cost, prof = _profit(p * (1 + pp / 100), v * (1 + vp / 100), u * (1 + cp / 100), f)
        rows.append({"name": nm, "price": round(p * (1 + pp / 100), 2), "volume": round(v * (1 + vp / 100), 1), "unit_cost": round(u * (1 + cp / 100), 2), "revenue": round(rev, 2), "cost": round(cost, 2), "profit": round(prof, 2), "margin_pct": None if rev == 0 else round(100 * prof / rev, 1)})
    rev0, cost0, prof0 = _profit(p, v, u, f)
    unit_margin = p - u
    be = None if unit_margin <= 0 else f / unit_margin
    sens = []
    for label, args in (("Price", (p, v, u, f)), ("Volume", (p, v, u, f)), ("Unit cost", (p, v, u, f)), ("Fixed cost", (p, v, u, f))):
        lo, hi = list(args), list(args)
        idx = {"Price": 0, "Volume": 1, "Unit cost": 2, "Fixed cost": 3}[label]
        lo[idx] *= (1 - shock / 100)
        hi[idx] *= (1 + shock / 100)
        pl, ph = _profit(*lo)[2], _profit(*hi)[2]
        sens.append({"driver": label, "profit_if_down": round(pl, 2), "profit_if_up": round(ph, 2), "swing": round(abs(ph - pl), 2)})
    sens.sort(key=lambda r: -r["swing"])
    notes = []
    if unit_margin <= 0:
        notes.append("Price is at or below unit cost: every unit sold loses money, so there is no break-even volume.")
    elif be is not None and be > v:
        notes.append(f"Base volume ({v:,.0f}) is below break-even ({be:,.0f} units): the base case loses money.")
    return {"base": {"revenue": round(rev0, 2), "cost": round(cost0, 2), "profit": round(prof0, 2), "margin_pct": None if rev0 == 0 else round(100 * prof0 / rev0, 1)},
            "break_even_units": None if be is None else round(be, 1), "scenarios": rows, "sensitivity": sens, "sensitivity_step_pct": shock, "notes": notes,
            "lesson": "Profit = (price - unit cost) x volume - fixed cost. A scenario changes several drivers together; a sensitivity changes one at a time to show which driver matters most (the biggest swing).",
            "limit": "A one-product model with straight-line costs. Real volume reacts to price (elasticity), which this does not model, so treat the scenarios as what-ifs, not predictions."}


# ------------------------------------------------------------------ distributions
SHAPES = [
    ("Normal", "Continuous", "Symmetric bell; mean = median = mode. Heights, measurement error. Many tests assume it."),
    ("Uniform", "Continuous", "Every value in a range equally likely; flat. Random draws, rounding error."),
    ("Binomial", "Discrete", "Number of successes in n yes/no trials with probability p. Symmetric when p = 0.5."),
    ("Poisson", "Discrete", "Count of events in a fixed interval; mean = variance = lambda. Calls per hour, defects per batch."),
    ("Exponential", "Continuous", "Waiting time between events; right-skewed, memoryless."),
    ("Log-normal", "Continuous", "Positive values whose logarithm is normal; right-skewed (income, file sizes, prices)."),
]
SHAPE_WORDS = [("Right-skewed", "A shape, not a named distribution: a long tail to the high side, usually mean > median. Several distributions look like this (exponential, log-normal, Poisson with a small mean)."),
               ("Bimodal", "A shape: two peaks, often two subgroups mixed together. Split by group before you summarise or model it.")]


def _skew_kurt(a):
    return float(st.skew(a, bias=False)), float(st.kurtosis(a, bias=False))


def dist_fit(values) -> dict:
    y = np.array(_series(values, 8, 100000, "values"))
    n = len(y)
    mean, med, sd = float(y.mean()), float(np.median(y)), float(y.std(ddof=1))
    if sd == 0:
        raise CalcError("All the values are the same, so there is no distribution to describe.")
    sk, ku = _skew_kurt(y)
    bc = (sk ** 2 + 1) / (ku + 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))) if n > 3 else None
    counts, _ = np.histogram(y, bins=min(30, max(5, int(math.sqrt(n)))))
    sm = np.convolve(counts, np.ones(3) / 3, mode="same")
    peaks = [i for i in range(1, len(sm) - 1) if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1] and sm[i] > 0.4 * sm.max()]
    shape = "roughly symmetric" if abs(sk) < 0.5 else ("right-skewed (long tail up)" if sk > 0 else "left-skewed (long tail down)")
    ints = bool(np.all(y == np.round(y)))
    pos = bool(np.all(y > 0))
    nonneg = bool(np.all(y >= 0))
    cands = []
    nrm_p = float(st.shapiro(y[:5000])[1]) if n >= 3 else None
    cands.append({"name": "Normal", "score": nrm_p, "evidence": f"Shapiro-Wilk p = {nrm_p:.3f}; skew {sk:.2f}, excess kurtosis {ku:.2f}.", "fit": "good" if nrm_p > 0.05 and abs(sk) < 0.5 else "poor"})
    if pos:
        lp = float(st.shapiro(np.log(y)[:5000])[1])
        cands.append({"name": "Log-normal", "score": lp, "evidence": f"The logarithm passes normality with p = {lp:.3f}.", "fit": "good" if lp > 0.05 else "poor"})
    if nonneg:
        ks = st.kstest(y, "expon", args=(0, mean))
        cands.append({"name": "Exponential", "score": float(ks.pvalue), "evidence": f"KS test against an exponential with mean {mean:.2f}: p = {ks.pvalue:.3f}; coefficient of variation {sd / mean:.2f} (about 1 for exponential).", "fit": "good" if ks.pvalue > 0.05 else "poor"})
    ku_u = st.kstest(y, "uniform", args=(float(y.min()), float(y.max() - y.min())))
    cands.append({"name": "Uniform", "score": float(ku_u.pvalue), "evidence": f"KS test against a flat range: p = {ku_u.pvalue:.3f}; excess kurtosis {ku:.2f} (about -1.2 for uniform).", "fit": "good" if ku_u.pvalue > 0.05 else "poor"})
    if ints and nonneg:
        disp = float(y.var(ddof=1) / mean) if mean > 0 else float("nan")
        cands.append({"name": "Poisson", "score": None, "evidence": f"Whole numbers; variance/mean = {disp:.2f} (about 1 for Poisson; well above 1 means over-dispersed).", "fit": "good" if 0.8 <= disp <= 1.25 else "poor"})
    bimodal = (bc is not None and bc > 0.555 and len(peaks) >= 2)
    if bimodal:
        cands.insert(0, {"name": "Bimodal (two groups)", "score": None, "evidence": f"Bimodality coefficient {bc:.2f} (above 0.555 suggests two peaks) and {len(peaks)} peaks in the histogram.", "fit": "good"})
    order = {"good": 0, "poor": 1}
    cands.sort(key=lambda c: (order[c["fit"]], -(c["score"] or 0)))
    advice = []
    if bimodal:
        advice.append("Two peaks usually mean two groups mixed together. Find the splitting column (region, product, customer type) and analyse each group separately.")
    if sk > 1 and pos:
        advice.append("Strong right skew with positive values: report the median, or take logs before using methods that assume a bell shape.")
    if abs(sk) < 0.5 and nrm_p > 0.05:
        advice.append("Close to normal: mean and standard deviation describe it well, and t-tests and linear models are reasonable.")
    z = np.abs((y - mean) / sd)
    out = int((z > 3).sum())
    if out:
        advice.append(f"{out} value(s) are more than 3 standard deviations from the mean; look at them before you fit anything.")
    advice.append("Always look at the picture too: a histogram and a Q-Q plot show what a single number can hide.")
    hist_counts, edges = np.histogram(y, bins=min(20, max(5, int(math.sqrt(n)))))
    return {"n": n, "mean": round(mean, 4), "median": round(med, 4), "sd": round(sd, 4), "min": float(y.min()), "max": float(y.max()), "skew": round(sk, 3), "excess_kurtosis": round(ku, 3),
            "shape": shape, "mean_vs_median": "mean above median: tail on the high side" if mean > med * (1 + 1e-9) and sk > 0.2 else ("mean below median: tail on the low side" if mean < med and sk < -0.2 else "mean and median are close"),
            "candidates": cands, "advice": advice, "histogram": [{"from": round(float(edges[i]), 3), "to": round(float(edges[i + 1]), 3), "count": int(c)} for i, c in enumerate(hist_counts)],
            "limit": "Tests reject or keep a candidate; they don't prove the data came from it. With very large samples every real-world column fails a normality test, and parameters estimated from the same data make KS p-values optimistic."}


def _need(params: dict, key: str, lo=None, hi=None, integer=False):
    if key not in params:
        raise CalcError(f"Missing {key}.")
    v = _money(params[key], key)
    if integer and v != int(v):
        raise CalcError(f"{key} must be a whole number.")
    if lo is not None and v < lo or hi is not None and v > hi:
        raise CalcError(f"{key} must be between {lo} and {hi}.")
    return int(v) if integer else v


def dist_calc(kind: str, params: dict, x: float | None = None, p: float | None = None) -> dict:
    k = (kind or "").lower()
    pr = params or {}
    if k == "normal":
        mu, sg = _need(pr, "mean"), _need(pr, "sd", 1e-12, 1e12)
        d, cont = st.norm(mu, sg), True
        facts = {"mean": mu, "variance": sg ** 2, "median": mu, "mode": mu, "skew": "none (symmetric)"}
    elif k == "uniform":
        a, b = _need(pr, "low"), _need(pr, "high")
        if b <= a:
            raise CalcError("high must be greater than low.")
        d, cont = st.uniform(a, b - a), True
        facts = {"mean": (a + b) / 2, "variance": (b - a) ** 2 / 12, "median": (a + b) / 2, "mode": "any value in the range", "skew": "none"}
    elif k == "exponential":
        r = _need(pr, "rate", 1e-12, 1e12)
        d, cont = st.expon(scale=1 / r), True
        facts = {"mean": 1 / r, "variance": 1 / r ** 2, "median": math.log(2) / r, "mode": 0, "skew": "right (always 2)"}
    elif k == "lognormal":
        mu, sg = _need(pr, "log_mean"), _need(pr, "log_sd", 1e-12, 50)
        d, cont = st.lognorm(s=sg, scale=math.exp(mu)), True
        facts = {"mean": math.exp(mu + sg ** 2 / 2), "variance": (math.exp(sg ** 2) - 1) * math.exp(2 * mu + sg ** 2), "median": math.exp(mu), "mode": math.exp(mu - sg ** 2), "skew": "right"}
    elif k == "binomial":
        n_, pp = _need(pr, "n", 1, 100000, True), _need(pr, "p", 0, 1)
        d, cont = st.binom(n_, pp), False
        facts = {"mean": n_ * pp, "variance": n_ * pp * (1 - pp), "median": float(d.median()), "mode": math.floor((n_ + 1) * pp), "skew": "none if p = 0.5, else toward the longer tail"}
    elif k == "poisson":
        lam = _need(pr, "lambda", 1e-9, 1e6)
        d, cont = st.poisson(lam), False
        facts = {"mean": lam, "variance": lam, "median": float(d.median()), "mode": math.floor(lam), "skew": "right (less as lambda grows)"}
    else:
        raise CalcError("Kind must be normal, uniform, exponential, lognormal, binomial or poisson.")
    out = {"kind": k, "continuous": cont, "facts": {a: (round(b, 6) if isinstance(b, float) else b) for a, b in facts.items()}}
    if x is not None:
        xv = _money(x, "x")
        if not cont and xv != int(xv):
            raise CalcError("x must be a whole number for this distribution.")
        out["at"] = {"x": xv, ("pdf" if cont else "pmf"): round(float(d.pdf(xv) if cont else d.pmf(int(xv))), 8), "cdf": round(float(d.cdf(xv)), 8), "tail": round(float(d.sf(xv)), 8)}
        out["reading"] = f"P(X <= {xv:g}) = {out['at']['cdf']:.4f}; P(X > {xv:g}) = {out['at']['tail']:.4f}." + ("" if not cont else " For a continuous variable the density is not a probability; areas are.")
    if p is not None:
        pv = _money(p, "p")
        if not 0 < pv < 1:
            raise CalcError("The percentile must be between 0 and 1 (exclusive).")
        out["quantile"] = {"p": pv, "value": round(float(d.ppf(pv)), 6)}
    return out


def dist_reference() -> dict:
    return {"shapes": [{"name": a, "type": b, "note": c} for a, b, c in SHAPES], "shape_words": [{"name": a, "note": b} for a, b in SHAPE_WORDS],
            "slips": ["The poster lists 'Bimodal' and 'Skewed (right)' as if they were distributions. They are shapes: many different distributions can be skewed, and a bimodal shape is usually two groups mixed together.",
                      "'Mean > median > mode' for a right-skewed distribution is a good rule of thumb, not a law; it can fail, especially for discrete or lumpy data.",
                      "'Right-skewed' for the Poisson distribution is only true for a small lambda; as lambda grows it becomes nearly symmetric.",
                      "Exponential and log-normal are drawn almost the same on the poster; they differ at the start: exponential is highest at zero, log-normal is zero at zero and peaks later."]}
