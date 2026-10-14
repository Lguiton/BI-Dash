"""Data mining and machine learning on any table: clusters, association rules, outliers, and a general predictor.

Predictive analytics = statistical modeling (Analysis Lab: regression, ARIMA, probability) + data mining (finding patterns:
clusters, associations, outliers; this module) + machine learning (learning a predictor from examples; this module's `predict`).
All of it is computed locally with scikit-learn. Findings are patterns in past data, not guarantees.
"""
from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, mean_absolute_error, precision_score, r2_score, recall_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.services import stats_lab
from app.services.datasets import DataError, q
from app.services.stats_lab import _f, _need, _rows, resolve, where_clause

MAX_ROWS = 50_000
MAX_LEVELS = 12


def _frame(source: str, cols_wanted: list[str], filters, mode, kinds_ok=("number",), limit=MAX_ROWS, what="column"):
    ident, cols = resolve(source)
    for c in cols_wanted:
        _need(cols, c, kinds_ok, what)
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in cols_wanted])
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    rows = _rows(f"SELECT {', '.join(q(c) for c in cols_wanted)} FROM {q(ident)}{w} LIMIT {limit}", params)
    return pd.DataFrame(rows, columns=cols_wanted), total, fwords, cols


# ------------------------------------------------------------------ clusters
def cluster(source: str, features: list[str], k: int | None = None, filters=None, mode: str = "and") -> dict:
    features = list(dict.fromkeys(features or []))
    if not 2 <= len(features) <= 8:
        raise DataError("Pick 2 to 8 number columns to group rows by.")
    df, total, fwords, _ = _frame(source, features, filters, mode)
    n = len(df)
    if n < 20:
        raise DataError(f"Only {n} usable rows; clustering needs at least 20.")
    X = df.to_numpy(dtype=float)
    sd = X.std(axis=0)
    if (sd == 0).any():
        raise DataError(f"'{features[int(np.argmin(sd))]}' never changes, so it can't help separate groups. Remove it.")
    Z = StandardScaler().fit_transform(X)
    sil_n = min(n, 3000)
    scores = []
    if k is None:
        for kk in range(2, min(8, n // 10) + 1):
            km = KMeans(n_clusters=kk, n_init=5, random_state=0).fit(Z)
            scores.append({"k": kk, "silhouette": _f(silhouette_score(Z, km.labels_, sample_size=sil_n, random_state=0), 3)})
        if not scores:
            raise DataError("Too few rows to compare group counts.")
        k = max(scores, key=lambda s: s["silhouette"] or -1)["k"]
    elif not 2 <= k <= 10 or k > n // 5:
        raise DataError("Choose between 2 and 10 groups, with at least 5 rows each on average.")
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Z)
    sil = float(silhouette_score(Z, km.labels_, sample_size=sil_n, random_state=0))
    order = list(np.argsort(-np.bincount(km.labels_, minlength=k)))  # biggest group first
    remap = {int(old): i + 1 for i, old in enumerate(order)}
    lab = np.array([remap[int(x)] for x in km.labels_])
    mu, sg = X.mean(axis=0), sd
    groups = []
    for cid in range(1, k + 1):
        m = lab == cid
        cen = X[m].mean(axis=0)
        dev = (cen - mu) / sg
        big = [i for i in np.argsort(-np.abs(dev)) if abs(dev[i]) >= 0.5][:2]
        label = ", ".join(f"{'high' if dev[i] > 0 else 'low'} {features[i]}" for i in big) or "close to average"
        groups.append({"id": cid, "size": int(m.sum()), "pct": _f(m.mean() * 100, 1), "label": label,
                       "centroid": {f: _f(cen[i], 4) for i, f in enumerate(features)}, "vs_average": {f: _f(dev[i], 2) for i, f in enumerate(features)}})
    pca = PCA(n_components=2, random_state=0).fit(Z)
    P = pca.transform(Z)
    idx = np.random.default_rng(1).permutation(n)[:600]
    strength = "strong" if sil >= 0.5 else "reasonable" if sil >= 0.25 else "weak"
    sentences = [f"{n:,} rows fall into {k} groups ({strength} separation, silhouette {sil:.2f}).",
                 "Largest group: " + groups[0]["label"] + f" ({groups[0]['pct']}% of rows)."]
    if len(groups) > 1:
        sentences.append("Smallest group: " + groups[-1]["label"] + f" ({groups[-1]['pct']}% of rows).")
    warn = []
    if sil < 0.25:
        warn.append("The groups overlap a lot. The data may not have natural clusters; treat the groups as one way to slice it, not as real types.")
    if total > n:
        warn.append(f"Used the first {n:,} of {total:,} rows.")
    return {"k": k, "rows": n, "features": features, "silhouette": _f(sil, 3), "strength": strength, "k_scores": scores, "groups": groups,
            "points": [{"x": _f(P[i, 0], 3), "y": _f(P[i, 1], 3), "g": int(lab[i])} for i in idx],
            "explained": [_f(v, 3) for v in pca.explained_variance_ratio_], "filters": fwords, "warnings": warn, "sentences": sentences,
            "lesson": ("Clustering (k-means) groups rows that look alike across several numbers, without being told the groups. Numbers are rescaled first so a big-unit column "
                       "doesn't dominate. The silhouette score (-1 to 1) says how clearly separated the groups are. Name the groups yourself by reading 'vs average'.")}


# ------------------------------------------------------------------ association rules
def associations(source: str, basket_col: str, item_col: str, min_support_pct: float = 1.0, min_confidence_pct: float = 30.0,
                 filters=None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, basket_col, ("text", "number", "bool"), "basket column")
    _need(cols, item_col, ("text", "bool"), "item column")
    if basket_col == item_col:
        raise DataError("The basket and the item must be different columns.")
    if not 0 < min_support_pct <= 100 or not 0 <= min_confidence_pct <= 100:
        raise DataError("Support and confidence are percentages (0 to 100).")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(basket_col)} IS NOT NULL", f"{q(item_col)} IS NOT NULL"])
    pairs = _rows(f"SELECT CAST({q(basket_col)} AS VARCHAR) AS b, CAST({q(item_col)} AS VARCHAR) AS i FROM {q(ident)}{w} GROUP BY 1, 2 LIMIT 1000000", params)
    baskets: dict[str, set[str]] = {}
    for r in pairs:
        baskets.setdefault(r["b"], set()).add(r["i"])
    N = len(baskets)
    if N < 10:
        raise DataError(f"Only {N} baskets; need at least 10.")
    multi = sum(1 for s in baskets.values() if len(s) >= 2)
    freq = Counter(i for s in baskets.values() for i in s)
    keep = {i for i, _ in freq.most_common(200)}
    pair_ct: Counter = Counter()
    skipped_big = 0
    for s in baskets.values():
        s = sorted(s & keep)
        if len(s) > 30:
            skipped_big += 1
            continue
        pair_ct.update(combinations(s, 2))
    min_count = max(2, math.ceil(min_support_pct / 100 * N))
    rules = []
    for (a, b), c in pair_ct.items():
        if c < min_count:
            continue
        for x, y in ((a, b), (b, a)):
            conf = c / freq[x]
            if conf * 100 < min_confidence_pct:
                continue
            lift = conf / (freq[y] / N)
            rules.append({"if": x, "then": y, "baskets": c, "support_pct": _f(c / N * 100, 2), "confidence_pct": _f(conf * 100, 1), "lift": _f(lift, 2)})
    rules.sort(key=lambda r: (-(r["lift"] or 0), -r["baskets"]))
    items = [{"item": i, "baskets": c, "pct": _f(c / N * 100, 1)} for i, c in freq.most_common(10)]
    warn = []
    if multi < 30:
        warn.append(f"Only {multi} baskets contain two or more different items, so rules are thin. Group by something that holds several items (a customer, an order).")
    if skipped_big:
        warn.append(f"{skipped_big} very large baskets (over 30 items) were skipped.")
    sentences = [f"{N:,} baskets, {len(freq):,} different items; {multi:,} baskets hold two or more items."]
    if rules:
        r = rules[0]
        sentences.append(f"Strongest link: baskets with '{r['if']}' also have '{r['then']}' {r['confidence_pct']}% of the time, {r['lift']}x more often than baskets in general.")
    else:
        sentences.append("No pair is frequent enough at these settings. Lower the minimum support.")
    return {"baskets": N, "items_total": len(freq), "multi_item_baskets": multi, "top_items": items, "rules": rules[:30], "min_count": min_count,
            "filters": fwords, "warnings": warn, "sentences": sentences,
            "lesson": ("Association rules ('market basket'): support = share of baskets with both items; confidence = of the baskets with A, the share that also have B; "
                       "lift = confidence divided by how common B is anyway. Lift above 1 means they travel together more than chance; near 1 means no real link. "
                       "A link is a pattern, not a cause.")}


