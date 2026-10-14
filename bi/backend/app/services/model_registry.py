"""Model registry, serving and drift check: the production side of the ML Lab (our own small take on MLflow's registry + a serving API).

* register: train a model with the ML Lab's settings and store it as name vX, with its metrics and a profile of the training data
* stages: none -> staging -> production (only one version per name is in production; promoting one archives the old one)
* predict: score new rows with a registered version (the production one by default)
* drift: compare the data the model was trained on with the most recent data, feature by feature (PSI)

Honest limits: models are saved with joblib in a local folder, so only load a models folder you made yourself. Predictions are only as
good as the test-set score says, on data that looks like the training data. The drift check says "the inputs changed", not "the model is wrong".
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from app.config import models_dir
from app.services import ml_lab, state, workspaces

STAGES = ("none", "staging", "production", "archived")
MAX_VERSIONS = 20
MAX_PREDICT_ROWS = 200
PSI_BINS = 10


class ModelError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")[:40]
    if not s:
        raise ModelError("Give the model a name (letters and numbers).")
    return s


def _shape(r: dict, full: bool = False) -> dict:
    out = {"id": r["id"], "name": r["name"], "version": r["version"], "stage": r["stage"], "task": r["task"], "kind": r["kind"], "model": r["model"],
           "features": json.loads(r["features"]), "metrics": json.loads(r["metrics"]), "baseline": json.loads(r["baseline"]),
           "params": json.loads(r["params"]), "note": r["note"], "created_at": r["created_at"]}
    if full:
        out["train_stats"] = json.loads(r["train_stats"])
    return out


COLS = "id, name, version, stage, task, kind, model, features, params, metrics, baseline, train_stats, note, created_at, file"


def list_models() -> list[dict]:
    rows = state.rows(f"SELECT {COLS} FROM models WHERE workspace = ? ORDER BY name, version DESC", (_ws(),))
    return [_shape(r) for r in rows]


def _get(name: str, version: int | None = None, stage: str | None = None) -> dict:
    name = slug(name)
    if version is not None:
        r = state.one(f"SELECT {COLS} FROM models WHERE workspace = ? AND name = ? AND version = ?", (_ws(), name, version))
    elif stage:
        r = state.one(f"SELECT {COLS} FROM models WHERE workspace = ? AND name = ? AND stage = ? ORDER BY version DESC", (_ws(), name, stage))
    else:
        r = (state.one(f"SELECT {COLS} FROM models WHERE workspace = ? AND name = ? AND stage = 'production'", (_ws(), name))
             or state.one(f"SELECT {COLS} FROM models WHERE workspace = ? AND name = ? AND stage <> 'archived' ORDER BY version DESC", (_ws(), name)))
    if not r:
        raise ModelError(f"No model '{name}'" + (f" version {version}" if version else "") + " in this workspace.", 404)
    return r


# ---------------------------------------------------------------- training profile (used by the drift check)
def _profile(df, feature_ids: list[str]) -> dict:
    import numpy as np
    prof = {}
    for f in feature_ids:
        col = df[f]
        if ml_lab.FEATURES[f].kind == "num":
            vals = col.dropna().to_numpy(dtype=float)
            if len(vals) == 0:
                prof[f] = {"kind": "num", "edges": [], "share": []}
                continue
            edges = sorted(set(float(x) for x in np.quantile(vals, np.linspace(0, 1, PSI_BINS + 1)[1:-1])))
            idx = np.searchsorted(edges, vals, side="right")
            share = [float((idx == i).mean()) for i in range(len(edges) + 1)]
            prof[f] = {"kind": "num", "edges": edges, "share": share, "min": float(vals.min()), "max": float(vals.max()), "mean": float(vals.mean())}
        else:
            vc = col.astype(str).value_counts(normalize=True)
            top = vc.head(15)
            prof[f] = {"kind": "cat", "share": {str(k): float(v) for k, v in top.items()}, "other": float(max(0.0, 1 - top.sum()))}
    return prof


def _psi(expected: list[float], actual: list[float]) -> float:
    eps = 1e-4
    return float(sum((max(a, eps) - max(e, eps)) * math.log(max(a, eps) / max(e, eps)) for e, a in zip(expected, actual)))


def _level(psi: float) -> str:
    return "stable" if psi < 0.1 else ("some drift" if psi < 0.25 else "significant drift")


# ---------------------------------------------------------------- register, stages, delete
def register(name: str, task: str, model: str, features: list[str], test_fraction: float = 0.2, balance_classes: bool = False,
             threshold: float = 0.5, note: str = "") -> dict:
    import joblib
    name = slug(name)
    try:
        res = ml_lab.train(task, model, features, test_fraction, balance_classes, threshold, light=True, keep_model=True)
    except ml_lab.MlError as e:
        raise ModelError(str(e)) from e
    pipe, train_df = res.pop("_pipe"), res.pop("_train_df")
    have = state.rows("SELECT version FROM models WHERE workspace = ? AND name = ?", (_ws(), name))
    if len(have) >= MAX_VERSIONS:
        raise ModelError(f"'{name}' already has {MAX_VERSIONS} versions. Delete old ones first.")
    ver = max([r["version"] for r in have], default=0) + 1
    if have:
        prev = _get(name)
        if prev["task"] != task:
            raise ModelError(f"'{name}' predicts '{prev['task']}'. A new version must predict the same thing; pick a new name for a new task.")
    d = models_dir() / _ws() / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"v{ver}.joblib"
    joblib.dump(pipe, f)
    params = {"test_fraction": test_fraction, "balance_classes": balance_classes, "threshold": threshold, "split": res["split"]}
    state.run("INSERT INTO models (workspace, name, version, stage, task, kind, model, features, params, metrics, baseline, train_stats, note, created_at, file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (_ws(), name, ver, "none", task, res["kind"], model, json.dumps(features), json.dumps(params), json.dumps(res["metrics"]), json.dumps(res["baseline"]),
               json.dumps(_profile(train_df, features)), note.strip()[:300], state.now(), str(f)))
    state.audit("model_register", f"{name} v{ver} ({model}, {task})")
    return card(name, ver)


def set_stage(name: str, version: int, stage: str) -> dict:
    if stage not in STAGES:
        raise ModelError(f"Stage must be one of: {', '.join(STAGES)}.")
    r = _get(name, version)
    if stage == "production":
        state.run("UPDATE models SET stage = 'archived' WHERE workspace = ? AND name = ? AND stage = 'production' AND version <> ?", (_ws(), r["name"], version))
    state.run("UPDATE models SET stage = ? WHERE id = ?", (stage, r["id"]))
    state.audit("model_stage", f"{r['name']} v{version} -> {stage}")
    return card(r["name"], version)


def delete(name: str, version: int) -> None:
    r = _get(name, version)
    if r["stage"] == "production":
        raise ModelError("This version is in production. Move another version to production (or archive this one) before deleting it.", 409)
    try:
        Path(r["file"]).unlink(missing_ok=True)
    except OSError:
        pass
    state.run("DELETE FROM models WHERE id = ?", (r["id"],))
    state.audit("model_delete", f"{r['name']} v{version}")


def card(name: str, version: int | None = None) -> dict:
    """What a model is, what it needs as input, how good it was, and what it can't tell you."""
    r = _get(name, version)
    out = _shape(r, full=True)
    inputs = []
    for f in out["features"]:
        st = out["train_stats"].get(f, {})
        spec = ml_lab.FEATURES[f]
        item = {"feature": f, "label": spec.label, "kind": spec.kind, "note": spec.note}
        if spec.kind == "num":
            item["seen_range"] = [st.get("min"), st.get("max")]
        else:
            item["common_values"] = list(st.get("share", {}))[:10]
        inputs.append(item)
    pm = "r2" if out["kind"] == "regression" else "f1"
    out["inputs"] = inputs
    out["primary"] = {"name": pm, "model": out["metrics"].get(pm), "baseline": out["baseline"].get(pm)}
    out["caveats"] = [
        f"Scored on the most recent {int(out['params']['test_fraction'] * 100)}% of days it never saw; the score may not hold on different data.",
        "Inputs far outside the ranges it saw in training (see 'seen range') give unreliable predictions.",
        "A prediction is an estimate, not a promise. Check the drift view before trusting an old model.",
    ]
    if out["primary"]["model"] is not None and out["primary"]["baseline"] is not None and out["primary"]["model"] <= out["primary"]["baseline"] + 0.01:
        out["caveats"].insert(0, "This model barely beats the naive baseline. Don't put it in production.")
    return out


