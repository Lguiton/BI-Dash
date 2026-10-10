"""ML Lab: train a small scikit-learn model on the dashboard's data, the way you would in a real project.

Good practice is built in so you can see why it matters:
  * the split is by TIME (train on the past, test on the most recent days), never shuffled
  * every result is compared with a naive baseline (predict the average / always guess the majority)
  * importance is measured by permutation on the test set (works for any model)
  * classification reports precision, recall and F1, not just accuracy (the classes are imbalanced)
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.db import get_cursor

MAX_ROWS = 20_000
MIN_ROWS = 100
RANDOM_STATE = 42


@dataclass(frozen=True)
class Feature:
    id: str
    label: str
    kind: str          # "num" or "cat"
    sql: str
    note: str


FEATURES = {f.id: f for f in [
    Feature("category", "Category", "cat", "COALESCE(e.category, 'Unknown')", "Business line of the entity."),
    Feature("entity", "Entity", "cat", "f.entity_id", "Which zone. Identifies the entity, so it can memorize it."),
    Feature("weekday", "Weekday", "cat", "DAYNAME(f.record_date)", "Monday..Sunday."),
    Feature("month", "Month", "num", "MONTH(f.record_date)", "1-12. A trend/season proxy."),
    Feature("is_weekend", "Is weekend", "num", "CASE WHEN DAYOFWEEK(f.record_date) IN (0, 6) THEN 1 ELSE 0 END", "0 or 1."),
    Feature("units_processed", "Units processed", "num", "f.units_processed", "Volume handled."),
    Feature("duration_minutes", "Duration (min)", "num", "f.duration_minutes", "How long the record took."),
    Feature("operational_cost", "Operational cost", "num", "f.operational_cost", "Cost of the record."),
    Feature("baseline_target", "Cost budget", "num", "e.baseline_target", "Per-record cost budget of the entity."),
]}

# task id -> (label, kind, SQL for the target, description)
TASKS = {
    "revenue": ("Predict revenue", "regression", "f.revenue", "Regression: how much revenue will a record bring in?"),
    "profit": ("Predict profit", "regression", "(f.revenue - f.operational_cost)", "Regression: revenue minus cost. Leave cost out of the features, or it becomes nearly an algebra problem."),
    "not_completed": ("Predict a problem record", "classification",
                      "CASE WHEN f.status IS NOT NULL AND f.status <> 'Completed' THEN 1 ELSE 0 END",
                      "Classification: will a record end up Delayed or Cancelled? Rare (about 1 in 14), so accuracy alone is misleading."),
}

MODELS = {
    "regression": {
        "linear": "Linear regression",
        "ridge": "Ridge regression",
        "random_forest": "Random forest",
        "gradient_boosting": "Gradient boosting",
        "neural_net": "Small neural network (MLP)",
        "hist_gradient_boosting": "Histogram gradient boosting (XGBoost-style)",
    },
    "classification": {
        "logistic": "Logistic regression",
        "random_forest": "Random forest",
        "gradient_boosting": "Gradient boosting",
        "neural_net": "Small neural network (MLP)",
        "hist_gradient_boosting": "Histogram gradient boosting (XGBoost-style)",
    },
}


class MlError(ValueError):
    """A problem the user can fix (shown as a 400)."""


def options() -> dict:
    return {
        "tasks": [{"id": k, "label": v[0], "kind": v[1], "description": v[3]} for k, v in TASKS.items()],
        "models": {k: [{"id": i, "label": l} for i, l in m.items()] for k, m in MODELS.items()},
        "features": [{"id": f.id, "label": f.label, "kind": f.kind, "note": f.note} for f in FEATURES.values()],
        "limits": {"min_rows": MIN_ROWS, "max_rows": MAX_ROWS},
    }


def _load(task: str, feature_ids: list[str]):
    import pandas as pd
    sel = ", ".join(f"{FEATURES[i].sql} AS {i}" for i in feature_ids)
    sql = (f"SELECT f.record_date AS record_date, {TASKS[task][2]} AS target, {sel} "
           "FROM fact_operations f LEFT JOIN dim_entities e ON f.entity_id = e.entity_id "
           "WHERE f.revenue IS NOT NULL AND f.operational_cost IS NOT NULL "
           "ORDER BY f.record_date DESC, f.fact_id LIMIT ?")
    with get_cursor() as cur:
        df = cur.execute(sql, [MAX_ROWS]).df()
    df = df.sort_values("record_date", kind="stable").reset_index(drop=True)
    # missing values: numbers get the median (learned from the data), text gets "Unknown"
    for i in feature_ids:
        if FEATURES[i].kind == "num":
            df[i] = pd.to_numeric(df[i], errors="coerce")
        else:
            df[i] = df[i].fillna("Unknown").astype(str)
    return df


def _time_split(df, test_fraction: float):
    """Split on a date boundary so no day appears on both sides."""
    dates = df["record_date"].drop_duplicates().tolist()
    if len(dates) < 4:
        raise MlError("Need at least 4 distinct days of data to split by time.")
    n_test_days = max(1, round(len(dates) * test_fraction))
    cutoff = dates[-n_test_days]
    train = df[df["record_date"] < cutoff]
    test = df[df["record_date"] >= cutoff]
    if len(train) < 50 or len(test) < 10:
        raise MlError(f"Not enough rows after the time split (train {len(train)}, test {len(test)}). Load more data or change the test size.")
    return train, test, cutoff


def _build_model(kind: str, name: str, num: list[str], cat: list[str], balance: bool):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor, GradientBoostingClassifier, GradientBoostingRegressor,
                                  RandomForestClassifier, RandomForestRegressor)
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    parts = []
    if num:
        parts.append(("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), num))
    if cat:
        parts.append(("cat", OneHotEncoder(handle_unknown="ignore"), cat))
    pre = ColumnTransformer(parts, sparse_threshold=0)       # dense output: some models (histogram boosting) can't take sparse input
    cw = "balanced" if balance else None
    est = {
        ("regression", "linear"): lambda: LinearRegression(),
        ("regression", "ridge"): lambda: Ridge(alpha=1.0),
        ("regression", "random_forest"): lambda: RandomForestRegressor(n_estimators=100, max_depth=8, random_state=RANDOM_STATE, n_jobs=1),
        ("regression", "gradient_boosting"): lambda: GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=RANDOM_STATE),
        # a small neural network: two hidden layers. scikit-learn's MLP runs on the CPU and needs no extra install.
        ("regression", "hist_gradient_boosting"): lambda: HistGradientBoostingRegressor(max_iter=150, random_state=RANDOM_STATE),
        ("classification", "hist_gradient_boosting"): lambda: HistGradientBoostingClassifier(max_iter=150, random_state=RANDOM_STATE, class_weight=cw),
        ("regression", "neural_net"): lambda: MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=400, random_state=RANDOM_STATE),
        ("classification", "neural_net"): lambda: MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=400, random_state=RANDOM_STATE),
        ("classification", "logistic"): lambda: LogisticRegression(max_iter=1000, class_weight=cw),
        ("classification", "random_forest"): lambda: RandomForestClassifier(n_estimators=100, max_depth=8, random_state=RANDOM_STATE, class_weight=cw, n_jobs=1),
        ("classification", "gradient_boosting"): lambda: GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=RANDOM_STATE),
    }[(kind, name)]()
    return Pipeline([("pre", pre), ("model", est)])


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


def train(task: str, model: str, feature_ids: list[str], test_fraction: float = 0.2,
          balance_classes: bool = False, threshold: float = 0.5, light: bool = False, keep_model: bool = False) -> dict:
    """`light=True` skips the slow extras (time-ordered cross-validation and permutation importance); used when comparing many models."""
    import time
    import numpy as np
    t0 = time.perf_counter()
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                                 mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score)
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score

    if task not in TASKS:
        raise MlError(f"Unknown task '{task}'.")
    kind = TASKS[task][1]
    if model not in MODELS[kind]:
        raise MlError(f"Model '{model}' isn't available for {kind}. Choose one of: {', '.join(MODELS[kind])}.")
    feature_ids = list(dict.fromkeys(feature_ids))
    if not feature_ids:
        raise MlError("Pick at least one feature.")
    bad = [f for f in feature_ids if f not in FEATURES]
    if bad:
        raise MlError(f"Unknown feature(s): {', '.join(bad)}.")
    if not 0.1 <= test_fraction <= 0.5:
        raise MlError("Test size must be between 10% and 50% of the days.")
    if not 0.05 <= threshold <= 0.95:
        raise MlError("Threshold must be between 0.05 and 0.95.")

    df = _load(task, feature_ids)
    if len(df) < MIN_ROWS:
        raise MlError(f"Only {len(df)} rows. Need at least {MIN_ROWS}. Load the sample dataset first (scripts/generate_sample_data.py).")
    train_df, test_df, cutoff = _time_split(df, test_fraction)
    num = [f for f in feature_ids if FEATURES[f].kind == "num"]
    cat = [f for f in feature_ids if FEATURES[f].kind == "cat"]
    X_tr, X_te = train_df[feature_ids], test_df[feature_ids]
    y_tr, y_te = train_df["target"].to_numpy(), test_df["target"].to_numpy()

    pipe = _build_model(kind, model, num, cat, balance_classes)
    warnings: list[str] = []
    lessons: list[str] = []

    if kind == "classification":
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        if y_tr.sum() < 5:
            raise MlError("Fewer than 5 problem records in the training period, so a model can't learn them. Load more data.")
        pipe.fit(X_tr, y_tr)
        proba = pipe.predict_proba(X_te)[:, 1]
        pred = (proba >= threshold).astype(int)
        base_label = int(y_tr.mean() >= 0.5)
        base_pred = np.full_like(y_te, base_label)
        tn, fp, fn, tp = confusion_matrix(y_te, pred, labels=[0, 1]).ravel()
        metrics = {
            "accuracy": _r(accuracy_score(y_te, pred)), "precision": _r(precision_score(y_te, pred, zero_division=0)),
            "recall": _r(recall_score(y_te, pred, zero_division=0)), "f1": _r(f1_score(y_te, pred, zero_division=0)),
            "roc_auc": _r(roc_auc_score(y_te, proba)) if len(set(y_te)) == 2 else None,
        }
        baseline = {"accuracy": _r(accuracy_score(y_te, base_pred)), "precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.5,
                    "description": "Always predict the most common outcome ('Completed')."}
        confusion = {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
        primary = ("f1", metrics["f1"], baseline["f1"])
        cv_scoring = "f1"
        if y_te.sum() == 0:
            warnings.append("The test period has no problem records, so recall and F1 are undefined (shown as 0). Use a longer test window.")
        if metrics["accuracy"] is not None and metrics["accuracy"] <= baseline["accuracy"] + 0.005:
            lessons.append(f"Accuracy ({metrics['accuracy']:.1%}) is no better than always guessing 'Completed' ({baseline['accuracy']:.1%}). "
                           "With rare events, accuracy hides failure. Look at recall and F1 instead.")
        if metrics["recall"] is not None and metrics["recall"] < 0.2 and not balance_classes:
            lessons.append("Recall is low: the model misses most problem records. Try 'Balance classes' or lower the threshold, then watch precision fall. That is the precision/recall trade-off.")
        sample = [{"actual": int(a), "predicted": _r(p, 3)} for a, p in list(zip(y_te, proba))[::max(1, -(-len(y_te) // 300))]]
    else:
        y_tr, y_te = y_tr.astype(float), y_te.astype(float)
        pipe.fit(X_tr, y_tr)
        pred = pipe.predict(X_te)
        base = np.full_like(y_te, y_tr.mean())
        rmse = lambda a, b: float(np.sqrt(mean_squared_error(a, b)))
        metrics = {"mae": _r(mean_absolute_error(y_te, pred), 2), "rmse": _r(rmse(y_te, pred), 2), "r2": _r(r2_score(y_te, pred))}
        baseline = {"mae": _r(mean_absolute_error(y_te, base), 2), "rmse": _r(rmse(y_te, base), 2), "r2": _r(r2_score(y_te, base)),
                    "description": "Always predict the average of the training period."}
        confusion = None
        primary = ("r2", metrics["r2"], baseline["r2"])
        cv_scoring = "r2"
        if metrics["mae"] >= baseline["mae"]:
            lessons.append("The model's error is no better than predicting the average. It found nothing useful. Check the features.")
        elif metrics["r2"] is not None and metrics["r2"] > 0.97:
            lessons.append("R² this high is worth a skeptical look: is a feature a near copy of the target? (e.g. units or duration may move almost 1:1 with revenue). "
                           "That is fine if you will know it at prediction time, and leakage if you won't.")
        sample = [{"actual": _r(a, 2), "predicted": _r(p, 2)} for a, p in list(zip(y_te, pred))[::max(1, -(-len(y_te) // 300))]]

    if kind == "classification" and balance_classes and model == "neural_net":
        warnings.append("The neural network has no class-weight option, so 'Balance classes' does nothing for it. Lower the threshold instead.")

    # time-ordered cross-validation on the training period only: shows how stable the score is
    cv = []
    try:
        if light:
            raise StopIteration
        cv = [_r(s) for s in cross_val_score(_build_model(kind, model, num, cat, balance_classes), X_tr, y_tr,
                                              cv=TimeSeriesSplit(n_splits=4), scoring=cv_scoring)]
    except StopIteration:
        pass
    except Exception:
        warnings.append("Cross-validation could not run on this selection (a fold had too little data).")

    # permutation importance on the test set: how much does the score drop when one feature is shuffled?
    importance = []
    if not light:
        imp = permutation_importance(pipe, X_te.head(3000), y_te[:3000], n_repeats=5, random_state=RANDOM_STATE,
                                     scoring=cv_scoring, n_jobs=1)
        importance = sorted(({"feature": f, "label": FEATURES[f].label, "importance": _r(m, 4)}
                             for f, m in zip(feature_ids, imp.importances_mean)), key=lambda x: -x["importance"])

    dates = lambda d: (str(d["record_date"].min())[:10], str(d["record_date"].max())[:10])
    return {
        "task": task, "kind": kind, "model": model, "features": feature_ids, "threshold": threshold if kind == "classification" else None,
        "balance_classes": balance_classes if kind == "classification" else None,
        "split": {"train_rows": len(train_df), "test_rows": len(test_df), "train_range": dates(train_df), "test_range": dates(test_df),
                  "cutoff": str(cutoff)[:10]},
        "metrics": metrics, "baseline": baseline, "primary_metric": {"name": primary[0], "model": primary[1], "baseline": primary[2]},
        "cv": {"metric": cv_scoring, "scores": cv, "mean": _r(np.mean(cv)) if cv else None, "std": _r(np.std(cv)) if cv else None},
        "confusion": confusion, "importance": importance, "sample": sample,
        "warnings": warnings, "lessons": lessons,
        "test_fraction": test_fraction, "seconds": round(time.perf_counter() - t0, 2),
        **({"_pipe": pipe, "_train_df": train_df[feature_ids]} if keep_model else {}),
    }


def compare(task: str, feature_ids: list[str], test_fraction: float = 0.2, balance_classes: bool = False,
            threshold: float = 0.5) -> dict:
    """Train every model that fits the task on the SAME split and rank them by the task's main score.

    Honest limits: it is one time-split, so a small gap between two models is noise, not a winner. The ranking tells you which
    family of model suits this data; it does not prove the top model will keep winning on next month's data.
    """
    if task not in TASKS:
        raise MlError(f"Unknown task '{task}'.")
    kind = TASKS[task][1]
    rows, failed = [], []
    for mid, label in MODELS[kind].items():
        try:
            res = train(task, mid, feature_ids, test_fraction, balance_classes, threshold, light=True)
        except MlError as e:
            if not rows and not failed:
                raise            # the same data problem would hit every model: say it once, plainly
            failed.append({"model": mid, "label": label, "error": str(e)})
            continue
        rows.append({"model": mid, "label": label, "result": res})
    # a higher R2 / F1 is better for every model here
    rows.sort(key=lambda r: (r["result"]["primary_metric"]["model"] is None, -(r["result"]["primary_metric"]["model"] or 0)))
    first = rows[0]["result"]
    pm = first["primary_metric"]
    out = []
    for i, r in enumerate(rows):
        res = r["result"]
        out.append({"rank": i + 1, "model": r["model"], "label": r["label"], "metrics": res["metrics"],
                    "score": res["primary_metric"]["model"], "seconds": res["seconds"], "result": res})
    best, second = out[0], out[1] if len(out) > 1 else None
    note = None
    if second and best["score"] is not None and second["score"] is not None and abs(best["score"] - second["score"]) < 0.02:
        note = (f"{best['label']} and {second['label']} are within 0.02 on {pm['name']}. With one time split that is a tie, "
                "not a winner: prefer the simpler or faster one.")
    return {"task": task, "kind": kind, "metric": pm["name"], "baseline": pm["baseline"], "features": first["features"],
            "split": first["split"], "models": out, "failed": failed, "note": note}