# ------------------------------------------------------------------ outliers
def outliers(source: str, features: list[str], label_col: str | None = None, top: int = 15, filters=None, mode: str = "and") -> dict:
    features = list(dict.fromkeys(features or []))
    if not 1 <= len(features) <= 8:
        raise DataError("Pick 1 to 8 number columns to check.")
    ident, cols = resolve(source)
    if label_col:
        _need(cols, label_col, None, "label column")
    want = features + ([label_col] if label_col and label_col not in features else [])
    df, total, fwords, _ = _frame_any(source, want, features, filters, mode)
    n = len(df)
    if n < 30:
        raise DataError(f"Only {n} usable rows; need at least 30.")
    X = df[features].to_numpy(dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    iso = IsolationForest(n_estimators=200, contamination=min(0.1, max(0.005, 5 / n)), random_state=0).fit(X)
    score = -iso.score_samples(X)  # higher = stranger
    order = np.argsort(-score)[: max(1, min(top, 50))]
    pcts = [(score <= score[i]).mean() * 100 for i in order]
    out = []
    for i, pc in zip(order, pcts):
        z = (X[i] - mu) / sd
        j = int(np.argmax(np.abs(z)))
        out.append({"row": int(i) + 1, "label": None if not label_col else _lab(df.iloc[i][label_col]), "score": _f(score[i], 3), "stranger_than_pct": _f(pc, 1),
                    "values": {f: _f(X[i, k], 4) for k, f in enumerate(features)}, "most_unusual": features[j], "z": _f(z[j], 2)})
    flagged = int((iso.predict(X) == -1).sum())
    warn = [f"Used the first {n:,} of {total:,} rows."] if total > n else []
    return {"rows": n, "flagged": flagged, "features": features, "outliers": out, "filters": fwords, "warnings": warn,
            "sentences": [f"{flagged} of {n:,} rows look unusual taken together across {', '.join(features)}.",
                          f"Most unusual row: {'#' + str(out[0]['row'])}" + (f" ({out[0]['label']})" if out[0]["label"] else "") + f", mainly because of {out[0]['most_unusual']} (z = {out[0]['z']})."],
            "lesson": ("An isolation forest finds rows that are easy to separate from the rest using several columns at once, so it catches combinations a single-column check "
                       "misses (a normal price with an abnormal quantity). Unusual does not mean wrong: check each one for errors, fraud or a genuine special case.")}


def _lab(v) -> str:
    return str(int(v)) if isinstance(v, (float, np.floating)) and float(v).is_integer() else str(v)


def _frame_any(source, want, numeric, filters, mode):
    ident, cols = resolve(source)
    for c in numeric:
        _need(cols, c, ("number",), "number column")
    for c in want:
        _need(cols, c, None, "column")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in numeric])
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {q(ident)}{w}", params)[0]["n"])
    rows = _rows(f"SELECT {', '.join(q(c) for c in want)} FROM {q(ident)}{w} LIMIT {MAX_ROWS}", params)
    return pd.DataFrame(rows, columns=want), total, fwords, cols


