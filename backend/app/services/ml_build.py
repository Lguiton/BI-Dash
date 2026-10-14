"""More ML learning tools: input and label drift, performance drift, a small automatic feature and model search,
a numpy neural network with backpropagation, an attention demo, a BPE tokenizer trainer and a semantic (LSA) search.
Seeds are fixed so results repeat. These teach mechanics; they do not replace scikit-learn, PyTorch or a real review."""
from __future__ import annotations

import io
import math
import re
import warnings
import zlib
from collections import Counter

import numpy as np
import pandas as pd

from app.services.ml_tools import MlToolError


def _nums(text: str, name: str, lo: int = 5, hi: int = 20000) -> np.ndarray:
    try:
        v = np.array([float(x) for x in re.split(r"[\s,;]+", (text or "").strip()) if x != ""])
    except ValueError:
        raise MlToolError(f"{name}: use numbers separated by spaces, commas or new lines.") from None
    if not np.all(np.isfinite(v)) or len(v) < lo or len(v) > hi:
        raise MlToolError(f"{name}: give {lo} to {hi:,} numbers.")
    return v


def _psi(p: np.ndarray, q: np.ndarray) -> float:
    p, q = np.clip(p, 1e-4, None), np.clip(q, 1e-4, None)
    p, q = p / p.sum(), q / q.sum()
    return float(np.sum((q - p) * np.log(q / p)))


def _band(psi: float) -> str:
    return "small (under 0.1)" if psi < 0.1 else "moderate (0.1 to 0.25)" if psi < 0.25 else "large (over 0.25)"


# ---------------------------------------------------------------- drift
def drift(reference: str, current: str, kind: str = "numeric") -> dict:
    if kind == "numeric":
        a, b = _nums(reference, "Reference"), _nums(current, "Current")
        from scipy import stats
        edges = np.unique(np.quantile(a, np.linspace(0, 1, 11)))
        if len(edges) < 3:
            raise MlToolError("The reference values barely vary, so bins cannot be built.")
        edges[0], edges[-1] = -np.inf, np.inf
        pa, pb = np.histogram(a, edges)[0] / len(a), np.histogram(b, edges)[0] / len(b)
        psi = _psi(pa, pb)
        ks = stats.ks_2samp(a, b)
        sd = a.std() or 1.0
        shift = (b.mean() - a.mean()) / sd
        verdict = "investigate" if psi >= 0.25 or ks.pvalue < 0.001 else "watch" if psi >= 0.1 or ks.pvalue < 0.05 else "no clear drift"
        return {"kind": "numeric", "n_reference": len(a), "n_current": len(b), "psi": round(psi, 4), "psi_band": _band(psi), "ks_statistic": round(float(ks.statistic), 4), "ks_p_value": float(f"{ks.pvalue:.4g}"),
                "mean_reference": round(float(a.mean()), 4), "mean_current": round(float(b.mean()), 4), "mean_shift_in_sd": round(float(shift), 3), "bins": [{"bin": i + 1, "reference_pct": round(float(x) * 100, 1), "current_pct": round(float(y) * 100, 1)} for i, (x, y) in enumerate(zip(pa, pb))],
                "verdict": verdict, "lesson": "PSI compares how the values fall into bins that held 10% each in the reference. The KS test asks how likely two samples are to come from one distribution. With large samples the test flags tiny, harmless shifts, so read the size of the shift too."}
    if kind == "labels":
        def cnt(t, nm):
            xs = [x.strip() for x in re.split(r"[\n,;]+", t or "") if x.strip()]
            if len(xs) < 5 or len(xs) > 50000:
                raise MlToolError(f"{nm}: give 5 to 50,000 labels.")
            return Counter(xs)
        ca, cb = cnt(reference, "Reference"), cnt(current, "Current")
        cats = sorted(set(ca) | set(cb))
        if len(cats) > 40:
            raise MlToolError("Too many different labels (limit 40).")
        pa = np.array([ca[c] for c in cats], float)
        pb = np.array([cb[c] for c in cats], float)
        psi = _psi(pa, pb)
        from scipy import stats
        tab = np.vstack([pa, pb])
        chi = stats.chi2_contingency(tab[:, tab.sum(0) > 0])
        verdict = "investigate" if psi >= 0.25 or chi[1] < 0.001 else "watch" if psi >= 0.1 or chi[1] < 0.05 else "no clear drift"
        return {"kind": "labels", "psi": round(psi, 4), "psi_band": _band(psi), "chi2_p_value": float(f"{chi[1]:.4g}"), "verdict": verdict,
                "categories": [{"label": c, "reference_pct": round(float(pa[i] / pa.sum()) * 100, 1), "current_pct": round(float(pb[i] / pb.sum()) * 100, 1)} for i, c in enumerate(cats)],
                "lesson": "Label drift (the mix of outcomes changing) is a different problem from input drift. If the share of fraud or churn moves, a threshold chosen on old data may no longer fit, and accuracy can fall without any input change."}
    raise MlToolError("Kind must be numeric or labels.")


