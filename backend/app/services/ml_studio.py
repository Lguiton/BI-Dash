"""Model Studio: build, compare, tune and check predictive models on a dashboard's data (or any imported table).

What it does for you:
  * works out regression or classification, uses a time-ordered test split when there are dates, and always includes a do-nothing baseline
  * tries a menu of real algorithms (linear, Lasso, elastic net, KNN, tree, random forest, extra trees, gradient boosting, SVM, naive Bayes, small neural net)
  * ranks them by cross-validation on the training part only, so the test rows are never used to pick the winner
  * can tune the best ones with a small randomised search, balance rare classes, and tells you whether more data would help
  * reports honest test scores, which inputs matter, how the prediction changes with each input, and for yes/no targets the best cut-off for your costs

Honest limits: scikit-learn models only (no GPU, no PyTorch). A model that cannot beat the baseline is reported as exactly that. It finds patterns, not causes,
and it can only be as good as the columns it is given. Saved models are Python pickles written and read by this app only.
"""
from __future__ import annotations

import json
import re
import time
import warnings

import numpy as np
import pandas as pd

from app.services import biz_models
from app.services.biz_models import ModelError, _dir, _leaky, _prep, load

REG_MODELS = ["baseline", "ridge", "lasso", "elasticnet", "knn", "tree", "forest", "extra", "boosting", "svm", "neural"]
CLS_MODELS = ["baseline", "logistic", "bayes", "knn", "tree", "forest", "extra", "boosting", "svm", "neural"]
NICE = {"baseline": "Baseline (no learning)", "ridge": "Ridge regression", "lasso": "Lasso regression", "elasticnet": "Elastic net", "knn": "K-nearest neighbours", "tree": "Decision tree",
        "forest": "Random forest", "extra": "Extra trees", "boosting": "Gradient boosting", "svm": "Support vector machine", "neural": "Small neural network (MLP)",
        "logistic": "Logistic regression", "bayes": "Naive Bayes"}
SCALED = {"ridge", "lasso", "elasticnet", "knn", "svm", "neural", "logistic", "bayes"}
SLOW_ROWS = {"svm": 6000, "knn": 40000, "neural": 30000}
MAX_SECONDS = 120


def _estimator(key: str, task: str, balance: bool, seed: int = 42):
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import ElasticNet, Lasso, LogisticRegression, Ridge
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.svm import SVC, SVR
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    cw = "balanced" if balance else None
    if task == "regression":
        return {"baseline": lambda: DummyRegressor(strategy="mean"), "ridge": lambda: Ridge(alpha=1.0), "lasso": lambda: Lasso(alpha=0.01, max_iter=5000),
                "elasticnet": lambda: ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=5000), "knn": lambda: KNeighborsRegressor(n_neighbors=7),
                "tree": lambda: DecisionTreeRegressor(max_depth=6, min_samples_leaf=5, random_state=seed),
                "forest": lambda: RandomForestRegressor(n_estimators=150, max_depth=10, min_samples_leaf=2, random_state=seed, n_jobs=1),
                "extra": lambda: ExtraTreesRegressor(n_estimators=150, max_depth=12, min_samples_leaf=2, random_state=seed, n_jobs=1),
                "boosting": lambda: HistGradientBoostingRegressor(max_iter=150, learning_rate=0.08, random_state=seed),
                "svm": lambda: SVR(C=3.0), "neural": lambda: MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-3, max_iter=400, early_stopping=True, random_state=seed)}[key]()
    return {"baseline": lambda: DummyClassifier(strategy="most_frequent"), "logistic": lambda: LogisticRegression(max_iter=1000, class_weight=cw), "bayes": lambda: GaussianNB(),
            "knn": lambda: KNeighborsClassifier(n_neighbors=7), "tree": lambda: DecisionTreeClassifier(max_depth=6, min_samples_leaf=5, class_weight=cw, random_state=seed),
            "forest": lambda: RandomForestClassifier(n_estimators=150, max_depth=10, min_samples_leaf=2, class_weight=cw, random_state=seed, n_jobs=1),
            "extra": lambda: ExtraTreesClassifier(n_estimators=150, max_depth=12, min_samples_leaf=2, class_weight=cw, random_state=seed, n_jobs=1),
            "boosting": lambda: HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, class_weight=cw, random_state=seed),
            "svm": lambda: SVC(C=3.0, probability=True, class_weight=cw, random_state=seed),
            "neural": lambda: MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-3, max_iter=400, early_stopping=True, random_state=seed)}[key]()


