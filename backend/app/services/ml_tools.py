"""Machine-learning learning tools: small, deterministic, numpy-only exercises that show WHY the usual rules exist.

  bias_variance  - fit polynomials of rising degree; watch training error fall while validation error turns upward
  grad_descent   - gradient descent on linear or logistic regression; see a learning rate that is too small or too big
  scratch_compare- kNN, logistic regression, a decision tree and naive Bayes written from scratch, against a dumb baseline
  score_report   - paste scores and true labels: ROC-AUC, PR-AUC, calibration, and the best threshold for YOUR costs
  leak_check     - scan a CSV for columns that give the answer away (target leakage) and other traps

Honest limits: data are synthetic or yours, sizes are capped, seeds are fixed so results repeat. These teach mechanics;
they are not a replacement for scikit-learn, PyTorch or a real validation process on real data.
"""
from __future__ import annotations

import io
import math
import re
import warnings

import numpy as np
import pandas as pd


class MlToolError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


MAX_ROWS = 20_000


def _num(v, name, lo, hi, integer=False):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise MlToolError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise MlToolError(f"{name} must be between {lo:g} and {hi:g}.")
    return int(x) if integer else x


# ------------------------------------------------------------------ bias and variance
def bias_variance(n=40, noise=0.3, degrees=None, seed=7) -> dict:
    n = _num(n, "Points", 12, 400, True)
    noise = _num(noise, "Noise", 0, 2)
    degs = [1, 2, 3, 5, 8, 12] if degrees is None else degrees
    if not isinstance(degs, list) or not 1 <= len(degs) <= 12:
        raise MlToolError("Give between 1 and 12 polynomial degrees.")
    degs = [_num(d, "Degree", 0, 15, True) for d in degs]
    rng = np.random.default_rng(int(_num(seed, "Seed", 0, 10**6, True)))
    x = np.sort(rng.uniform(0, 1, n))
    y = np.sin(2 * np.pi * x) + rng.normal(0, noise, n)
    idx = rng.permutation(n)
    cut = max(6, n // 2)
    tr, va = idx[:cut], idx[cut:]
    if len(va) < 4:
        raise MlToolError("Not enough points left for validation; raise Points.")
    rows = []
    for d in sorted(set(degs)):
        if d >= len(tr):
            rows.append({"degree": d, "train_mse": None, "valid_mse": None, "verdict": "skipped: more parameters than training points"})
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = np.polyfit(x[tr], y[tr], d)
        tm = float(np.mean((np.polyval(c, x[tr]) - y[tr]) ** 2))
        vm = float(np.mean((np.polyval(c, x[va]) - y[va]) ** 2))
        rows.append({"degree": d, "train_mse": round(tm, 4), "valid_mse": round(vm, 4)})
    ok = [r for r in rows if r["valid_mse"] is not None]
    best = min(ok, key=lambda r: r["valid_mse"])
    floor = noise ** 2
    for r in ok:
        if r["degree"] < best["degree"] and r["valid_mse"] > best["valid_mse"] * 1.3:
            r["verdict"] = "underfit: too simple, both errors are high"
        elif r["degree"] > best["degree"] and r["valid_mse"] > best["valid_mse"] * 1.3 and r["train_mse"] < best["train_mse"]:
            r["verdict"] = "overfit: training error keeps falling, validation error is worse"
        elif r["degree"] == best["degree"]:
            r["verdict"] = "best on validation"
        else:
            r["verdict"] = "close to the best"
    return {"rows": rows, "best_degree": best["degree"], "noise_floor_mse": round(floor, 4), "train_points": int(len(tr)), "valid_points": int(len(va)),
            "lesson": "Training error alone always favours the most flexible model. Only the held-out error tells you whether it learned the pattern or memorised the noise. "
                      f"The best any model can do here is about the noise variance ({floor:.3f}); validation error below that on {len(va)} points is luck.",
            "limit": "One random split of a small data set is noisy: change the seed and the winner can move by a degree or two. Real work repeats this with cross-validation."}


# ------------------------------------------------------------------ gradient descent
def grad_descent(task="linear", lr=0.1, steps=100, seed=3) -> dict:
    if task not in ("linear", "logistic"):
        raise MlToolError("Task must be linear or logistic.")
    lr = _num(lr, "Learning rate", 1e-4, 50)
    steps = _num(steps, "Steps", 1, 2000, True)
    rng = np.random.default_rng(int(_num(seed, "Seed", 0, 10**6, True)))
    n = 120
    X = rng.normal(0, 1, (n, 2))
    w_true = np.array([2.0, -1.0]); b_true = 0.5
    z = X @ w_true + b_true
    y = z + rng.normal(0, 0.3, n) if task == "linear" else (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-z))).astype(float)
    w = np.zeros(2); b = 0.0
    losses = []
    diverged = False
    for t in range(steps):
        p = X @ w + b
        if task == "logistic":
            p = 1 / (1 + np.exp(-np.clip(p, -50, 50)))
            loss = float(-np.mean(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)))
        else:
            loss = float(np.mean((p - y) ** 2) / 2)
        if not math.isfinite(loss) or loss > 1e8:
            diverged = True
            losses.append(None)
            break
        losses.append(loss)
        g = p - y
        w = w - lr * (X.T @ g) / n
        b = b - lr * float(np.mean(g))
    pts = [{"step": i, "loss": None if v is None else round(v, 5)} for i, v in enumerate(losses) if i % max(1, steps // 20) == 0 or i == len(losses) - 1]
    first = next((v for v in losses if v is not None), None)
    last = next((v for v in reversed(losses) if v is not None), None)
    if diverged:
        verdict = "Diverged: the learning rate is too large, so each step overshoots and the loss grows. Lower it."
    elif first is not None and last is not None and last > first * 0.9:
        verdict = "Barely moved: the learning rate is too small (or too few steps). Raise it or run longer."
    elif len(losses) > 20 and abs(losses[-1] - losses[-10]) < 1e-4:
        verdict = "Converged: the loss stopped improving."
    else:
        verdict = "Still improving: more steps would help."
    return {"task": task, "lr": lr, "steps_run": len(losses), "curve": pts, "diverged": diverged,
            "weights": [round(float(v), 3) for v in w], "bias": round(b, 3), "true_weights": w_true.tolist(), "true_bias": b_true,
            "verdict": verdict,
            "lesson": "Gradient descent repeats one move: step downhill by learning-rate times the slope. Everything in deep learning (Adam, schedules, warmup) is a refinement of this loop.",
            "limit": "Two features, fixed synthetic data. For logistic regression the recovered weights are only close to the truth because the labels are random draws."}


# ------------------------------------------------------------------ algorithms from scratch
def _moons(n, noise, rng):
    h = n // 2
    t = rng.uniform(0, math.pi, h)
    a = np.c_[np.cos(t), np.sin(t)]
    b = np.c_[1 - np.cos(t), 0.5 - np.sin(t)]
    X = np.vstack([a, b]) + rng.normal(0, noise, (2 * h, 2))
    y = np.r_[np.zeros(h), np.ones(h)]
    p = rng.permutation(2 * h)
    return X[p], y[p]


def _knn(Xtr, ytr, Xte, k):
    d = ((Xte[:, None, :] - Xtr[None, :, :]) ** 2).sum(-1)
    nn = np.argsort(d, axis=1)[:, :k]
    return (ytr[nn].mean(1) >= 0.5).astype(float)


def _logreg(Xtr, ytr, Xte, lr=0.5, steps=400):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    w = np.zeros(A.shape[1]); b = 0.0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(A @ w + b)))
        w -= lr * A.T @ (p - ytr) / len(A); b -= lr * float(np.mean(p - ytr))
    return ((B @ w + b) > 0).astype(float)


