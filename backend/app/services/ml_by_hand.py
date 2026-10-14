"""ML by hand: solve small machine-learning problems step by step with every number shown, then check the answer against the real library.

Sandbox rules: everything runs in memory on the few rows you type in; nothing is saved and no dashboard data is changed.
Limits: 60 rows, 8 features. Methods: simple regression, multiple regression, KNN, decision tree, random forest, metrics."""
from __future__ import annotations

import csv
import io
import math
import random
from collections import Counter
from fractions import Fraction

MAX_ROWS, MAX_FEATURES = 60, 8
METHODS = ("linear", "multiple", "knn", "tree", "forest", "metrics", "tfidf", "bayes", "ngram", "edit", "nn", "gd", "perceptron")


class HandError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _f(x: float | Fraction, nd: int = 4) -> str:
    v = float(x)
    if v == int(v) and abs(v) < 1e12:
        return str(int(v))
    return f"{v:.{nd}f}".rstrip("0").rstrip(".")


def _step(title: str, detail: str = "", math_: str = "") -> dict:
    return {"title": title, "detail": detail, "math": math_}


def parse_table(text: str, numeric_target: bool = True) -> tuple[list[str], list[list[str]]]:
    rows = [r for r in csv.reader(io.StringIO((text or "").strip())) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise HandError("Enter a header row and at least one data row (comma separated).")
    head = [h.strip() or f"col{i + 1}" for i, h in enumerate(rows[0])]
    body = [[c.strip() for c in r] for r in rows[1:]]
    if any(len(r) != len(head) for r in body):
        raise HandError("Every row must have the same number of values as the header.")
    if len(body) > MAX_ROWS:
        raise HandError(f"Too many rows for working by hand ({MAX_ROWS} max). Use the ML Lab for bigger data.")
    if len(head) - 1 > MAX_FEATURES:
        raise HandError(f"Too many columns ({MAX_FEATURES} features max).")
    return head, body


def _num(s: str, what: str) -> Fraction:
    try:
        v = Fraction(s.replace(",", "").replace("$", ""))
    except (ValueError, ZeroDivisionError) as e:
        raise HandError(f"'{s}' in {what} is not a number.") from e
    return v


def _nums(rows: list[list[str]], cols: list[int], names: list[str]) -> list[list[Fraction]]:
    return [[_num(r[c], names[c]) for c in cols] for r in rows]


def _query(text: str, n: int, names: list[str]) -> list[str] | None:
    if not (text or "").strip():
        return None
    vals = [c.strip() for c in next(csv.reader(io.StringIO(text.strip())))]
    if len(vals) != n:
        raise HandError(f"The new row needs {n} values (one per feature: {', '.join(names)}).")
    return vals


def _reg_metrics(y: list[Fraction], p: list[Fraction]) -> tuple[list[dict], dict]:
    n = len(y)
    err = [yi - pi for yi, pi in zip(y, p)]
    mae = sum(abs(e) for e in err) / n
    mse = sum(e * e for e in err) / n
    rmse = math.sqrt(float(mse))
    ym = sum(y) / n
    sst = sum((yi - ym) ** 2 for yi in y)
    sse = sum(e * e for e in err)
    r2 = 1 - float(sse / sst) if sst else None
    steps = [_step("Errors (actual minus predicted)", ", ".join(_f(e) for e in err)),
             _step("MAE: mean absolute error", "Average size of the error. Closer to 0 is better.", f"({' + '.join(_f(abs(e)) for e in err)}) / {n} = {_f(mae)}"),
             _step("MSE: mean squared error", "Squares each error so big misses count more.", f"({' + '.join(_f(e * e) for e in err)}) / {n} = {_f(mse)}"),
             _step("RMSE: root of MSE", "Back in the same units as y.", f"sqrt({_f(mse)}) = {_f(rmse)}"),
             _step("R squared", "1 means a perfect fit; 0 means no better than always guessing the mean.", f"1 - SSE/SST = 1 - {_f(sse)}/{_f(sst)} = {_f(r2) if r2 is not None else 'undefined (y never changes)'}")]
    return steps, {"MAE": float(mae), "MSE": float(mse), "RMSE": rmse, "R2": r2}


def _solve(A: list[list[Fraction]], b: list[Fraction]) -> tuple[list[Fraction], list[str]]:
    """Gauss-Jordan elimination with exact fractions. Returns the solution and a log of the row operations."""
    n = len(A)
    M = [row[:] + [bi] for row, bi in zip(A, b)]
    log = []
    for c in range(n):
        piv = next((r for r in range(c, n) if M[r][c] != 0), None)
        if piv is None:
            raise HandError("These features can't be separated: one column is a copy, multiple or combination of others, so the equations have no single answer. Remove or change a feature.")
        if piv != c:
            M[c], M[piv] = M[piv], M[c]
            log.append(f"Swap row {c + 1} and row {piv + 1}")
        d = M[c][c]
        M[c] = [v / d for v in M[c]]
        log.append(f"Row {c + 1} / {_f(d)}")
        for r in range(n):
            if r != c and M[r][c] != 0:
                k = M[r][c]
                M[r] = [a - k * bb for a, bb in zip(M[r], M[c])]
                log.append(f"Row {r + 1} - {_f(k)} x row {c + 1}")
    return [M[i][n] for i in range(n)], log


# ------------------------------------------------------------------ simple linear regression
def linear(text: str, query: str = "") -> dict:
    head, body = parse_table(text)
    if len(head) != 2:
        raise HandError("Simple regression needs exactly two columns: x then y. Use Multiple regression for more inputs.")
    pts = _nums(body, [0, 1], head)
    n = len(pts)
    if n < 2:
        raise HandError("Give at least 2 rows.")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    xm, ym = sum(xs) / n, sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    if sxx == 0:
        raise HandError("All x values are the same, so no line can be fitted.")
    sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    m = sxy / sxx
    c = ym - m * xm
    steps = [_step("Goal", f"Fit y = m*x + c, where y is {head[1]} and x is {head[0]}."),
             _step("Means", f"Average of x and of y over {n} rows.", f"x̄ = {_f(sum(xs))}/{n} = {_f(xm)};  ȳ = {_f(sum(ys))}/{n} = {_f(ym)}"),
             _step("Differences from the means", "For each row: (x - x̄), (y - ȳ), their product and (x - x̄) squared.",
                   "\n".join(f"row {i + 1}: ({_f(x - xm)}) ({_f(y - ym)}) = {_f((x - xm) * (y - ym))};  ({_f(x - xm)})² = {_f((x - xm) ** 2)}" for i, (x, y) in enumerate(pts))),
             _step("Add them up", "", f"Σ(x-x̄)(y-ȳ) = {_f(sxy)};  Σ(x-x̄)² = {_f(sxx)}"),
             _step("Slope m", "How much y changes when x goes up by 1.", f"m = {_f(sxy)} / {_f(sxx)} = {_f(m)}"),
             _step("Intercept c", "The value of y when x is 0 (the line must pass through the point of means).", f"c = ȳ - m*x̄ = {_f(ym)} - {_f(m)} x {_f(xm)} = {_f(c)}"),
             _step("Fitted model", "This is what 'fitting' means: finding m and c.", f"y = {_f(m)} * x + {_f(c)}")]
    preds = [m * x + c for x in xs]
    ms, metrics = _reg_metrics(ys, preds)
    steps.append(_step("Predictions on your rows", ", ".join(f"{_f(x)} → {_f(p)}" for x, p in zip(xs, preds))))
    steps += ms
    answer = {"slope": float(m), "intercept": float(c)}
    q = _query(query, 1, head[:1])
    if q:
        qx = _num(q[0], head[0])
        pred = m * qx + c
        steps.append(_step("Predict a new value", f"Put x = {_f(qx)} into the model.", f"y = {_f(m)} x {_f(qx)} + {_f(c)} = {_f(pred)}"))
        answer["prediction"] = float(pred)
    import numpy as np
    sl, ic = np.polyfit([float(x) for x in xs], [float(y) for y in ys], 1)
    check = {"library": "numpy.polyfit (least squares)", "values": {"slope": float(sl), "intercept": float(ic)}, "agrees": bool(abs(sl - float(m)) < 1e-6 and abs(ic - float(c)) < 1e-6)}
    return {"method": "linear", "steps": steps, "answer": answer, "metrics": metrics, "check": check}


# ------------------------------------------------------------------ multiple linear regression
def multiple(text: str, query: str = "") -> dict:
    head, body = parse_table(text)
    p = len(head) - 1
    if p < 2:
        raise HandError("Multiple regression needs at least two input columns plus the target (last column).")
    n = len(body)
    names = head[:-1]
    X = _nums(body, list(range(p)), head)
    y = [_num(r[-1], head[-1]) for r in body]
    unknowns = p + 1
    if n < unknowns:
        raise HandError(f"{n} rows give {n} equations, but the model has {unknowns} unknowns ({p} coefficients and an intercept). You need at least {unknowns} rows; with fewer there are many equally good answers, so any single answer is a guess.")
    Xa = [row + [Fraction(1)] for row in X]
    coefs_names = [f"a{i + 1} ({names[i]})" for i in range(p)] + ["b (intercept)"]
    steps = [_step("Goal", f"Fit {head[-1]} = " + " + ".join(f"a{i + 1}*{names[i]}" for i in range(p)) + " + b."),
             _step("Write one equation per row", "Each row says: coefficients times its values, plus b, must equal the target.",
                   "\n".join(" + ".join(f"{_f(v)}*a{i + 1}" for i, v in enumerate(r[:-1])) + f" + b = {_f(t)}" for r, t in zip(Xa, y)))]
    if n == unknowns:
        A, b = Xa, y
        steps.append(_step("Exactly as many equations as unknowns", "So the system can be solved exactly (if no feature is a copy of another)."))
    else:
        A = [[sum(Xa[k][i] * Xa[k][j] for k in range(n)) for j in range(unknowns)] for i in range(unknowns)]
        b = [sum(Xa[k][i] * y[k] for k in range(n)) for i in range(unknowns)]
        steps.append(_step(f"{n} rows but {unknowns} unknowns: use least squares", "No line passes through every point, so find the coefficients with the smallest squared error. That means solving the normal equations (XᵀX) β = Xᵀy.",
                           "XᵀX =\n" + "\n".join("  [" + ", ".join(_f(v) for v in r) + "]" for r in A) + "\nXᵀy = [" + ", ".join(_f(v) for v in b) + "]"))
    sol, log = _solve(A, b)
    steps.append(_step("Solve by elimination", "Row operations until each unknown stands alone.", "\n".join(log[:40]) + ("\n…" if len(log) > 40 else "")))
    steps.append(_step("Coefficients", "", "\n".join(f"{nm} = {_f(v)}" for nm, v in zip(coefs_names, sol))))
    model = " + ".join(f"{_f(sol[i])}*{names[i]}" for i in range(p)) + f" + {_f(sol[-1])}"
    steps.append(_step("Fitted model", "A feature whose coefficient is 0 has no effect on predictions.", f"{head[-1]} = {model}"))
    preds = [sum(c * v for c, v in zip(sol, r)) for r in Xa]
    ms, metrics = _reg_metrics(y, preds)
    steps.append(_step("Predictions on your rows", ", ".join(f"{_f(pv)}" for pv in preds)))
    steps += ms
    answer = {**{f"a{i + 1}": float(sol[i]) for i in range(p)}, "b": float(sol[-1])}
    q = _query(query, p, names)
    if q:
        qv = [_num(v, names[i]) for i, v in enumerate(q)] + [Fraction(1)]
        pred = sum(c * v for c, v in zip(sol, qv))
        steps.append(_step("Predict a new row", "", " + ".join(f"{_f(c)}*{_f(v)}" for c, v in zip(sol[:-1], qv[:-1])) + f" + {_f(sol[-1])} = {_f(pred)}"))
        answer["prediction"] = float(pred)
    import numpy as np
    lib, *_ = np.linalg.lstsq(np.array([[float(v) for v in r] for r in Xa]), np.array([float(v) for v in y]), rcond=None)
    ok = all(abs(float(a) - float(b2)) < 1e-6 for a, b2 in zip(sol, lib))
    check = {"library": "numpy.linalg.lstsq", "values": {k: float(v) for k, v in zip(["a" + str(i + 1) for i in range(p)] + ["b"], lib)}, "agrees": bool(ok)}
    return {"method": "multiple", "steps": steps, "answer": answer, "metrics": metrics, "check": check}


# ------------------------------------------------------------------ k nearest neighbours
def knn(text: str, query: str, k: int = 3, task: str = "classification", scale: bool = False) -> dict:
    head, body = parse_table(text)
    p = len(head) - 1
    if p < 1:
        raise HandError("Need at least one feature column plus the target (last column).")
    k = int(k)
    if not 1 <= k <= len(body):
        raise HandError(f"k must be between 1 and the number of rows ({len(body)}).")
    names = head[:-1]
    X = _nums(body, list(range(p)), head)
    q = _query(query, p, names)
    if not q:
        raise HandError(f"Give the new row to classify ({p} values: {', '.join(names)}).")
    qv = [_num(v, names[i]) for i, v in enumerate(q)]
    steps = [_step("Idea", "Find the k rows closest to the new row and let them vote (classification) or average their answers (regression).")]
    if scale:
        lo = [min(r[i] for r in X + [qv]) for i in range(p)]
        hi = [max(r[i] for r in X + [qv]) for i in range(p)]
        sc = lambda r: [(v - lo[i]) / (hi[i] - lo[i]) if hi[i] != lo[i] else Fraction(0) for i, v in enumerate(r)]
        steps.append(_step("Scale every feature to 0..1", "So a feature measured in thousands doesn't drown out one measured in tenths.", "x' = (x - min) / (max - min)"))
        Xs, qs = [sc(r) for r in X], sc(qv)
    else:
        Xs, qs = X, qv
    dist = []
    for i, r in enumerate(Xs):
        sq = sum((a - b) ** 2 for a, b in zip(r, qs))
        dist.append((math.sqrt(float(sq)), i, sq))
    order = sorted(dist, key=lambda t: (t[0], t[1]))
    steps.append(_step("Distance to the new row", "Straight-line (Euclidean) distance: square root of the sum of squared differences.",
                       "\n".join(f"row {i + 1} ({body[i][-1]}): sqrt({_f(sq)}) = {_f(d)}" for d, i, sq in dist)))
    nn = order[:k]
    steps.append(_step(f"The {k} nearest", "Smallest distances first.", "\n".join(f"#{j + 1}: row {i + 1}, distance {_f(d)}, answer {body[i][-1]}" for j, (d, i, _) in enumerate(nn))))
    if task == "regression":
        vals = [_num(body[i][-1], head[-1]) for _, i, _ in nn]
        pred = sum(vals) / k
        steps.append(_step("Average their answers", "", f"({' + '.join(_f(v) for v in vals)}) / {k} = {_f(pred)}"))
        answer: dict = {"prediction": float(pred)}
    else:
        votes = Counter(body[i][-1] for _, i, _ in nn)
        top = max(votes.values())
        winners = [lab for lab, c in votes.items() if c == top]
        if len(winners) > 1:
            tot = {lab: sum(d for d, i, _ in nn if body[i][-1] == lab) for lab in winners}
            win = min(winners, key=lambda lab: (tot[lab], lab))
            note = f"Tie between {', '.join(sorted(winners))}. Rule used here: the tied group with the smaller total distance wins ({win}). Choose an odd k to avoid ties."
        else:
            win, note = winners[0], ""
        steps.append(_step("Vote", note or "The most common answer among the neighbours wins.", ", ".join(f"{lab}: {c}" for lab, c in votes.most_common())))
        pred = win
        answer = {"prediction": win}
    check = {"library": "scikit-learn KNeighbors" + ("Regressor" if task == "regression" else "Classifier"), "values": {}, "agrees": None}
    try:
        from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
        Xf = [[float(v) for v in r] for r in Xs]
        qf = [[float(v) for v in qs]]
        if task == "regression":
            m = KNeighborsRegressor(n_neighbors=k).fit(Xf, [float(body[i][-1]) for i in range(len(body))])
            lp = float(m.predict(qf)[0])
            check.update(values={"prediction": lp}, agrees=bool(abs(lp - float(pred)) < 1e-6))
        else:
            m = KNeighborsClassifier(n_neighbors=k).fit(Xf, [r[-1] for r in body])
            lp = str(m.predict(qf)[0])
            check.update(values={"prediction": lp}, agrees=lp == pred)
    except Exception:  # noqa: BLE001
        pass
    return {"method": "knn", "steps": steps, "answer": answer, "check": check}


# ------------------------------------------------------------------ decision tree
def _impurity(labels: list[str], criterion: str) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    ps = [c / n for c in Counter(labels).values()]
    return 1 - sum(p * p for p in ps) if criterion == "gini" else -sum(p * math.log2(p) for p in ps if p > 0)


def _candidates(rows: list[list[str]], labels: list[str], feats: list[int], names: list[str], numeric: list[bool], criterion: str) -> list[dict]:
    parent = _impurity(labels, criterion)
    n = len(rows)
    out = []
    for f in feats:
        if numeric[f]:
            vals = sorted({float(r[f]) for r in rows})
            cuts = [(a + b) / 2 for a, b in zip(vals, vals[1:])]
            tests = [(f"{names[f]} <= {_f(c)}", (lambda r, c=c, f=f: float(r[f]) <= c)) for c in cuts]
        else:
            tests = [(f"{names[f]} = {v}", (lambda r, v=v, f=f: r[f] == v)) for v in sorted({r[f] for r in rows})]
        for label, test in tests:
            left = [lab for r, lab in zip(rows, labels) if test(r)]
            right = [lab for r, lab in zip(rows, labels) if not test(r)]
            if not left or not right:
                continue
            w = len(left) / n * _impurity(left, criterion) + len(right) / n * _impurity(right, criterion)
            out.append({"test": label, "f": f, "fn": test, "left": left, "right": right, "weighted": w, "gain": parent - w})
    out.sort(key=lambda c: (-round(c["gain"], 12), c["f"]))
    return out


def _major(labels: list[str]) -> str:
    c = Counter(labels)
    top = max(c.values())
    return sorted(l for l, v in c.items() if v == top)[0]


def _build(rows, labels, feats, names, numeric, criterion, depth, steps, path="root", detail=True):
    imp = _impurity(labels, criterion)
    if depth == 0 or imp == 0 or len(set(map(tuple, rows))) == 1:
        return {"leaf": _major(labels), "n": len(labels), "counts": dict(Counter(labels))}
    cands = _candidates(rows, labels, feats, names, numeric, criterion)
    if not cands or cands[0]["gain"] <= 1e-12:
        return {"leaf": _major(labels), "n": len(labels), "counts": dict(Counter(labels))}
    best = cands[0]
    name = "Gini" if criterion == "gini" else "Entropy"
    if detail:
        steps.append(_step(f"{path}: impurity before splitting", f"{name} of {len(labels)} rows {dict(Counter(labels))}. 0 means all the same class.", f"{name} = {_f(imp)}"))
        steps.append(_step(f"{path}: try every split", "Weighted impurity after the split = (left share) x impurity + (right share) x impurity. Gain = before - after. Biggest gain wins.",
                           "\n".join(f"{c['test']}: left {dict(Counter(c['left']))}, right {dict(Counter(c['right']))}, after {_f(c['weighted'])}, gain {_f(c['gain'])}" for c in cands[:12]) + ("\n…" if len(cands) > 12 else "")))
        steps.append(_step(f"{path}: best split", "", f"{best['test']}  (gain {_f(best['gain'])})"))
    li = [i for i, r in enumerate(rows) if best["fn"](r)]
    ri = [i for i in range(len(rows)) if i not in set(li)]
    return {"test": best["test"], "fn": best["fn"], "n": len(labels), "counts": dict(Counter(labels)),
            "yes": _build([rows[i] for i in li], [labels[i] for i in li], feats, names, numeric, criterion, depth - 1, steps, path + " > yes", detail),
            "no": _build([rows[i] for i in ri], [labels[i] for i in ri], feats, names, numeric, criterion, depth - 1, steps, path + " > no", detail)}


def _outline(node, indent=0) -> list[str]:
    pad = "  " * indent
    if "leaf" in node:
        return [f"{pad}→ {node['leaf']}  ({node['n']} rows {node['counts']})"]
    return [f"{pad}if {node['test']}?  ({node['n']} rows {node['counts']})"] + [f"{pad} yes:"] + _outline(node["yes"], indent + 1) + [f"{pad} no:"] + _outline(node["no"], indent + 1)


def _predict(node, row):
    while "leaf" not in node:
        node = node["yes"] if node["fn"](row) else node["no"]
    return node["leaf"]


def _is_num(col: list[str]) -> bool:
    try:
        [float(v) for v in col]
        return True
    except ValueError:
        return False


def tree(text: str, query: str = "", criterion: str = "gini", depth: int = 2) -> dict:
    head, body = parse_table(text)
    p = len(head) - 1
    if p < 1:
        raise HandError("Need at least one feature column plus the class (last column).")
    if criterion not in ("gini", "entropy"):
        raise HandError("criterion must be gini or entropy.")
    depth = max(1, min(int(depth), 3))
    names = head[:-1]
    rows = [r[:p] for r in body]
    labels = [r[-1] for r in body]
    numeric = [_is_num([r[c] for r in rows]) for c in range(p)]
    steps = [_step("Idea", "Ask the yes/no question that separates the classes best, then repeat on each side until the groups are pure or the depth limit is reached.")]
    node = _build(rows, labels, list(range(p)), names, numeric, criterion, depth, steps)
    steps.append(_step("The finished tree", "", "\n".join(_outline(node))))
    answer: dict = {"root_split": node.get("test", "no split needed")}
    q = _query(query, p, names)
    if q:
        pred = _predict(node, q)
        steps.append(_step("Predict a new row", "Follow the questions down to a leaf.", f"{', '.join(f'{n}={v}' for n, v in zip(names, q))} → {pred}"))
        answer["prediction"] = pred
    check = {"library": "scikit-learn DecisionTreeClassifier", "values": {}, "agrees": None}
    if all(numeric):
        try:
            from sklearn.tree import DecisionTreeClassifier
            m = DecisionTreeClassifier(criterion=criterion, max_depth=depth, random_state=0).fit([[float(v) for v in r] for r in rows], labels)
            vals: dict = {}
            if q:
                vals["prediction"] = str(m.predict([[float(v) for v in q]])[0])
            vals["training_accuracy"] = float(m.score([[float(v) for v in r] for r in rows], labels))
            mine = sum(_predict(node, r) == l for r, l in zip(rows, labels)) / len(rows)
            check.update(values=vals, agrees=abs(vals["training_accuracy"] - mine) < 1e-9 and (not q or vals["prediction"] == answer["prediction"]))
            answer["training_accuracy"] = mine
        except Exception:  # noqa: BLE001
            pass
    else:
        check["note"] = "The library check needs all-number features; this data has words, so only the hand result is shown."
        answer["training_accuracy"] = sum(_predict(node, r) == l for r, l in zip(rows, labels)) / len(rows)
    return {"method": "tree", "steps": steps, "answer": answer, "check": check}


# ------------------------------------------------------------------ random forest
def forest(text: str, query: str, trees: int = 5, seed: int = 1, criterion: str = "gini") -> dict:
    head, body = parse_table(text)
    p = len(head) - 1
    if p < 1:
        raise HandError("Need at least one feature column plus the class (last column).")
    trees = max(1, min(int(trees), 9))
    names = head[:-1]
    rows = [r[:p] for r in body]
    labels = [r[-1] for r in body]
    numeric = [_is_num([r[c] for r in rows]) for c in range(p)]
    q = _query(query, p, names)
    if not q:
        raise HandError(f"Give the new row to classify ({p} values).")
    rnd = random.Random(int(seed))
    m_feat = max(1, math.ceil(math.sqrt(p)))
    steps = [_step("Idea", "Grow several small trees, each on a random re-sample of the rows (a bootstrap) and a random subset of the features. Each tree votes; the majority wins. Averaging many different trees cancels out their individual mistakes."),
             _step("Settings", f"{trees} trees, each looking at {m_feat} of {p} features at every split (about the square root), random seed {int(seed)} so you can repeat this exactly.")]
    votes = []
    n = len(rows)
    for t in range(trees):
        idx = [rnd.randrange(n) for _ in range(n)]
        feats = sorted(rnd.sample(range(p), m_feat))
        br, bl = [rows[i] for i in idx], [labels[i] for i in idx]
        sub: list[dict] = []
        node = _build(br, bl, feats, names, numeric, criterion, 1, sub, f"tree {t + 1}", detail=False)
        v = _predict(node, q)
        votes.append(v)
        oob = n - len(set(idx))
        steps.append(_step(f"Tree {t + 1}", f"Bootstrap rows (numbers are row positions, repeats allowed): {[i + 1 for i in idx]}. {oob} rows were left out. Features it may use: {[names[f] for f in feats]}.",
                           "\n".join(_outline(node)) + f"\nVote for the new row: {v}"))
    c = Counter(votes)
    top = max(c.values())
    win = sorted(l for l, v in c.items() if v == top)[0]
    steps.append(_step("Count the votes", "Majority wins (ties go to the first label alphabetically).", ", ".join(f"{l}: {v}" for l, v in c.most_common()) + f"  →  {win}"))
    check = {"library": "scikit-learn RandomForestClassifier", "values": {}, "agrees": None, "note": "A library forest uses a different random generator, so its trees differ. The answer should usually match, but small data can differ."}
    if all(numeric):
        try:
            from sklearn.ensemble import RandomForestClassifier
            m = RandomForestClassifier(n_estimators=max(trees, 25), max_depth=1 if False else None, random_state=int(seed)).fit([[float(v) for v in r] for r in rows], labels)
            lp = str(m.predict([[float(v) for v in q]])[0])
            check.update(values={"prediction": lp}, agrees=lp == win)
        except Exception:  # noqa: BLE001
            pass
    return {"method": "forest", "steps": steps, "answer": {"prediction": win, "votes": dict(c)}, "check": check}


# ------------------------------------------------------------------ metrics
def metrics(text: str, kind: str = "regression") -> dict:
    head, body = parse_table(text)
    if len(head) != 2:
        raise HandError("Give two columns: actual then predicted.")
    if kind == "regression":
        y = [_num(r[0], head[0]) for r in body]
        pr = [_num(r[1], head[1]) for r in body]
        steps, m = _reg_metrics(y, pr)
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        yf, pf = [float(v) for v in y], [float(v) for v in pr]
        lib = {"MAE": mean_absolute_error(yf, pf), "MSE": mean_squared_error(yf, pf), "R2": r2_score(yf, pf) if len(set(yf)) > 1 else None}
        ok = all(abs(lib[k] - m[k]) < 1e-9 for k in ("MAE", "MSE")) and (lib["R2"] is None or abs(lib["R2"] - m["R2"]) < 1e-9)
        return {"method": "metrics", "steps": steps, "answer": m, "check": {"library": "scikit-learn.metrics", "values": lib, "agrees": ok}}
    actual = [r[0] for r in body]
    pred = [r[1] for r in body]
    labs = sorted(set(actual) | set(pred))
    pos = labs[-1] if len(labs) == 2 else None
    n = len(actual)
    acc = sum(a == b for a, b in zip(actual, pred)) / n
    cm = {(a, b): sum(1 for x, y in zip(actual, pred) if x == a and y == b) for a in labs for b in labs}
    steps = [_step("Confusion matrix", "Rows are the actual class, columns are what was predicted.", "actual \\ predicted   " + "  ".join(labs) + "\n" + "\n".join(f"{a:>10}            " + "  ".join(str(cm[(a, b)]) for b in labs) for a in labs)),
             _step("Accuracy", "Share of rows predicted correctly. Misleading when one class is rare.", f"{sum(cm[(l, l)] for l in labs)} / {n} = {_f(acc)}")]
    ans: dict = {"accuracy": acc}
    if pos:
        neg = labs[0]
        tp, fp, fn, tn = cm[(pos, pos)], cm[(neg, pos)], cm[(pos, neg)], cm[(neg, neg)]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        steps += [_step(f"Treating '{pos}' as the positive class", f"TP={tp} (said {pos}, was {pos}); FP={fp}; FN={fn}; TN={tn}."),
                  _step("Precision", "When it says positive, how often is it right?", f"TP / (TP + FP) = {tp}/{tp + fp} = {_f(prec)}"),
                  _step("Recall", "Of the real positives, how many did it find?", f"TP / (TP + FN) = {tp}/{tp + fn} = {_f(rec)}"),
                  _step("F1", "One number balancing precision and recall.", f"2 x P x R / (P + R) = {_f(f1)}")]
        ans.update(precision=prec, recall=rec, f1=f1)
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        lib = {"accuracy": accuracy_score(actual, pred), "precision": precision_score(actual, pred, pos_label=pos, zero_division=0), "recall": recall_score(actual, pred, pos_label=pos, zero_division=0), "f1": f1_score(actual, pred, pos_label=pos, zero_division=0)}
        ok = all(abs(lib[k] - ans[k]) < 1e-9 for k in lib)
    else:
        lib, ok = {"accuracy": acc}, True
        steps.append(_step("More than two classes", "Precision and recall are worked out per class; this lab shows the confusion matrix and accuracy."))
    return {"method": "metrics", "steps": steps, "answer": ans, "check": {"library": "scikit-learn.metrics", "values": lib, "agrees": ok}}


PRESETS = [
    {"id": "taxi", "method": "linear", "title": "Taxi fare (from the course, checked)", "data": "distance_km,fare\n2,100\n4,150\n6,200\n8,250\n10,300", "query": "15", "note": "Slope 25, intercept 50, so 15 km costs 425."},
    {"id": "lathe", "method": "multiple", "title": "Lathe cutting force (4 rows, solvable)", "data": "speed,feed,depth,force\n100,0.2,1.0,230\n120,0.25,1.2,285\n140,0.3,1.5,345\n150,0.35,1.4,365", "query": "160,0.4,1.6",
     "note": "Four rows give four equations for four unknowns, so there is exactly one answer: force = 2*speed + 100*feed + 50*depth - 40, so the new row gives 400."},
    {"id": "lathe3", "method": "multiple", "title": "Why 3 rows can't fit 4 unknowns", "data": "speed,feed,depth,force\n100,0.2,1.0,200\n120,0.25,1.2,250\n140,0.3,1.5,300", "query": "", "note": "This is the course's original example. Run it to see why it has no single answer."},
    {"id": "knn", "method": "knn", "title": "Is the part good or bad? (KNN)", "data": "temp,pressure,result\n70,30,good\n72,32,good\n75,35,good\n90,50,bad\n92,55,bad\n95,52,bad", "query": "88,48", "params": {"k": 3, "task": "classification", "scale": False}, "note": ""},
    {"id": "tree", "method": "tree", "title": "Machine fault tree", "data": "vibration,temp,fault\n2,60,no\n3,65,no\n4,70,no\n7,85,yes\n8,90,yes\n6,95,yes\n3,92,yes\n5,64,no", "query": "6,88", "params": {"criterion": "gini", "depth": 2}, "note": ""},
    {"id": "forest", "method": "forest", "title": "Random forest vote", "data": "vibration,temp,load,fault\n2,60,10,no\n3,65,12,no\n4,70,15,no\n7,85,30,yes\n8,90,35,yes\n6,95,28,yes\n3,92,14,yes\n5,64,11,no", "query": "6,88,29", "params": {"trees": 5, "seed": 1, "criterion": "gini"}, "note": ""},
    {"id": "metrics", "method": "metrics", "title": "Regression errors", "data": "actual,predicted\n200,195\n250,262\n300,290\n280,285", "query": "", "params": {"kind": "regression"}, "note": ""},
    {"id": "metrics-c", "method": "metrics", "title": "Classification scores", "data": "actual,predicted\nyes,yes\nyes,no\nno,no\nno,no\nyes,yes\nno,yes\nyes,yes", "query": "", "params": {"kind": "classification"}, "note": ""},
]


def run(method: str, data: str, query: str = "", params: dict | None = None) -> dict:
    params = params or {}
    if method not in METHODS:
        raise HandError("Unknown method.")
    if len(data or "") > 20000 or len(query or "") > 500:
        raise HandError("That is too much text for working by hand.")
    if method in ("tfidf", "bayes", "ngram", "edit", "nn", "gd", "perceptron"):
        from app.services import nlp_dl_by_hand
        return nlp_dl_by_hand.run(method, data, query, params)
    if method == "linear":
        return linear(data, query)
    if method == "multiple":
        return multiple(data, query)
    if method == "knn":
        return knn(data, query, int(params.get("k", 3)), str(params.get("task", "classification")), bool(params.get("scale", False)))
    if method == "tree":
        return tree(data, query, str(params.get("criterion", "gini")), int(params.get("depth", 2)))
    if method == "forest":
        return forest(data, query, int(params.get("trees", 5)), int(params.get("seed", 1)), str(params.get("criterion", "gini")))
    return metrics(data, str(params.get("kind", "regression")))


TOOL_HAND = {"name": "ml_by_hand", "description": "Work a SMALL machine-learning problem step by step with every number shown, then check it against scikit-learn. Use it to teach, to show the working, or to verify a model by hand. "
             "method: linear (2 columns x,y), multiple (features then target), knn (features then label; query is the new row; params k, task classification|regression, scale), tree (features then class; params criterion gini|entropy, depth 1-3), "
             "forest (params trees, seed), metrics (2 columns actual,predicted; params kind regression|classification). "
             "NLP: tfidf (data = one document per line, query = search phrase), bayes (data = label,text rows, query = message), ngram (data = sentences, query = phrase), edit (data = first word, query = second word). "
             "Deep learning: nn (data = x1,x2,target row; params wh[4], bh[2], wo[2], bo, lr, steps), gd (x,y rows; params lr, steps), perceptron (x1,x2,class rows; params lr, epochs). "
             "data is text/CSV, max 60 rows and 8 features; query is one comma separated row (or a phrase). Nothing is saved.",
             "input_schema": {"type": "object", "properties": {"method": {"type": "string", "enum": list(METHODS)}, "data": {"type": "string"}, "query": {"type": "string"}, "params": {"type": "object"}}, "required": ["method", "data"]}}


def tool_result(args: dict) -> str:
    """Compact JSON for an agent: the answer, the library check and the steps (trimmed)."""
    import json
    r = run(str(args.get("method", "")), str(args.get("data", "")), str(args.get("query", "")), args.get("params") if isinstance(args.get("params"), dict) else {})
    steps = [{"title": s["title"], "detail": s["detail"][:300], "math": s["math"][:700]} for s in r["steps"]]
    return json.dumps({"method": r["method"], "answer": r["answer"], "check": {k: r["check"].get(k) for k in ("library", "values", "agrees")}, "steps": steps}, default=str)[:9000]


def all_presets() -> list[dict]:
    from app.services import nlp_dl_by_hand
    return PRESETS + nlp_dl_by_hand.PRESETS
