"""Job Autopilot: give it a file and (optionally) a worry, and it runs every analysis that fits, then explains each in plain English.

Nothing here writes to the user's tables. Every step reports ran / skipped / failed and why, so no tool is ever "shut out".
"""
from __future__ import annotations

import base64
import io
import json
import math
import re
from typing import Any

MAX_BYTES = 25 * 1024 * 1024
IMG = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
TABLE_EXT = (".csv", ".tsv", ".xlsx", ".xlsm", ".json", ".jsonl", ".ndjson", ".xml", ".parquet", ".html", ".htm")


class AutoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _step(sid: str, title: str, status: str, plain: str, result: Any = None, caveats: list[str] | None = None, why: str = "") -> dict:
    return {"id": sid, "title": title, "status": status, "plain": plain, "result": result, "caveats": caveats or [], "why": why}


# ---------------------------------------------------------------- tables
def _frame(raw: bytes, name: str, sheet: str | None = None):
    import pandas as pd
    from app.services import datasets
    header, rows, info = datasets.read_table(raw, name, sheet)
    seen, cols = {}, []
    for i, h in enumerate(header):
        h = (h or "").strip() or f"column_{i + 1}"
        seen[h] = seen.get(h, 0) + 1
        cols.append(h if seen[h] == 1 else f"{h}_{seen[h]}")
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns:
        s = df[c]
        if s.dtype == object or not pd.api.types.is_numeric_dtype(s):
            num = pd.to_numeric(s.astype(object).where(s.notna(), None).map(lambda v: v.replace(",", "").replace("$", "") if isinstance(v, str) else v), errors="coerce")
            if s.notna().sum() and num.notna().sum() >= 0.9 * s.notna().sum():
                df[c] = num
            else:
                df[c] = s.astype(object)
    return df, info


def _is_date_name(c: str) -> bool:
    return bool(re.search(r"date|time|_ts$|^ts$|timestamp|day|month|created|start|due", c, re.I))


def _dates(df):
    import pandas as pd
    out = []
    for c in df.columns:
        if df[c].dtype == object and _is_date_name(c):
            d = pd.to_datetime(df[c], errors="coerce", format="mixed")
            if d.notna().sum() >= 0.8 * max(df[c].notna().sum(), 1):
                out.append((c, d))
    return out


def _binary(s) -> bool:
    v = set(s.dropna().unique().tolist())
    if not v:
        return False
    if len(v) == 2:
        return True
    return False


def _truthy(s):
    import pandas as pd
    if s.dtype != object:
        vals = sorted(s.dropna().unique().tolist())
        return (s == vals[-1]).astype(int)
    pos = {"1", "yes", "y", "true", "t", "converted", "churned", "won", "clicked", "purchased"}
    return s.str.strip().str.lower().isin(pos).astype(int)


def profile(df) -> dict:
    n = len(df)
    cols = []
    for c in df.columns:
        s = df[c]
        item = {"column": c, "type": "number" if s.dtype != object else "text", "missing_pct": round(100 * s.isna().mean(), 1), "distinct": int(s.nunique())}
        if s.dtype != object and s.notna().any():
            item.update(min=round(float(s.min()), 4), mean=round(float(s.mean()), 4), max=round(float(s.max()), 4))
        cols.append(item)
    dup = int(df.duplicated().sum())
    return {"rows": n, "columns": len(df.columns), "duplicate_rows": dup, "cols": cols[:40]}


def step_profile(df) -> dict:
    p = profile(df)
    worst = [c for c in p["cols"] if c["missing_pct"] >= 20]
    bits = [f"{p['rows']:,} rows and {p['columns']} columns."]
    if p["duplicate_rows"]:
        bits.append(f"{p['duplicate_rows']} rows are exact copies of another row; they may double count.")
    if worst:
        bits.append("Mostly-empty columns: " + ", ".join(f"{c['column']} ({c['missing_pct']}%)" for c in worst[:4]) + ".")
    if len(bits) == 1:
        bits.append("No obvious emptiness or duplicates.")
    return _step("profile", "Data check: size, empties, duplicates", "ran", " ".join(bits) + " Fix these before trusting any number below.", p)