def _gini(y):
    if len(y) == 0:
        return 0.0
    p = float(np.mean(y))
    return 2 * p * (1 - p)


def _grow(X, y, depth):
    if depth == 0 or len(set(y)) == 1 or len(y) < 4:
        return float(np.mean(y) >= 0.5)
    best = (None, None, _gini(y))
    for j in range(X.shape[1]):
        for thr in np.unique(np.quantile(X[:, j], np.linspace(0.1, 0.9, 9))):
            m = X[:, j] <= thr
            if m.sum() < 2 or (~m).sum() < 2:
                continue
            g = (m.sum() * _gini(y[m]) + (~m).sum() * _gini(y[~m])) / len(y)
            if g < best[2] - 1e-12:
                best = (j, float(thr), g)
    if best[0] is None:
        return float(np.mean(y) >= 0.5)
    j, thr, _ = best
    m = X[:, j] <= thr
    return (j, thr, _grow(X[m], y[m], depth - 1), _grow(X[~m], y[~m], depth - 1))


def _tree_predict(node, x):
    while isinstance(node, tuple):
        node = node[2] if x[node[0]] <= node[1] else node[3]
    return node


def _nb(Xtr, ytr, Xte):
    ll = []
    for c in (0.0, 1.0):
        Xc = Xtr[ytr == c]
        mu, var = Xc.mean(0), Xc.var(0) + 1e-6
        ll.append(np.log(len(Xc) / len(Xtr)) - 0.5 * (np.log(2 * math.pi * var) + (Xte - mu) ** 2 / var).sum(1))
    return (ll[1] > ll[0]).astype(float)