GRIDS = {
    "ridge": {"m__alpha": [0.01, 0.1, 1, 10, 100]}, "lasso": {"m__alpha": [0.0005, 0.001, 0.01, 0.1, 1]}, "elasticnet": {"m__alpha": [0.001, 0.01, 0.1, 1], "m__l1_ratio": [0.2, 0.5, 0.8]},
    "logistic": {"m__C": [0.01, 0.1, 1, 10, 100]}, "knn": {"m__n_neighbors": [3, 5, 9, 15, 25], "m__weights": ["uniform", "distance"]},
    "tree": {"m__max_depth": [3, 5, 8, 12], "m__min_samples_leaf": [1, 3, 5, 10, 20]},
    "forest": {"m__n_estimators": [100, 200], "m__max_depth": [None, 6, 10, 16], "m__min_samples_leaf": [1, 3, 5], "m__max_features": ["sqrt", 0.5, 1.0]},
    "extra": {"m__n_estimators": [100, 200], "m__max_depth": [None, 8, 14], "m__min_samples_leaf": [1, 3, 5], "m__max_features": ["sqrt", 0.5, 1.0]},
    "boosting": {"m__learning_rate": [0.03, 0.06, 0.1, 0.2], "m__max_depth": [None, 3, 5], "m__max_leaf_nodes": [15, 31, 63], "m__l2_regularization": [0, 0.1, 1.0]},
    "svm": {"m__C": [0.3, 1, 3, 10, 30]}, "neural": {"m__hidden_layer_sizes": [(16,), (32,), (32, 16), (64, 32)], "m__alpha": [1e-4, 1e-3, 1e-2]},
    "bayes": {"m__var_smoothing": [1e-9, 1e-7, 1e-5, 1e-3]},
}


def _pre(num: list[str], cat: list[str], scale: bool):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    steps_n = [("imp", SimpleImputer(strategy="median"))] + ([("sc", StandardScaler())] if scale else [])
    return ColumnTransformer([("n", Pipeline(steps_n), num), ("c", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                              ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=5, sparse_output=False))]), cat)])


def _pipe(key, task, num, cat, balance):
    from sklearn.pipeline import Pipeline
    return Pipeline([("pre", _pre(num, cat, key in SCALED)), ("m", _estimator(key, task, balance))])


def _r(x, nd=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), nd)


def _splitter(date_col, task, y_tr):
    from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit
    if date_col:
        return TimeSeriesSplit(n_splits=3), "time-ordered folds"
    if task == "classification" and y_tr.value_counts().min() >= 3:
        return StratifiedKFold(n_splits=3, shuffle=True, random_state=42), "3-fold stratified"
    return KFold(n_splits=3, shuffle=True, random_state=42), "3-fold"


def _scores(task, y_true, pr, proba, classes):
    from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss, f1_score, log_loss, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
    if task == "regression":
        yt = np.asarray(y_true, dtype=float)
        mape = float(np.mean(np.abs((yt - pr) / yt))) * 100 if np.all(yt != 0) else None
        return {"mae": _r(mean_absolute_error(yt, pr)), "rmse": _r(mean_squared_error(yt, pr) ** 0.5), "r2": _r(r2_score(yt, pr)), "mape_pct": _r(mape, 2)}
    out = {"accuracy": _r(accuracy_score(y_true, pr)), "balanced_accuracy": _r(balanced_accuracy_score(y_true, pr)), "macro_f1": _r(f1_score(y_true, pr, average="macro"))}
    if proba is not None:
        try:
            yt = np.asarray(y_true)
            if len(classes) == 2:
                pos = (yt == classes[1]).astype(int)
                out.update(roc_auc=_r(roc_auc_score(pos, proba[:, 1])), pr_auc=_r(average_precision_score(pos, proba[:, 1])), brier=_r(brier_score_loss(pos, proba[:, 1])), log_loss=_r(log_loss(pos, proba[:, 1])))
            else:
                out.update(roc_auc=_r(roc_auc_score(yt, proba, multi_class="ovr", labels=list(classes))), log_loss=_r(log_loss(yt, proba, labels=list(classes))))
        except ValueError:
            pass
    return out