# ------------------------------------------------------------------ machine learning on any table
MODELS = {"regression": {"linear": "Ridge (a straight-line model)", "forest": "Random forest (many decision trees)", "boosting": "Gradient boosting (trees that fix each other's mistakes)"},
          "classification": {"logistic": "Logistic regression (a straight-line model for classes)", "forest": "Random forest", "boosting": "Gradient boosting"}}


def _make(kind: str, model: str):
    if model not in MODELS[kind]:
        raise DataError(f"Model '{model}' isn't available for {kind}. Choose: {', '.join(MODELS[kind])}.")
    if kind == "regression":
        return {"linear": lambda: Ridge(alpha=1.0), "forest": lambda: RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=0, n_jobs=2),
                "boosting": lambda: HistGradientBoostingRegressor(random_state=0)}[model]()
    return {"logistic": lambda: LogisticRegression(max_iter=1000), "forest": lambda: RandomForestClassifier(n_estimators=150, min_samples_leaf=2, random_state=0, n_jobs=2),
            "boosting": lambda: HistGradientBoostingClassifier(random_state=0)}[model]()


def predict(source: str, target: str, x_numeric: list[str] | None = None, x_categorical: list[str] | None = None, model: str | None = None,
            test_pct: int = 20, positive: str | None = None, case: dict | None = None, filters=None, mode: str = "and") -> dict:
    xn, xc = list(dict.fromkeys(x_numeric or [])), list(dict.fromkeys(x_categorical or []))
    if not xn and not xc:
        raise DataError("Pick at least one input column.")
    if len(xn) + len(xc) > 12:
        raise DataError("Use at most 12 input columns.")
    ident, cols = resolve(source)
    _need(cols, target, ("number", "text", "bool"), "column to predict")
    if target in xn or target in xc:
        raise DataError("The column you predict can't also be an input.")
    for c in xn:
        _need(cols, c, ("number",), "number input")
    for c in xc:
        _need(cols, c, ("text", "bool"), "category input")
    kind = "regression" if cols[target] == "number" else "classification"
    model = model or ("linear" if kind == "regression" else "logistic")
    est = _make(kind, model)
    want = [target] + xn + xc
    df, total, fwords, _ = _frame_any(source, want, [], filters, mode)
    df = df.dropna(subset=want)
    n = len(df)
    if n < 60:
        raise DataError(f"Only {n} usable rows; need at least 60 to train and test fairly.")
    levels: dict[str, list[str]] = {}
    for c in xc:
        df[c] = df[c].astype(str)
        vc = df[c].value_counts()
        if len(vc) > MAX_LEVELS:
            raise DataError(f"'{c}' has {len(vc)} different values; use a column with at most {MAX_LEVELS}, or filter first.")
        levels[c] = list(vc.index)
    classes = None
    if kind == "classification":
        df[target] = df[target].astype(str)
        vc = df[target].value_counts()
        if len(vc) < 2 or len(vc) > 10:
            raise DataError(f"'{target}' has {len(vc)} different values; classification needs 2 to 10.")
        if vc.min() < 5:
            raise DataError("One of the classes has fewer than 5 rows. Filter it out or pick another column.")
        classes = list(vc.index)
        if positive and positive not in classes:
            raise DataError(f"'{positive}' isn't a value of {target}: {', '.join(classes)}.")
        positive = positive or (classes[-1] if len(classes) == 2 else None)
    elif float(df[target].std()) == 0:
        raise DataError(f"'{target}' never changes, so there is nothing to predict.")
    X = pd.get_dummies(df[xn + xc], columns=xc, dtype=float)
    y = df[target]
    strat = y if kind == "classification" else None
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=max(0.1, min(0.5, test_pct / 100)), random_state=7, stratify=strat)
    scaler = None
    if model in ("linear", "logistic"):
        scaler = StandardScaler().fit(Xtr)
        fit_X, test_X = scaler.transform(Xtr), scaler.transform(Xte)
    else:
        fit_X, test_X = Xtr.to_numpy(), Xte.to_numpy()
    est.fit(fit_X, ytr)
    pred, ptr = est.predict(test_X), est.predict(fit_X)
    res: dict = {"kind": kind, "model": model, "model_label": MODELS[kind][model], "target": target, "train_rows": len(Xtr), "test_rows": len(Xte), "filters": fwords, "warnings": [], "sentences": []}

    def score_fn(yt, yp):
        return r2_score(yt, yp) if kind == "regression" else accuracy_score(yt, yp)

    train_s, test_s = float(score_fn(ytr, ptr)), float(score_fn(yte, pred))
    if kind == "regression":
        base_mae = float(np.mean(np.abs(yte - ytr.mean())))
        mae = float(mean_absolute_error(yte, pred))
        better = mae < base_mae * 0.95  # a clear win, not a rounding-error edge
        res["metrics"] = {"r2_test": _f(test_s, 4), "r2_train": _f(train_s, 4), "mae": _f(mae, 4), "rmse": _f(math.sqrt(float(np.mean((yte - pred) ** 2))), 4),
                          "baseline_mae": _f(base_mae, 4), "better_than_baseline": bool(better)}
        res["sentences"].append(f"On {len(Xte)} rows it had never seen, the average miss is {mae:,.4g} versus {base_mae:,.4g} for always guessing the average; R² = {test_s:.2f}.")
    else:
        maj = float(yte.value_counts(normalize=True).max())
        m = {"accuracy_test": _f(test_s, 4), "accuracy_train": _f(train_s, 4), "baseline_accuracy": _f(maj, 4), "better_than_baseline": bool(test_s > maj + 0.01)}
        cm = confusion_matrix(yte, pred, labels=classes)
        res["confusion"] = {"labels": classes, "matrix": cm.tolist()}
        if positive and len(classes) == 2:
            yb, pb = (yte == positive).astype(int), (pd.Series(pred, index=yte.index) == positive).astype(int)
            m.update({"positive": positive, "precision": _f(precision_score(yb, pb, zero_division=0), 4), "recall": _f(recall_score(yb, pb, zero_division=0), 4), "f1": _f(f1_score(yb, pb, zero_division=0), 4)})
            if hasattr(est, "predict_proba"):
                try:
                    pr = est.predict_proba(test_X)[:, list(est.classes_).index(positive)]
                    m["auc"] = _f(roc_auc_score(yb, pr), 4)
                except ValueError:
                    pass
        res["metrics"] = m
        res["sentences"].append(f"On {len(Xte)} rows it had never seen it is right {test_s:.0%} of the time; always guessing the most common class is right {maj:.0%}.")
        better = test_s > maj + 0.01
    if not better:
        res["warnings"].append("The model is not clearly better than the simple guess. These inputs may not predict this column.")
    if train_s - test_s > 0.15:
        res["warnings"].append(f"It scores {train_s:.2f} on the rows it learned from but {test_s:.2f} on new rows: over-fitting. Use a simpler model, more rows, or fewer inputs.")
    if total > MAX_ROWS:
        res["warnings"].append(f"Used the first {MAX_ROWS:,} of {total:,} rows.")
    # which inputs matter: shuffle one input at a time on the held-out rows and see how much the score drops
    rng = np.random.default_rng(0)
    imp = []
    base = score_fn(yte, pred)
    groups = {c: [c] for c in xn} | {c: [k for k in X.columns if k.startswith(f"{c}_")] for c in xc}
    for name, ks in groups.items():
        drops = []
        for _ in range(5):
            Xp = Xte.copy()
            perm = rng.permutation(len(Xp))
            Xp[ks] = Xp[ks].to_numpy()[perm]
            inp = scaler.transform(Xp) if scaler is not None else Xp.to_numpy()
            drops.append(base - score_fn(yte, est.predict(inp)))
        imp.append({"input": name, "drop": _f(float(np.mean(drops)), 4)})
    imp.sort(key=lambda x: -(x["drop"] or 0))
    res["importance"] = imp
    if imp and (imp[0]["drop"] or 0) > 0:
        res["sentences"].append(f"Most useful input: {imp[0]['input']} (shuffling it costs {imp[0]['drop']:.3f} of the score).")
    if case:
        row = {}
        for c in xn:
            if case.get(c) in (None, ""):
                raise DataError(f"For a what-if, give a value for '{c}'.")
            row[c] = float(stats_lab._typed("number", case[c]))
        for c in xc:
            v = str(case.get(c, levels[c][0]))
            if v not in levels[c]:
                raise DataError(f"'{v}' isn't a value of {c}. Choose one of: {', '.join(levels[c])}.")
            row[c] = v
        one = pd.get_dummies(pd.DataFrame([row]), columns=xc, dtype=float).reindex(columns=X.columns, fill_value=0.0)
        inp = scaler.transform(one) if scaler is not None else one.to_numpy()
        if kind == "regression":
            res["case"] = {"inputs": row, "prediction": _f(float(est.predict(inp)[0]), 4), "typical_miss": res["metrics"]["mae"]}
        else:
            probs = est.predict_proba(inp)[0] if hasattr(est, "predict_proba") else None
            res["case"] = {"inputs": row, "prediction": str(est.predict(inp)[0]), "probabilities": ({str(c): _f(float(p), 3) for c, p in zip(est.classes_, probs)} if probs is not None else None)}
    res["lesson"] = ("Machine learning learns a predictor from past examples. The honest test is on rows the model never saw: compare it with the simple guess (the average, or the most common class). "
                     "A model that only shines on the rows it trained on has memorized, not learned. Importance shows what the model leaned on, not what causes the result.")
    return res