def scratch_compare(n=300, noise=0.25, k=7, depth=4, seed=11) -> dict:
    n = _num(n, "Rows", 60, 1500, True)
    noise = _num(noise, "Noise", 0, 1)
    k = _num(k, "k", 1, 51, True)
    depth = _num(depth, "Tree depth", 1, 10, True)
    rng = np.random.default_rng(int(_num(seed, "Seed", 0, 10**6, True)))
    X, y = _moons(n, noise, rng)
    cut = int(len(y) * 0.7)
    Xtr, ytr, Xte, yte = X[:cut], y[:cut], X[cut:], y[cut:]
    base = float(max(np.mean(yte == 0), np.mean(yte == 1)))
    tree = _grow(Xtr, ytr, depth)
    preds = {
        "k-nearest neighbours": _knn(Xtr, ytr, Xte, k),
        "logistic regression": _logreg(Xtr, ytr, Xte),
        "decision tree": np.array([_tree_predict(tree, r) for r in Xte]),
        "naive Bayes (gaussian)": _nb(Xtr, ytr, Xte),
    }
    why = {"k-nearest neighbours": "Remembers the training points; bends around the moons. Slow on big data.",
           "logistic regression": "Draws one straight line, so it cannot separate two interlocking moons well.",
           "decision tree": "Splits on one feature at a time; depth is the dial between simple and overfit.",
           "naive Bayes (gaussian)": "Assumes each class is a bell shape with independent features; fast but wrong here."}
    rows = [{"model": m, "accuracy": round(float(np.mean(p == yte)), 3), "beats_baseline": bool(np.mean(p == yte) > base + 0.02), "note": why[m]} for m, p in preds.items()]
    rows.sort(key=lambda r: -r["accuracy"])
    return {"rows": rows, "baseline_accuracy": round(base, 3), "train_rows": int(cut), "test_rows": int(len(yte)),
            "lesson": "No model is best everywhere: the shape of the data decides. Write each one once by hand and you will know what it assumes. Always compare with the dumb baseline.",
            "limit": "Two-feature synthetic 'moons' data, one split. Real tabular work uses scikit-learn, cross-validation and tuned settings; this code is for understanding, not speed."}


# ------------------------------------------------------------------ scores, AUC, calibration, costs
def _parse_scores(text):
    if not isinstance(text, str) or not text.strip():
        raise MlToolError("Paste lines of 'score,label' (label 1 or 0).")
    s, y = [], []
    for ln in text.strip().splitlines()[:MAX_ROWS + 1]:
        ln = ln.strip()
        if not ln or ln.lower().startswith(("score", "#")):
            continue
        parts = re.split(r"[,\s;\t]+", ln)
        if len(parts) < 2:
            raise MlToolError(f"Line '{ln[:40]}' needs a score and a label.")
        try:
            sc, lb = float(parts[0]), float(parts[1])
        except ValueError:
            raise MlToolError(f"Line '{ln[:40]}' has a non-numeric value.") from None
        if lb not in (0.0, 1.0) or not math.isfinite(sc):
            raise MlToolError(f"Line '{ln[:40]}': the label must be 0 or 1 and the score a number.")
        s.append(sc); y.append(lb)
    if len(s) > MAX_ROWS:
        raise MlToolError(f"Keep it to {MAX_ROWS:,} rows.")
    if len(s) < 10:
        raise MlToolError("Give at least 10 rows.")
    y = np.array(y); s = np.array(s)
    if y.sum() == 0 or y.sum() == len(y):
        raise MlToolError("Both classes (0 and 1) must appear.")
    return s, y


