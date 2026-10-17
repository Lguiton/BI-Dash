"""Data science depth: Bayesian tests, power, survival, optimisation, geospatial, fairness, causal and bootstrap."""
from __future__ import annotations

import math
import random

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "scientist"
lab(T, "Data science depth: experiments, survival, optimization, fairness, causal inference and uncertainty")


def bayes_ab(a):
    ca, na, cb, nb = (int(num(a, k, lo=0)) for k in ("conv_a", "n_a", "conv_b", "n_b"))
    if ca > na or cb > nb or na < 1 or nb < 1:
        raise ProError("Conversions cannot exceed visitors.")
    rnd, n = random.Random(int(num(a, "seed", lo=0))), 20000
    wins, lift = 0, []
    for _ in range(n):
        pa, pb = rnd.betavariate(1 + ca, 1 + na - ca), rnd.betavariate(1 + cb, 1 + nb - cb)
        wins += pb > pa
        lift.append((pb - pa) / pa if pa else 0)
    lift.sort()
    p = wins / n
    return {"rate_a": r(ca / na, 4), "rate_b": r(cb / nb, 4), "chance_b_beats_a": r(p, 3), "expected_lift_pct": r(100 * sum(lift) / n, 1), "lift_95_interval_pct": f"{r(100 * lift[int(0.025 * n)], 1)} to {r(100 * lift[int(0.975 * n)], 1)}",
            "verdict": "B is very likely better." if p > 0.95 else "A is very likely better." if p < 0.05 else "Not settled: keep collecting data or accept the uncertainty.",
            "how": "Beta-Binomial model with a flat prior; compare 20,000 random draws of each true rate. Seeded for repeat results. Decide the stopping rule before you start: peeking and stopping early inflates false wins."}


tool(T, "bayes_ab", "Bayesian A/B test", "Chance that B beats A, with a lift range.", [("conv_a", "Conversions A", 120), ("n_a", "Visitors A", 2400), ("conv_b", "Conversions B", 150), ("n_b", "Visitors B", 2400), ("seed", "Seed", 5)], bayes_ab)


def _z(p):
    # inverse normal CDF (Acklam approximation)
    a1 = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b1 = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c1 = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d1 = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c1[0] * q + c1[1]) * q + c1[2]) * q + c1[3]) * q + c1[4]) * q + c1[5]) / ((((d1[0] * q + d1[1]) * q + d1[2]) * q + d1[3]) * q + 1)
    if p <= 1 - pl:
        q = p - 0.5
        t = q * q
        return (((((a1[0] * t + a1[1]) * t + a1[2]) * t + a1[3]) * t + a1[4]) * t + a1[5]) * q / (((((b1[0] * t + b1[1]) * t + b1[2]) * t + b1[3]) * t + b1[4]) * t + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c1[0] * q + c1[1]) * q + c1[2]) * q + c1[3]) * q + c1[4]) * q + c1[5]) / ((((d1[0] * q + d1[1]) * q + d1[2]) * q + d1[3]) * q + 1)


def power(a):
    base, mde, alpha, pw, daily = num(a, "baseline_rate_pct", lo=0.01, hi=99.9) / 100, num(a, "relative_lift_pct", lo=0.01) / 100, num(a, "alpha", lo=0.001, hi=0.5), num(a, "power", lo=0.5, hi=0.999), num(a, "visitors_per_day", lo=1)
    p2 = base * (1 + mde)
    if p2 >= 1:
        raise ProError("The new rate would be 100% or more: lower the lift.")
    za, zb = _z(1 - alpha / 2), _z(pw)
    pbar = (base + p2) / 2
    n = ((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(base * (1 - base) + p2 * (1 - p2))) ** 2) / (p2 - base) ** 2
    n = math.ceil(n)
    return {"per_group": n, "total": 2 * n, "days_needed": math.ceil(2 * n / daily), "new_rate_pct": r(p2 * 100, 3),
            "tips": ["Halving the lift you want to detect needs about 4 times the sample.", "Run for whole weeks to cover weekday patterns.", "If the sample is out of reach, test a bigger change or use a metric with more signal."]}