def _group_cols(df):
    """Columns with exactly 2 text levels, ranked by how much their name sounds like a test split."""
    out = []
    for c in df.columns:
        s = df[c]
        if s.dtype == object and s.nunique() == 2 and s.notna().mean() > 0.9:
            score = 2 if re.search(r"group|variant|arm|test|cohort|treat|bucket|experiment|ab", c, re.I) else 0
            lv = {str(x).lower() for x in s.dropna().unique()}
            if lv & {"control", "variant", "a", "b", "treatment", "test", "baseline", "new", "old"}:
                score += 3
            if score:
                out.append((score, c))
    out.sort(reverse=True)
    return [c for _, c in out]


def _outcome_cols(df, group):
    out = []
    for c in df.columns:
        if c == group:
            continue
        s = df[c]
        if s.dtype != object and _binary(s):
            score = 3 if re.search(r"convert|click|purchase|signup|success|bought|won|retained|churn", c, re.I) else 1
            out.append((score, c, "binary"))
        elif s.dtype != object and s.nunique() > 5 and not re.search(r"(^|_)id$|^id$", c, re.I):
            score = 2 if re.search(r"value|revenue|amount|spend|time|score|price|total", c, re.I) else 0
            out.append((score, c, "number"))
    out.sort(key=lambda x: -x[0])
    return out


def step_ab(df) -> dict:
    from app.services import analyst_pro
    groups = _group_cols(df)
    if not groups:
        return _step("ab_test", "A/B test", "skipped", "No column splits the rows into exactly two groups (like control / variant), so there is nothing to compare.",
                     why="An A/B test needs one column naming the group and one column with the result.")
    g = groups[0]
    outs = _outcome_cols(df, g)
    if not outs:
        return _step("ab_test", "A/B test", "skipped", f"Found the group column '{g}' but no result column (a 0/1 outcome or a number).", why="Add a result column such as converted (0/1).")
    lv = sorted(df[g].dropna().unique().tolist(), key=lambda x: (str(x).lower() not in {"control", "a", "baseline", "old"}, str(x)))
    a, b = lv[0], lv[1]
    res = {"group_column": g, "a": str(a), "b": str(b), "tests": []}
    lines, cav = [], []
    sizes = df[g].value_counts()
    if abs(sizes[a] - sizes[b]) / max(sizes[a], sizes[b]) > 0.1:
        cav.append(f"The groups are different sizes ({sizes[a]} vs {sizes[b]}). Check how people were split; a lopsided split can hint at a setup problem.")
    for score, oc, kind in outs[:3]:
        da, db = df[df[g] == a][oc].dropna(), df[df[g] == b][oc].dropna()
        if kind == "binary":
            ya, yb = _truthy(da), _truthy(db)
            r = analyst_pro.ab_test(len(ya), int(ya.sum()), len(yb), int(yb.sum()))
            res["tests"].append({"outcome": oc, "kind": "rate", **r})
            lines.append(f"{oc}: {a} {r['a_rate_pct']}% vs {b} {r['b_rate_pct']}% (lift {r['lift_pct']}%, p={r['p_value'] if 'p_value' in r else '?'}). {r['verdict']}")
            pa, pb = r["a_rate_pct"] / 100, r["b_rate_pct"] / 100
            if pa != pb and score >= 1 and not res.get("sample_size_per_group"):
                need = int(math.ceil(16 * ((pa + pb) / 2) * (1 - (pa + pb) / 2) / (pb - pa) ** 2))
                res["sample_size_per_group"] = need
                lines.append(f"To confirm a gap this size you would need about {need:,} people per group; you have {len(ya):,} and {len(yb):,}.")
        else:
            from scipy import stats
            t = stats.ttest_ind(db, da, equal_var=False)
            lo_hi = None
            diff = float(db.mean() - da.mean())
            se = math.sqrt(da.var(ddof=1) / len(da) + db.var(ddof=1) / len(db))
            lo_hi = [round(diff - 1.96 * se, 3), round(diff + 1.96 * se, 3)]
            ok = bool(t.pvalue < 0.05)
            verdict = "A real difference is likely (p below 0.05)." if ok else "No clear difference: the gap could be chance."
            res["tests"].append({"outcome": oc, "kind": "average", "a_mean": round(float(da.mean()), 3), "b_mean": round(float(db.mean()), 3),
                                 "difference": round(diff, 3), "difference_95ci": lo_hi, "p_value": round(float(t.pvalue), 4), "verdict": verdict})
            lines.append(f"{oc} (average): {a} {da.mean():.2f} vs {b} {db.mean():.2f}, p={t.pvalue:.3f}. {verdict}")
            if (da == 0).mean() > 0.5:
                cav.append(f"Most '{oc}' values are 0 (people who did not buy). Compare the rate first; the average is dominated by the zeros.")
    if len(outs) > 1:
        cav.append(f"{min(len(outs), 3)} results were tested; with several tests, one 'win' can appear by luck. Treat the first (main) result as the answer and the rest as clues.")
    cav += ["Decide the sample size before starting; stopping early when it looks good inflates false wins.", "Statistics say the gap is probably real or not; they do not say why."]
    return _step("ab_test", "A/B test between the two groups", "ran", " ".join(lines), res, cav)