def perf_drift(rows: str) -> dict:
    out = []
    for ln in (rows or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        p = [x.strip() for x in ln.split(",")]
        if len(p) != 3:
            raise MlToolError(f"Line '{ln}': use 'period, correct, total'.")
        try:
            c, t = int(p[1]), int(p[2])
        except ValueError:
            raise MlToolError(f"Line '{ln}': correct and total must be whole numbers.") from None
        if t < 1 or not 0 <= c <= t:
            raise MlToolError(f"Line '{ln}': total must be 1 or more and correct cannot exceed it.")
        out.append((p[0], c, t))
    if len(out) < 3 or len(out) > 60:
        raise MlToolError("Give 3 to 60 periods. The first period is the baseline.")
    from scipy import stats
    b = out[0]
    base = b[1] / b[2]
    rows_o = []
    for name, c, t in out:
        acc = c / t
        lo, hi = _wilson(c, t)
        z = (acc - base) / math.sqrt(max(base * (1 - base), 1e-9) * (1 / t + 1 / b[2]))
        p = float(stats.norm.cdf(z))
        rows_o.append({"period": name, "accuracy_pct": round(acc * 100, 1), "ci_low_pct": round(lo * 100, 1), "ci_high_pct": round(hi * 100, 1), "n": t, "drop_p_value": None if name == b[0] else float(f"{p:.3g}"),
                       "flag": "" if name == b[0] else ("significant drop" if p < 0.01 else "possible drop" if p < 0.05 else "")})
    flagged = [r["period"] for r in rows_o if r["flag"] == "significant drop"]
    return {"baseline_accuracy_pct": round(base * 100, 1), "periods": rows_o, "flagged": flagged, "verdict": "investigate" if flagged else "no clear drop",
            "lesson": "Accuracy from small periods is noisy; the interval shows how much. A drop that stays inside the interval of the baseline is not evidence. Performance drift needs true outcomes, which often arrive late, so input and label drift are the early warnings."}


def _wilson(c: int, n: int, z: float = 1.96):
    p = c / n
    d = 1 + z * z / n
    m = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, m - h), min(1.0, m + h)


DRIFT_SAMPLE = {"reference": " ".join(str(round(float(x), 2)) for x in np.random.default_rng(1).normal(50, 10, 200)), "current": " ".join(str(round(float(x), 2)) for x in np.random.default_rng(2).normal(56, 12, 200))}
PERF_SAMPLE = "Jan, 460, 500\nFeb, 455, 500\nMar, 448, 500\nApr, 430, 500\nMay, 405, 500"