# ------------------------------------------------------------------ decision tree: a readable model
def decision_tree(source: str, target: str, x_numeric: list[str] | None = None, x_categorical: list[str] | None = None, max_depth: int = 3,
                  filters=None, mode: str = "and", focus_class: str | None = None, focus_cost: float = 1.0) -> dict:
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    xn, xc = list(dict.fromkeys(x_numeric or [])), list(dict.fromkeys(x_categorical or []))
    if not xn and not xc:
        raise DataError("Pick at least one input column.")
    if not 1 <= float(focus_cost) <= 20:
        raise DataError("The relative cost of missing the class you care about must be between 1 and 20.")
    if len(xn) + len(xc) > 10 or not 1 <= max_depth <= 5:
        raise DataError("Use at most 10 input columns and a depth from 1 to 5.")
    ident, cols = resolve(source)
    _need(cols, target, ("number", "text", "bool"), "column to predict")
    if target in xn or target in xc:
        raise DataError("The column you predict can't also be an input.")
    for c in xn:
        _need(cols, c, ("number",), "number input")
    for c in xc:
        _need(cols, c, ("text", "bool"), "category input")
    kind = "regression" if cols[target] == "number" else "classification"
    want = [target] + xn + xc
    df, total, fwords, _ = _frame_any(source, want, [], filters, mode)
    df = df.dropna(subset=want)
    n = len(df)
    if n < 40:
        raise DataError(f"Only {n} usable rows; need at least 40.")
    for c in xc:
        df[c] = df[c].astype(str)
        if df[c].nunique() > MAX_LEVELS:
            raise DataError(f"'{c}' has {df[c].nunique()} different values; use a column with at most {MAX_LEVELS}, or filter first.")
    classes = None
    if kind == "classification":
        df[target] = df[target].astype(str)
        vc = df[target].value_counts()
        if len(vc) < 2 or len(vc) > 8 or vc.min() < 3:
            raise DataError(f"'{target}' needs 2 to 8 different values with at least 3 rows each.")
        classes = sorted(vc.index)
    elif float(df[target].std()) == 0:
        raise DataError(f"'{target}' never changes, so there is nothing to predict.")
    X = pd.get_dummies(df[xn + xc], columns=xc, dtype=float)
    y = df[target]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y if kind == "classification" else None)
    leaf = max(5, int(len(Xtr) * 0.02))
    focus = None
    if kind == "classification":
        focus = str(focus_class) if focus_class not in (None, "") else str(ytr.value_counts().idxmin())
        if focus not in classes:
            raise DataError(f"'{focus}' isn't one of the values of {target}.")

    def fit_cls(cost: float):
        cw = {c: (float(cost) if c == focus else 1.0) for c in classes}
        return DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=leaf, random_state=0, class_weight=cw).fit(Xtr, ytr)

    def rates(model) -> dict:
        pr = model.predict(Xte)
        pos, neg = (yte == focus), (yte != focus)
        sens = float(((pr == focus) & pos).sum() / max(1, pos.sum()))
        spec = float(((pr != focus) & neg).sum() / max(1, neg.sum()))
        return {"sensitivity": _f(sens, 3), "specificity": _f(spec, 3), "accuracy": _f(float(accuracy_score(yte, pr)), 3),
                "false_positives": int(((pr == focus) & neg).sum()), "false_negatives": int(((pr != focus) & pos).sum())}
    est = (fit_cls(focus_cost) if kind == "classification"
           else DecisionTreeRegressor(max_depth=max_depth, min_samples_leaf=leaf, random_state=0))
    if kind != "classification":
        est.fit(Xtr, ytr)
    t, names = est.tree_, list(X.columns)

    def label(f: str, thr: float, left: bool) -> str:
        if f in xn:
            return f"{f} {'<=' if left else '>'} {thr:,.4g}"
        base = next(c for c in xc if f.startswith(f"{c}_"))
        return f"{base} {'is not' if left else 'is'} {f[len(base) + 1:]}"

    def node(i: int, cond: str) -> dict:
        cnt = t.n_node_samples[i]
        v = t.value[i][0]
        if kind == "classification":
            share = v / v.sum()
            top = int(np.argmax(share))
            pred, extra = str(est.classes_[top]), {"shares": {str(est.classes_[k]): _f(float(share[k]), 3) for k in range(len(share))}, "confidence": _f(float(share[top]), 3)}
        else:
            pred, extra = _f(float(v[0]), 4), {}
        out = {"condition": cond, "n": int(cnt), "prediction": pred, **extra}
        if t.children_left[i] != -1:
            f, thr = names[t.feature[i]], float(t.threshold[i])
            out["children"] = [node(int(t.children_left[i]), label(f, thr, True)), node(int(t.children_right[i]), label(f, thr, False))]
        return out

    tree = node(0, "All rows")
    pred = est.predict(Xte)
    if kind == "classification":
        score, base = float(accuracy_score(yte, pred)), float(yte.value_counts(normalize=True).max())
        metric = {"accuracy_test": _f(score, 4), "baseline_accuracy": _f(base, 4), "better_than_baseline": bool(score > base + 0.01)}
        rt = rates(est)
        metric.update({"focus_class": focus, "focus_cost": float(focus_cost), **rt})
        sweep = [{"cost": c, **rates(fit_cls(c))} for c in (1, 2, 4, 9)]
        from scipy.stats import binomtest
        from sklearn.metrics import roc_auc_score, roc_curve
        k_ok = int((pred == yte).sum())
        pv = float(binomtest(k_ok, len(yte), min(0.999, max(0.001, base)), alternative="greater").pvalue)
        metric["p_vs_baseline"] = _f(pv, 4)
        pi = list(est.classes_).index(focus)
        proba = est.predict_proba(Xte)[:, pi]
        fpr, tpr, _ = roc_curve((yte == focus).astype(int), proba)
        keep = np.unique(np.linspace(0, len(fpr) - 1, min(len(fpr), 40)).astype(int))
        roc = [{"fpr": _f(float(fpr[i]), 3), "tpr": _f(float(tpr[i]), 3)} for i in keep]
        metric["auc"] = _f(float(roc_auc_score((yte == focus).astype(int), proba)), 3)
        sent = (f"On {len(Xte)} rows it had never seen, the tree is right {score:.0%} of the time; always guessing the most common class is right {base:.0%}. "
                f"For '{focus}': it catches {rt['sensitivity']:.0%} of the real ones (sensitivity) and correctly clears {rt['specificity']:.0%} of the others (specificity); "
                f"{rt['false_negatives']} missed, {rt['false_positives']} false alarms.")
    else:
        mae, base = float(mean_absolute_error(yte, pred)), float(np.mean(np.abs(yte - ytr.mean())))
        metric = {"mae": _f(mae, 4), "baseline_mae": _f(base, 4), "r2_test": _f(float(r2_score(yte, pred)), 4), "better_than_baseline": bool(mae < base * 0.95)}
        sent = f"On {len(Xte)} rows it had never seen, the average miss is {mae:,.4g} versus {base:,.4g} for always guessing the average."
    sweep, roc = locals().get("sweep"), locals().get("roc")
    imps = sorted(({"input": names[k], "weight": _f(float(est.feature_importances_[k]), 3)} for k in range(len(names)) if est.feature_importances_[k] > 0), key=lambda x: -x["weight"])
    warn = [] if metric["better_than_baseline"] else ["The tree is not clearly better than the simple guess. These inputs may not predict this column."]
    if total > MAX_ROWS:
        warn.append(f"Used the first {MAX_ROWS:,} of {total:,} rows.")
    return {"kind": kind, "target": target, "rows_used": n, "filters": fwords, "tree": tree, "leaves": int(t.n_leaves), "metrics": metric, "importance": imps[:10],
            "cost_sweep": sweep if kind == "classification" else None, "roc": roc if kind == "classification" else None,
            "sentences": [sent, "Read the tree from the top: each branch is a yes/no question, and the box at the end is the guess for rows that follow that path."], "warnings": warn,
            "lesson": ("A decision tree learns a chain of yes/no questions that best separate the outcomes. Its strength is that you can read exactly why it guessed what it did. "
                       "Deep trees memorize noise, so this one is kept shallow and graded on rows it never saw.")}