def step_group_compare(df) -> dict:
    """Average of each number by each small category column, to answer 'which X is best/worst'."""
    cats = [c for c in df.columns if df[c].dtype == object and 2 <= df[c].nunique() <= 8 and not _is_date_name(c) and not re.search(r"(^|_)id$", c, re.I)]
    nums = [c for c in df.columns if df[c].dtype != object and df[c].nunique() > 5 and not re.search(r"(^|_)id$|^id$", c, re.I)]
    if not cats or not nums:
        return _step("groups", "Compare categories", "skipped", "Needs a category column (like region) and a number column (like sales).", why="Not found in this file.")
    c, n = cats[0], nums[0]
    t = df.groupby(c)[n].agg(["count", "sum", "mean"]).sort_values("sum", ascending=False).round(2)
    rows = [{"group": str(k), "rows": int(v["count"]), "total": float(v["sum"]), "average": float(v["mean"])} for k, v in t.iterrows()]
    best, worst = rows[0], rows[-1]
    return _step("groups", f"Compare {c} on {n}", "ran", f"{best['group']} has the highest total {n} ({best['total']:,.0f}) and {worst['group']} the lowest ({worst['total']:,.0f}). Category sizes differ, so compare averages too.", {"by": c, "measure": n, "table": rows})


def step_trend(df) -> dict:
    import numpy as np
    ds = _dates(df)
    nums = [c for c in df.columns if df[c].dtype != object and df[c].nunique() > 5 and not re.search(r"(^|_)id$|^id$", c, re.I)]
    if not ds or not nums:
        return _step("trend", "Trend over time", "skipped", "Needs a date column and a number column.", why="No date column was recognised.")
    dc, d = ds[0]
    n = nums[0]
    s = df.assign(_d=d).dropna(subset=["_d"]).set_index("_d")[n].resample("W").sum() if d.nunique() > 14 else df.assign(_d=d).dropna(subset=["_d"]).groupby("_d")[n].sum()
    if len(s) < 3:
        return _step("trend", "Trend over time", "skipped", "Fewer than 3 time periods, too short to see a trend.")
    x = np.arange(len(s))
    slope = float(np.polyfit(x, s.values, 1)[0])
    direction = "rising" if slope > 0 else "falling"
    pct = 100 * slope / (abs(float(s.mean())) or 1)
    return _step("trend", f"Trend of {n} over {dc}", "ran", f"{n} is {direction} by about {abs(pct):.1f}% of its average per period across {len(s)} periods.",
                 {"date_column": dc, "measure": n, "periods": len(s), "slope_per_period": round(slope, 3)}, ["A short history can mislead; seasonality needs at least a year of data."])


