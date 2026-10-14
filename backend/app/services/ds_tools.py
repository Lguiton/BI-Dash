"""Data Science tools: forecast studio, model card, model drift check, customer segmentation.

Honest by design: every forecast is compared with the dumbest possible guess on a rolling backtest, ranges come from how wrong the method really was on past
data, and every result says when it should not be trusted. Nothing here is a promise about the future."""
from __future__ import annotations

import html
import json
import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from app.services import biz_models, workspaces
from app.services.db import get_cursor

FREQ = {"day": 7, "week": 4, "month": 12}
AGG = {"sum": "SUM({c})", "avg": "AVG({c})", "count": "COUNT(*)"}
STEP = {"day": timedelta(days=1), "week": timedelta(days=7)}


class DsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _cols(t: str) -> dict[str, str]:
    with get_cursor() as cur:
        rows = cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ? AND table_schema = 'main'", [t]).fetchall()
    return {r[0]: r[1].upper() for r in rows}


def _table(source: str) -> str:
    try:
        return biz_models._table_for(source)[0]
    except biz_models.ModelError as e:
        raise DsError(str(e), getattr(e, "status", 400)) from None


def _nextdate(d: date, freq: str) -> date:
    if freq == "month":
        return date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return d + STEP[freq]


# ------------------------------------------------------------------ 1. forecast studio

def series(source: str, date_col: str, value_col: str | None, agg: str, freq: str) -> list[tuple[date, float]]:
    if freq not in FREQ:
        raise DsError("freq must be day, week or month.")
    if agg not in AGG:
        raise DsError("agg must be sum, avg or count.")
    t = _table(source)
    cs = _cols(t)
    if date_col not in cs or not any(k in cs[date_col] for k in ("DATE", "TIMESTAMP")):
        raise DsError(f"'{date_col}' is not a date column. Date columns here: " + (", ".join(c for c, ty in cs.items() if "DATE" in ty or "TIMESTAMP" in ty) or "none") + ".")
    if agg != "count":
        if value_col not in cs or not any(k in cs[value_col] for k in ("DOUBLE", "INT", "DECIMAL", "FLOAT", "HUGEINT")):
            raise DsError("Choose a number column to add up or average.")
        expr = AGG[agg].format(c='"' + value_col + '"')
    else:
        expr = AGG["count"]
    with get_cursor() as cur:
        rows = cur.execute(f'SELECT date_trunc(\'{freq}\', "{date_col}")::DATE d, {expr} v FROM {t} WHERE "{date_col}" IS NOT NULL GROUP BY 1 ORDER BY 1').fetchall()
    out = [(r[0], float(r[1] or 0)) for r in rows]
    # fill gaps with zero for sum/count so a quiet week is not skipped; averages stay missing and are carried forward
    if not out:
        return out
    full, cur_d, m = [], out[0][0], dict(out)
    last = None
    while cur_d <= out[-1][0]:
        v = m.get(cur_d)
        if v is None:
            v = 0.0 if agg != "avg" else (last if last is not None else 0.0)
        full.append((cur_d, v))
        last = v
        cur_d = _nextdate(cur_d, freq)
    return full


def _naive(y: list[float], h: int, s: int) -> list[float]:
    return [y[-1]] * h


def _snaive(y: list[float], h: int, s: int) -> list[float]:
    if len(y) < s:
        return _naive(y, h, s)
    return [y[-s + (i % s)] for i in range(h)]


def _ma(y: list[float], h: int, s: int) -> list[float]:
    w = max(2, min(s, len(y)))
    buf = list(y)
    out = []
    for _ in range(h):
        v = float(np.mean(buf[-w:]))
        out.append(v)
        buf.append(v)
    return out


def _boost(y: list[float], h: int, s: int) -> list[float]:
    from sklearn.ensemble import GradientBoostingRegressor
    L = max(3, min(s, 12))
    if len(y) < L + 8:
        return _ma(y, h, s)
    X = np.array([y[i - L:i] for i in range(L, len(y))])
    t = np.array(y[L:])
    m = GradientBoostingRegressor(n_estimators=80, max_depth=2, learning_rate=0.1, random_state=0).fit(X, t)
    buf = list(y)
    out = []
    for _ in range(h):
        v = float(m.predict(np.array([buf[-L:]]))[0])
        out.append(v)
        buf.append(v)
    return out