# ---------------------------------------------------------------- automatic search
def automl(csv_text: str, target: str, max_features: int = 6) -> dict:
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    if not 1 <= max_features <= 12:
        raise MlToolError("Features to keep must be 1 to 12.")
    try:
        df = pd.read_csv(io.StringIO(csv_text or ""))
    except Exception:
        raise MlToolError("Could not read the data as CSV (first line = column names).") from None
    if target not in df.columns:
        raise MlToolError(f"There is no column named '{target}'. Columns: {', '.join(map(str, df.columns[:20]))}.")
    if not 30 <= len(df) <= 5000 or df.shape[1] > 31:
        raise MlToolError("Use 30 to 5,000 rows and at most 30 feature columns.")
    y = df[target]
    if y.isna().any():
        raise MlToolError("The target column has blanks; remove or fill those rows first.")
    X = df.drop(columns=[target])
    dropped = [c for c in X.columns if X[c].nunique() <= 1 or (X[c].dtype == object and X[c].nunique() > 20)
               or (pd.api.types.is_integer_dtype(X[c]) and X[c].nunique() == len(X) and (X[c].is_monotonic_increasing or X[c].is_monotonic_decreasing))]
    X = X.drop(columns=dropped)
    X = pd.get_dummies(X, drop_first=True, dtype=float)
    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    if X.shape[1] == 0:
        raise MlToolError("No usable feature columns are left.")
    cls = (y.dtype == object) or y.nunique() <= 10
    if cls:
        yy = pd.factorize(y)[0]
        if len(set(yy)) < 2 or Counter(yy).most_common()[-1][1] < 5:
            raise MlToolError("Each class needs at least 5 rows.")
        cv, scoring, sname = StratifiedKFold(5, shuffle=True, random_state=0), "accuracy", "accuracy"
        models = {"logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)), "decision tree (depth 4)": DecisionTreeClassifier(max_depth=4, random_state=0), "random forest (60 trees)": RandomForestClassifier(60, max_depth=6, random_state=0, n_jobs=1)}
        base_model = DummyClassifier(strategy="most_frequent")
    else:
        yy = y.astype(float).values
        cv, scoring, sname = KFold(5, shuffle=True, random_state=0), "r2", "R squared"
        models = {"ridge regression": make_pipeline(StandardScaler(), Ridge(1.0)), "decision tree (depth 4)": DecisionTreeRegressor(max_depth=4, random_state=0), "random forest (60 trees)": RandomForestRegressor(60, max_depth=6, random_state=0, n_jobs=1)}
        base_model = DummyRegressor()

    def score(m, cols):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = cross_val_score(m, X[cols].values, yy, cv=cv, scoring=scoring)
        return float(s.mean()), float(s.std())
    base = score(base_model, list(X.columns[:1]))
    fast = list(models.values())[0 if cls else 0]
    chosen, steps, best = [], [], -1e9
    left = list(X.columns)
    while left and len(chosen) < max_features:
        trial = [(score(fast, chosen + [c])[0], c) for c in left]
        s, c = max(trial)
        if chosen and s <= best + 0.01:
            steps.append({"step": len(chosen) + 1, "tried": len(trial), "result": f"stopped: the best next column ({c}) improves {sname} by only {s - best:.4f}"})
            break
        chosen.append(c)
        left.remove(c)
        best = s
        steps.append({"step": len(chosen), "tried": len(trial), "added": c, "cv_score": round(s, 4)})
    table = []
    for n, m in models.items():
        mean, sd = score(m, chosen)
        table.append({"model": n, "cv_mean": round(mean, 4), "cv_sd": round(sd, 4)})
    table.sort(key=lambda r: -r["cv_mean"])
    top = table[0]
    warn = []
    if top["cv_mean"] > 0.97 and cls or top["cv_mean"] > 0.97:
        warn.append("A score this high is suspicious. Check for a column that gives the answer away (leakage) before celebrating.")
    if len(table) > 1 and table[0]["cv_mean"] - table[1]["cv_mean"] < table[0]["cv_sd"]:
        warn.append("The top two models differ by less than one standard deviation of the folds. That is a tie; choose the simpler one.")
    if top["cv_mean"] - base[0] < 0.02:
        warn.append("The best model barely beats the do-nothing baseline. The features may not carry signal.")
    warn.append("The same data chose the features and measured the score, so the score is a little optimistic. Keep a final test set that this search never saw.")
    return {"task": "classification" if cls else "regression", "metric": sname, "baseline": {"model": "most common class" if cls else "predict the mean", "cv_mean": round(base[0], 4)}, "selected_features": chosen, "ignored_columns": dropped, "ignored_note": "Columns that never vary, text with many different values, and counters that look like row IDs are ignored.",
            "search_steps": steps, "models": table, "best": top["model"], "warnings": warn, "rows": len(df),
            "lesson": "Automatic search tries many options and keeps the one that scored best. The more it tries, the more likely the winner is partly luck, which is why a clean test set and a baseline matter more, not less."}


def _auto_sample():
    r = np.random.default_rng(5)
    n = 200
    a, b, c = r.normal(0, 1, n), r.normal(0, 1, n), r.normal(0, 1, n)
    y = (1.2 * a - 0.8 * b + r.normal(0, 0.7, n) > 0).astype(int)
    return "a,b,c,noise_id,target\n" + "\n".join(f"{a[i]:.3f},{b[i]:.3f},{c[i]:.3f},{i},{y[i]}" for i in range(n))


# ---------------------------------------------------------------- neural network
def _data(name: str, n: int, rng):
    if name == "xor":
        X = rng.uniform(-1, 1, (n, 2))
        return X, ((X[:, 0] * X[:, 1]) > 0).astype(float)
    if name == "circles":
        r = np.where(rng.random(n) < 0.5, 0.4, 0.9)
        t = rng.uniform(0, 2 * np.pi, n)
        X = np.c_[r * np.cos(t), r * np.sin(t)] + rng.normal(0, 0.07, (n, 2))
        return X, (r > 0.6).astype(float)
    if name == "moons":
        t = rng.uniform(0, np.pi, n)
        top = rng.random(n) < 0.5
        X = np.where(top[:, None], np.c_[np.cos(t), np.sin(t)], np.c_[1 - np.cos(t), 0.4 - np.sin(t)]) + rng.normal(0, 0.1, (n, 2))
        return X - X.mean(0), top.astype(float)
    if name == "line":
        X = rng.uniform(-1, 1, (n, 2))
        return X, (X[:, 0] + 0.5 * X[:, 1] > 0).astype(float)
    raise MlToolError("Data must be xor, circles, moons or line.")


def nn_train(data: str = "xor", hidden: str = "8", activation: str = "tanh", lr: float = 0.1, epochs: int = 300, seed: int = 3, n: int = 200) -> dict:
    try:
        sizes = [int(x) for x in re.split(r"[\s,]+", hidden.strip()) if x] if hidden.strip() else []
    except ValueError:
        raise MlToolError("Hidden layers: whole numbers like 8 or 8,4.") from None
    if len(sizes) > 3 or any(not 1 <= s <= 32 for s in sizes):
        raise MlToolError("Use 0 to 3 hidden layers of 1 to 32 units each.")
    if activation not in ("tanh", "relu", "sigmoid") or not 0.001 <= lr <= 5 or not 10 <= epochs <= 3000 or not 40 <= n <= 1000:
        raise MlToolError("Check: activation tanh/relu/sigmoid, learning rate 0.001 to 5, epochs 10 to 3000, points 40 to 1000.")
    rng = np.random.default_rng(seed)
    X, y = _data(data, n, rng)
    idx = rng.permutation(n)
    k = int(n * 0.75)
    tr, te = idx[:k], idx[k:]
    dims = [2] + sizes + [1]
    W = [rng.normal(0, math.sqrt(2 / dims[i]), (dims[i], dims[i + 1])) for i in range(len(dims) - 1)]
    B = [np.zeros(dims[i + 1]) for i in range(len(dims) - 1)]
    act = {"tanh": (np.tanh, lambda a: 1 - a * a), "relu": (lambda z: np.maximum(0, z), lambda a: (a > 0).astype(float)), "sigmoid": (lambda z: 1 / (1 + np.exp(-z)), lambda a: a * (1 - a))}[activation]

    def fwd(Xb):
        A = [Xb]
        for i in range(len(W) - 1):
            A.append(act[0](A[-1] @ W[i] + B[i]))
        z = A[-1] @ W[-1] + B[-1]
        return A, 1 / (1 + np.exp(-np.clip(z, -30, 30))).ravel()

    hist = []
    for ep in range(epochs):
        A, p = fwd(X[tr])
        yt = y[tr]
        loss = float(-np.mean(yt * np.log(p + 1e-9) + (1 - yt) * np.log(1 - p + 1e-9)))
        d = ((p - yt) / len(yt))[:, None]
        for i in range(len(W) - 1, -1, -1):
            gW, gB = A[i].T @ d, d.sum(0)
            if i > 0:
                d = (d @ W[i].T) * act[1](A[i])
            W[i] -= lr * gW
            B[i] -= lr * gB
        if ep % max(1, epochs // 40) == 0 or ep == epochs - 1:
            hist.append({"epoch": ep, "loss": round(loss, 4)})
    _, ptr = fwd(X[tr])
    _, pte = fwd(X[te])
    acc_tr, acc_te = float(np.mean((ptr > 0.5) == y[tr])), float(np.mean((pte > 0.5) == y[te]))
    g = np.linspace(X.min() - 0.1, X.max() + 0.1, 24)
    gx, gy = np.meshgrid(g, g)
    _, pg = fwd(np.c_[gx.ravel(), gy.ravel()])
    grid = (pg.reshape(24, 24) > 0.5).astype(int).tolist()
    params = sum(w.size for w in W) + sum(b.size for b in B)
    notes = []
    if acc_tr - acc_te > 0.1:
        notes.append("Training accuracy is well above test accuracy: the network is memorising. Use fewer units, fewer epochs or more data.")
    if acc_te < 0.7:
        notes.append("Test accuracy is low. Try more epochs, more hidden units, or a different learning rate. A network with no hidden layer can only draw a straight line.")
    if hist[-1]["loss"] > hist[0]["loss"]:
        notes.append("The loss went up. The learning rate is probably too large.")
    return {"architecture": dims, "parameters": params, "train_accuracy_pct": round(acc_tr * 100, 1), "test_accuracy_pct": round(acc_te * 100, 1), "loss_curve": hist, "boundary_grid": grid,
            "points": [{"x": round(float(X[i, 0]), 3), "y": round(float(X[i, 1]), 3), "label": int(y[i]), "split": "train" if i in set(tr.tolist()) else "test"} for i in range(min(n, 300))], "notes": notes,
            "lesson": "Backpropagation is the chain rule applied layer by layer: the error at the output is passed backward to tell each weight which way to move. A hidden layer lets the network bend its boundary; xor and circles cannot be solved by a straight line."}


def grad_check() -> dict:
    rng = np.random.default_rng(0)
    x, y = rng.normal(size=(5, 3)), rng.integers(0, 2, 5).astype(float)
    W1, W2 = rng.normal(size=(3, 4)) * 0.5, rng.normal(size=(4, 1)) * 0.5

    def loss(W1, W2):
        h = np.tanh(x @ W1)
        p = 1 / (1 + np.exp(-(h @ W2).ravel()))
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    h = np.tanh(x @ W1)
    p = 1 / (1 + np.exp(-(h @ W2).ravel()))
    d2 = ((p - y) / 5)[:, None]
    g2 = h.T @ d2
    d1 = (d2 @ W2.T) * (1 - h * h)
    g1 = x.T @ d1
    e = 1e-5
    rows = []
    for name, G, W in (("W1[0,0]", g1[0, 0], 0), ("W1[2,3]", g1[2, 3], 1), ("W2[1,0]", g2[1, 0], 2)):
        a, b = W1.copy(), W2.copy()
        if W == 0:
            a[0, 0] += e
            c, d = W1.copy(), W2.copy()
            c[0, 0] -= e
        elif W == 1:
            a[2, 3] += e
            c, d = W1.copy(), W2.copy()
            c[2, 3] -= e
        else:
            b[1, 0] += e
            c, d = W1.copy(), W2.copy()
            d[1, 0] -= e
        num = (loss(a, b) - loss(c, d)) / (2 * e)
        rows.append({"weight": name, "backprop_gradient": round(float(G), 8), "numerical_gradient": round(float(num), 8), "difference": float(f"{abs(G - num):.2e}")})
    return {"checks": rows, "ok": all(r["difference"] < 1e-6 for r in rows), "lesson": "A gradient check nudges one weight up and down and measures the change in loss directly. If it matches the backpropagation gradient to many digits, the backward pass is right. It is the standard test when writing backprop by hand."}


def attention(text: str, dim: int = 8, causal: bool = False, seed: int = 4) -> dict:
    toks = [t for t in re.findall(r"\w+|[^\w\s]", (text or "").lower())]
    if not 2 <= len(toks) <= 16 or not 2 <= dim <= 32:
        raise MlToolError("Give 2 to 16 tokens (words) and a size of 2 to 32.")
    rng = np.random.default_rng(seed)
    E = {t: np.random.default_rng(zlib.crc32(t.encode())).normal(0, 1, dim) for t in set(toks)}
    X = np.array([E[t] for t in toks]) + 0.3 * np.sin(np.arange(len(toks))[:, None] / (10 ** (np.arange(dim) / dim)))
    Wq, Wk, Wv = (rng.normal(0, 1 / math.sqrt(dim), (dim, dim)) for _ in range(3))
    Q, K, V = X @ Wq, X @ Wk, X @ Wv
    S = Q @ K.T / math.sqrt(dim)
    if causal:
        S = np.where(np.tril(np.ones_like(S)) == 1, S, -1e9)
    S = S - S.max(1, keepdims=True)
    A = np.exp(S)
    A /= A.sum(1, keepdims=True)
    return {"tokens": toks, "weights": [[round(float(x), 3) for x in r] for r in A], "rows_sum_to_one": bool(np.allclose(A.sum(1), 1)), "output_shape": list(map(int, (A @ V).shape)),
            "strongest": [{"token": toks[i], "attends_most_to": toks[int(A[i].argmax())], "weight": round(float(A[i].max()), 3)} for i in range(len(toks))], "causal": causal,
            "lesson": "Each token makes a query, a key and a value. A token's query is compared with every key (a dot product, scaled), softmax turns the scores into weights that add to 1, and the output is the weighted mix of values. A causal mask stops a token looking at later tokens, which is how text generators are trained.",
            "limits": "The embeddings and projection matrices are random, so the weights show the mechanism, not meaning. A trained model learns these matrices from data."}


# ---------------------------------------------------------------- BPE
def bpe(text: str, merges: int = 20, test: str = "") -> dict:
    if not 1 <= merges <= 200 or not 20 <= len(text or "") <= 50000:
        raise MlToolError("Give 20 to 50,000 characters of text and 1 to 200 merges.")
    words = Counter((text or "").lower().split())
    vocab = {tuple(w) + ("</w>",): c for w, c in words.items()}
    ops = []
    for step in range(merges):
        pairs = Counter()
        for w, c in vocab.items():
            for a, b in zip(w, w[1:]):
                pairs[(a, b)] += c
        if not pairs:
            break
        (a, b), c = max(pairs.items(), key=lambda kv: (kv[1], kv[0]))
        if c < 2:
            break
        ops.append({"step": step + 1, "merge": f"{a} + {b}", "new_token": a + b, "count": c})
        nv = {}
        for w, cnt in vocab.items():
            out, i = [], 0
            while i < len(w):
                if i < len(w) - 1 and w[i] == a and w[i + 1] == b:
                    out.append(a + b)
                    i += 2
                else:
                    out.append(w[i])
                    i += 1
            nv[tuple(out)] = nv.get(tuple(out), 0) + cnt
        vocab = nv
    base = {ch for w in words for ch in w} | {"</w>"}
    tokens = base | {o["new_token"] for o in ops}

    def encode(word: str):
        t = list(word) + ["</w>"]
        for o in ops:
            a, b = o["merge"].split(" + ")
            i = 0
            while i < len(t) - 1:
                if t[i] == a and t[i + 1] == b:
                    t[i:i + 2] = [a + b]
                else:
                    i += 1
        return t
    sample = (test or " ".join(list(words)[:3]) or "").lower().split()
    enc = [{"word": w, "tokens": encode(w)} for w in sample[:20]]
    chars = sum(len(w) + 1 for w in sample[:20])
    ntok = sum(len(e["tokens"]) for e in enc)
    return {"merges": ops, "vocab_size": len(tokens), "base_symbols": len(base), "encoded": enc, "chars": chars, "tokens": ntok, "chars_per_token": round(chars / ntok, 2) if ntok else None,
            "lesson": "Byte-pair encoding starts from single characters and repeatedly merges the most frequent neighbouring pair into a new token. Common words end up as one token and rare words split into pieces, so any text can be written with a fixed vocabulary.",
            "limits": "Character-level and lowercase, built from the text you give. Real tokenizers work on bytes, train on huge text and use extra rules."}


BPE_SAMPLE = "low low low low low lower lower newest newest newest newest newest newest widest widest widest"


# ---------------------------------------------------------------- LSA semantic search
_STOP = set("a an the of and or to in on for with is are was be it this that as at by from".split())


def lsa(docs: str, query: str, k: int = 2) -> dict:
    ds = [d.strip() for d in (docs or "").splitlines() if d.strip()]
    if not 3 <= len(ds) <= 300 or not 1 <= k <= 20 or not (query or "").strip():
        raise MlToolError("Give 3 to 300 documents (one per line), a query, and 1 to 20 concepts.")
    tok = lambda s: [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP]  # noqa: E731
    T = [tok(d) for d in ds]
    vocab = sorted({w for t in T for w in t})
    if len(vocab) < 3:
        raise MlToolError("The documents share too few words.")
    ix = {w: i for i, w in enumerate(vocab)}
    tf = np.zeros((len(ds), len(vocab)))
    for i, t in enumerate(T):
        for w in t:
            tf[i, ix[w]] += 1
    df = (tf > 0).sum(0)
    idf = np.log((1 + len(ds)) / (1 + df)) + 1
    M = tf * idf
    M /= np.linalg.norm(M, axis=1, keepdims=True) + 1e-12
    q = np.zeros(len(vocab))
    for w in tok(query):
        if w in ix:
            q[ix[w]] += 1
    known = [w for w in tok(query) if w in ix]
    q = q * idf
    qn = np.linalg.norm(q)
    if qn == 0:
        raise MlToolError("None of the query words appear in the documents.")
    q /= qn
    kk = min(k, min(M.shape) - 1)
    U, S, Vt = np.linalg.svd(M, full_matrices=False)
    Dk, Vk = U[:, :kk] * S[:kk], Vt[:kk]
    qk = q @ Vk.T
    cos = lambda a, b: (a @ b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)  # noqa: E731
    rows = [{"doc": i + 1, "text": ds[i][:120], "keyword_score": round(float(M[i] @ q), 3), "concept_score": round(float(cos(Dk[i], qk)), 3)} for i in range(len(ds))]
    concepts = [{"concept": c + 1, "strength": round(float(S[c]), 3), "top_words": [vocab[j] for j in np.argsort(-np.abs(Vt[c]))[:5]]} for c in range(kk)]
    return {"query_words_found": known, "results": sorted(rows, key=lambda r: -r["concept_score"]), "concepts": concepts, "vocabulary": len(vocab),
            "found_only_by_concepts": [r["doc"] for r in rows if r["keyword_score"] < 0.01 and r["concept_score"] > 0.3],
            "lesson": "TF-IDF scores documents by shared words. Latent semantic analysis (a singular value decomposition) finds groups of words that appear together and compares documents and queries in that smaller concept space, so a document can match a query without sharing its words.",
            "limits": "A small, old technique. Modern search uses learned embeddings from neural models; the idea of comparing meaning by vector direction is the same."}


LSA_SAMPLE = {"docs": "the car engine needs oil and a new battery\nautomobile engine repair and maintenance guide\nbaking bread needs flour yeast and an oven\nrecipe for sourdough bread and pastry dough\nbattery and engine problems in older vehicles", "query": "car repair", "k": 2}

SLIPS = ["Drift guides say 'PSI over 0.2 means retrain'. The 0.1 and 0.25 cut-offs are rules of thumb from credit scoring, not laws; a large shift in a feature the model ignores is harmless.",
         "AutoML marketing says it 'removes the need for data science'. It searches faster, but it cannot tell you the target is leaked, the labels are wrong or the data will not look like next month's.",
         "Neural network explainers draw backpropagation as 'errors flowing backward' without saying it is just the chain rule; a gradient check is the proof you wrote it right.",
         "Tokenizer explainers often say a token is a word. Tokens are pieces chosen by frequency; many words are several tokens.",
         "Search posts call embeddings a 2020s idea. Latent semantic analysis did meaning-based search in 1990 with a matrix decomposition."]
NOT_BUILT = ["GPU training, convolutional or recurrent networks, a full transformer, or pretraining any language model.", "A production AutoML system or hyperparameter search at scale.", "Learned embeddings from a neural model (needs a model download); LSA is the offline stand-in."]


def reference() -> dict:
    return {"samples": {"drift": DRIFT_SAMPLE, "perf": PERF_SAMPLE, "automl": _auto_sample(), "bpe": BPE_SAMPLE, "lsa": LSA_SAMPLE, "attention": "the cat sat on the mat"}, "slips": SLIPS, "not_built": NOT_BUILT}