def build(source: str, target: str, features: list[str] | None = None, task: str = "auto", options: dict | None = None) -> dict:
    """options: models (list of keys or 'all'), tune (bool), balance (True/False/'auto'), seconds (time budget), fp_cost, fn_cost, seed."""
    from sklearn.base import clone
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import RandomizedSearchCV, cross_val_score
    import joblib
    o = options or {}
    t0 = time.time()
    budget = max(15, min(int(o.get("seconds", 75)), MAX_SECONDS))
    warnings.filterwarnings("ignore")
    df, label = load(source)
    df, cols, date_col, notes = _prep(df, target, features)
    if not cols:
        raise ModelError("No usable input columns left to predict from.")
    y = df[target]
    numeric_target = pd.api.types.is_numeric_dtype(y)
    if task == "auto":
        task = "regression" if numeric_target and y.nunique() > 12 else "classification"
    if task not in ("regression", "classification"):
        raise ModelError("task must be auto, regression or classification.")
    if task == "regression" and not numeric_target:
        raise ModelError(f"'{target}' isn't a number, so it can only be classified.")
    if y.nunique() < 2:
        raise ModelError(f"'{target}' has one value only: nothing to predict.")
    if task == "classification":
        vc = y.astype(str).value_counts()
        if len(vc) > 12:
            raise ModelError(f"'{target}' has {len(vc)} distinct values; classification handles up to 12.")
        if vc.min() < 5:
            notes.append(f"Rarest class '{vc.idxmin()}' has only {vc.min()} rows, so its results are unreliable.")
        y = y.astype(str)
    X = df[cols]
    num = [c for c in cols if pd.api.types.is_numeric_dtype(X[c])]
    cat = [c for c in cols if c not in num]
    leaks = _leaky(X, y, task, cols, num)
    if leaks and not features:
        notes += [f"Left out '{c}': on its own it predicts '{target}' almost perfectly ({how}), so it is probably a copy of the answer, not a real driver." for c, how in leaks]
        cols = [c for c in cols if c not in dict(leaks)]
        X = df[cols]
        num, cat = [c for c in num if c in cols], [c for c in cat if c in cols]
        if not cols:
            raise ModelError("Every input looks like a copy of the answer. Choose different inputs.")
    elif leaks:
        notes += [f"'{c}' predicts '{target}' almost perfectly on its own ({how}); the model may just be copying it." for c, how in leaks]
    cut = int(len(df) * 0.8)
    if date_col:
        tr, te = np.arange(cut), np.arange(cut, len(df))
        split = f"time-ordered: trained on the earliest 80%, tested on the latest 20% (after {df[date_col].iloc[cut - 1].date()})"
    else:
        idx = np.random.default_rng(int(o.get("seed", 42))).permutation(len(df))
        tr, te = idx[:cut], idx[cut:]
        split = "random 80/20 (no date column to order by)"
    ytr, yte = y.iloc[tr], y.iloc[te]
    classes = sorted(ytr.unique()) if task == "classification" else None
    if task == "classification":
        yte_known = yte.isin(classes)
        if not yte_known.all():
            te = te[yte_known.to_numpy()]
            yte = y.iloc[te]
    minority = float(ytr.value_counts(normalize=True).min()) if task == "classification" else 1.0
    balance = (minority < 0.25) if o.get("balance", "auto") == "auto" else bool(o.get("balance"))
    if task == "classification" and balance:
        notes.append(f"Rare classes are re-weighted so they count equally (smallest class is {minority * 100:.0f}% of training rows).")
    menu = REG_MODELS if task == "regression" else CLS_MODELS
    want = menu if o.get("models") in (None, "all") else [m for m in o["models"] if m in menu]
    if "baseline" not in want:
        want = ["baseline"] + want
    cv, cv_name = _splitter(date_col, task, ytr)
    scoring = "neg_mean_absolute_error" if task == "regression" else "f1_macro"
    board, fitted, skipped = [], {}, []
    Xtr, Xte = X.iloc[tr], X.iloc[te]
    for key in want:
        if time.time() - t0 > budget * 0.6 and key != "baseline":
            skipped.append({"model": NICE[key], "why": "ran out of the time budget"})
            continue
        if key in SLOW_ROWS and len(tr) > SLOW_ROWS[key]:
            skipped.append({"model": NICE[key], "why": f"too slow on {len(tr):,} rows (limit {SLOW_ROWS[key]:,})"})
            continue
        s0 = time.time()
        try:
            pipe = _pipe(key, task, num, cat, balance)
            cvs = cross_val_score(pipe, Xtr, ytr, cv=cv, scoring=scoring, n_jobs=1)
            pipe.fit(Xtr, ytr)
            pr = pipe.predict(Xte)
            proba = pipe.predict_proba(Xte) if task == "classification" and hasattr(pipe, "predict_proba") else None
            if proba is not None and list(pipe.classes_) != list(classes):
                proba = None
        except Exception as e:  # noqa: BLE001
            skipped.append({"model": NICE[key], "why": f"failed: {type(e).__name__}"})
            continue
        sc = _scores(task, yte, pr, proba, classes)
        board.append({"key": key, "model": NICE[key], "cv_mean": _r(cvs.mean() if task == "classification" else -cvs.mean()), "cv_std": _r(cvs.std()), "test": sc, "seconds": _r(time.time() - s0, 1), "tuned": False})
        fitted[key] = pipe
    if len(board) < 2:
        raise ModelError("No model could be trained on this data. " + "; ".join(f"{s['model']}: {s['why']}" for s in skipped))
    higher = task == "classification"
    order = sorted(board, key=lambda r: -r["cv_mean"] if higher else r["cv_mean"])
    base = next(r for r in board if r["key"] == "baseline")
    # tuning: the two best real models
    tuned_note = ""
    if o.get("tune"):
        done = []
        for r in [r for r in order if r["key"] != "baseline"][:2]:
            if time.time() - t0 > budget or r["key"] not in GRIDS:
                continue
            try:
                s0 = time.time()
                rs = RandomizedSearchCV(_pipe(r["key"], task, num, cat, balance), GRIDS[r["key"]], n_iter=10, cv=cv, scoring=scoring, random_state=42, n_jobs=1, refit=True)
                rs.fit(Xtr, ytr)
                new_cv = rs.best_score_ if higher else -rs.best_score_
                better = new_cv > r["cv_mean"] if higher else new_cv < r["cv_mean"]
                if better:
                    pr = rs.best_estimator_.predict(Xte)
                    proba = rs.best_estimator_.predict_proba(Xte) if task == "classification" and hasattr(rs.best_estimator_, "predict_proba") else None
                    if proba is not None and list(rs.best_estimator_.classes_) != list(classes):
                        proba = None
                    prm = {k.replace("m__", ""): (v if isinstance(v, (int, float, str, type(None), tuple)) else str(v)) for k, v in rs.best_params_.items()}
                    board.append({"key": r["key"] + "+tuned", "model": NICE[r["key"]] + " (tuned)", "cv_mean": _r(new_cv), "cv_std": _r(rs.cv_results_["std_test_score"][rs.best_index_]), "test": _scores(task, yte, pr, proba, classes),
                                  "seconds": _r(time.time() - s0, 1), "tuned": True, "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in prm.items()}})
                    fitted[r["key"] + "+tuned"] = rs.best_estimator_
                    done.append(f"{NICE[r['key']]}: CV {r['cv_mean']} → {_r(new_cv)}")
                else:
                    done.append(f"{NICE[r['key']]}: tuning found nothing better than the defaults")
            except Exception:  # noqa: BLE001
                continue
        tuned_note = "Tuning: " + "; ".join(done) + "." if done else "Tuning was skipped (no time left or nothing tunable)."
        order = sorted(board, key=lambda r: -r["cv_mean"] if higher else r["cv_mean"])
    best = next(r for r in order if r["key"] != "baseline")
    # honest verdict against the baseline on the held-out test rows
    if task == "regression":
        b_mae, m_mae = base["test"]["mae"], best["test"]["mae"]
        gain = 100.0 * (b_mae - m_mae) / b_mae if b_mae else 0.0
        useful = gain >= 5
        verdict = (f"{best['model']} is off by {m_mae:,.2f} on average on rows it never saw, {gain:.0f}% better than always guessing the average ({b_mae:,.2f}). " if useful else
                   f"No model beat guessing the average by a meaningful margin (best gain {gain:.0f}%). The inputs don't explain '{target}' well, so don't rely on this. ")
    else:
        gain = 100.0 * (best["test"]["accuracy"] - base["test"]["accuracy"])
        gain_f1 = best["test"]["macro_f1"] - base["test"]["macro_f1"]
        useful = (gain >= 5 or (minority < 0.25 and gain_f1 >= 0.1)) and best["test"]["macro_f1"] > base["test"]["macro_f1"]
        verdict = (f"{best['model']} gets {best['test']['accuracy'] * 100:.0f}% right on rows it never saw (macro F1 {best['test']['macro_f1']:.2f}), against {base['test']['accuracy'] * 100:.0f}% for always guessing the most common. " if useful else
                   f"No model beat always guessing the most common class ({base['test']['accuracy'] * 100:.0f}% right) by a meaningful margin. The inputs don't explain '{target}' well, so don't rely on this. ")
    cv_pick = f"Ranked by {cv_name} cross-validation on the training rows only; the test rows were never used to choose."
    if len(te) < 60:
        notes.append(f"Only {len(te)} test rows, so these numbers are rough.")
    best_pipe = fitted[best["key"]]
    pr_best = best_pipe.predict(Xte)
    detail: dict = {}
    if task == "classification":
        from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
        cm = confusion_matrix(yte, pr_best, labels=classes)
        p_, r_, f_, s_ = precision_recall_fscore_support(yte, pr_best, labels=classes, zero_division=0)
        detail["confusion"] = {"labels": classes, "matrix": cm.tolist()}
        detail["per_class"] = [{"class": c, "precision": _r(a), "recall": _r(b), "f1": _r(d), "rows": int(e)} for c, a, b, d, e in zip(classes, p_, r_, f_, s_)]
        if len(classes) == 2 and hasattr(best_pipe, "predict_proba") and list(best_pipe.classes_) == list(classes):
            pp = best_pipe.predict_proba(Xte)[:, 1]
            pos = (yte.to_numpy() == classes[1])
            fpc, fnc = float(o.get("fp_cost", 1.0)), float(o.get("fn_cost", 1.0))
            grid = np.round(np.linspace(0.05, 0.95, 19), 2)
            costs = [float(((pp >= t) & ~pos).sum() * fpc + ((pp < t) & pos).sum() * fnc) for t in grid]
            bi = int(np.argmin(costs))
            detail["threshold"] = {"positive_class": classes[1], "fp_cost": fpc, "fn_cost": fnc, "best_cutoff": float(grid[bi]), "cost_at_best": _r(costs[bi], 2), "cost_at_0.5": _r(costs[int(np.argmin(abs(grid - 0.5)))], 2),
                                   "curve": [{"cutoff": float(t), "cost": _r(c, 2)} for t, c in zip(grid, costs)],
                                   "note": f"Call a row '{classes[1]}' when its probability is at least {grid[bi]:.2f} to minimise cost (a false alarm costs {fpc:g}, a miss costs {fnc:g})."}
    else:
        err = np.abs(yte.to_numpy(dtype=float) - pr_best)
        within = float(np.mean(err <= 0.1 * np.abs(yte.to_numpy(dtype=float)))) if np.all(yte != 0) else None
        detail["errors"] = {"median_abs_error": _r(np.median(err)), "p90_abs_error": _r(np.quantile(err, 0.9)), "share_within_10pct": _r(within, 3), "bias": _r(float(np.mean(pr_best - yte.to_numpy(dtype=float))))}
    # learning curve: would more data help?
    lc = []
    try:
        if time.time() - t0 < budget:
            for frac in (0.4, 0.7, 1.0):
                n_ = max(30, int(len(tr) * frac))
                p2 = clone(best_pipe).fit(Xtr.iloc[:n_], ytr.iloc[:n_])
                pr2 = p2.predict(Xte)
                lc.append({"rows": int(n_), "score": _r(_scores(task, yte, pr2, None, classes)["mae" if task == "regression" else "macro_f1"])})
    except Exception:  # noqa: BLE001
        lc = []
    if len(lc) == 3:
        a, b = lc[1]["score"], lc[2]["score"]
        better = (b < a) if task == "regression" else (b > a)
        detail["learning_curve"] = {"points": lc, "metric": "mae" if task == "regression" else "macro_f1",
                                    "says": "Still improving as rows are added, so collecting more data should help." if better and abs(b - a) > 0.02 * (abs(a) or 1) else "Flat at the end, so more rows of the same kind are unlikely to help; better inputs would."}
    imp = permutation_importance(best_pipe, Xte, yte, n_repeats=5, random_state=42, n_jobs=1, scoring="neg_mean_absolute_error" if task == "regression" else "f1_macro")
    order_i = np.argsort(-imp.importances_mean)[:8]
    importance = [] if not useful else [{"input": cols[i], "importance": _r(imp.importances_mean[i]), "spread": _r(imp.importances_std[i])} for i in order_i if imp.importances_mean[i] > 0]
    # how the prediction moves with each of the top numeric inputs
    effects = []
    if useful:
        try:
            for c in [i["input"] for i in importance if i["input"] in num][:3]:
                qs = np.unique(np.quantile(Xtr[c].dropna(), np.linspace(0.05, 0.95, 7)))
                vals = []
                for q in qs:
                    Z = Xte.copy()
                    Z[c] = q
                    if task == "regression":
                        vals.append(float(np.mean(best_pipe.predict(Z))))
                    elif hasattr(best_pipe, "predict_proba") and len(classes) == 2 and list(best_pipe.classes_) == list(classes):
                        vals.append(float(np.mean(best_pipe.predict_proba(Z)[:, 1])))
                    else:
                        vals.append(float(np.mean(best_pipe.predict(Z) == classes[0])))
                effects.append({"input": c, "values": [_r(q) for q in qs], "average_prediction": [_r(v) for v in vals],
                                "meaning": "average predicted value" if task == "regression" else (f"average chance of '{classes[1]}'" if len(classes) == 2 else f"share predicted '{classes[0]}'")})
        except Exception:  # noqa: BLE001
            effects = []
    baselines = {c: (float(Xtr[c].median()) if c in num else str(Xtr[c].mode().iloc[0])) for c in cols if Xtr[c].notna().any()}
    mid = f"{re.sub(r'[^a-z0-9]+', '-', source.lower()).strip('-')[:24]}-{re.sub(r'[^a-z0-9]+', '-', target.lower())[:16]}-{int(time.time()) % 10**7}"
    report = {"id": mid, "engine": "studio", "source": source, "label": label, "target": target, "task": task, "inputs": cols, "rows": int(len(df)), "train_rows": int(len(tr)), "test_rows": int(len(te)),
              "split": split, "cv": cv_name, "balanced": bool(balance), "leaderboard": [{k: v for k, v in r.items() if k != "key"} for r in order], "skipped": skipped, "best": best["model"], "best_key": best["key"],
              "baseline_test": base["test"], "useful": bool(useful), "verdict": verdict.strip(), "how_chosen": cv_pick, "tuning": tuned_note, "importance": importance, "effects": effects, "detail": detail,
              "notes": notes, "created": time.strftime("%Y-%m-%d %H:%M"), "input_types": {c: ("number" if c in num else "text") for c in cols}, "baselines": baselines,
              "classes": classes, "seconds": _r(time.time() - t0, 1),
              # keep the same fields the simple builder reports so the existing screens keep working
              "results": [{"model": r["model"], **{k: v for k, v in r["test"].items() if k in ("mae", "r2", "accuracy", "macro_f1")}} for r in order]}
    d = _dir()
    joblib.dump(best_pipe, d / f"{mid}.joblib")
    (d / f"{mid}.json").write_text(json.dumps(report, default=str))
    for old in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-biz_models.MAX_MODELS]:
        old.unlink(missing_ok=True)
        old.with_suffix(".joblib").unlink(missing_ok=True)
    return report


def predict_proba(mid: str, rows: list[dict]) -> dict:
    """Predictions plus, for classification, the chance of each class."""
    import joblib
    j, m = biz_models._paths(mid)
    rep = json.loads(j.read_text())
    out = biz_models.predict(mid, rows)
    res = {**out, "classes": rep.get("classes")}
    pipe = joblib.load(m)
    if rep["task"] == "classification" and hasattr(pipe, "predict_proba"):
        df = _frame(rep, rows)
        pr = pipe.predict_proba(df[rep["inputs"]])
        res["probabilities"] = [{c: _r(p) for c, p in zip(pipe.classes_, row)} for row in pr]
    return res


def _frame(rep: dict, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if {"day_of_week", "month"} & set(rep["inputs"]) and "record_date" in df.columns:
        d = pd.to_datetime(df["record_date"], errors="coerce")
        df["day_of_week"], df["month"] = d.dt.dayofweek, d.dt.month
    miss = [c for c in rep["inputs"] if c not in df.columns]
    if miss:
        raise ModelError("Each row needs: " + ", ".join(rep["inputs"]) + ". Missing: " + ", ".join(miss) + ".")
    for c, t in rep["input_types"].items():
        if t == "number":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def explain_row(mid: str, row: dict) -> dict:
    """Why this prediction? Swap each input for a typical value and see how far the prediction moves."""
    import joblib
    j, m = biz_models._paths(mid)
    rep = json.loads(j.read_text())
    if "baselines" not in rep:
        raise ModelError("This model was built before explanations existed. Build it again with the Model Studio.")
    pipe = joblib.load(m)
    df = _frame(rep, [row])[rep["inputs"]]
    cls = rep["task"] == "classification"

    def score(frame):
        if not cls:
            return float(pipe.predict(frame)[0])
        if hasattr(pipe, "predict_proba") and len(rep["classes"]) == 2:
            return float(pipe.predict_proba(frame)[0][list(pipe.classes_).index(rep["classes"][1])])
        return float(pipe.predict(frame)[0] == rep["classes"][0])
    full = score(df)
    rows = []
    for c in rep["inputs"]:
        z = df.copy()
        z[c] = rep["baselines"].get(c, z[c].iloc[0])
        rows.append({"input": c, "value": df[c].iloc[0] if not hasattr(df[c].iloc[0], "item") else df[c].iloc[0].item(), "typical": rep["baselines"].get(c), "effect": _r(full - score(z))})
    rows.sort(key=lambda r: -abs(r["effect"] or 0))
    what = "predicted value" if not cls else (f"chance of '{rep['classes'][1]}'" if len(rep["classes"]) == 2 else f"chance of '{rep['classes'][0]}'")
    pred = pipe.predict(df)[0]
    return {"model": mid, "prediction": pred.item() if hasattr(pred, "item") else pred, "score": _r(full), "score_means": what, "reasons": rows[:8],
            "how": "Each 'effect' is how much the " + what + " changes versus replacing that one input with a typical value. Positive pushes it up. It describes this model, not cause and effect."}


def batch_score(mid: str, csv_text: str) -> dict:
    """Score every row of a CSV (up to 20,000). Returns the rows with prediction columns added."""
    import io
    import joblib
    j, m = biz_models._paths(mid)
    rep = json.loads(j.read_text())
    df = pd.read_csv(io.StringIO(csv_text))
    if len(df) == 0 or len(df) > 20000:
        raise ModelError("Send between 1 and 20,000 rows.")
    f = _frame(rep, df.to_dict("records"))
    pipe = joblib.load(m)
    out = df.copy()
    out["prediction"] = pipe.predict(f[rep["inputs"]])
    if rep["task"] == "classification" and hasattr(pipe, "predict_proba"):
        pr = pipe.predict_proba(f[rep["inputs"]])
        for i, c in enumerate(pipe.classes_):
            out[f"probability_{c}"] = np.round(pr[:, i], 4)
    return {"rows": int(len(out)), "csv": out.to_csv(index=False), "columns": list(out.columns)}


def menu() -> dict:
    return {"regression": [{"key": k, "name": NICE[k]} for k in REG_MODELS], "classification": [{"key": k, "name": NICE[k]} for k in CLS_MODELS],
            "limits": {"seconds": MAX_SECONDS, "svm_rows": SLOW_ROWS["svm"]}}


TOOL_STUDIO = {"name": "ml_studio", "description": "Do real machine-learning work on one of the user's dashboard tables, or on text they paste. action 'build': compare many models (baseline, linear, Lasso, KNN, tree, forest, extra trees, boosting, SVM, naive Bayes, small neural net) "
               "by cross-validation, then report honest held-out scores, whether it beats guessing, what matters, and for yes/no targets the best cut-off for given costs (source = dashboard id such as repair-jobs, target = column, optional features, tune true/false, fp_cost, fn_cost). "
               "action 'language': run the language or deep-learning agent from a plain request (request = e.g. 'sort tickets by category', 'find unusual rows', 'forecast price with a neural network'; source or data = the rows; optional text_col, label_col, target). "
               "Saved models appear in the Model Studio. Always report the baseline comparison and whether the result is trustworthy.",
               "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["build", "language"]}, "source": {"type": "string"}, "target": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}},
                                                                 "tune": {"type": "boolean"}, "fp_cost": {"type": "number"}, "fn_cost": {"type": "number"}, "request": {"type": "string"}, "data": {"type": "string"}, "text_col": {"type": "string"}, "label_col": {"type": "string"}},
                                "required": ["action"]}}