METHODS = {"naive": ("Repeat the last value", _naive), "seasonal_naive": ("Repeat the same period last cycle", _snaive),
           "moving_average": ("Moving average", _ma), "boosting": ("Boosting on recent values", _boost)}


def forecast(source: str, date_col: str, value_col: str | None = None, agg: str = "sum", freq: str = "day", horizon: int = 14, folds: int = 3) -> dict:
    horizon = int(horizon)
    if not 1 <= horizon <= 90:
        raise DsError("horizon must be between 1 and 90 periods.")
    folds = max(1, min(int(folds), 6))
    sr = series(source, date_col, value_col, agg, freq)
    y = [v for _, v in sr]
    s = FREQ[freq]
    need = max(2 * s, 14) + horizon
    if len(y) < need:
        raise DsError(f"Need at least {need} {freq}s of history to forecast {horizon} ahead and test it honestly; there are {len(y)}.")
    # rolling-origin backtest: forecast `horizon` ahead from several earlier cut points and score against what really happened
    board = {k: {"label": v[0], "errors": [], "by_step": [[] for _ in range(horizon)]} for k, v in METHODS.items()}
    used = 0
    for k in range(folds):
        cut = len(y) - horizon * (folds - k)
        if cut < max(2 * s, 14):
            continue
        used += 1
        act = y[cut:cut + horizon]
        for key, (_, fn) in METHODS.items():
            fc = fn(y[:cut], horizon, s)
            for i, (a, f) in enumerate(zip(act, fc)):
                board[key]["errors"].append(abs(a - f))
                board[key]["by_step"][i].append(abs(a - f))
    if not used:
        raise DsError("Not enough history for a backtest.")
    rows = []
    for key, b in board.items():
        mae = float(np.mean(b["errors"]))
        rows.append({"method": key, "label": b["label"], "mae": round(mae, 3)})
    base = next(r for r in rows if r["method"] == "naive")["mae"]
    for r in rows:
        r["better_than_naive_pct"] = round(100.0 * (base - r["mae"]) / base, 1) if base else 0.0
    best = min(rows, key=lambda r: r["mae"])
    useful = best["method"] != "naive" and best["better_than_naive_pct"] >= 5
    chosen = best["method"] if useful else "naive"
    fc = METHODS[chosen][1](y, horizon, s)
    errs = board[chosen]["errors"]
    q = float(np.quantile(errs, 0.8)) if errs else 0.0
    d, pts = sr[-1][0], []
    for i, f in enumerate(fc):
        d = _nextdate(d, freq)
        step_err = board[chosen]["by_step"][i]
        w = float(np.quantile(step_err, 0.8)) if len(step_err) >= 3 else q
        w = max(w, q * 0.5)
        lo = f - w
        if agg != "avg" and min(y) >= 0:
            lo = max(0.0, lo)
        pts.append({"date": d.isoformat(), "forecast": round(f, 2), "low": round(lo, 2), "high": round(f + w, 2)})
    verdict = (f"{best['label']} was {best['better_than_naive_pct']:.0f}% closer than just repeating the last value across {used} past test windows, so it was used."
               if useful else "No method beat just repeating the last value by a meaningful margin on past data, so that is what is shown. Treat this as a level, not a prediction of change.")
    return {"source": source, "freq": freq, "agg": agg, "horizon": horizon, "history": [{"date": a.isoformat(), "value": round(b, 2)} for a, b in sr[-120:]], "history_periods": len(y),
            "backtest": sorted(rows, key=lambda r: r["mae"]), "windows_tested": used, "method_used": chosen, "forecast": pts, "verdict": verdict,
            "range_note": "The range is the size of error this method really made on past test windows (80% of misses were smaller). Real misses can be bigger, especially after a change in the business.",
            "caution": "A forecast assumes the recent past keeps going. Holidays, price changes, new customers or a broken data feed will not be seen coming." + (" Counts or sums of zero were filled in for quiet periods." if agg != "avg" else "")}


