"""ML, NLP and deep-learning tools: a labeling workbench with an honest text classifier, an extraction tester, and an experiment tracker.

The classifier is TF-IDF plus logistic regression, scored by cross-validation against the 'always guess the most common label' baseline. It tells you where it fails, and
sends low-confidence texts to a human. It is a sound first model for sorting tickets, reviews and emails; it is not a language model and does not understand meaning."""
from __future__ import annotations

import csv
import io
import json
import math
import re
import time
import uuid

from app.services import biz_models, state, workspaces
from app.services.db import get_cursor


class TextError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key(name: str) -> str:
    return f"textlab:{name}:{workspaces.active()}"


def _load(name: str) -> dict:
    raw = state.kv_get(_key(name))
    d = json.loads(raw) if raw else {}
    d.setdefault("sets", {}) if name == "sets" else d.setdefault("runs", [])
    return d


def _save(name: str, d: dict) -> None:
    state.kv_set(_key(name), json.dumps(d))


def _t(v, n) -> str:
    return re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v or "")).strip()[:n]


# ------------------------------------------------------------------ labeling sets
def set_create(name: str, labels: list[str]) -> dict:
    nm = _t(name, 60)
    ls = list(dict.fromkeys(_t(x, 40) for x in labels or [] if _t(x, 40)))
    if not nm:
        raise TextError("Name the set.")
    if not 2 <= len(ls) <= 20:
        raise TextError("Give between 2 and 20 labels (the categories).")
    d = _load("sets")
    if nm in d["sets"]:
        raise TextError("A set with that name already exists.")
    d["sets"][nm] = {"labels": ls, "examples": [], "next": 1}
    _save("sets", d)
    return {"name": nm, "labels": ls}


def set_list() -> list[dict]:
    out = []
    for n, s in _load("sets")["sets"].items():
        cnt = {l: 0 for l in s["labels"]}
        for e in s["examples"]:
            cnt[e["label"]] = cnt.get(e["label"], 0) + 1
        out.append({"name": n, "labels": s["labels"], "examples": len(s["examples"]), "per_label": cnt})
    return out


def set_get(name: str, limit: int = 200) -> dict:
    s = _load("sets")["sets"].get(name)
    if not s:
        raise TextError("No set with that name.", 404)
    return {"name": name, "labels": s["labels"], "examples": s["examples"][-limit:], "total": len(s["examples"])}


def set_delete(name: str) -> dict:
    d = _load("sets")
    if name not in d["sets"]:
        raise TextError("No set with that name.", 404)
    d["sets"].pop(name)
    _save("sets", d)
    return {"deleted": name}


def add_examples(name: str, rows: list[dict]) -> dict:
    d = _load("sets")
    s = d["sets"].get(name)
    if not s:
        raise TextError("No set with that name.", 404)
    added = skipped = 0
    for r in rows[:2000]:
        tx, lb = _t(r.get("text"), 2000), _t(r.get("label"), 40)
        if not tx or lb not in s["labels"]:
            skipped += 1
            continue
        s["examples"].append({"id": s["next"], "text": tx, "label": lb})
        s["next"] += 1
        added += 1
    s["examples"] = s["examples"][-5000:]
    _save("sets", d)
    return {"added": added, "skipped": skipped, "total": len(s["examples"]), "note": "Skipped rows had no text or a label that is not in the set." if skipped else ""}


def add_from_text(name: str, text: str) -> dict:
    """One example per line: label, a tab or comma, then the text."""
    rows = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        parts = re.split(r"\t|,", line, maxsplit=1)
        if len(parts) == 2:
            rows.append({"label": parts[0].strip(), "text": parts[1].strip()})
    if not rows:
        raise TextError("Use one example per line: label, then a comma or tab, then the text.")
    return add_examples(name, rows)


