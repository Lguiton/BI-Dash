"""Statistics fundamentals for every analysis role: frequency tables and Pareto, cross tables, one-sample tests of a mean, sampling distributions
(the central limit theorem you can watch), margin of error and sample size, and what kind of variable each column is.

Everything works on the sample you have. The plain-language sentences say what a result means about the population, and what it does not.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from app.services.datasets import DataError, q
from app.services.stats_lab import _f, _need, _rows, resolve, where_clause

MAX_VALUES = 50_000
MAX_LEVELS = 40
ORDINAL_WORDS = {"low", "medium", "high", "very low", "very high", "small", "large", "poor", "fair", "good", "excellent", "never", "rarely", "sometimes", "often", "always",
                 "bronze", "silver", "gold", "platinum", "strongly disagree", "disagree", "neutral", "agree", "strongly agree", "junior", "mid", "senior"}


def variable_types(source: str) -> dict:
    """Classify each column: categorical or numerical; discrete or continuous; nominal/ordinal or interval/ratio (best guess, you confirm)."""
    ident, cols = resolve(source)
    out = []
    for c, k in cols.items():
        col = q(c)
        r = _rows(f"SELECT COUNT({col}) AS n, COUNT(DISTINCT {col}) AS d, MIN({col}) AS lo FROM {q(ident)}", [])[0]
        n, d = int(r["n"]), int(r["d"])
        item = {"column": c, "kind": k, "distinct": d, "non_missing": n}
        if k in ("text", "bool"):
            vals = {str(x["v"]).strip().lower() for x in _rows(f"SELECT DISTINCT {col} AS v FROM {q(ident)} WHERE {col} IS NOT NULL LIMIT 30", [])}
            ordinal = len(vals) >= 2 and len(vals & ORDINAL_WORDS) >= max(2, int(0.6 * len(vals)))
            item.update({"type": "categorical", "level": "ordinal" if ordinal else "nominal", "group": "qualitative",
                         "note": "The values look like they have a natural order, so treat it as ordinal." if ordinal else "Categories with no natural order (nominal)."})
        elif k == "date":
            item.update({"type": "numerical", "level": "interval", "group": "quantitative", "note": "Dates are an interval scale: differences make sense, but there is no true zero."})
        else:
            integer = int(_rows(f"SELECT COUNT(*) AS k FROM {q(ident)} WHERE {col} IS NOT NULL AND {col} <> FLOOR({col})", [])[0]["k"]) == 0
            low = r["lo"]
            ratio = low is not None and float(low) >= 0
            name = c.lower()
            temp = any(w in name for w in ("temp", "celsius", "fahrenheit"))
            item.update({"type": "numerical", "subtype": "discrete (counts)" if integer and d <= max(20, n // 5) else "continuous",
                         "level": "interval" if temp else "ratio" if ratio else "interval", "group": "quantitative",
                         "note": ("Temperature in Celsius or Fahrenheit is interval (no true zero)." if temp else
                                  "Has a true zero, so ratios make sense (twice as much)." if ratio else "Can go below zero, so check whether zero is a true 'none' before using ratios.")})
        out.append(item)
    return {"source": source, "columns": out,
            "lesson": "Categorical data describes groups; numerical data are numbers. Qualitative levels are nominal (no order) or ordinal (ordered); quantitative levels are interval (no true zero) or ratio (true zero). The type decides which charts and statistics are valid. These are best guesses from the values: you know the meaning."}


def frequency(source: str, column: str, filters: list[dict] | None = None, mode: str = "and", top: int = 15) -> dict:
    """Frequency table with absolute, relative and cumulative frequency, in Pareto order (biggest first)."""
    ident, cols = resolve(source)
    _need(cols, column, ("text", "bool", "number", "date"), "column")
    top = min(max(int(top), 3), MAX_LEVELS)
    w, params, fw = where_clause(cols, filters, mode, [f"{q(column)} IS NOT NULL"])
    c = q(column)
    rows = _rows(f"SELECT CAST({c} AS VARCHAR) AS v, COUNT(*) AS k FROM {q(ident)}{w} GROUP BY 1 ORDER BY k DESC, v", params)
    total = sum(int(r["k"]) for r in rows)
    if total == 0:
        raise DataError("No values to count with these filters.")
    if len(rows) > 300 and cols[column] == "number":
        raise DataError("That number has too many different values for a frequency table. Use the Distribution tab (histogram) instead.")
    shown, cum, table = rows[:top], 0, []
    for r in shown:
        cum += int(r["k"])
        table.append({"value": r["v"], "absolute": int(r["k"]), "relative": _f(int(r["k"]) / total, 4), "cumulative": _f(cum / total, 4)})
    rest = rows[top:]
    if rest:
        k = sum(int(r["k"]) for r in rest)
        cum += k
        table.append({"value": f"Other ({len(rest):,} values)", "absolute": k, "relative": _f(k / total, 4), "cumulative": _f(cum / total, 4)})
    n80 = next((i + 1 for i, t in enumerate(table) if t["cumulative"] >= 0.8), len(table))
    sentences = [f"{total:,} values in {len(rows):,} different categories. The most common is '{table[0]['value']}' at {table[0]['relative'] * 100:.1f}%.",
                 f"The top {n80} categor{'y' if n80 == 1 else 'ies'} cover 80% or more of all rows" + (" (a Pareto pattern: a few categories make up most of the total)." if n80 <= max(1, len(rows) // 3) else ".")]
    return {"column": column, "filters": fw, "total": total, "distinct": len(rows), "table": table, "sentences": sentences,
            "lesson": "A frequency table counts each value: absolute frequency is the count, relative frequency is the share, cumulative frequency adds the shares up to 100%. Sorted biggest first with the cumulative line, it is a Pareto diagram."}


def crosstab(source: str, row_col: str, col_col: str, filters: list[dict] | None = None, mode: str = "and") -> dict:
    """Cross (contingency) table of two categorical columns, with a chi-square test of independence and Cramér's V."""
    ident, cols = resolve(source)
    _need(cols, row_col, ("text", "bool"), "row column")
    _need(cols, col_col, ("text", "bool"), "column column")
    if row_col == col_col:
        raise DataError("Pick two different columns.")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(row_col)} IS NOT NULL", f"{q(col_col)} IS NOT NULL"])
    rows = _rows(f"SELECT CAST({q(row_col)} AS VARCHAR) AS r, CAST({q(col_col)} AS VARCHAR) AS c, COUNT(*) AS k FROM {q(ident)}{w} GROUP BY 1, 2", params)
    rl, cl = sorted({r["r"] for r in rows}), sorted({r["c"] for r in rows})
    if len(rl) < 2 or len(cl) < 2:
        raise DataError("Each column needs at least 2 different values.")
    if len(rl) > 12 or len(cl) > 12:
        raise DataError("Too many different values for a readable cross table (limit 12 each). Group the rare values first in Data cleaning.")
    ri, ci = {v: i for i, v in enumerate(rl)}, {v: i for i, v in enumerate(cl)}
    m = np.zeros((len(rl), len(cl)))
    for r in rows:
        m[ri[r["r"]], ci[r["c"]]] = r["k"]
    n = m.sum()
    chi2, p, dof, exp = sps.chi2_contingency(m, correction=False)
    v = math.sqrt(chi2 / (n * (min(m.shape) - 1))) if n else 0
    small = int((exp < 5).sum())
    strength = "very weak" if v < 0.1 else "weak" if v < 0.3 else "moderate" if v < 0.5 else "strong"
    table = [{"row": rl[i], "counts": [int(x) for x in m[i]], "total": int(m[i].sum()), "row_pct": [_f(x / m[i].sum(), 3) if m[i].sum() else None for x in m[i]]} for i in range(len(rl))]
    totals = [int(x) for x in m.sum(axis=0)]
    notes = [f"{small} of {exp.size} expected counts are under 5, so the test is less reliable: group small categories."] if small else []
    sentences = [f"{int(n):,} rows. {row_col} and {col_col} are {'linked' if p < 0.05 else 'not clearly linked'} (chi-square p = {p:.3g}); the strength of the link is {strength} (Cramér's V = {v:.2f}).",
                 "A significant p-value says the pattern is unlikely to be chance, not that one causes the other." if p < 0.05 else "A large p-value means the data are consistent with no relationship; it does not prove there is none, especially in a small sample."]
    return {"row_col": row_col, "col_col": col_col, "filters": fw, "n": int(n), "col_labels": cl, "table": table, "col_totals": totals,
            "chi2": _f(chi2, 4), "dof": int(dof), "p": _f(p, 6), "cramers_v": _f(v, 3), "strength": strength, "sentences": sentences, "notes": notes,
            "lesson": "A cross (contingency) table counts rows for each pair of categories. The chi-square test asks whether the counts differ from what independence would give; Cramér's V (0 to 1) says how strong the link is."}


