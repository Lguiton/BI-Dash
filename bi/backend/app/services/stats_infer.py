"""Descriptive and inferential statistics on a sample: distribution (centre, spread, shape, confidence interval),
group comparison (hypothesis tests) and correlation. Every result says what it can and cannot tell you.

A sample is a representative part of a population; descriptive statistics summarize the sample, inferential statistics
reason from it to the population. The data loaded here is the sample.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from app.services.datasets import DataError, q
from app.services.stats_lab import _f, _need, _rows, resolve, where_clause

MAX_VALUES = 200_000
MAX_GROUPS = 12
MAX_CORR = 8


def _num(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else float(x)


def distribution(source: str, column: str, filters: list[dict] | None = None, mode: str = "and", bins: int = 20, conf: float = 0.95) -> dict:
    ident, cols = resolve(source)
    _need(cols, column, ("number",), "number column")
    if conf not in (0.9, 0.95, 0.99):
        raise DataError("Confidence must be 90%, 95% or 99%.")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(column)} IS NOT NULL"])
    c = q(column)
    r = _rows(f"SELECT COUNT(*) AS n, AVG({c}) AS mean, MEDIAN({c}) AS median, VAR_SAMP({c}) AS var, STDDEV_SAMP({c}) AS sd, MIN({c}) AS lo, MAX({c}) AS hi, "
              f"QUANTILE_CONT({c}, 0.25) AS q1, QUANTILE_CONT({c}, 0.75) AS q3, SKEWNESS({c}) AS skew, KURTOSIS({c}) AS kurt FROM {q(ident)}{w}", params)[0]
    n = int(r["n"])
    if n < 2:
        raise DataError("Need at least 2 values with these filters.")
    md = _rows(f"SELECT {c} AS v, COUNT(*) AS k FROM {q(ident)}{w} GROUP BY 1 ORDER BY k DESC, v LIMIT 3", params)
    mean, sd = float(r["mean"]), float(r["sd"] or 0)
    se = sd / math.sqrt(n)
    tcrit = float(sps.t.ppf(1 - (1 - conf) / 2, n - 1))
    ci = (mean - tcrit * se, mean + tcrit * se)
    lo, hi = float(r["lo"]), float(r["hi"])
    k = min(max(int(bins), 5), 50)
    edges = np.linspace(lo, hi, k + 1) if hi > lo else np.array([lo, lo + 1])
    vals = [float(x["v"]) for x in _rows(f"SELECT {c} AS v FROM {q(ident)}{w} LIMIT {MAX_VALUES}", params)]
    counts, _ = np.histogram(vals, bins=edges)
    cum = 0
    hist = []
    for i in range(len(counts)):
        cum += int(counts[i])
        hist.append({"from": _f(edges[i], 4), "to": _f(edges[i + 1], 4), "count": int(counts[i]), "relative": _f(int(counts[i]) / n, 4), "cumulative": _f(cum / n, 4)})
    width = float((hi - lo) / k) if hi > lo else 0.0
    sk = _num(r["skew"])
    shape = ("roughly symmetric" if sk is None or abs(sk) < 0.5 else "skewed right (a long tail of large values)" if sk > 0 else "skewed left (a long tail of small values)")
    mode_note = ""
    if md and md[0]["k"] > 1:
        mode_note = f"The most common value is {md[0]['v']:g} ({int(md[0]['k']):,} times)."
    elif md:
        mode_note = "No value repeats, so there is no useful mode."
    sentences = [f"{n:,} values: the average is {mean:,.4g}, the middle value is {float(r['median']):,.4g}, and typical spread is {sd:,.4g}. {mode_note}".strip(),
                 f"The shape is {shape}." + (" With skew, the median describes a typical value better than the mean." if sk is not None and abs(sk) >= 0.5 else ""),
                 f"If these {n:,} rows are a sample of a larger population, the population average is likely between {ci[0]:,.4g} and {ci[1]:,.4g} ({int(conf * 100)}% confidence interval)."]
    return {"column": column, "filters": fw, "n": n, "central": {"mean": _f(mean, 4), "median": _f(r["median"], 4), "mode": [{"value": _f(x["v"], 4), "count": int(x["k"])} for x in md]},
            "dispersion": {"variance": _f(r["var"], 4), "sd": _f(sd, 4), "population_variance": _f(float(r["var"]) * (n - 1) / n, 4), "population_sd": _f(math.sqrt(float(r["var"]) * (n - 1) / n), 4),
                           "cv": _f(sd / abs(mean), 4) if mean else None, "interval_width": _f(width, 4), "range": _f(hi - lo, 4), "min": _f(lo, 4), "max": _f(hi, 4), "iqr": _f(float(r["q3"]) - float(r["q1"]), 4),
                           "q1": _f(r["q1"], 4), "q3": _f(r["q3"], 4)},
            "shape": {"skewness": _f(sk, 3), "kurtosis": _f(r["kurt"], 3), "label": shape},
            "interval": {"level": conf, "low": _f(ci[0], 4), "high": _f(ci[1], 4), "std_error": _f(se, 4)}, "histogram": hist, "sentences": sentences,
            "lesson": ("Descriptive statistics summarize the sample (sample variance and standard deviation divide by n - 1; the population versions divide by N and are shown for when your rows are the entire population). The coefficient of variation is the standard deviation as a share of the mean, for comparing spread across different scales. Descriptive statistics summarize the sample: centre (mean, median, mode), dispersion (variance, standard deviation, range) and shape (skewness). "
                       "The confidence interval is inferential: it reflects sampling error and gives a range for the population value. A wider interval means less certainty, and a small or unrepresentative sample can mislead.")}


def compare(source: str, value_col: str, group_col: str, groups: list[str] | None = None, filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, value_col, ("number",), "number column")
    _need(cols, group_col, ("text", "bool"), "group column")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(value_col)} IS NOT NULL", f"{q(group_col)} IS NOT NULL"])
    g, v = q(group_col), q(value_col)
    summ = _rows(f"SELECT CAST({g} AS VARCHAR) AS g, COUNT(*) AS n, AVG({v}) AS mean, STDDEV_SAMP({v}) AS sd, MEDIAN({v}) AS median FROM {q(ident)}{w} GROUP BY 1 HAVING COUNT(*) >= 2 ORDER BY n DESC, g", params)
    if groups:
        want = [str(x) for x in groups][:MAX_GROUPS]
        summ = [s for s in summ if s["g"] in want]
    summ = summ[:MAX_GROUPS]
    if len(summ) < 2:
        raise DataError("Need at least two groups with 2 or more values each.")
    samples = {}
    for s in summ:
        rows = _rows(f"SELECT {v} AS v FROM {q(ident)}{w} AND CAST({g} AS VARCHAR) = ? LIMIT {MAX_VALUES // MAX_GROUPS}", params + [s["g"]])
        samples[s["g"]] = np.array([float(x["v"]) for x in rows])
    names = [s["g"] for s in summ]
    arrs = [samples[x] for x in names]
    out = {"value_col": value_col, "group_col": group_col, "filters": fw, "groups": [{"group": s["g"], "n": int(s["n"]), "mean": _f(s["mean"], 4), "sd": _f(s["sd"], 4), "median": _f(s["median"], 4)} for s in summ]}
    notes = ["The test asks whether the gap is bigger than chance alone would make in samples this size. It says nothing about why the groups differ."]
    if any(a.size < 15 for a in arrs):
        notes.append("Some groups have fewer than 15 values, so the result is fragile.")
    if len(arrs) == 2:
        a, b = arrs
        t = sps.ttest_ind(a, b, equal_var=False)
        diff = float(a.mean() - b.mean())
        va, vb = a.var(ddof=1) / a.size, b.var(ddof=1) / b.size
        se = math.sqrt(va + vb)
        dfw = (va + vb) ** 2 / ((va ** 2) / (a.size - 1) + (vb ** 2) / (b.size - 1)) if se > 0 else a.size + b.size - 2
        tc = float(sps.t.ppf(0.975, dfw))
        sp = math.sqrt(((a.size - 1) * a.var(ddof=1) + (b.size - 1) * b.var(ddof=1)) / (a.size + b.size - 2)) or 1.0
        d = diff / sp
        try:
            mw = float(sps.mannwhitneyu(a, b, alternative="two-sided").pvalue)
        except ValueError:
            mw = None
        p = _num(t.pvalue)
        size = "negligible" if abs(d) < 0.2 else "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
        out["test"] = {"name": "Welch t-test (two groups)", "statistic": _f(t.statistic, 3), "p": _f(p, 5), "difference": _f(diff, 4), "ci_low": _f(diff - tc * se, 4), "ci_high": _f(diff + tc * se, 4),
                       "effect_size": _f(d, 3), "effect_label": size, "backup_p": _f(mw, 5), "backup_name": "Mann-Whitney (rank-based, no bell-curve assumption)"}
        sig = p is not None and p < 0.05
        out["sentences"] = [f"{names[0]} averages {a.mean():,.4g} and {names[1]} averages {b.mean():,.4g}: a difference of {diff:,.4g} (95% interval {diff - tc * se:,.4g} to {diff + tc * se:,.4g}).",
                            (f"p = {p:.3g}: a gap this large would be unusual if the true averages were equal, so it is {'statistically significant' if sig else 'not significant'} at the 5% level." if p is not None else "p-value unavailable."),
                            f"The effect size (Cohen's d = {d:.2f}) is {size}. Significance depends on sample size; effect size says if the gap matters."]
    else:
        f = sps.f_oneway(*arrs)
        try:
            kw = float(sps.kruskal(*arrs).pvalue)
        except ValueError:
            kw = None
        allv = np.concatenate(arrs)
        ssb = sum(x.size * (x.mean() - allv.mean()) ** 2 for x in arrs)
        sst = float(((allv - allv.mean()) ** 2).sum())
        eta = ssb / sst if sst else 0.0
        p = _num(f.pvalue)
        out["test"] = {"name": f"One-way ANOVA ({len(arrs)} groups)", "statistic": _f(f.statistic, 3), "p": _f(p, 5), "effect_size": _f(eta, 3), "effect_label": "share of variation explained by the group",
                       "backup_p": _f(kw, 5), "backup_name": "Kruskal-Wallis (rank-based)"}
        sig = p is not None and p < 0.05
        out["sentences"] = [f"Comparing {len(arrs)} groups: p = {p:.3g}, so the averages {'differ by more than chance would explain' if sig else 'do not clearly differ'} at the 5% level." if p is not None else "p-value unavailable.",
                            f"The group explains {eta * 100:.1f}% of the variation in {value_col} (eta squared)."]
        notes.append("A significant ANOVA says some group differs, not which one. Look at the group averages, and be careful picking pairs afterwards (many comparisons produce false alarms).")
    out["notes"] = notes
    out["lesson"] = ("Hypothesis testing asks whether an observed difference is likely to exist in the population or just appeared by chance in this sample. "
                     "A small p-value is evidence against 'no difference', not proof, and it is not the size of the effect. Report the difference with its interval and an effect size.")
    return out


def correlate(source: str, columns: list[str], filters: list[dict] | None = None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    if not 2 <= len(columns) <= MAX_CORR or len(set(columns)) != len(columns):
        raise DataError(f"Pick 2 to {MAX_CORR} different number columns.")
    for c in columns:
        _need(cols, c, ("number",), "number column")
    w, params, fw = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in columns])
    rows = _rows(f"SELECT {', '.join(q(c) for c in columns)} FROM {q(ident)}{w} LIMIT {MAX_VALUES}", params)
    n = len(rows)
    if n < 5:
        raise DataError("Need at least 5 rows with all of these columns filled in.")
    data = {c: np.array([float(r[c]) for r in rows]) for c in columns}
    pairs = []
    for i, a in enumerate(columns):
        for b in columns[i + 1:]:
            if data[a].std() == 0 or data[b].std() == 0:
                pairs.append({"a": a, "b": b, "pearson": None, "p": None, "spearman": None, "note": "One of these never changes, so correlation is undefined."})
                continue
            pr, pp = sps.pearsonr(data[a], data[b])
            sr, _sp = sps.spearmanr(data[a], data[b])
            lo = hi = None
            if n > 3 and abs(pr) < 1:
                z, se = math.atanh(pr), 1 / math.sqrt(n - 3)
                lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
            strength = "very weak" if abs(pr) < 0.2 else "weak" if abs(pr) < 0.4 else "moderate" if abs(pr) < 0.6 else "strong" if abs(pr) < 0.8 else "very strong"
            cov_s = float(np.cov(data[a], data[b], ddof=1)[0, 1])
            pairs.append({"a": a, "b": b, "cov_sample": _f(cov_s, 4), "cov_population": _f(cov_s * (n - 1) / n, 4), "pearson": _f(pr, 3), "p": _f(pp, 5), "spearman": _f(sr, 3), "ci_low": _f(lo, 3), "ci_high": _f(hi, 3), "strength": f"{strength} {'positive' if pr > 0 else 'negative'}",
                          "r2": _f(pr * pr, 3)})
    pairs.sort(key=lambda x: -abs(x["pearson"] or 0))
    scatter = None
    if len(columns) == 2:
        idx = np.linspace(0, n - 1, min(n, 500)).astype(int)
        scatter = [{"x": _f(data[columns[0]][i], 4), "y": _f(data[columns[1]][i], 4)} for i in idx]
    sentences = []
    if pairs and pairs[0]["pearson"] is not None:
        t = pairs[0]
        sentences.append(f"The strongest link is {t['a']} with {t['b']}: r = {t['pearson']} ({t['strength']}); about {float(t['r2']) * 100:.0f}% of the movement in one lines up with the other.")
    sentences.append("Correlation measures how two numbers move together, not whether one causes the other. A third factor, or chance, can produce it.")
    notes = [f"With {len(pairs)} pairs checked, a few will look significant by luck. Treat the strongest as leads to test."] if len(pairs) > 5 else []
    return {"columns": columns, "filters": fw, "rows_used": n, "pairs": pairs, "scatter": scatter, "sentences": sentences, "notes": notes,
            "lesson": "Pearson r measures a straight-line relationship (-1 to +1); Spearman uses ranks and copes better with outliers and curves. Always look at the scatterplot, because very different patterns can share the same r."}
