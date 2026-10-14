"""Survey numbers and probability tables: can I trust this percentage, is this gap real, what do these joint probabilities say?

Built from a data-analysis cheat sheet (joint and marginal distributions, correlation, regression) and a vendor survey report with
N=150 and subgroups of 30 to 55. The reports quote percentages without saying how much they can move; these tools show it.
Assumes a simple random sample. Real surveys with weights or clusters have wider error. Thresholds are rules of thumb.
"""
from __future__ import annotations

import math
import re


class SurveyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


Z = {90: 1.6449, 95: 1.96, 99: 2.5758}


def _z(conf) -> float:
    try:
        c = int(conf)
    except (TypeError, ValueError):
        raise SurveyError("Confidence must be 90, 95 or 99.")
    if c not in Z:
        raise SurveyError("Confidence must be 90, 95 or 99.")
    return Z[c]


def _pct(v, name="Percent") -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100:
        raise SurveyError(f"{name} must be 0 to 100.")
    return float(v) / 100


def _n(v, name="Sample size") -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 2 or v != int(v):
        raise SurveyError(f"{name} must be a whole number of at least 2.")
    return int(v)


def _wilson(p: float, n: int, z: float):
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)


def proportion(pct: float, n: int, confidence: int = 95) -> dict:
    p, n, z = _pct(pct), _n(n), _z(confidence)
    lo, hi = _wilson(p, n, z)
    moe = z * math.sqrt(p * (1 - p) / n)
    worst = z * math.sqrt(0.25 / n)
    notes = []
    if n < 100:
        notes.append(f"With {n} people this is a rough estimate: read it as a direction, not a number.")
    if n * p < 10 or n * (1 - p) < 10:
        notes.append("Very few people are in one of the answer groups, so the usual formula is shaky; the interval shown (Wilson) is safer.")
    return {"percent": round(p * 100, 1), "n": n, "confidence": confidence, "low": round(lo * 100, 1), "high": round(hi * 100, 1),
            "plus_minus_points": round(moe * 100, 1), "worst_case_plus_minus_points": round(worst * 100, 1),
            "sentence": f"{pct:g}% of {n} could plausibly be anywhere from {lo * 100:.0f}% to {hi * 100:.0f}% in the whole group.", "notes": notes,
            "lesson": "Every survey percentage is an estimate. Smaller groups swing more."}


def compare(pct1: float, n1: int, pct2: float, n2: int, confidence: int = 95) -> dict:
    p1, p2, n1, n2, z = _pct(pct1, "First percent"), _pct(pct2, "Second percent"), _n(n1, "First sample size"), _n(n2, "Second sample size"), _z(confidence)
    d = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
    se0 = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    zs = d / se0 if se0 else 0.0
    pv = math.erfc(abs(zs) / math.sqrt(2))
    lo, hi = d - z * se, d + z * se
    real = pv < (100 - confidence) / 100
    notes = []
    if min(n1, n2) < 60:
        notes.append("At least one group is small (under 60). Treat even a 'real' gap as a lead to check.")
    if abs(d) < 0.02:
        notes.append("The gap is under 2 points: even if real, it is too small to act on.")
    return {"difference_points": round(d * 100, 1), "low": round(lo * 100, 1), "high": round(hi * 100, 1), "z": round(zs, 2), "p_value": round(pv, 4), "likely_real": real,
            "verdict": ("Probably a real difference" if real else "Within the noise: the data does not show a difference") + f" at {confidence}% confidence.",
            "notes": notes + ["This assumes two separate random samples. The same people answering twice, overlapping groups, or many comparisons at once need a different test."],
            "lesson": "A big-looking gap between small groups can be luck. Check the interval, not the headline."}


def sample_size(moe_points: float, confidence: int = 95, expected_pct: float = 50) -> dict:
    z = _z(confidence)
    p = _pct(expected_pct, "Expected percent")
    if isinstance(moe_points, bool) or not isinstance(moe_points, (int, float)) or not 0.1 <= moe_points <= 50:
        raise SurveyError("Margin must be between 0.1 and 50 points.")
    m = moe_points / 100
    n = math.ceil(z * z * p * (1 - p) / (m * m))
    return {"needed": n, "per_subgroup_note": f"Each subgroup you want to report on needs about this many on its own: {n} people for ±{moe_points:g} points.",
            "lesson": "Halving the margin needs four times the people."}


def multi_select(text: str, n: int | None = None) -> dict:
    rows = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = [x.strip() for x in ln.split("|")]
        if len(parts) != 2 or not re.fullmatch(r"\d+(\.\d+)?%?", parts[1]):
            raise SurveyError(f"Line '{ln}': use 'answer | percent'.")
        rows.append((parts[0], float(parts[1].rstrip("%"))))
    if len(rows) < 2:
        raise SurveyError("Give at least two answers.")
    total = round(sum(v for _, v in rows), 1)
    out = {"answers": [{"answer": a, "percent": v} for a, v in rows], "total": total}
    if total > 100.5:
        out["verdict"] = f"The answers add to {total}%, so people could pick more than one. 'Greatest' or 'top' wording cannot be read as one choice each."
        out["average_picks_per_person"] = round(total / 100, 2)
    elif total < 99.5:
        out["verdict"] = f"The answers add to {total}%: the rest chose something else, skipped, or were left out."
    else:
        out["verdict"] = "The answers add to about 100%, consistent with one choice each."
    if n:
        n = _n(n)
        out["head_count"] = [{"answer": a, "people": round(v / 100 * n)} for a, v in rows]
    return out