def test_mean(source: str, column: str, mu0: float, alternative: str = "two-sided", alpha: float = 0.05, sigma: float | None = None,
              filters: list[dict] | None = None, mode: str = "and") -> dict:
    """One-sample test of a mean against a value you hypothesised (mu0). Uses z when the population sd (sigma) is known, otherwise Student's t."""
    ident, cols = resolve(source)
    _need(cols, column, ("number",), "number column")
    if alternative not in ("two-sided", "greater", "less"):
        raise DataError("The alternative must be two-sided, greater or less.")
    if not 0.001 <= alpha <= 0.2:
        raise DataError("The significance level (alpha) should be between 0.001 and 0.2.")
    if sigma is not None and sigma <= 0:
        raise DataError("The known population standard deviation must be positive.")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(column)} IS NOT NULL"])
    vals = np.array([float(r["v"]) for r in _rows(f"SELECT {q(column)} AS v FROM {q(ident)}{w} LIMIT {MAX_VALUES}", params)])
    n = len(vals)
    if n < 3:
        raise DataError("Need at least 3 values.")
    mean, s = float(vals.mean()), float(vals.std(ddof=1))
    if s == 0 and sigma is None:
        raise DataError("The values never change, so the test can't be run.")
    use_z = sigma is not None
    sd = float(sigma) if use_z else s
    se = sd / math.sqrt(n)
    stat = (mean - mu0) / se
    dist = sps.norm if use_z else sps.t(n - 1)
    cdf, ppf, sf = (dist.cdf, dist.ppf, dist.sf) if use_z else (dist.cdf, dist.ppf, dist.sf)
    if alternative == "two-sided":
        p = 2 * float(sf(abs(stat)))
        crit = float(ppf(1 - alpha / 2))
        region = f"reject H0 if the {'z' if use_z else 't'}-statistic is below -{crit:.3f} or above {crit:.3f}"
        ci = (mean - crit * se, mean + crit * se)
    elif alternative == "greater":
        p = float(sf(stat))
        crit = float(ppf(1 - alpha))
        region = f"reject H0 if the {'z' if use_z else 't'}-statistic is above {crit:.3f}"
        ci = (mean - crit * se, math.inf)
    else:
        p = float(cdf(stat))
        crit = float(ppf(1 - alpha))
        region = f"reject H0 if the {'z' if use_z else 't'}-statistic is below -{crit:.3f}"
        ci = (-math.inf, mean + crit * se)
    reject = p < alpha
    # power: the chance of rejecting H0 if the true mean were the sample mean (observed effect). Approximate, and flattered by a lucky sample.
    delta = (mean - mu0) / se
    if use_z:
        zc = float(sps.norm.ppf(1 - (alpha / 2 if alternative == "two-sided" else alpha)))
        power = (float(sps.norm.sf(zc - delta) + sps.norm.cdf(-zc - delta)) if alternative == "two-sided" else float(sps.norm.sf(zc - delta) if alternative == "greater" else sps.norm.cdf(-zc - delta)))
    else:
        tc = float(sps.t.ppf(1 - (alpha / 2 if alternative == "two-sided" else alpha), n - 1))
        nct = sps.nct(n - 1, delta)
        power = (float(nct.sf(tc) + nct.cdf(-tc)) if alternative == "two-sided" else float(nct.sf(tc) if alternative == "greater" else nct.cdf(-tc)))
    sym = {"two-sided": "≠", "greater": ">", "less": "<"}[alternative]
    h0 = {"two-sided": "=", "greater": "≤", "less": "≥"}[alternative]
    sentences = [f"H0: the population mean {h0} {mu0:g}.  H1: the population mean {sym} {mu0:g}. Sample of {n:,}: mean {mean:,.4g}, standard error {se:,.4g}.",
                 f"The {'z' if use_z else 't'}-statistic is {stat:.3f} and the p-value is {p:.4g}. At a significance level of {alpha:g} you {'reject' if reject else 'fail to reject'} H0.",
                 ("In plain words: a sample mean this far from the hypothesised value would be rare if H0 were true." if reject else
                  "In plain words: the sample is consistent with H0. That is not proof H0 is true, only that this sample doesn't contradict it.")]
    notes = []
    if n < 30 and not use_z:
        notes.append("Small sample: the t-test assumes the values are roughly normal. Check the histogram.")
    if not use_z:
        notes.append("No known population standard deviation was given, so the sample's own spread was used (Student's t).")
    notes.append(f"Type I error (rejecting a true H0, a false positive) happens {alpha * 100:g}% of the time by design. Type II error (missing a real difference, a false negative) is the other risk: at the observed effect the test's power is about {power * 100:.0f}%, so the chance of a Type II error is about {(1 - power) * 100:.0f}% (power estimated from this same sample, so it is optimistic).")
    return {"column": column, "filters": fw, "n": n, "mean": _f(mean, 4), "sd_used": _f(sd, 4), "sd_kind": "known population sd (z)" if use_z else "sample sd (t)", "std_error": _f(se, 4),
            "mu0": mu0, "alternative": alternative, "alpha": alpha, "statistic": _f(stat, 4), "statistic_name": "z" if use_z else "t", "df": None if use_z else n - 1,
            "critical": _f(crit, 4), "rejection_region": region, "p_value": _f(p, 6), "reject": bool(reject), "decision": "reject H0" if reject else "fail to reject H0",
            "ci": {"level": 1 - alpha, "low": _f(ci[0], 4) if math.isfinite(ci[0]) else None, "high": _f(ci[1], 4) if math.isfinite(ci[1]) else None},
            "power": _f(power, 3), "sentences": sentences, "notes": notes,
            "lesson": ("A hypothesis test starts from the null (H0, the claim to test) and the alternative (H1, what you suspect). The p-value is the smallest significance level at which you could still reject H0. "
                       "Reject if p is below the significance level (alpha) you chose in advance. Two-tailed tests catch a difference either way; one-tailed tests look one way only. A statistically significant result can still be too small to matter.")}