tool(T, "sample_size", "Sample size and test length", "Visitors needed to detect a lift.", [("baseline_rate_pct", "Current conversion rate (%)", 5), ("relative_lift_pct", "Smallest lift worth detecting (% of the rate)", 10), ("alpha", "Significance level", 0.05), ("power", "Power", 0.8), ("visitors_per_day", "Visitors per day", 1500)], power)


def km(a):
    rows = lines(a, "data", "the data", 3)
    obs = []
    for p in rows:
        if len(p) < 2:
            raise ProError("Each line: time, event (1 = event happened, 0 = still going / lost).")
        obs.append((float(p[0]), int(float(p[1]))))
    obs.sort()
    s, atrisk, curve, med = 1.0, len(obs), [], None
    i = 0
    while i < len(obs):
        t = obs[i][0]
        d = c = 0
        while i < len(obs) and obs[i][0] == t:
            d += obs[i][1]
            c += 1
            i += 1
        if d:
            s *= 1 - d / atrisk
            curve.append({"time": t, "at_risk": atrisk, "events": d, "survival": r(s, 4)})
            if med is None and s <= 0.5:
                med = t
        atrisk -= c
    return {"curve": curve, "median_survival": med if med is not None else "not reached", "events": sum(e for _, e in obs), "censored": sum(1 for _, e in obs if not e),
            "how": "Kaplan-Meier: at each event time multiply survival by (1 - events / people still at risk). Censored people (still active) count until they leave. Use it for customer churn, time to repair, equipment life.", "tip": "Compare groups with a log-rank test; add covariates with a Cox model."}


tool(T, "kaplan_meier", "Kaplan-Meier survival", "How long things last, with censoring.", [("data", "Lines of: time, event (1 or 0)", "3,1\n5,1\n6,0\n8,1\n9,1\n12,0\n14,1\n15,0", "area")], km)


def lp(a):
    try:
        from scipy.optimize import linprog
    except ImportError:
        raise ProError("The optimiser (scipy) is not installed.") from None
    prods = lines(a, "products", "the products")
    cons = lines(a, "limits", "the limits")
    names = [p[0] for p in prods]
    prof = [float(p[1]) for p in prods]
    A, b, cn = [], [], []
    for p in cons:
        if len(p) != len(names) + 2:
            raise ProError(f"{p[0]}: give a use per product ({len(names)}) and then the limit.")
        A.append([float(x) for x in p[1:-1]])
        b.append(float(p[-1]))
        cn.append(p[0])
    res = linprog([-x for x in prof], A_ub=A, b_ub=b, bounds=[(0, None)] * len(names), method="highs")
    xs = [float(v) for v in res.x] if res.status == 0 else []
    if res.status != 0:
        raise ProError("No solution found: " + (res.message or "check the limits") + ".")
    used = [sum(A[i][j] * xs[j] for j in range(len(names))) for i in range(len(A))]
    duals = [float(d) for d in getattr(res.ineqlin, "marginals", [])]
    return {"plan": [{"product": n, "quantity": r(q, 2)} for n, q in zip(names, xs)], "total_profit": r(float(-res.fun), 2),
            "limits": [{"limit": c, "used": r(u, 2), "available": bb, "binding": abs(u - bb) < 1e-6, "value_of_one_more_unit": r(-d, 2) if d is not None else None} for c, u, bb, d in zip(cn, used, b, duals or [None] * len(b))],
            "how": "Linear programming picks quantities that maximise profit without exceeding any limit. Binding limits are the bottlenecks; the value of one more unit shows what extra capacity is worth.", "tip": "Quantities may come out fractional: round and recheck, or use integer programming."}