def _auc(s, y):
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s)); ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def score_report(text, fp_cost=1.0, fn_cost=5.0) -> dict:
    s, y = _parse_scores(text)
    fp_cost = _num(fp_cost, "Cost of a false alarm", 0, 1e9)
    fn_cost = _num(fn_cost, "Cost of a miss", 0, 1e9)
    if s.min() < 0 or s.max() > 1:
        scores_note = "Scores are outside 0 to 1, so calibration is skipped (it needs probabilities)."
    else:
        scores_note = ""
    # PR AUC as average precision
    order = np.argsort(-s, kind="mergesort")
    ys = y[order]
    tp = np.cumsum(ys); prec = tp / np.arange(1, len(ys) + 1)
    ap = float(np.sum(prec * ys) / ys.sum())
    thr_rows = []
    best = None
    for t in np.unique(np.r_[s, s.max() + 1e-9]):
        pred = s >= t
        tpn = int(np.sum(pred & (y == 1))); fpn = int(np.sum(pred & (y == 0)))
        fnn = int(np.sum(~pred & (y == 1))); tnn = int(np.sum(~pred & (y == 0)))
        cost = fpn * fp_cost + fnn * fn_cost
        rec = {"threshold": round(float(t), 4), "tp": tpn, "fp": fpn, "fn": fnn, "tn": tnn, "cost": round(cost, 2),
               "precision": round(tpn / (tpn + fpn), 3) if tpn + fpn else None, "recall": round(tpn / (tpn + fnn), 3)}
        if best is None or cost < best["cost"]:
            best = rec
        thr_rows.append(rec)
    step = max(1, len(thr_rows) // 12)
    shown = thr_rows[::step]
    if best not in shown:
        shown.append(best)
    shown.sort(key=lambda r: r["threshold"])
    at_half = next((r for r in thr_rows if r["threshold"] >= 0.5), thr_rows[-1])
    out = {"rows": len(s), "positives": int(y.sum()), "positive_rate": round(float(y.mean()), 3),
           "roc_auc": round(_auc(s, y), 4), "pr_auc": round(ap, 4), "pr_auc_baseline": round(float(y.mean()), 3),
           "best_threshold": best, "cost_at_0_5": at_half["cost"], "cost_if_never_alarm": round(float(y.sum()) * fn_cost, 2),
           "table": shown, "calibration": None, "note": scores_note}
    if not scores_note:
        brier = float(np.mean((s - y) ** 2)); bins = []
        ece = 0.0
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            m = (s >= lo) & ((s < hi) if i < 9 else (s <= hi))
            if m.sum():
                gap = abs(float(s[m].mean()) - float(y[m].mean())); ece += gap * m.sum() / len(s)
                bins.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()), "mean_score": round(float(s[m].mean()), 3), "actual_rate": round(float(y[m].mean()), 3)})
        out["calibration"] = {"brier": round(brier, 4), "ece": round(ece, 4), "bins": bins}
    out["lesson"] = ("ROC-AUC says how well scores rank positives above negatives; it ignores your costs and flatters rare-event problems. PR-AUC is judged against the positive rate. "
                     "The threshold is a business decision: with a miss costing more than a false alarm, the cheapest cut-off is rarely 0.5.")
    out["limit"] = "Computed on exactly the rows you paste. If those rows were used to train the model, every number here is too optimistic. Rare positives (under ~30) make the threshold unstable."
    return out


# ------------------------------------------------------------------ leakage scan
_SUSPECT = re.compile(r"(outcome|result|churned|cancel|refund|chargeback|default|resolved|closed_?date|after_|post_|final_|label|target|status_at_end|ended)", re.I)