def sampling_demo(source: str, column: str, n: int = 30, reps: int = 1000, filters: list[dict] | None = None, mode: str = "and") -> dict:
    """The central limit theorem you can watch: draw many samples, look at the distribution of their means, compare the spread with sigma / sqrt(n)."""
    ident, cols = resolve(source)
    _need(cols, column, ("number",), "number column")
    n, reps = int(n), int(reps)
    if not 2 <= n <= 500 or not 100 <= reps <= 5000:
        raise DataError("Use a sample size from 2 to 500 and 100 to 5,000 repeated samples.")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(column)} IS NOT NULL"])
    vals = np.array([float(r["v"]) for r in _rows(f"SELECT {q(column)} AS v FROM {q(ident)}{w} LIMIT {MAX_VALUES}", params)])
    N = len(vals)
    if N < 20:
        raise DataError("Need at least 20 values to draw samples from.")
    if n >= N:
        raise DataError(f"The sample size must be smaller than the {N:,} rows available.")
    rng = np.random.default_rng(7)
    means = np.array([rng.choice(vals, size=n, replace=True).mean() for _ in range(reps)])
    mu, sigma = float(vals.mean()), float(vals.std(ddof=0))
    theo = sigma / math.sqrt(n)
    emp = float(means.std(ddof=1))
    k = 20
    edges = np.linspace(means.min(), means.max(), k + 1) if means.max() > means.min() else np.array([means.min(), means.min() + 1])
    c1, _ = np.histogram(means, bins=edges)
    k2 = 20
    e2 = np.linspace(vals.min(), vals.max(), k2 + 1) if vals.max() > vals.min() else np.array([vals.min(), vals.min() + 1])
    c2, _ = np.histogram(vals, bins=e2)
    skew_pop, skew_means = float(sps.skew(vals)), float(sps.skew(means))
    return {"column": column, "filters": fw, "population_rows": N, "sample_size": n, "repeats": reps,
            "population": {"mean": _f(mu, 4), "sd": _f(sigma, 4), "skewness": _f(skew_pop, 3), "histogram": [{"x": _f((e2[i] + e2[i + 1]) / 2, 4), "count": int(c2[i])} for i in range(len(c2))]},
            "sampling": {"mean_of_means": _f(float(means.mean()), 4), "std_error_observed": _f(emp, 4), "std_error_formula": _f(theo, 4), "skewness": _f(skew_means, 3),
                         "histogram": [{"x": _f((edges[i] + edges[i + 1]) / 2, 4), "count": int(c1[i])} for i in range(len(c1))]},
            "sentences": [f"Drawing {reps:,} samples of {n} from your {N:,} rows: the sample means centre on {float(means.mean()):,.4g} (the full-data mean is {mu:,.4g}).",
                          f"Their spread (the standard error) is {emp:,.4g}, close to the formula sigma / square root of n = {theo:,.4g}. Bigger samples shrink it.",
                          f"The data's own skewness is {skew_pop:.2f}; the skewness of the sample means is {skew_means:.2f}. That pull toward a bell shape is the central limit theorem."],
            "lesson": "Whatever the shape of the underlying data, the means of many samples tend to follow a normal distribution, centred on the population mean with spread sigma / square root of n (the standard error). That is why confidence intervals and many tests work on means. It needs a large enough sample, and very skewed data needs more."}


