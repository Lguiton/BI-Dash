"""Experiment tracker: the ML Lab's own, small version of what MLflow does.

Every training run is stored with its settings and metrics (see study.log_ml_run). Here you can star a run, write what you
learned, compare runs side by side, download them as CSV, or copy them into a local MLflow store if MLflow is installed.
The runs live in the app-state file, so they survive switching between Practice and Real.
"""
from __future__ import annotations

import csv
import io
import json

from app.services import state


class ExperimentError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def _shape(r: dict) -> dict:
    for k in ("features", "params", "metrics"):
        try:
            r[k] = json.loads(r[k]) if r.get(k) else ([] if k == "features" else {})
        except ValueError:
            r[k] = [] if k == "features" else {}
    r["starred"] = bool(r.get("starred"))
    return r


def list_runs(limit: int = 50, task: str | None = None, starred: bool = False) -> list[dict]:
    where, args = ["workspace = ?"], [_ws()]
    if task:
        where.append("task = ?"); args.append(task)
    if starred:
        where.append("starred = 1")
    rows = state.rows("SELECT id, created_at, task, model, features, metric, model_score, baseline_score, test_rows, note, starred, params, metrics, cv_mean, seconds, batch "
                      f"FROM ml_runs WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?", args + [max(1, min(limit, 200))])
    out = []
    for r in rows:
        r = _shape(r)
        b, s = r["baseline_score"], r["model_score"]
        r["lift"] = None if b is None or s is None else round(s - b, 4)
        out.append(r)
    return out


def _get(run_id: int) -> dict:
    r = state.one("SELECT id FROM ml_runs WHERE id = ? AND workspace = ?", (run_id, _ws()))
    if not r:
        raise ExperimentError(f"No run #{run_id} in this workspace.", 404)
    return r


def update(run_id: int, note: str | None = None, starred: bool | None = None) -> dict:
    _get(run_id)
    if note is not None:
        state.run("UPDATE ml_runs SET note = ? WHERE id = ?", (note.strip()[:1000] or None, run_id))
    if starred is not None:
        state.run("UPDATE ml_runs SET starred = ? WHERE id = ?", (1 if starred else 0, run_id))
    return next(r for r in list_runs(200) if r["id"] == run_id) if any(r["id"] == run_id for r in list_runs(200)) else {"id": run_id}


def delete(run_id: int) -> None:
    _get(run_id)
    state.run("DELETE FROM ml_runs WHERE id = ?", (run_id,))


def compare_runs(ids: list[int]) -> dict:
    """Side-by-side table of 2 to 6 runs: what differed (model, features, settings) and how the scores moved."""
    ids = list(dict.fromkeys(ids))
    if not 2 <= len(ids) <= 6:
        raise ExperimentError("Pick between 2 and 6 runs to compare.")
    runs = {r["id"]: r for r in list_runs(200)}
    missing = [i for i in ids if i not in runs]
    if missing:
        raise ExperimentError(f"Run(s) not found in this workspace: {', '.join('#' + str(i) for i in missing)}.", 404)
    sel = [runs[i] for i in ids]
    if len({r["task"] for r in sel}) > 1 or len({r["metric"] for r in sel}) > 1:
        raise ExperimentError("These runs predict different things, so their scores can't be compared. Pick runs for the same task.")
    feats = [set(r["features"]) for r in sel]
    common = set.intersection(*feats)
    diffs = []
    if len({r["model"] for r in sel}) > 1:
        diffs.append("model")
    if any(f != feats[0] for f in feats):
        diffs.append("features")
    for key in ("test_fraction", "balance_classes", "threshold"):
        if len({json.dumps(r["params"].get(key)) for r in sel}) > 1:
            diffs.append(key)
    best = max(sel, key=lambda r: r["model_score"] if r["model_score"] is not None else float("-inf"))
    rows = [{"id": r["id"], "created_at": r["created_at"], "model": r["model"], "metric": r["metric"], "score": r["model_score"],
             "baseline": r["baseline_score"], "lift": r["lift"], "cv_mean": r["cv_mean"], "seconds": r["seconds"],
             "extra_features": sorted(set(r["features"]) - common), "metrics": r["metrics"], "note": r["note"]} for r in sel]
    hint = ("Only one thing changed, so the score difference is attributable to it." if len(diffs) == 1 else
            "Several things changed at once, so you can't tell which one moved the score. Change one thing per run." if diffs else
            "The settings are identical, so any score gap comes from randomness in the model or the data.")
    return {"task": sel[0]["task"], "metric": sel[0]["metric"], "common_features": sorted(common), "changed": diffs,
            "best_id": best["id"], "runs": rows, "hint": hint}


def export_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "task", "model", "features", "metric", "score", "baseline", "cv_mean", "test_rows", "seconds", "starred", "note"])
    for r in reversed(list_runs(200)):
        w.writerow([r["id"], r["created_at"], r["task"], r["model"], "|".join(r["features"]), r["metric"], r["model_score"], r["baseline_score"],
                    r["cv_mean"], r["test_rows"], r["seconds"], int(r["starred"]), r["note"] or ""])
    return buf.getvalue()


def to_mlflow(tracking_dir: str, experiment: str = "bi-dashboard") -> dict:
    """Copy this workspace's runs into a local MLflow file store. MLflow is optional: it is not in requirements.txt."""
    try:
        import mlflow
    except ImportError as e:
        raise ExperimentError("MLflow isn't installed. Run: pip install mlflow   (it is optional, the built-in tracker works without it).", 501) from e
    runs = list_runs(200)
    if not runs:
        raise ExperimentError("There are no runs to copy yet. Train a model first.")
    import pathlib
    pathlib.Path(tracking_dir).mkdir(parents=True, exist_ok=True)
    uri = f"sqlite:///{pathlib.Path(tracking_dir, 'mlflow.db').as_posix()}"      # MLflow now prefers a database to its old file store
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment)
    for r in reversed(runs):
        with mlflow.start_run(run_name=f"{r['task']}-{r['model']}-#{r['id']}"):
            mlflow.log_params({"task": r["task"], "model": r["model"], "features": ",".join(r["features"]),
                               **{k: v for k, v in r["params"].items() if k != "split" and v is not None}})
            for k, v in (r["metrics"] or {}).items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))
            if r["cv_mean"] is not None:
                mlflow.log_metric("cv_mean", float(r["cv_mean"]))
            if r["note"]:
                mlflow.set_tag("note", r["note"])
    return {"copied": len(runs), "tracking_dir": tracking_dir, "experiment": experiment,
            "view_with": f"mlflow ui --backend-store-uri {uri}"}