def leak_check(csv_text, target) -> dict:
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise MlToolError("Paste a CSV with a header row.")
    if len(csv_text) > 3_000_000:
        raise MlToolError("Keep it under 3 MB.")
    try:
        df = pd.read_csv(io.StringIO(csv_text), nrows=MAX_ROWS)
    except Exception as e:
        raise MlToolError(f"Could not read that as CSV: {str(e)[:120]}") from None
    if len(df) < 20:
        raise MlToolError("Need at least 20 rows.")
    if target not in df.columns:
        raise MlToolError(f"Column '{target}' isn't in the CSV. Columns: {', '.join(map(str, df.columns))[:200]}")
    yv = df[target]
    if yv.isna().all():
        raise MlToolError("The target column is empty.")
    binary = yv.dropna().nunique() == 2
    if binary:
        codes = pd.Series(pd.factorize(yv)[0], index=yv.index).astype(float)
        yn = codes.where(yv.notna())
    else:
        yn = pd.to_numeric(yv, errors="coerce")
    findings, table = [], []
    for c in df.columns:
        if c == target:
            continue
        col = df[c]
        uniq = col.nunique(dropna=True) / max(1, col.notna().sum())
        score, kind = None, ""
        mask = col.notna() & ~pd.isna(yn)
        if pd.api.types.is_numeric_dtype(col) and mask.sum() >= 20 and col[mask].nunique() > 1:
            if binary and set(np.unique(yn[mask])) <= {0.0, 1.0} and yn[mask].nunique() == 2:
                a = _auc(col[mask].to_numpy(float), yn[mask].astype(float)); score, kind = max(a, 1 - a), "single-feature AUC"
            else:
                r = np.corrcoef(col[mask].to_numpy(float), yn[mask].to_numpy(float))[0, 1]
                score, kind = abs(float(r)) if math.isfinite(r) else None, "|correlation|"
        elif binary and col.nunique() <= 50:
            g = pd.DataFrame({"c": col, "y": yn}).dropna().groupby("c")["y"].agg(["mean", "size"])
            if len(g) > 1:
                score, kind = float(((g["mean"].round()).eq(g["mean"]) * g["size"]).sum() / g["size"].sum()), "share of rows in categories that are 100% one class"
        flags = []
        if score is not None and ((kind == "single-feature AUC" and score >= 0.95) or (kind == "|correlation|" and score >= 0.9)):
            flags.append("almost predicts the target by itself; suspect leakage")
        if _SUSPECT.search(str(c)):
            flags.append("name sounds like something known only after the outcome")
        if uniq > 0.98 and len(df) > 30:
            flags.append("unique on nearly every row (an ID); a model can memorise it")
        if col.isna().mean() > 0.4:
            flags.append(f"{col.isna().mean() * 100:.0f}% missing; check whether missing means 'the outcome happened'")
        table.append({"column": str(c), "signal": None if score is None else round(score, 3), "measure": kind, "flags": flags})
        for f in flags:
            findings.append({"column": str(c), "issue": f})
    dups = int(df.duplicated().sum())
    if dups:
        findings.append({"column": "(rows)", "issue": f"{dups} fully duplicated rows: copies can land in both train and test and inflate the score"})
    if binary:
        rate = float(yn.dropna().mean())
        if min(rate, 1 - rate) < 0.1:
            findings.append({"column": str(target), "issue": f"the rarer class is {min(rate, 1 - rate) * 100:.1f}% of rows; accuracy will mislead, use PR-AUC and a cost threshold"})
    table.sort(key=lambda r: -(r["signal"] or 0))
    return {"rows": int(len(df)), "target": target, "target_type": "binary" if binary else "numeric", "findings": findings, "columns": table[:40],
            "verdict": "Likely leakage: remove or justify the flagged columns before trusting any score." if any("leakage" in f["issue"] or "after" in f["issue"] for f in findings) else
                       ("Some traps to look at." if findings else "No obvious leaks found, which does not prove there are none."),
            "lesson": "A leak is a column the model would not have at prediction time. Ask of every feature: 'would I know this the moment I need the prediction?' Then split by time, not at random.",
            "limit": "Heuristics on single columns: they miss leaks hidden in combinations and cannot know your business timeline. Numeric columns only get AUC or correlation."}


SAMPLES = {
    "scores": "score,label\n" + "\n".join(f"{s},{l}" for s, l in [(0.95, 1), (0.91, 1), (0.88, 1), (0.81, 0), (0.77, 1), (0.7, 1), (0.66, 0), (0.62, 1), (0.55, 0), (0.48, 1),
                                                              (0.44, 0), (0.4, 0), (0.33, 1), (0.3, 0), (0.25, 0), (0.2, 0), (0.15, 0), (0.1, 0), (0.07, 0), (0.03, 0)]),
    "leak": "customer_id,tenure_months,monthly_charge,support_calls,cancellation_date_filled,churned\n" + "\n".join(
        f"{1000 + i},{(i * 7) % 60 + 1},{40 + (i * 13) % 50},{(i * 3) % 6},{1 if i % 4 == 0 else 0},{1 if i % 4 == 0 else 0}" for i in range(60)),
}


def reference() -> dict:
    return {"samples": SAMPLES,
            "not_built": ["Training deep networks, GPUs, PyTorch or TensorFlow code.", "Boosting libraries (XGBoost, LightGBM), PCA, UMAP and DBSCAN: use ML Lab and scikit-learn for the first, and learn the others in a notebook.",
                          "Hyper-parameter search, AutoML and cloud notebooks.", "Judging a real model: these tools use synthetic data or whatever you paste."]}