def add_from_table(name: str, source: str, text_col: str, label_col: str, limit: int = 1000) -> dict:
    try:
        t, _ = biz_models._table_for(source)
    except biz_models.ModelError as e:
        raise TextError(str(e), getattr(e, "status", 400)) from None
    for c in (text_col, label_col):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", c or ""):
            raise TextError("Pick a column from the table.")
    with get_cursor() as cur:
        have = {r[0] for r in cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = ? AND table_schema='main'", [t]).fetchall()}
        if text_col not in have or label_col not in have:
            raise TextError("That column is not in the table.")
        rows = cur.execute(f'SELECT "{text_col}", "{label_col}" FROM {t} WHERE "{text_col}" IS NOT NULL AND "{label_col}" IS NOT NULL LIMIT {int(min(limit, 5000))}').fetchall()
    return add_examples(name, [{"text": a, "label": str(b)} for a, b in rows])


def delete_example(name: str, eid: int) -> dict:
    d = _load("sets")
    s = d["sets"].get(name)
    if not s:
        raise TextError("No set with that name.", 404)
    s["examples"] = [e for e in s["examples"] if e["id"] != eid]
    _save("sets", d)
    return {"deleted": eid}


# ------------------------------------------------------------------ the classifier
def _pipe():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    return Pipeline([("tf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1, sublinear_tf=True)), ("lr", LogisticRegression(max_iter=1000, class_weight="balanced"))])


def _data(name: str):
    s = set_get(name, 10**6)
    ex = s["examples"]
    from collections import Counter
    cnt = Counter(e["label"] for e in ex)
    usable = [l for l, n in cnt.items() if n >= 3]
    if len(usable) < 2:
        raise TextError(f"Need at least 2 labels with 3 or more examples each. Right now: " + ", ".join(f"{l} {n}" for l, n in cnt.most_common()) + ".")
    ex = [e for e in ex if e["label"] in usable]
    return [e["text"] for e in ex], [e["label"] for e in ex], cnt, [l for l in s["labels"] if l not in usable and cnt.get(l, 0) < 3]


def train_report(name: str) -> dict:
    import numpy as np
    from sklearn.dummy import DummyClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    X, y, cnt, thin = _data(name)
    k = max(2, min(5, min(cnt[l] for l in set(y))))
    cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=0)
    pred = cross_val_predict(_pipe(), X, y, cv=cv)
    base = cross_val_predict(DummyClassifier(strategy="most_frequent"), X, y, cv=cv)
    acc, bacc = accuracy_score(y, pred), accuracy_score(y, base)
    f1, bf1 = f1_score(y, pred, average="macro"), f1_score(y, base, average="macro")
    labs = sorted(set(y))
    p, r, f, sup = precision_recall_fscore_support(y, pred, labels=labs, zero_division=0)
    per = [{"label": l, "examples": int(s), "precision": round(float(a), 2), "recall": round(float(b), 2), "f1": round(float(c), 2)} for l, a, b, c, s in zip(labs, p, r, f, sup)]
    fails = [{"text": X[i][:200], "actual": y[i], "predicted": pred[i]} for i in range(len(y)) if pred[i] != y[i]][:12]
    conf: dict[str, dict[str, int]] = {a: {b: 0 for b in labs} for a in labs}
    for a, b in zip(y, pred):
        conf[a][b] += 1
    full = _pipe().fit(X, y)
    vocab = np.array(full.named_steps["tf"].get_feature_names_out())
    coef = full.named_steps["lr"].coef_
    classes = list(full.named_steps["lr"].classes_)
    top = {}
    for i, c in enumerate(classes if len(classes) > 2 else classes[-1:]):
        row = coef[i] if len(classes) > 2 else coef[0]
        top[c] = [str(w) for w in vocab[np.argsort(row)[::-1][:8]]]
        if len(classes) == 2:
            top[classes[0]] = [str(w) for w in vocab[np.argsort(-row)[::-1][:8]]]
    useful = (f1 - bf1) >= 0.1 and acc > bacc
    small = len(y) < 60
    verdict = (f"On texts it had not seen, it got {acc * 100:.0f}% right (macro F1 {f1:.2f}) against {bacc * 100:.0f}% for always guessing '{max(set(y), key=y.count)}'. It beats the simple guess, so it is a usable first sorter."
               if useful else f"It got {acc * 100:.0f}% right against {bacc * 100:.0f}% for guessing the most common label. That is not a meaningful improvement: add more examples or make the labels easier to tell apart.")
    run = {"id": uuid.uuid4().hex[:8], "at": time.strftime("%Y-%m-%d %H:%M"), "set": name, "examples": len(y), "accuracy": round(acc, 3), "macro_f1": round(f1, 3)}
    h = _load("runs")
    h["runs"] = (h["runs"] + [run])[-50:]
    _save("runs", h)
    return {"set": name, "examples": len(y), "folds": k, "accuracy": round(acc, 3), "macro_f1": round(f1, 3), "baseline_accuracy": round(bacc, 3), "baseline_macro_f1": round(bf1, 3), "useful": bool(useful), "verdict": verdict,
            "per_label": per, "confusion": conf, "failures": fails, "top_words": top, "labels_too_thin": thin, "history": [r for r in h["runs"] if r["set"] == name][-8:],
            "caution": ("Only %d examples: the score is rough and can change a lot with more data. " % len(y) if small else "") + "Scores come from cross-validation (each text is scored by a model that never saw it). New kinds of text can still fail. Review the failures above and add examples like them."}


def classify(name: str, texts: list[str], min_confidence: float = 0.6) -> dict:
    X, y, _, _ = _data(name)
    m = _pipe().fit(X, y)
    ts = [_t(t, 2000) for t in texts[:200] if _t(t, 2000)]
    if not ts:
        raise TextError("Give at least one text to sort.")
    pr = m.predict_proba(ts)
    out = []
    for t, row in zip(ts, pr):
        i = int(row.argmax())
        conf = float(row[i])
        out.append({"text": t[:200], "label": m.classes_[i], "confidence": round(conf, 2), "needs_human": conf < min_confidence})
    return {"results": out, "needs_human": sum(r["needs_human"] for r in out), "note": f"Anything under {min_confidence:.0%} confidence is marked for a person to check. Confidence is the model's own estimate, not a guarantee."}


# ------------------------------------------------------------------ extraction tester
def _safe_pattern(p: str) -> re.Pattern:
    if not p or len(p) > 200:
        raise TextError("Each pattern must be 1 to 200 characters.")
    if re.search(r"\([^)]*[+*]\)[+*{]", p) or re.search(r"(\.\*){3,}", p):
        raise TextError("That pattern could run forever on some texts. Make it simpler.")
    try:
        return re.compile(p, re.I | re.M)
    except re.error as e:
        raise TextError(f"Bad pattern: {e}.") from None


def extract_test(rules: list[dict], docs: list[dict]) -> dict:
    if not rules or not docs:
        raise TextError("Give at least one field rule and one sample document.")
    comp = {}
    for r in rules[:30]:
        f = _t(r.get("field"), 40)
        if not f:
            raise TextError("Every rule needs a field name.")
        comp[f] = _safe_pattern(str(r.get("pattern") or ""))
    per = {f: {"correct": 0, "wrong": 0, "missed": 0, "expected": 0, "extra": 0} for f in comp}
    detail = []
    for i, d in enumerate(docs[:100], 1):
        text, exp = str(d.get("text") or "")[:20000], d.get("expected") or {}
        row = {"doc": i, "fields": []}
        for f, rx in comp.items():
            m = rx.search(text)
            got = (m.group(1) if m and m.groups() else m.group(0) if m else None)
            got = got.strip() if got else None
            want = str(exp[f]).strip() if exp.get(f) not in (None, "") else None
            if want is not None:
                per[f]["expected"] += 1
            if want is None and got is None:
                state_ = "ok (absent)"
            elif want is None:
                per[f]["extra"] += 1
                state_ = "found but none expected"
            elif got is None:
                per[f]["missed"] += 1
                state_ = "missed"
            elif got.lower() == want.lower():
                per[f]["correct"] += 1
                state_ = "correct"
            else:
                per[f]["wrong"] += 1
                state_ = "wrong"
            row["fields"].append({"field": f, "expected": want, "found": got, "state": state_})
        detail.append(row)
    summary = []
    for f, c in per.items():
        e = c["expected"]
        found = c["correct"] + c["wrong"] + c["extra"]
        summary.append({"field": f, **c, "recall_pct": round(100 * c["correct"] / e, 1) if e else None, "precision_pct": round(100 * c["correct"] / found, 1) if found else None})
    return {"summary": summary, "documents": detail, "caution": "Patterns that work on your samples can fail on new layouts. Test with at least 20 varied real documents, and keep a person checking fields that matter (amounts, dates, IDs)."}


# ------------------------------------------------------------------ experiment tracker
def exp_log(name: str, params: dict, metrics: dict, notes: str = "", dataset: str = "") -> dict:
    nm = _t(name, 80)
    if not nm:
        raise TextError("Name the experiment.")
    clean_m = {}
    for k, v in (metrics or {}).items():
        try:
            clean_m[_t(k, 30)] = float(v)
        except (TypeError, ValueError):
            raise TextError(f"Metric '{k}' must be a number.") from None
    if not clean_m:
        raise TextError("Add at least one metric (like accuracy 0.84).")
    d = _load("exps")
    d.setdefault("items", [])
    d["items"].append({"id": uuid.uuid4().hex[:8], "name": nm, "params": {_t(k, 30): _t(v, 80) for k, v in (params or {}).items()}, "metrics": clean_m, "notes": _t(notes, 400), "dataset": _t(dataset, 80), "at": time.strftime("%Y-%m-%d %H:%M")})
    d["items"] = d["items"][-500:]
    _save("exps", d)
    return {"id": d["items"][-1]["id"]}


def _exps() -> dict:
    raw = state.kv_get(_key("exps"))
    d = json.loads(raw) if raw else {}
    d.setdefault("items", [])
    return d


def exp_list(sort_by: str = "", higher_is_better: bool = True) -> list[dict]:
    items = list(reversed(_exps()["items"]))
    if sort_by:
        items = sorted(items, key=lambda e: (e["metrics"].get(sort_by) is None, -(e["metrics"].get(sort_by) or 0) if higher_is_better else (e["metrics"].get(sort_by) or 0)))
    return items


def exp_delete(eid: str) -> dict:
    d = _exps()
    d["items"] = [e for e in d["items"] if e["id"] != eid]
    _save("exps", d)
    return {"deleted": eid}


def exp_csv() -> str:
    items = _exps()["items"]
    pk = sorted({k for e in items for k in e["params"]})
    mk = sorted({k for e in items for k in e["metrics"]})
    b = io.StringIO()
    w = csv.writer(b)
    w.writerow(["id", "at", "name", "dataset"] + [f"param:{k}" for k in pk] + [f"metric:{k}" for k in mk] + ["notes"])
    for e in items:
        w.writerow([e["id"], e["at"], e["name"], e["dataset"]] + [e["params"].get(k, "") for k in pk] + [e["metrics"].get(k, "") for k in mk] + [e["notes"]])
    return b.getvalue()
