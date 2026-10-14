"""Build, check and use a predictive model on a business dashboard's data (or any imported table).

Pick a target column and the builder works out the rest: regression or classification, a time-ordered test split when the
data has dates, a do-nothing baseline to beat, two real candidates, honest metrics on rows the model never saw, which
inputs matter, and a plain verdict. Models are saved next to the database file and can score new rows.

Honest limits: this is a careful baseline model, not a production ML system. It cannot tell correlation from cause, it
trusts the columns it is given, and a model that only ties the baseline is reported as exactly that. Model files are
Python pickles written and read by this app only; never copy in a model file from someone else.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from app.services import biz_packs
from app.services.db import fetch_all, get_cursor

MAX_ROWS = 100_000
MIN_ROWS = 40
MAX_MODELS = 30
MAX_PREDICT_ROWS = 200


class ModelError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _dir() -> Path:
    from app.config import db_path
    from app.services import db
    base = Path(db._path) if getattr(db, "_path", None) else db_path()
    d = base.parent / f"{base.stem}_models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _table_for(source: str) -> tuple[str, str]:
    """Return (sql table name, label). A pack id maps to its biz_ table; any other name must be an existing table."""
    if biz_packs.find(source):
        if biz_packs.installed(source) is None:
            raise ModelError("That dashboard has no data yet.")
        return biz_packs._table(source), biz_packs.find(source)["title"]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", source or ""):
        raise ModelError("Give a dashboard id or a table name.")
    with get_cursor() as cur:
        ok = cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ? AND table_schema = 'main'", [source]).fetchone()[0]
    if not ok:
        raise ModelError(f"No table or dashboard called '{source}'.", 404)
    return source, source


def load(source: str) -> tuple[pd.DataFrame, str]:
    t, label = _table_for(source)
    with get_cursor() as cur:
        df = cur.execute(f"SELECT * FROM {t} LIMIT {MAX_ROWS}").df()
    return df, label


def _prep(df: pd.DataFrame, target: str, features: list[str] | None):
    if target not in df.columns:
        raise ModelError(f"'{target}' isn't a column. Columns: {', '.join(df.columns)}.")
    df = df.dropna(subset=[target]).copy()
    if len(df) < MIN_ROWS:
        raise ModelError(f"Need at least {MIN_ROWS} rows with a value for '{target}'; found {len(df)}.")
    date_col = next((c for c in df.columns if str(df[c].dtype).startswith("datetime") or c == "record_date"), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)
        df["day_of_week"] = df[date_col].dt.dayofweek
        df["month"] = df[date_col].dt.month
    notes: list[str] = []
    cols = [c for c in (features or df.columns) if c not in (target, date_col) and c in df.columns]
    if features:
        bad = [c for c in features if c not in df.columns]
        if bad:
            raise ModelError("Unknown feature columns: " + ", ".join(bad))
    if not features and date_col:
        cols += ["day_of_week", "month"]
    n = len(df)
    keep = []
    for c in dict.fromkeys(cols):
        s = df[c]
        if s.nunique(dropna=True) <= 1:
            notes.append(f"Dropped '{c}': one value only.")
        elif s.dtype == object and s.nunique() > max(30, 0.5 * n):
            notes.append(f"Dropped '{c}': looks like an ID or free text ({s.nunique()} distinct values).")
        else:
            keep.append(c)
    return df, keep, date_col, notes


def _leaky(X: pd.DataFrame, y: pd.Series, task: str, cols: list[str], num: list[str]) -> list[tuple[str, str]]:
    """Inputs that, alone, predict the target almost perfectly under cross-validation (a tiny tree, so only a near-copy passes)."""
    from sklearn.model_selection import cross_val_score
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    n = min(len(X), 4000)
    idx = np.random.default_rng(7).permutation(len(X))[:n]
    yy = y.iloc[idx]
    out = []
    for c in cols:
        col = X[c].iloc[idx]
        v = col.to_numpy(dtype=float, na_value=np.nan) if c in num else pd.factorize(col.astype(str))[0].astype(float)
        v = np.nan_to_num(v, nan=-1e9).reshape(-1, 1)
        try:
            if task == "regression":
                sc = float(cross_val_score(DecisionTreeRegressor(max_depth=6, min_samples_leaf=5, random_state=0), v, yy, cv=3, scoring="r2").mean())
                if sc >= 0.98:
                    out.append((c, f"R2 {sc:.2f}"))
            else:
                sc = float(cross_val_score(DecisionTreeClassifier(max_depth=6, min_samples_leaf=5, random_state=0), v, yy, cv=3, scoring="accuracy").mean())
                if sc >= 0.98 and yy.value_counts(normalize=True).iloc[0] < 0.95:
                    out.append((c, f"{sc*100:.0f}% right"))
        except ValueError:
            continue
    return out


def build(source: str, target: str, features: list[str] | None = None, task: str = "auto") -> dict:
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    import joblib

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
        notes += [f"Left out '{c}': on its own it predicts '{target}' almost perfectly ({how}), so it is probably a copy of the answer, not a real driver. Pass it in features to force it." for c, how in leaks]
        cols = [c for c in cols if c not in dict(leaks)]
        X = df[cols]
        num = [c for c in num if c in cols]
        cat = [c for c in cat if c in cols]
        if not cols:
            raise ModelError("Every input looks like a copy of the answer. Choose different inputs.")
    elif leaks:
        notes += [f"'{c}' predicts '{target}' almost perfectly on its own ({how}); the model may just be copying it." for c, how in leaks]
    cut = int(len(df) * 0.8)
    if date_col:
        tr, te = np.arange(cut), np.arange(cut, len(df))
        split = f"time-ordered: trained on the earliest 80%, tested on the latest 20% (after {df[date_col].iloc[cut - 1].date()})"
    else:
        rng = np.random.default_rng(42)
        idx = rng.permutation(len(df))
        tr, te = idx[:cut], idx[cut:]
        split = "random 80/20 (no date column to order by)"

    def pre(scale: bool):
        steps_n = [("imp", SimpleImputer(strategy="median"))] + ([("sc", StandardScaler())] if scale else [])
        return ColumnTransformer([("n", Pipeline(steps_n), num), ("c", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                                  ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=5, sparse_output=False))]), cat)])

    if task == "regression":
        models = {"Baseline (always the average)": DummyRegressor(strategy="mean"), "Ridge regression": Ridge(alpha=1.0),
                  "Random forest": RandomForestRegressor(n_estimators=150, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=1)}
    else:
        models = {"Baseline (always the most common)": DummyClassifier(strategy="most_frequent"),
                  "Logistic regression": LogisticRegression(max_iter=500), "Random forest": RandomForestClassifier(n_estimators=150, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=1)}
    results, fitted = [], {}
    for name, est in models.items():
        pipe = Pipeline([("pre", pre(scale="regression" in name.lower() or "logistic" in name.lower())), ("m", est)])
        pipe.fit(X.iloc[tr], y.iloc[tr])
        pr = pipe.predict(X.iloc[te])
        if task == "regression":
            row = {"model": name, "mae": float(mean_absolute_error(y.iloc[te], pr)), "r2": float(r2_score(y.iloc[te], pr))}
            row["score"] = -row["mae"]
        else:
            row = {"model": name, "accuracy": float(accuracy_score(y.iloc[te], pr)), "macro_f1": float(f1_score(y.iloc[te], pr, average="macro"))}
            row["score"] = row["accuracy"]
        results.append(row)
        fitted[name] = pipe
    base = results[0]
    best = max(results[1:], key=lambda r: r["score"])
    if task == "regression":
        gain = 100.0 * (base["mae"] - best["mae"]) / base["mae"] if base["mae"] else 0.0
        useful = gain >= 5
        verdict = (f"{best['model']} is off by {best['mae']:,.2f} on average on unseen rows, {gain:.0f}% better than always guessing the average ({base['mae']:,.2f}). "
                   if useful else f"No model beat guessing the average by a meaningful margin (best gain {gain:.0f}%). The inputs don't explain '{target}' well, so don't rely on this. ")
    else:
        gain = 100.0 * (best["accuracy"] - base["accuracy"])
        useful = gain >= 5 and best["macro_f1"] > base["macro_f1"]
        verdict = (f"{best['model']} gets {best['accuracy']*100:.0f}% right on unseen rows, {gain:.0f} points better than always guessing the most common ({base['accuracy']*100:.0f}%). "
                   if useful else f"No model beat always guessing the most common class ({base['accuracy']*100:.0f}% right) by a meaningful margin. The inputs don't explain '{target}' well, so don't rely on this. ")
    if len(te) < 60:
        notes.append(f"Only {len(te)} test rows, so these numbers are rough.")
    best_pipe = fitted[best["model"]]
    imp = permutation_importance(best_pipe, X.iloc[te], y.iloc[te], n_repeats=5, random_state=42, n_jobs=1,
                                 scoring="neg_mean_absolute_error" if task == "regression" else "f1_macro")
    order = np.argsort(-imp.importances_mean)[:8]
    importance = [] if not useful else [{"input": cols[i], "importance": round(float(imp.importances_mean[i]), 4)} for i in order if imp.importances_mean[i] > 0]
    mid = f"{re.sub(r'[^a-z0-9]+', '-', source.lower()).strip('-')[:24]}-{re.sub(r'[^a-z0-9]+', '-', target.lower())[:16]}-{int(time.time()) % 10**7}"
    report = {"id": mid, "source": source, "label": label, "target": target, "task": task, "inputs": cols, "rows": int(len(df)), "train_rows": int(len(tr)),
              "test_rows": int(len(te)), "split": split, "results": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "score"} for r in results],
              "best": best["model"], "useful": bool(useful), "verdict": verdict.strip(), "importance": importance, "notes": notes,
              "created": time.strftime("%Y-%m-%d %H:%M"), "input_types": {c: ("number" if c in num else "text") for c in cols}}
    d = _dir()
    joblib.dump(best_pipe, d / f"{mid}.joblib")
    (d / f"{mid}.json").write_text(json.dumps(report))
    for old in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-MAX_MODELS]:
        old.unlink(missing_ok=True)
        old.with_suffix(".joblib").unlink(missing_ok=True)
    return report


def list_models() -> list[dict]:
    out = []
    for p in sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text())
            out.append({k: r[k] for k in ("id", "label", "target", "task", "best", "useful", "verdict", "created")})
        except (OSError, ValueError, KeyError):
            continue
    return out


def _paths(mid: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[a-z0-9-]{3,80}", mid or ""):
        raise ModelError("No such model.", 404)
    d = _dir()
    j, m = d / f"{mid}.json", d / f"{mid}.joblib"
    if not j.exists() or not m.exists():
        raise ModelError("No such model.", 404)
    return j, m


def get(mid: str) -> dict:
    return json.loads(_paths(mid)[0].read_text())


def delete(mid: str) -> dict:
    j, m = _paths(mid)
    j.unlink(missing_ok=True)
    m.unlink(missing_ok=True)
    return {"deleted": mid}


def predict(mid: str, rows: list[dict]) -> dict:
    import joblib
    j, m = _paths(mid)
    rep = json.loads(j.read_text())
    if not rows or len(rows) > MAX_PREDICT_ROWS:
        raise ModelError(f"Send between 1 and {MAX_PREDICT_ROWS} rows.")
    inputs = rep["inputs"]
    derived = {"day_of_week", "month"} & set(inputs)
    df = pd.DataFrame(rows)
    if derived and "record_date" in df.columns:
        d = pd.to_datetime(df["record_date"], errors="coerce")
        df["day_of_week"], df["month"] = d.dt.dayofweek, d.dt.month
    missing = [c for c in inputs if c not in df.columns]
    if missing:
        raise ModelError("Each row needs: " + ", ".join(inputs) + ". Missing: " + ", ".join(missing) + ".")
    for c, t in rep["input_types"].items():
        if t == "number":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    out = joblib.load(m).predict(df[inputs])
    return {"model": mid, "target": rep["target"], "predictions": [x.item() if hasattr(x, "item") else x for x in out]}