def step_correlations(df) -> dict:
    nums = df.select_dtypes("number").loc[:, lambda x: x.nunique() > 5]
    nums = nums[[c for c in nums.columns if not re.search(r"(^|_)id$|^id$", c, re.I)]]
    if nums.shape[1] < 2:
        return _step("corr", "What moves together", "skipped", "Needs at least two number columns.")
    c = nums.corr().abs()
    pairs = []
    cols = list(c.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = nums[cols[i]].corr(nums[cols[j]])
            if v == v:
                pairs.append((abs(v), v, cols[i], cols[j]))
    pairs.sort(reverse=True)
    top = [{"a": a, "b": b, "r": round(v, 3)} for _, v, a, b in pairs[:5]]
    t = top[0]
    return _step("corr", "What moves together", "ran", f"The strongest link is {t['a']} and {t['b']} (r={t['r']}). Moving together is not the same as one causing the other.", top)


def _target_guess(df, concern: str):
    low = (concern or "").lower()
    for c in df.columns:
        if re.search(r"(?<![a-z0-9_])" + re.escape(c.lower()) + r"(?![a-z0-9_])", low) and c != df.columns[0] and df[c].nunique() > 1:
            return c
    pref = re.compile(r"churn|target|label|outcome|default|fraud|converted|survived", re.I)
    for c in df.columns:
        if pref.search(c) and (df[c].nunique() <= 20):
            return c
    return None


def _leaky(df, y, target):
    """Columns that rebuild the answer by themselves: a single column predicts nearly perfectly."""
    out = []
    for c in df.columns:
        if c == target:
            continue
        s = df[c]
        if s.dtype != object and s.nunique() > 1:
            r = abs(s.corr(y)) if y.nunique() > 1 else 0
            if r == r and r > 0.97:
                out.append(c)
        if re.search(r"(^|_)(id|uuid)$|^id$", c, re.I) and s.nunique() > 0.95 * len(df):
            out.append(c)
        elif s.dtype != object and y.nunique() == 2 and s.notna().sum() > 20:
            try:
                from sklearn.metrics import roc_auc_score
                a = roc_auc_score(y[s.notna()], s.dropna())
                if max(a, 1 - a) > 0.98 and c not in out:
                    out.append(c)
            except Exception:  # noqa: BLE001
                pass
    return out


def step_ml(df, concern: str) -> dict:
    import numpy as np
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.model_selection import StratifiedKFold, KFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    target = _target_guess(df, concern)
    if not target:
        return _step("ml", "Machine-learning models", "skipped", "No clear outcome column to predict. Name it in your concern (for example 'predict churned') and run again.",
                     why="Models need to know which column is the answer.")
    d = df.dropna(subset=[target]).copy()
    if len(d) < 60:
        return _step("ml", "Machine-learning models", "skipped", f"Only {len(d)} rows have a '{target}'; models need roughly 60 or more to be worth comparing.")
    classify = d[target].nunique() <= 10
    y = d[target]
    if classify and y.value_counts().min() < 5:
        return _step("ml", "Machine-learning models", "skipped", f"The rarest answer in '{target}' appears fewer than 5 times, too few to learn from or test fairly.")
    if classify:
        y = _truthy(y) if y.nunique() == 2 else y.astype(str)
    leak = _leaky(d, y if y.dtype != object else y.astype("category").cat.codes, target)
    drop = list(dict.fromkeys(leak + [c for c in d.columns if c != target and d[c].dtype == object and d[c].nunique() > 0.5 * len(d)]))
    X = d.drop(columns=[target] + drop)
    for c, dt in _dates(X):
        X[c + "_month"] = dt.dt.month.values
        X = X.drop(columns=[c])
    num = [c for c in X.columns if X[c].dtype != object]
    cat = [c for c in X.columns if X[c].dtype == object]
    if not num and not cat:
        return _step("ml", "Machine-learning models", "skipped", "After removing id-like columns, no usable inputs were left.")
    pre = ColumnTransformer([("n", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num),
                             ("c", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), cat)])
    if classify:
        cv = StratifiedKFold(5, shuffle=True, random_state=0)
        scoring, label = "roc_auc" if y.nunique() == 2 else "accuracy", "AUC" if y.nunique() == 2 else "accuracy"
        models = {"Baseline (always guess the common answer)": DummyClassifier(strategy="prior"), "Logistic regression": LogisticRegression(max_iter=1000),
                  "Random forest": RandomForestClassifier(200, random_state=0, n_jobs=1), "Gradient boosting": GradientBoostingClassifier(random_state=0)}
    else:
        cv = KFold(5, shuffle=True, random_state=0)
        scoring, label = "r2", "R²"
        models = {"Baseline (always guess the average)": DummyRegressor(), "Ridge regression": Ridge(), "Random forest": RandomForestRegressor(200, random_state=0, n_jobs=1),
                  "Gradient boosting": GradientBoostingRegressor(random_state=0)}
    board = []
    for name, m in models.items():
        try:
            sc = cross_val_score(make_pipeline(pre, m), X, y, cv=cv, scoring=scoring)
            board.append({"model": name, "score": round(float(sc.mean()), 3), "spread": round(float(sc.std()), 3)})
        except Exception as e:  # noqa: BLE001
            board.append({"model": name, "score": None, "error": str(e)[:100]})
    ok = [b for b in board if b.get("score") is not None]
    if len(ok) < 2:
        return _step("ml", "Machine-learning models", "failed", "The models could not be scored on this data.", board)
    base = ok[0]["score"]
    best = max(ok[1:], key=lambda b: b["score"])
    cav = ["Scores come from 5-fold cross-checking on this file only; real-world results are usually a little worse.", "A model is a prediction aid, not proof of why anything happens."]
    if leak:
        cav.insert(0, f"Removed {', '.join(leak)} because it gives the answer away or is just an id; keeping it would fake a great score.")
    if best["score"] > 0.98:
        cav.insert(0, "A near-perfect score is a warning sign of leakage (a column that contains the answer). Check the inputs.")
    beat = best["score"] - base
    if beat < max(0.05, 2 * best.get("spread", 0)):
        plain = f"Predicting '{target}': no model clearly beats the baseline ({label} {base} vs best {best['score']}). The inputs may not carry enough signal; do not rely on a model here."
    else:
        plain = f"Predicting '{target}': best is {best['model']} with {label} {best['score']} against a baseline of {base}. That is a real improvement, but test it on fresh data before using it."
    importance = None
    try:
        pipe = make_pipeline(pre, RandomForestClassifier(200, random_state=0) if classify else RandomForestRegressor(200, random_state=0)).fit(X, y)
        names = pipe[0].get_feature_names_out()
        imp = pipe[-1].feature_importances_
        agg: dict = {}
        for nme, v in zip(names, imp):
            col = nme.split("__", 1)[1]
            for c in X.columns:
                if col == c or col.startswith(c + "_"):
                    agg[c] = agg.get(c, 0) + float(v)
                    break
        importance = [{"input": k, "weight": round(v, 3)} for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:6]]
        if importance:
            plain += f" Inputs that matter most: {', '.join(i['input'] for i in importance[:3])}."
    except Exception:  # noqa: BLE001
        pass
    return _step("ml", f"Machine-learning models predicting {target}", "ran", plain,
                 {"target": target, "task": "classification" if classify else "regression", "metric": label, "leaderboard": board, "inputs_used": list(X.columns), "inputs_dropped": drop, "top_inputs": importance}, cav)