# ------------------------------------------------------------------ sequential patterns
def sequences(source: str, entity_col: str, event_col: str, date_col: str, top: int = 12, collapse_repeats: bool = True, filters=None, mode: str = "and") -> dict:
    ident, cols = resolve(source)
    _need(cols, entity_col, ("text", "number"), "entity column")
    _need(cols, event_col, ("text", "bool"), "event column")
    _need(cols, date_col, ("date",), "date column")
    if entity_col == event_col:
        raise DataError("The entity (who) and the event (what happened) must be different columns.")
    w, params, fwords = where_clause(cols, filters, mode, [f"{q(c)} IS NOT NULL" for c in (entity_col, event_col, date_col)])
    rows = _rows(f"SELECT CAST({q(entity_col)} AS VARCHAR) AS e, CAST({q(event_col)} AS VARCHAR) AS ev FROM {q(ident)}{w} ORDER BY e, {q(date_col)} LIMIT 100000", params)
    if len(rows) < 20:
        raise DataError("Need at least 20 rows with an entity, an event and a date.")
    seqs: dict[str, list[str]] = {}
    for r in rows:
        s = seqs.setdefault(r["e"], [])
        if not (collapse_repeats and s and s[-1] == r["ev"]):
            s.append(r["ev"])
    multi = {k: v for k, v in seqs.items() if len(v) >= 2}
    if not multi:
        raise DataError("No entity has two or more events in order, so there are no sequences to study.")
    trans, out_of, pairs, tri, first, last = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for s in multi.values():
        first[s[0]] += 1
        last[s[-1]] += 1
        for a, b in zip(s, s[1:]):
            trans[(a, b)] += 1
            out_of[a] += 1
        for k in range(len(s) - 2):
            tri[(s[k], s[k + 1], s[k + 2])] += 1
    ne = len(multi)
    top = max(3, min(int(top), 30))
    steps = [{"from": a, "to": b, "count": c, "probability": _f(c / out_of[a], 3)} for (a, b), c in trans.most_common(top)]
    paths = [{"path": " > ".join(p), "count": c, "customers_pct": _f(c / ne * 100, 1)} for p, c in tri.most_common(top) if c >= 2]
    lens = [len(s) for s in multi.values()]
    sentences = [f"{ne:,} {entity_col} value(s) have two or more {event_col} events in date order; the typical sequence is {float(np.median(lens)):g} steps long."]
    if steps:
        s0 = steps[0]
        sentences.append(f"The most common step is {s0['from']} to {s0['to']}: it follows {s0['probability']:.0%} of the time {s0['from']} happens.")
    sentences.append(f"Most sequences start with {first.most_common(1)[0][0]} and end with {last.most_common(1)[0][0]}.")
    return {"entity_col": entity_col, "event_col": event_col, "filters": fwords, "entities": len(seqs), "entities_used": ne, "avg_length": _f(float(np.mean(lens)), 2),
            "steps": steps, "paths": paths, "starts": [{"event": e, "count": c} for e, c in first.most_common(5)], "ends": [{"event": e, "count": c} for e, c in last.most_common(5)],
            "sentences": sentences, "warnings": ["Rows on the same date have no reliable order, so the order inside a day is arbitrary."] if collapse_repeats is not None else [],
            "lesson": ("Sequential pattern mining follows events in time order for each person or thing, such as the shopping trail from the first visit to the last. "
                       "Unlike 'bought together', order matters: A then B is not the same as B then A. Common sequences are leads to test, not proof that one step causes the next.")}