def tool_result(args: dict) -> str:
    a = args or {}
    if a.get("action") == "language":
        from app.services import nlp_dl_studio as nd
        try:
            r = nd.run(str(a.get("request", "")), str(a.get("data", "")), str(a.get("source", "")), str(a.get("text_col", "")), str(a.get("label_col", "")), str(a.get("target", "")), "")
        except nd.StudioError as e:
            raise ModelError(e.message, e.status) from e
        return json.dumps({k: r[k] for k in ("agent", "task", "findings", "caveats", "used")} | {"tables": [{"title": t["title"], "columns": t["columns"], "rows": t["rows"][:8]} for t in r["tables"][:3]]}, default=str)[:8000]
    r = build(str(a.get("source", "")), str(a.get("target", "")), a.get("features") or None, "auto",
              {"tune": bool(a.get("tune")), "fp_cost": a.get("fp_cost", 1.0), "fn_cost": a.get("fn_cost", 1.0), "seconds": 60})
    keep = {k: r[k] for k in ("id", "task", "rows", "split", "best", "useful", "verdict", "how_chosen", "tuning", "notes")}
    keep["leaderboard"] = [{"model": x["model"], "cv": x["cv_mean"], "test": x["test"]} for x in r["leaderboard"]]
    keep["important_inputs"] = [i["input"] for i in r["importance"]]
    th = r["detail"].get("threshold")
    if th:
        keep["cutoff_advice"] = th["note"]
    return json.dumps(keep, default=str)[:8000]