def step_pm(df) -> dict:
    st = next((c for c in df.columns if re.search(r"status|state", c, re.I)), None)
    est = next((c for c in df.columns if re.search(r"estimate|days|points|effort", c, re.I) and df[c].dtype != object), None)
    if not st:
        return _step("pm", "Project status", "skipped", "No status column found.")
    cnt = df[st].value_counts().to_dict()
    res: dict = {"by_status": {str(k): int(v) for k, v in cnt.items()}}
    plain = "Status counts: " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + "."
    if est:
        tot = float(df[est].sum())
        done = float(df[df[st].astype(str).str.lower().isin(["done", "closed", "complete", "completed"])][est].sum())
        res.update(total_effort=tot, done_effort=done, done_pct=round(100 * done / tot, 1) if tot else None)
        plain += f" About {100 * done / tot:.0f}% of the planned {est} is done." if tot else ""
    rk = next((c for c in df.columns if re.search(r"risk|priority", c, re.I)), None)
    if rk:
        hi = df[df[rk].astype(str).str.lower().isin(["high", "critical", "p0", "p1"])]
        res["high_risk_items"] = hi.iloc[:, 1].astype(str).tolist()[:8] if len(df.columns) > 1 else []
        plain += f" {len(hi)} item(s) are marked high risk."
    return _step("pm", "Project status and risk", "ran", plain, res, ["Dates and estimates are only as good as the people who entered them."])