tool(T, "optimize_lp", "Optimization (linear programming)", "Best product mix under limits.", [("products", "Lines of: product, profit per unit", "Chairs,45\nTables,80", "area"), ("limits", "Lines of: limit name, use per product..., available", "Wood,5,20,400\nLabor,10,15,450", "area")], lp)


def geo(a):
    lat1, lon1, lat2, lon2 = (num(a, k, lo=-180, hi=180) for k in ("lat1", "lon1", "lat2", "lon2"))
    if abs(lat1) > 90 or abs(lat2) > 90:
        raise ProError("Latitude must be between -90 and 90.")
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * R * math.asin(math.sqrt(h))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return {"distance_km": r(d, 2), "distance_miles": r(d / 1.609344, 2), "initial_bearing_deg": r(brg, 1), "drive_distance_note": "Straight-line (great-circle) distance. Roads are often 20 to 40% longer.", "tips": ["Never use plain degrees as distance: a degree of longitude shrinks toward the poles.", "For many points use a spatial index (geohash, H3, R-tree) instead of comparing all pairs."]}


tool(T, "haversine", "Distance between two places", "Great-circle distance and bearing.", [("lat1", "Latitude 1", 36.0395), ("lon1", "Longitude 1", -114.9817), ("lat2", "Latitude 2", 36.1699), ("lon2", "Longitude 2", -115.1398)], geo)


def fairness(a):
    rows = lines(a, "groups", "the groups", 2)
    out = []
    for p in rows:
        if len(p) < 5:
            raise ProError("Each line: group, people, selected, truly qualified, selected among qualified.")
        g, n, sel, q, tp = p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4])
        if n <= 0 or sel > n or tp > q or tp > sel:
            raise ProError(f"{g}: numbers do not add up.")
        out.append({"group": g, "selection_rate": sel / n, "true_positive_rate": tp / q if q else None})
    top = max(x["selection_rate"] for x in out)
    res = []
    for x in out:
        ratio = x["selection_rate"] / top if top else 1
        res.append({"group": x["group"], "selection_rate": r(x["selection_rate"], 3), "ratio_to_highest": r(ratio, 3), "four_fifths_rule": "pass" if ratio >= 0.8 else "FAIL", "true_positive_rate": r(x["true_positive_rate"], 3) if x["true_positive_rate"] is not None else None})
    tprs = [x["true_positive_rate"] for x in out if x["true_positive_rate"] is not None]
    gap = max(tprs) - min(tprs) if tprs else None
    return {"groups": res, "equal_opportunity_gap": r(gap, 3) if gap is not None else None, "verdict": "Selection rates fail the four-fifths guideline for at least one group: investigate." if any(x["four_fifths_rule"] == "FAIL" for x in res) else "Passes the four-fifths guideline on these numbers.",
            "limits": ["Different fairness measures can conflict: pick the one that fits the harm you are trying to prevent.", "Small groups give noisy rates: show the counts.", "This is a screening check, not a legal finding. Involve legal and domain experts for high-stakes decisions."]}


tool(T, "fairness_audit", "Fairness audit", "Selection rates, four-fifths rule and equal opportunity.", [("groups", "Lines of: group, people, selected, truly qualified, selected among qualified", "Group A,500,200,250,170\nGroup B,400,110,200,110", "area")], fairness)


def did(a):
    tb, ta, cb, ca = (num(a, k) for k in ("treated_before", "treated_after", "control_before", "control_after"))
    effect = (ta - tb) - (ca - cb)
    return {"treated_change": r(ta - tb, 3), "control_change": r(ca - cb, 3), "difference_in_differences": r(effect, 3), "relative_to_treated_before_pct": r(100 * effect / tb, 1) if tb else None,
            "assumptions": ["Parallel trends: without the change both groups would have moved alike. Check several periods before the change.", "No other event hit only one group at the same time.", "Groups were not chosen because of the outcome."], "how": "The control group's change estimates what would have happened to the treated group anyway; the extra change is the effect."}