def margin_calc(sd: float, margin: float | None = None, n: int | None = None, confidence: float = 0.95, population_known: bool = True) -> dict:
    """Margin of error for a given sample size, or the sample size needed for a target margin."""
    if sd <= 0:
        raise DataError("Standard deviation must be positive.")
    if confidence not in (0.9, 0.95, 0.99):
        raise DataError("Confidence must be 90%, 95% or 99%.")
    if (margin is None) == (n is None):
        raise DataError("Give either a target margin of error or a sample size, not both.")
    z = float(sps.norm.ppf(1 - (1 - confidence) / 2))
    if n is not None:
        if n < 2:
            raise DataError("Sample size must be at least 2.")
        t = float(sps.t.ppf(1 - (1 - confidence) / 2, n - 1)) if not population_known else z
        m = t * sd / math.sqrt(n)
        return {"mode": "margin", "sd": sd, "n": int(n), "confidence": confidence, "reliability_factor": _f(t, 4), "margin_of_error": _f(m, 4),
                "sentence": f"With {int(n):,} values and a standard deviation of {sd:g}, a {int(confidence * 100)}% interval is the sample mean plus or minus {m:,.4g}."}
    if margin <= 0:
        raise DataError("The target margin of error must be positive.")
    need = math.ceil((z * sd / margin) ** 2)
    return {"mode": "sample_size", "sd": sd, "margin_target": margin, "confidence": confidence, "reliability_factor": _f(z, 4), "n_needed": int(need),
            "sentence": f"To estimate a mean within plus or minus {margin:g} at {int(confidence * 100)}% confidence when the standard deviation is about {sd:g}, you need about {need:,} values. Halving the margin needs about four times as many."}