# ---------------------------------------------------------------- predict
def predict(name: str, rows: list[dict], version: int | None = None) -> dict:
    import joblib
    import pandas as pd
    if not isinstance(rows, list) or not rows:
        raise ModelError("Send at least one row.")
    if len(rows) > MAX_PREDICT_ROWS:
        raise ModelError(f"Send at most {MAX_PREDICT_ROWS} rows at a time.")
    r = _get(name, version)
    c = card(r["name"], r["version"])
    feats = c["features"]
    clean, warnings = [], []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ModelError(f"Row {i} must be an object with the model's inputs.")
        extra = set(row) - set(feats)
        if extra:
            raise ModelError(f"Row {i}: unknown input(s) {', '.join(sorted(extra))}. This model uses: {', '.join(feats)}.")
        item = {}
        for inp in c["inputs"]:
            f = inp["feature"]
            if f not in row or row[f] in (None, ""):
                raise ModelError(f"Row {i}: '{f}' is missing.")
            if inp["kind"] == "num":
                try:
                    v = float(row[f])
                except (TypeError, ValueError):
                    raise ModelError(f"Row {i}: '{f}' must be a number.") from None
                if v != v or abs(v) == float("inf"):
                    raise ModelError(f"Row {i}: '{f}' must be a finite number.")
                lo, hi = inp["seen_range"]
                if lo is not None and not lo <= v <= hi:
                    warnings.append(f"Row {i}: {f}={v:g} is outside the training range ({lo:g} to {hi:g}), so treat this prediction with caution.")
                item[f] = v
            else:
                v = str(row[f])
                if inp["common_values"] and v not in inp["common_values"]:
                    warnings.append(f"Row {i}: {f}='{v}' wasn't among the common values seen in training.")
                item[f] = v
        clean.append(item)
    try:
        pipe = joblib.load(r["file"])
    except Exception as e:  # noqa: BLE001
        raise ModelError(f"The saved model file couldn't be loaded ({type(e).__name__}). Register it again.", 500) from e
    df = pd.DataFrame(clean, columns=feats)
    if r["kind"] == "classification":
        thr = json.loads(r["params"]).get("threshold") or 0.5
        proba = pipe.predict_proba(df)[:, 1]
        preds = [{"prediction": int(p >= thr), "probability": round(float(p), 4), "label": "problem" if p >= thr else "fine"} for p in proba]
    else:
        preds = [{"prediction": round(float(p), 2)} for p in pipe.predict(df)]
    return {"name": r["name"], "version": r["version"], "stage": r["stage"], "task": r["task"], "predictions": preds, "warnings": warnings[:20]}