def step_quality_events(df) -> dict:
    ids = next((c for c in df.columns if re.search(r"(event|order|record|row)_?id$|^id$", c, re.I)), None)
    issues, res = [], {}
    if ids and df[ids].duplicated().any():
        k = int(df[ids].duplicated().sum())
        issues.append(f"{k} repeated {ids} values (the same event arrived twice).")
        res["duplicate_ids"] = k
    for c in df.columns:
        if df[c].dtype != object and re.search(r"amount|price|qty|cost|value", c, re.I):
            neg = int((df[c] < 0).sum())
            if neg:
                issues.append(f"{neg} negative '{c}' values.")
                res.setdefault("negative", {})[c] = neg
            q1, q3 = df[c].quantile(.25), df[c].quantile(.75)
            out = int(((df[c] > q3 + 3 * (q3 - q1)) | (df[c] < q1 - 3 * (q3 - q1))).sum()) if q3 > q1 else 0
            if out:
                issues.append(f"{out} extreme outliers in '{c}'.")
                res.setdefault("outliers", {})[c] = out
    ds = _dates(df)
    if ds:
        c, d = ds[0]
        bad = int(d.isna().sum() + df[c].isna().sum())
        if d.notna().any() and d.max() > __import__("pandas").Timestamp.now() + __import__("pandas").Timedelta(days=1):
            issues.append(f"Some '{c}' dates are in the future.")
            res["future_dates"] = True
        if bad:
            issues.append(f"{bad} unreadable dates in '{c}'.")
    return _step("quality", "Data quality rules", "ran", " ".join(issues) if issues else "No duplicate ids, negative amounts, wild outliers or impossible dates found.", res or None,
                 ["Rows that fail should be held back and fixed, not silently deleted."])


# ---------------------------------------------------------------- other file kinds
def _text(raw: bytes) -> str:
    from app.services import datasets
    return datasets.decode(raw)


def _analyze_security(raw):
    from app.services import seclogs
    r = seclogs.analyze(_text(raw))
    f = r["findings"]
    top = f[0]["title"] if f else "no suspicious pattern found"
    return _step("seclog", "Security log analysis", "ran", f"{len(f)} finding(s). Most serious: {top}.", {"findings": [{k: x[k] for k in ("severity", "title", "detail")} for x in f[:8]], "info": r["info"]},
                 [r.get("caveat", "Log patterns are clues, not proof. Confirm before acting.")])


def _analyze_pcap(raw):
    from app.services import net_pcap
    r = net_pcap.read(base64.b64encode(raw).decode())
    f = r["findings"]
    return _step("pcap", "Network capture analysis", "ran", f"{r['packets']} packets. " + (" ".join(f[:3]) if f else "Nothing unusual flagged."),
                 {"packets": r["packets"], "protocols": r["protocols"], "top_talkers": r["top_talkers"], "findings": f}, [r.get("lesson", "Findings are clues; verify in Wireshark.")])


def _analyze_events(text):
    from app.services import itlab
    r = itlab.read_events(text)
    return _step("events", "Windows event log analysis", "ran", " ".join(r.get("findings", [])[:3]) if r.get("findings") else "Event IDs counted; nothing alarming flagged.", {"table": r.get("table", [])[:10]})


def _analyze_openapi(text):
    from app.services import prolab
    from app.services import prolab_fullstack  # noqa: F401  (registers the tools)
    r = prolab.run("fullstack", "openapi_lint", {"spec": text})
    return _step("openapi", "OpenAPI lint", "ran", "Checked the API description for common gaps.", r)


def _analyze_verilog(text):
    from app.services import codecheck
    try:
        r = codecheck.verilog_sim(text)
    except codecheck.CodeError as e:
        return _step("verilog", "Verilog simulation", "failed", e.message, why="Install the simulator or remove the blocked statement.")
    return _step("verilog", "Verilog compile and testbench run", "ran" if r["compiled"] else "failed", r["plain"],
                 {k: r.get(k) for k in ("modules", "top", "has_testbench", "issues", "fail_lines", "pass_lines", "unknown_value_lines")},
                 ["A passing testbench proves only the cases it checks."])