# ------------------------------------------------------------------ 2. model card

def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _sample() -> bool:
    return workspaces.active() == "practice"


def model_card(mid: str, owner: str = "", purpose: str = "") -> str:
    try:
        rep = biz_models.get(mid)
    except (FileNotFoundError, KeyError):
        raise DsError("No saved model with that id.", 404) from None
    except Exception as e:
        raise DsError("No saved model with that id.", 404) from e
    lb = rep.get("leaderboard") or []
    task = rep.get("task")
    head = "<th>Model</th>" + ("<th>Typical miss</th><th>R²</th>" if task == "regression" else "<th>Right</th><th>Macro F1</th>")
    rows = ""
    for r in lb:
        t = r.get("test") or r
        if task == "regression":
            rows += f"<tr><td>{_e(r.get('model'))}</td><td>{_e(t.get('mae'))}</td><td>{_e(t.get('r2'))}</td></tr>"
        else:
            acc = t.get("accuracy")
            rows += f"<tr><td>{_e(r.get('model'))}</td><td>{_e(round(acc * 100) if isinstance(acc, (int, float)) else acc)}%</td><td>{_e(t.get('macro_f1'))}</td></tr>"
    imp = "".join(f"<li>{_e(i.get('input'))}</li>" for i in (rep.get("importance") or [])[:8]) or "<li>No input stood out.</li>"
    inputs = "".join(f"<li>{_e(c)} <span class='m'>({_e((rep.get('input_types') or {}).get(c, ''))})</span></li>" for c in rep.get("inputs", []))
    useful = rep.get("useful")
    use = ("Use it to rank or flag things for a human to look at." if useful else "Do not use it to decide anything: it did not beat the simple guess.")
    banner = "<div style='background:#fef3c7;border:1px solid #f59e0b;padding:6px 10px;border-radius:6px;margin-bottom:10px'><b>SAMPLE DATA</b>: this card describes a model built on practice data.</div>" if _sample() else ""
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Model card: {_e(rep.get('label') or mid)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#111}}h1{{font-size:22px}}h2{{font-size:15px;margin-top:20px;border-bottom:1px solid #ddd;padding-bottom:3px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #ddd;padding:4px 8px;text-align:left}}.m{{color:#666}}.v{{padding:8px 10px;border-radius:6px;background:{'#ecfdf5' if useful else '#fef2f2'}}}</style></head><body>
{banner}<h1>Model card: {_e(rep.get('label') or mid)}</h1>
<p class='m'>Built {_e(rep.get('created'))} &middot; id {_e(mid)}{(' &middot; owner ' + _e(owner)) if owner else ''}</p>
<h2>What it does</h2><p>{_e(purpose) or ('Predicts <b>' + _e(rep.get('target')) + '</b> (' + _e('a number' if task == 'regression' else 'a category') + ') from the columns below.')}</p>
<h2>Data it learned from</h2><p>{_e(rep.get('rows'))} rows from {_e(rep.get('label') or rep.get('source'))}. Train {_e(rep.get('train_rows'))}, test {_e(rep.get('test_rows'))} (rows the model never saw).</p>
<h2>Inputs</h2><ul>{inputs}</ul>
<h2>How well it works</h2><div class='v'>{_e(rep.get('verdict'))}</div>
<table><tr>{head}</tr>{rows}</table>
<h2>What mattered most</h2><ul>{imp}</ul>
<h2>How to use it</h2><p>{_e(use)}</p>
<h2>Limits and care</h2><ul><li>It only knows the patterns in the rows above. A new kind of customer, product or season can break it.</li>
<li>It finds patterns, not causes. Do not use it to claim why something happens.</li><li>Check it again on new data (Model drift check) every few months, and retrain if it gets worse.</li>
<li>Do not use it for decisions about people (credit, hiring, health) without a human review and a legal check.</li></ul>
</body></html>"""


# ------------------------------------------------------------------ 3. model drift

def _psi_like(ref: pd.Series, new: pd.Series) -> float:
    """Shift of the mean in units of the reference spread."""
    sd = float(ref.std() or 0)
    if sd == 0 or ref.dropna().empty or new.dropna().empty:
        return 0.0
    return round(float((new.mean() - ref.mean()) / sd), 2)


def drift(mid: str, recent_days: int = 30, new_source: str | None = None) -> dict:
    from app.services import ml_studio
    try:
        rep = biz_models.get(mid)
        import joblib
        pipe = joblib.load(biz_models._paths(mid)[1])
    except Exception as e:
        raise DsError("No saved model with that id.", 404) from e
    src = new_source or rep["source"]
    try:
        df, _ = biz_models.load(src)
    except biz_models.ModelError as e:
        raise DsError(str(e), getattr(e, "status", 400)) from None
    target, inputs, task = rep["target"], rep["inputs"], rep["task"]
    if target not in df.columns:
        raise DsError(f"The data has no '{target}' column, so the model can't be scored.")
    if new_source:
        ref = df.iloc[: max(1, len(df) // 2)]
        new = df.iloc[len(df) // 2:]
        note = "No dates were used: the first half of the data is compared with the second half."
        if len(df) < 40:
            raise DsError("Need at least 40 rows to compare.")
    else:
        if "record_date" not in df.columns:
            raise DsError("This data has no record_date, so pick a second table to compare with (new data).")
        d = pd.to_datetime(df["record_date"], errors="coerce")
        cut = d.max() - pd.Timedelta(days=int(recent_days))
        new, ref = df[d > cut], df[d <= cut]
        note = f"Rows from the last {int(recent_days)} days are compared with everything before."
    if len(new) < 20 or len(ref) < 20:
        raise DsError(f"Need at least 20 rows on each side; got {len(ref)} older and {len(new)} newer.")

    def score(part: pd.DataFrame) -> dict:
        part = part.dropna(subset=[target])
        X = ml_studio._frame(rep, part.to_dict("records"))[inputs]
        pr = pipe.predict(X)
        if task == "regression":
            yt = pd.to_numeric(part[target], errors="coerce").to_numpy(dtype=float)
            ok = ~np.isnan(yt)
            return {"rows": int(ok.sum()), "error": float(np.mean(np.abs(yt[ok] - pr[ok]))), "guess": float(np.mean(np.abs(yt[ok] - np.nanmean(yt[ok]))))}
        yt = part[target].astype(str).to_numpy()
        pr = np.asarray(pr).astype(str)
        mode = pd.Series(yt).mode().iloc[0]
        return {"rows": int(len(yt)), "error": float(np.mean(yt != pr)), "guess": float(np.mean(yt != mode))}

    a, b = score(ref), score(new)
    unit = "typical miss" if task == "regression" else "share wrong"
    worse = (b["error"] - a["error"]) / a["error"] * 100 if a["error"] else 0.0
    beats = b["error"] < b["guess"]
    shifts = []
    for c in inputs:
        if c not in new.columns and c in ("day_of_week", "month"):
            continue
        if c not in new.columns:
            continue
        if (rep.get("input_types") or {}).get(c) == "number":
            sh = _psi_like(pd.to_numeric(ref[c], errors="coerce"), pd.to_numeric(new[c], errors="coerce"))
            shifts.append({"input": c, "kind": "number", "shift": sh, "flag": abs(sh) >= 0.5, "says": f"average moved {sh:+.1f} spreads"})
        else:
            unseen = sorted(set(new[c].dropna().astype(str)) - set(ref[c].dropna().astype(str)))
            vc_r, vc_n = ref[c].astype(str).value_counts(normalize=True), new[c].astype(str).value_counts(normalize=True)
            tv = round(float(0.5 * sum(abs(vc_n.get(k, 0) - vc_r.get(k, 0)) for k in set(vc_r.index) | set(vc_n.index))), 2)
            shifts.append({"input": c, "kind": "text", "shift": tv, "flag": bool(unseen) or tv >= 0.2, "says": ("new values: " + ", ".join(unseen[:4]) + ". " if unseen else "") + f"mix changed by {tv * 100:.0f}%"})
    if not beats:
        status, say = "retrain", "On the recent rows the model is no better than the simple guess. Retrain it before relying on it."
    elif worse >= 25:
        status, say = "retrain", f"The model is {worse:.0f}% worse on recent rows than before. Retrain on newer data."
    elif worse >= 10 or any(s["flag"] for s in shifts):
        status, say = "watch", "Some drift is showing. It still works, but check again soon and look at the flagged inputs."
    else:
        status, say = "ok", "No meaningful drift: the model is holding up on recent rows."
    return {"model": mid, "status": status, "says": say, "unit": unit, "older": {k: round(v, 3) if isinstance(v, float) else v for k, v in a.items()},
            "recent": {k: round(v, 3) if isinstance(v, float) else v for k, v in b.items()}, "change_pct": round(worse, 1), "beats_guess_now": bool(beats), "inputs": shifts, "how": note,
            "caution": "This checks the model on rows that already have a known answer. If the answers arrive late, drift can only be seen late."}


# ------------------------------------------------------------------ 4. segmentation

def segments(source: str, features: list[str], k: int | None = None, max_rows: int = 20000) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler
    if not 2 <= len(features or []) <= 8:
        raise DsError("Choose between 2 and 8 number columns.")
    df, _ = biz_models.load(source)
    miss = [f for f in features if f not in df.columns]
    if miss:
        raise DsError("Not in the data: " + ", ".join(miss) + ".")
    X = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 30:
        raise DsError(f"Need at least 30 complete rows; only {len(X)} have every chosen column filled with a number.")
    if len(X) > max_rows:
        X = X.sample(max_rows, random_state=0)
    Z = StandardScaler().fit_transform(X)
    best = None
    cands = [int(k)] if k else range(2, min(6, len(X) // 10) + 1)
    for kk in cands:
        if not 2 <= kk <= 8:
            raise DsError("k must be between 2 and 8.")
        km = KMeans(n_clusters=kk, n_init=10, random_state=0).fit(Z)
        sil = float(silhouette_score(Z, km.labels_, sample_size=min(3000, len(Z)), random_state=0))
        if best is None or sil > best[0]:
            best = (sil, kk, km)
    sil, kk, km = best
    overall, sd = X.mean(), X.std().replace(0, 1)
    out = []
    for c in range(kk):
        part = X[km.labels_ == c]
        prof = []
        for f in features:
            z = float((part[f].mean() - overall[f]) / sd[f])
            prof.append({"column": f, "average": round(float(part[f].mean()), 2), "overall": round(float(overall[f]), 2), "z": round(z, 2), "level": "high" if z >= 0.5 else "low" if z <= -0.5 else "typical"})
        hi = [p for p in sorted(prof, key=lambda p: -p["z"]) if p["level"] == "high"][:2]
        lo = [p for p in sorted(prof, key=lambda p: p["z"]) if p["level"] == "low"][:2]
        name = ", ".join([f"high {p['column']}" for p in hi] + [f"low {p['column']}" for p in lo]) or "close to average on everything"
        out.append({"segment": c + 1, "name": name[0].upper() + name[1:], "rows": int(len(part)), "share_pct": round(100 * len(part) / len(X), 1), "profile": prof})
    out.sort(key=lambda s: -s["rows"])
    for i, s in enumerate(out):
        s["segment"] = i + 1
    strength = "clear" if sil >= 0.5 else "fair" if sil >= 0.25 else "weak"
    return {"source": source, "features": features, "k": kk, "rows_used": int(len(X)), "silhouette": round(sil, 2), "separation": strength, "segments": out,
            "caution": ("The groups overlap a lot, so treat the names as rough hints, not real customer types. " if strength == "weak" else "") +
            "Segments are a way to describe your data, not facts about people. A different k or different columns gives different groups. Check each one against what you know before acting."}