def joint(text: str) -> dict:
    """Lines: x | y | probability. Returns marginals, conditionals, independence check and expectations."""
    cells, xs, ys = {}, [], []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        p = [s.strip() for s in ln.split("|")]
        if len(p) != 3:
            raise SurveyError(f"Line '{ln}': use 'x | y | probability'.")
        try:
            v = float(p[2])
        except ValueError:
            raise SurveyError(f"Line '{ln}': probability must be a number.")
        if not 0 <= v <= 1:
            raise SurveyError(f"Line '{ln}': a probability must be between 0 and 1.")
        if (p[0], p[1]) in cells:
            raise SurveyError(f"The pair ({p[0]}, {p[1]}) appears twice.")
        cells[(p[0], p[1])] = v
        if p[0] not in xs:
            xs.append(p[0])
        if p[1] not in ys:
            ys.append(p[1])
    if len(cells) < 4 or len(xs) < 2 or len(ys) < 2:
        raise SurveyError("Give at least a 2 by 2 table: one line per cell.")
    total = sum(cells.values())
    if abs(total - 1) > 1e-6:
        raise SurveyError(f"The probabilities add to {total:g}, not 1. Check each cell.")
    px = {x: round(sum(cells.get((x, y), 0) for y in ys), 6) for x in xs}
    py = {y: round(sum(cells.get((x, y), 0) for x in xs), 6) for y in ys}
    cond = [{"given_x": x, "y": y, "p": round(cells.get((x, y), 0) / px[x], 6) if px[x] else None} for x in xs for y in ys]
    gap = max(abs(cells.get((x, y), 0) - px[x] * py[y]) for x in xs for y in ys)
    indep = gap < 1e-6
    out = {"x_values": xs, "y_values": ys, "marginal_x": px, "marginal_y": py, "conditional_y_given_x": cond,
           "independent": indep, "largest_gap_from_independence": round(gap, 6),
           "verdict": "X and Y are independent: knowing one tells you nothing about the other." if indep else f"X and Y are NOT independent (largest gap {gap:.3f} between the cell and the product of its marginals)."}
    try:
        nx = {float(x): v for x, v in px.items()}
        ny = {float(y): v for y, v in py.items()}
        ex = sum(k * v for k, v in nx.items())
        ey = sum(k * v for k, v in ny.items())
        exy = sum(float(x) * float(y) * v for (x, y), v in cells.items())
        out["expected_x"], out["expected_y"], out["covariance"] = round(ex, 6), round(ey, 6), round(exy - ex * ey, 6)
    except ValueError:
        pass
    out["lesson"] = "Marginals are row and column totals; conditionals divide a cell by its total. Independent means every cell equals the product of its marginals."
    return out


SAMPLE = {"joint": "0 | 0 | 0.1\n0 | 1 | 0.2\n1 | 0 | 0.2\n1 | 1 | 0.5",
          "multi": "Manufacturability and costing | 51\nQuality control and inspection | 47\nProduction execution | 32\nSupplier selection and qualification | 25"}
SLIPS = [
    "Data analysis cheat sheet: the cleaning example removes the row with a missing age. Deleting is only one option; it throws away the other known fields, and can bias results if values are missing for a reason. The row shown also repeats ID 2, which is a duplicate-key problem, not only a missing value.",
    "Data analysis cheat sheet: the variance formulas shown (divide by n-1, and the probability-weighted E[(X-mu)^2]) are for different things (a sample estimate and a known distribution) and are not labelled. Mixing them is a common mistake.",
    "Data analysis cheat sheet: the correlation panel says r near zero is 'no relationship'. Pearson's r only measures straight-line association; a clear curve can give r near 0. Also, 'ask a clear question first' sits at the bottom of the flow, though it comes before collecting data.",
    "Data analysis cheat sheet: regression is shown as a fitted line with no assumptions (a straight-line pattern, spread that stays similar, independent errors) and no mention that a fit does not show cause.",
    "2027 Manufacturing Outlook: the survey has 150 executives (margin of error 8.0 points), and its own methodology says the subgroups of 30 to 55 are 'directional'. Yet the text compares them as facts (for example 44% vs 16% on spare capacity, or 18% vs 40% on supplier selection). Use the compare tool before believing a subgroup gap.",
    "2027 Manufacturing Outlook: 'greatest impact' percentages (51%, 47%, 32%, 25%) add to 155%, so respondents chose more than one. They are not shares of a single choice, and 'leading use case' overstates a pick-several question.",
    "2027 Manufacturing Outlook: the company that wrote it sells instant quotes and a supplier marketplace, and its findings point to buying more of both. Platform figures (quote volume up 60%, certified work worth 3.4 times more, 85% accept the process recommendation) have no baseline or comparison: acceptance of a default is not proof it was right, and certified work is costlier by nature.",
    "2027 Manufacturing Outlook: the year-on-year 'significant ROI' jump (44% to 57%) compares two surveys of different samples. At about 150 people each, a 13-point gap gives p of about 0.02 and only if the two samples are independent, and 'significant' is whatever the respondent decided it meant.",
]
NOT_BUILT = ["Weighted or cluster-sample survey error, which needs the survey design from the publisher.",
             "Checking the publisher's raw data. You can only test the numbers printed in the report."]


def reference() -> dict:
    return {"slips": SLIPS, "not_built": NOT_BUILT, "sample": SAMPLE}