def _analyze_c(text):
    from app.services import codecheck
    try:
        r = codecheck.c_check(text, run=False)
    except codecheck.CodeError as e:
        return _step("c_code", "C compile check", "failed", e.message, why="Install a C compiler.")
    return _step("c_code", "C compile and strict warnings", "ran" if r["compiled"] else "failed", r["plain"], {"issues": r["issues"]},
                 ["Autopilot only compiles. To run it, use the Computer Engineering lab tool 'C compile, lint and run' after you have read the code."])


def _analyze_can(text):
    from app.services import veh_decode
    sigs, frames = [], []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("#") and "|" in ln:
            sigs.append(ln.lstrip("# ").strip())
        m = re.match(r"\(([\d.]+)\)\s*(\w+)#([0-9A-Fa-f]+)", ln)
        if m:
            frames.append(m.groups())
    if not frames:
        return None
    out = []
    for _, i, data in frames[:3]:
        try:
            out.append({"id": i, "decoded": veh_decode.can_signals(data, "\n".join(s for s in sigs if s.count("|") >= 7))})
        except Exception as e:  # noqa: BLE001
            out.append({"id": i, "error": str(e)[:100]})
    return _step("can", "CAN signal decode", "ran", f"{len(frames)} frames read; decoded the first {len(out)} with the signal list in the file.", out, ["A decode is only right if the signal definitions (bit position, scale) are right."])


def _read_other_text(name: str, raw: bytes) -> tuple[str, str]:
    from app.routers import filetext
    low = name.lower()
    if low.endswith((".xlsx", ".xlsm")):
        return filetext._xlsx(raw)[0], ""
    if low.endswith(".docx"):
        return filetext._docx(raw), ""
    if low.endswith(".pdf"):
        from app.services import fileformats
        return fileformats.pdf_text(raw), ""
    if low.endswith(IMG):
        return filetext._scan(name, raw)
    return _text(raw), ""


def _text_steps(text: str, concern: str) -> list[dict]:
    words = re.findall(r"[A-Za-z']{4,}", text.lower())
    stop = set("this that with from have will your their there which would about were been what when they them then than into also each other more some such only over after before should could shall must".split())
    from collections import Counter
    top = [w for w, _ in Counter(w for w in words if w not in stop).most_common(8)]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    qs = [ln for ln in lines if "?" in ln][:5]
    reqs = [ln for ln in lines if re.search(r"\b(shall|must|should|need to|required)\b", ln, re.I)][:8]
    res = {"characters": len(text), "lines": len(lines), "top_terms": top, "questions": qs, "requirement_like_lines": reqs}
    plain = f"Read {len(text):,} characters. Main terms: {', '.join(top[:5])}."
    if reqs:
        plain += f" {len(reqs)} line(s) read like requirements (shall/must/should)."
    if qs:
        plain += f" {len(qs)} open question(s) in the text."
    return [_step("text", "Read and outline the document", "ran", plain, res, ["This is a quick outline from the words themselves. Ask the AI step for a fuller summary and decisions."])]


# ---------------------------------------------------------------- driver
def _wants(concern: str, *keys) -> bool:
    low = (concern or "").lower()
    return any(k in low for k in keys)