# ---------------------------------------------------------------- drift
def _log_drift(r: dict, overall: str, worst: dict, n: int, feats: list[dict]) -> None:
    """Keep every drift reading so the registry can chart it over time (inputs only, like the check itself)."""
    try:
        state.run("INSERT INTO drift_history (workspace, at, model, version, overall, worst_feature, worst_psi, recent_rows, detail) VALUES (?,?,?,?,?,?,?,?,?)",
                  (workspaces.active(), state.now(), r["name"], r["version"], overall, worst["label"], worst["psi"], n,
                   json.dumps({f["label"]: f["psi"] for f in feats})))
        state.run("DELETE FROM drift_history WHERE id NOT IN (SELECT id FROM drift_history ORDER BY id DESC LIMIT 2000)")
    except Exception:  # noqa: BLE001  history is a convenience; it must never break the check
        pass


def drift_history(name: str, version: int | None = None, limit: int = 60) -> list[dict]:
    r = _get(name, version)
    rows = state.rows("SELECT at, overall, worst_feature, worst_psi, recent_rows, detail FROM drift_history WHERE workspace = ? AND model = ? AND version = ? ORDER BY id DESC LIMIT ?",
                      (workspaces.active(), r["name"], r["version"], max(1, min(int(limit), 500))))
    for x in rows:
        x["detail"] = json.loads(x["detail"] or "{}")
    return list(reversed(rows))


def drift(name: str, version: int | None = None, recent_days: int = 14) -> dict:
    import numpy as np
    r = _get(name, version)
    feats = json.loads(r["features"])
    prof = json.loads(r["train_stats"])
    try:
        df = ml_lab._load(r["task"], feats)
    except Exception as e:  # noqa: BLE001
        raise ModelError(f"Couldn't read the current data: {e}") from e
    if df.empty:
        raise ModelError("There is no data to compare against.")
    dates = df["record_date"].drop_duplicates().tolist()
    cut = dates[-min(max(1, recent_days), len(dates))]
    recent = df[df["record_date"] >= cut]
    if len(recent) < 30:
        raise ModelError(f"Only {len(recent)} recent rows. Need at least 30 for a drift check; load more recent data or use more days.")
    out = []
    for f in feats:
        p = prof[f]
        col = recent[f]
        if p["kind"] == "num":
            vals = col.dropna().to_numpy(dtype=float)
            idx = np.searchsorted(p["edges"], vals, side="right")
            actual = [float((idx == i).mean()) for i in range(len(p["edges"]) + 1)] if len(vals) else p["share"]
            score = _psi(p["share"], actual)
            out.append({"feature": f, "label": ml_lab.FEATURES[f].label, "psi": round(score, 4), "level": _level(score),
                        "train_mean": round(p.get("mean", 0), 3), "recent_mean": round(float(vals.mean()), 3) if len(vals) else None})
        else:
            keys = list(p["share"])
            cur = col.astype(str).value_counts(normalize=True)
            exp = [p["share"][k] for k in keys] + [p["other"]]
            act = [float(cur.get(k, 0.0)) for k in keys] + [float(max(0.0, 1 - sum(cur.get(k, 0.0) for k in keys)))]
            score = _psi(exp, act)
            out.append({"feature": f, "label": ml_lab.FEATURES[f].label, "psi": round(score, 4), "level": _level(score)})
    worst = max(out, key=lambda x: x["psi"])
    overall = _level(worst["psi"])
    _log_drift(r, overall, worst, len(recent), out)
    return {"name": r["name"], "version": r["version"], "recent_rows": len(recent), "recent_from": str(cut)[:10], "features": out, "overall": overall,
            "advice": {"stable": "The recent inputs look like the training data. The model's inputs haven't shifted.",
                       "some drift": f"'{worst['label']}' has shifted a little. Keep an eye on it and re-check the model's error on recent outcomes.",
                       "significant drift": f"'{worst['label']}' has changed a lot since training. Retrain on recent data and compare before trusting this version."}[overall],
            "note": "PSI (population stability index): under 0.1 stable, 0.1 to 0.25 some drift, over 0.25 significant. It compares input data only; it can't see whether predictions are still right."}