tool(T, "diff_in_diff", "Difference in differences", "Effect of a change using a control group.", [("treated_before", "Treated group before", 100), ("treated_after", "Treated group after", 130), ("control_before", "Control group before", 95), ("control_after", "Control group after", 110)], did)


def boot(a):
    xs = [float(v) for v in txt(a, "values", "the values").replace("\n", ",").split(",") if v.strip()]
    if len(xs) < 5:
        raise ProError("Give at least 5 values.")
    stat, n, seed = txt(a, "statistic").lower(), int(num(a, "resamples", lo=200, hi=50000)), int(num(a, "seed", lo=0))
    f = {"mean": lambda v: sum(v) / len(v), "median": lambda v: sorted(v)[len(v) // 2] if len(v) % 2 else sum(sorted(v)[len(v) // 2 - 1:len(v) // 2 + 1]) / 2}.get(stat)
    if not f:
        raise ProError("Statistic must be mean or median.")
    rnd = random.Random(seed)
    s = sorted(f([rnd.choice(xs) for _ in xs]) for _ in range(n))
    return {"estimate": r(f(xs), 4), "ci95_low": r(s[int(0.025 * n)], 4), "ci95_high": r(s[int(0.975 * n)], 4), "n": len(xs),
            "how": "Resample your own data with replacement many times and take the middle 95% of the results. No formula assumptions.", "tips": ["Works for medians and other awkward statistics.", "Tiny or very skewed samples give wide, unstable ranges: that is honest information.", "Resample whole customers or units, not rows, when rows belong together."]}


tool(T, "bootstrap_ci", "Bootstrap confidence interval", "Uncertainty for a mean or median.", [("values", "Values (comma)", "12,15,11,19,14,13,40,16,12,15", "area"), ("statistic", "mean or median", "median"), ("resamples", "Resamples", 5000), ("seed", "Seed", 11)], boot)

ref(T, "causal", "Causal inference ladder", [
    {"title": "From weakest to strongest evidence", "head": ["Method", "Idea", "Needs"], "rows": [["Correlation", "Two things move together", "Nothing, and it proves little"], ["Controlled comparison", "Adjust for known differences", "You measured the confounders"], ["Difference in differences", "Compare change against a control", "Parallel trends"], ["Regression discontinuity", "Compare just above and below a cutoff", "A sharp rule and no gaming"], ["Instrumental variable", "Use something that nudges treatment only", "A valid instrument"], ["Randomized experiment", "Chance assigns treatment", "Ability to randomize"]]},
    {"title": "Habits", "items": ["Draw the causal story (who affects whom) before modeling.", "Ask what else could explain it and look for it.", "A prediction model is not a causal model: do not read its weights as effects."]}])
ref(T, "expcheck", "Experiment checklist", [
    {"title": "Before", "items": ["One clear question and one main metric; decide guardrail metrics too.", "Calculate sample size and run time; fix the stopping rule.", "Randomize at the right unit (user, not page view); check there is no overlap between groups."]},
    {"title": "During and after", "items": ["Check the split is as planned (sample ratio mismatch means a bug).", "Do not peek and stop early on a good-looking number.", "Run whole weeks; watch for novelty effects.", "Report the effect with a range, and note what you did not test.", "Many metrics or segments mean many chances for a false win: correct or treat extras as ideas."]}])
ref(T, "ethics", "Ethics and responsible data", [
    {"title": "Audit questions", "items": ["Who could be harmed by an error, and who checks?", "Is the data collected with permission and used for that purpose?", "Is any group missing from or mislabeled in the data?", "Could a variable stand in for a protected trait (postcode, name)?", "Can a person see, contest and correct a decision about them?", "Is the model's limit written down for the people who use it?"]},
    {"title": "Keep records", "items": ["Document data sources, known gaps, tests run and who approved release.", "Monitor after release: errors, drift and complaints."]}])