def run(name: str, raw: bytes, concern: str = "", field: str = "") -> dict:
    name = name or "upload.csv"
    low = name.lower()
    if not raw or not raw.strip():
        raise AutoError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise AutoError("That file is over 25 MB. Export a smaller slice.")
    if low.endswith(".xls"):
        raise AutoError("This is an old Excel (.xls) file. Open it in Excel and Save As .xlsx or CSV.")
    steps: list[dict] = []
    kind = "table"
    notes: list[str] = []
    try:
        if low.endswith((".pcap", ".pcapng", ".cap")):
            kind = "capture"
            steps.append(_analyze_pcap(raw))
        elif low.endswith(IMG) or low.endswith((".docx", ".pdf")):
            # a PDF with a clean table is treated as a table first
            kind = "document"
            tbl = None
            if low.endswith(".pdf"):
                try:
                    tbl = _frame(raw, name)
                except Exception:  # noqa: BLE001
                    tbl = None
            if tbl is not None and tbl[0].shape[0] >= 5 and tbl[0].shape[1] >= 3:
                kind = "table"
                df, info = tbl
                return _finish(name, kind, df, info, concern, steps)
            text, note = _read_other_text(name, raw)
            if note.strip():
                notes.append(note.strip())
            steps += _text_steps(text, concern)
            if low.endswith(IMG):
                notes.append("This was a picture or scan, so the words come from OCR and may contain misreads. Check numbers against the original.")
        else:
            text = _text(raw) if not low.endswith((".xlsx", ".xlsm")) else ""
            head = text[:4000]
            if low.endswith(".json") and ('"openapi"' in head or '"swagger"' in head):
                kind = "api"
                steps.append(_analyze_openapi(text))
            elif low.endswith((".v", ".sv")):
                kind = "verilog"
                steps.append(_analyze_verilog(text))
            elif low.endswith(".c"):
                kind = "c_code"
                steps.append(_analyze_c(text))
            elif re.search(r"\b(sshd|Failed password|Accepted password|GET /|POST /|HTTP/1\.[01]\")", head) and low.endswith((".log", ".txt")):
                kind = "security_log"
                steps.append(_analyze_security(raw))
            elif low.endswith((".log", ".txt")) and re.search(r"\(\d+\.\d+\)\s*\w+#[0-9A-Fa-f]+", text):
                kind = "can_log"
                s = _analyze_can(text)
                if s:
                    steps.append(s)
            elif re.search(r"Event ID", head, re.I) and low.endswith((".csv", ".log", ".txt")):
                kind = "event_log"
                steps.append(_analyze_events(text))
            elif low.endswith((".txt", ".md", ".log")) and "," not in head[:300] and "\t" not in head[:300]:
                kind = "document"
                steps += _text_steps(text, concern)
            else:
                df, info = _frame(raw, name)
                return _finish(name, kind, df, info, concern, steps)
    except AutoError:
        raise
    except Exception as e:  # noqa: BLE001
        steps.append(_step("read", "Open the file", "failed", f"The file could not be analysed: {str(e)[:200]}", why="Try exporting it as CSV or .xlsx."))
    return _wrap(name, kind, steps, concern, notes)


def _finish(name, kind, df, info, concern, steps):
    import pandas as pd
    notes = []
    if info.get("sheets") and len(info["sheets"]) > 1:
        notes.append(f"Read sheet '{info.get('sheet')}' (the file also has: {', '.join(s for s in info['sheets'] if s != info.get('sheet'))}).")
    steps.append(step_profile(df))
    runners = [("ab_test", step_ab), ("groups", step_group_compare), ("trend", step_trend), ("corr", step_correlations)]
    cols = " ".join(df.columns).lower()
    if re.search(r"status", cols) and re.search(r"estimate|due|owner", cols):
        runners.insert(0, ("pm", step_pm))
    if re.search(r"event|amount|_ts|id", cols):
        runners.insert(1, ("quality", step_quality_events))
    for sid, fn in runners:
        try:
            steps.append(fn(df))
        except Exception as e:  # noqa: BLE001
            steps.append(_step(sid, sid, "failed", f"This step hit an error and was skipped: {str(e)[:150]}"))
    try:
        steps.append(step_ml(df, concern))
    except Exception as e:  # noqa: BLE001
        steps.append(_step("ml", "Machine-learning models", "failed", f"Could not run: {str(e)[:150]}"))
    return _wrap(name, "table", steps, concern, notes, {"rows": len(df), "columns": list(map(str, df.columns))})


def _wrap(name, kind, steps, concern, notes, shape=None) -> dict:
    ran = [s for s in steps if s["status"] == "ran"]
    head = [s["plain"].split(". ")[0] + "." for s in ran if s["id"] in ("ab_test", "ml", "seclog", "pcap", "events", "pm", "quality", "openapi", "can", "verilog", "c_code")][:4]
    summary = " ".join(head) if head else "Nothing could be run on this file."
    return {"file": name, "kind": kind, "concern": concern, "shape": shape, "summary": summary, "notes": notes, "steps": steps,
            "counts": {"ran": len(ran), "skipped": sum(s["status"] == "skipped" for s in steps), "failed": sum(s["status"] == "failed" for s in steps)},
            "disclaimer": "Nothing was saved or changed in your data. These are automatic first-pass results from this one file; check them before you send anything to a client. AI and statistics can be wrong."}
