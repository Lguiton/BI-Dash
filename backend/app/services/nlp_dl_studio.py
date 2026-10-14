"""NLP and Deep Learning workspace: type what you need, the right agent plans the job, runs it on your data and reports honestly.

Language agent:  classify text, sentiment, similar-case search, topics, keywords, entities, summaries.
Deep-learning agent:  neural nets on a table, neural nets on text, anomaly detection (autoencoder), forecasting with lags, and a how-it-learns demo.

Real scikit-learn models (TF-IDF, logistic regression, naive Bayes, KMeans, MLP neural networks, IsolationForest).
Honest limits: no GPU, no PyTorch, no pretrained language models, so no image/audio/translation work and no true "understanding" of meaning.
Every model is compared with a do-nothing baseline on rows it never saw; if it can't beat the baseline it says so. Nothing is saved or sent anywhere.
"""
from __future__ import annotations

import io
import re
import time
import warnings

import numpy as np
import pandas as pd

from app.services import nlp_lab

MAX_ROWS = 20000
MAX_BYTES = 3_000_000
MIN_CLASSIFY = 30


class StudioError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


NLP_TASKS = {
    "classify": ("classify categorize categorise tag label sort route triage predict category bucket", "Sort each message into a category"),
    "sentiment": ("sentiment tone mood feeling happy angry upset satisfied complaints reviews", "Read the mood of the text"),
    "similar": ("similar like match duplicate related lookup nearest resembles same case", "Find the most similar past cases"),
    "topics": ("topic topics theme themes cluster group saying about discuss", "Find the main themes"),
    "keywords": ("keyword keywords phrases common frequent words terms popular", "Pull out the key words and phrases"),
    "entities": ("entities entity extract names emails phone dates money amounts people places", "Extract names, emails, phones, dates and money"),
    "summary": ("summarize summarise summary digest shorten tldr gist", "Summarise the text"),
}
DL_TASKS = {
    "anomaly": ("anomaly anomalies unusual outlier outliers fraud weird strange suspicious autoencoder", "Find unusual rows with an autoencoder"),
    "forecast_net": ("forecast future next predict ahead project demand sales lags", "Forecast with a neural network and compare"),
    "demo": ("how xor learn learns learning demo explain understand teach", "Watch a tiny network learn"),
    "text_net": ("text language message mlp", "Train a neural network on text"),
    "tabular_net": ("predict network mlp regression classification table", "Train a neural network on a table"),
}
DL_WORDS = {"unusual", "weird", "strange", "suspicious", "fraud", "neural", "deep", "autoencoder", "mlp", "perceptron", "backprop", "deep-learning", "anomaly", "anomalies", "outlier", "outliers", "forecast", "xor"}
TEXT_HINT = {"text", "message", "messages", "notes", "ticket", "tickets", "review", "reviews", "comment", "comments", "email", "emails", "feedback", "description", "sentiment", "topic", "topics", "summarize", "summarise", "keywords", "nlp", "language", "words"}


def _norm(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _words(s: str) -> list[str]:
    return [_norm(w) for w in re.findall(r"[a-z0-9']+", (s or "").lower())]


def route(prompt: str, has_text: bool = False, has_table: bool = False) -> dict:
    """Decide agent and task from a plain sentence. Rules, not a language model, so it works offline and is predictable."""
    w = set(_words(prompt))
    DLW = {_norm(x) for x in DL_WORDS}
    TXT = {_norm(x) for x in TEXT_HINT}
    if not w:
        raise StudioError("Type what you need, for example: 'sort these tickets by category' or 'find unusual rows'.")
    dl = len(w & DLW) + (1 if "deep" in w and "learning" in w else 0)
    nlp = len(w & TXT)
    agent = "dl" if dl > nlp or (dl and not nlp) or (w & {"neural", "deep", "mlp", "autoencoder", "perceptron"}) else "nlp"
    if dl == nlp == 0:
        agent = "nlp" if has_text or not has_table else "dl"
    table = NLP_TASKS if agent == "nlp" else DL_TASKS
    best, score = None, 0
    for t, (keys, _d) in table.items():
        s = len(w & {_norm(k) for k in keys.split()})
        if s > score:
            best, score = t, s
    if agent == "dl" and best == "tabular_net" and (w & {"text", "message", "ticket", "review", "note", "email", "comment"}):
        best = "text_net"
    if best is None:
        best = "keywords" if agent == "nlp" and has_text else ("classify" if agent == "nlp" else ("tabular_net" if has_table else "demo"))
    return {"agent": agent, "task": best, "what": table[best][1]}


# ---------------------------------------------------------------- data


def parse(data: str, source: str = "") -> pd.DataFrame:
    """CSV text (with a header row) or plain lines (one document each). Or a dashboard table by name."""
    if source:
        from app.services import biz_models
        try:
            df, _ = biz_models.load(source)
        except biz_models.ModelError as e:
            raise StudioError(e.message, e.status) from e
        return df.head(MAX_ROWS)
    t = (data or "").lstrip("﻿")
    if not t.strip():
        raise StudioError("Paste some data first: either a CSV with a header row, or one text per line.")
    if len(t.encode("utf-8", "ignore")) > MAX_BYTES:
        raise StudioError(f"That's more than {MAX_BYTES // 1_000_000} MB. Send a smaller sample.")
    lines = [ln for ln in t.splitlines() if ln.strip()]
    head = lines[0]
    if len(lines) > 1 and "," in head and not head.rstrip().endswith((".", "?", "!")):
        try:
            df = pd.read_csv(io.StringIO(t), nrows=MAX_ROWS, skipinitialspace=True)
            if df.shape[1] >= 2:
                return df
        except Exception:  # noqa: BLE001
            pass
    return pd.DataFrame({"text": [ln.strip() for ln in lines[:MAX_ROWS]]})


def _text_col(df: pd.DataFrame, want: str = "") -> str:
    if want:
        if want not in df.columns:
            raise StudioError(f"There's no column called '{want}'. Columns: {', '.join(map(str, df.columns))}.")
        return want
    best, bl = None, 0.0
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith("str"):
            s = df[c].dropna().astype(str)
            if len(s) and s.nunique() / len(s) > 0.3 and s.str.len().mean() > bl and s.str.len().mean() >= 12:
                best, bl = c, float(s.str.len().mean())
    if best is None:
        raise StudioError("I can't find a column of free text (sentences). Name it, or paste one text per line.")
    return best


def _label_col(df: pd.DataFrame, text: str, want: str = "", prompt: str = "") -> str | None:
    if want:
        if want not in df.columns:
            raise StudioError(f"There's no column called '{want}'.")
        return want
    low = (prompt or "").lower()
    cands = [c for c in df.columns if c != text and 2 <= df[c].nunique() <= 12]
    for c in cands:
        if str(c).lower().replace("_", " ") in low:
            return c
    cands = [c for c in cands if not pd.api.types.is_float_dtype(df[c])]
    return cands[0] if cands else None


def _clean(df: pd.DataFrame, text: str) -> pd.DataFrame:
    d = df.copy()
    d[text] = d[text].astype(str).str.strip()
    d = d[d[text].str.len() > 2].reset_index(drop=True)
    if len(d) < 3:
        raise StudioError("Fewer than 3 usable text rows.")
    return d


def _r(x, n=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def _out(agent: str, task: str, plan: list[dict], findings: list[str], tables: list[dict] | None = None, caveats: list[str] | None = None, charts: list[dict] | None = None, nxt: list[str] | None = None, extra: dict | None = None) -> dict:
    return {"agent": agent, "task": task, "plan": plan, "findings": findings, "tables": tables or [], "charts": charts or [], "caveats": caveats or [], "next": nxt or [], **(extra or {})}


def _tab(title, cols, rows):
    return {"title": title, "columns": cols, "rows": rows}


# ---------------------------------------------------------------- language agent


def _vec(docs, ngram=(1, 2), min_df=2):
    from sklearn.feature_extraction.text import TfidfVectorizer
    return TfidfVectorizer(ngram_range=ngram, min_df=min_df if len(docs) >= 20 else 1, sublinear_tf=True, stop_words="english", max_features=20000)


def _split(n, y=None, seed=42):
    from sklearn.model_selection import train_test_split
    idx = np.arange(n)
    try:
        return train_test_split(idx, test_size=0.25, random_state=seed, stratify=y)
    except ValueError:
        return train_test_split(idx, test_size=0.25, random_state=seed)


def nlp_classify(df, text, label, query="", deep=False) -> dict:
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.naive_bayes import ComplementNB
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import LinearSVC
    if not label:
        raise StudioError("To classify I need a column of known categories to learn from (2 to 12 different values). Name it, or add it to your data.")
    d = _clean(df.dropna(subset=[label]), text)
    d[label] = d[label].astype(str)
    vc = d[label].value_counts()
    keep = vc[vc >= 4].index
    notes = []
    if len(keep) < len(vc):
        notes.append(f"Dropped categories with fewer than 4 rows: {', '.join(vc[vc < 4].index[:5])}.")
        d = d[d[label].isin(keep)].reset_index(drop=True)
    if d[label].nunique() < 2 or len(d) < MIN_CLASSIFY:
        raise StudioError(f"Need at least {MIN_CLASSIFY} labelled texts across 2 or more categories to learn from; have {len(d)}.")
    tr, te = _split(len(d), d[label])
    Xtr, Xte, ytr, yte = d[text].iloc[tr], d[text].iloc[te], d[label].iloc[tr], d[label].iloc[te]
    balanced = float(ytr.value_counts(normalize=True).min()) < 0.25
    models = {"Baseline (always the most common)": DummyClassifier(strategy="most_frequent"),
              "Logistic regression": LogisticRegression(max_iter=1000, C=5, class_weight="balanced" if balanced else None),
              "Linear SVM": LinearSVC(C=0.7, class_weight="balanced" if balanced else None),
              "Naive Bayes": ComplementNB(alpha=0.3)}
    if deep:
        models["Neural network (MLP)"] = MLPClassifier(hidden_layer_sizes=(64,), alpha=1e-3, early_stopping=True, max_iter=300, random_state=1)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=1) if ytr.value_counts().min() >= 3 else 3
    rows, fitted = [], {}
    for name, m in models.items():
        pipe = make_pipeline(_vec(Xtr), m)
        try:
            cvs = cross_val_score(pipe, Xtr, ytr, cv=cv, scoring="f1_macro")
            pipe.fit(Xtr, ytr)
            pr = pipe.predict(Xte)
        except Exception:  # noqa: BLE001
            continue
        fitted[name] = pipe
        rows.append([name, _r(cvs.mean()), _r(accuracy_score(yte, pr)), _r(f1_score(yte, pr, average="macro"))])
    base = next(r for r in rows if r[0].startswith("Baseline"))
    real = sorted([r for r in rows if not r[0].startswith("Baseline")], key=lambda r: -r[1])
    best = real[0]
    useful = best[3] - base[3] >= 0.08
    pipe = fitted[best[0]]
    pr = pipe.predict(Xte)
    findings = [f"Best model: {best[0]}. On {len(te)} texts it had never seen it got {best[2] * 100:.0f}% right (macro F1 {best[3]:.2f}), against {base[2] * 100:.0f}% for always guessing '{ytr.mode().iloc[0]}'."
                if useful else f"No model clearly beat guessing '{ytr.mode().iloc[0]}' every time ({base[2] * 100:.0f}% right). The wording doesn't separate these categories well enough to rely on."]
    labels = sorted(d[label].unique())
    tables = [_tab("Leaderboard (ranked by cross-validation on training rows only)", ["Model", "CV macro-F1", "Test accuracy", "Test macro-F1"], sorted(rows, key=lambda r: -r[1]))]
    cm = confusion_matrix(yte, pr, labels=labels)
    tables.append(_tab("Confusion matrix (rows = real, columns = predicted)", ["real \\ predicted"] + labels, [[labels[i]] + [int(v) for v in cm[i]] for i in range(len(labels))]))
    lr = fitted.get("Logistic regression")
    if lr is not None and useful:
        vec, clf = lr.steps[0][1], lr.steps[1][1]
        names = np.array(vec.get_feature_names_out())
        coef = clf.coef_ if clf.coef_.shape[0] > 1 else np.vstack([-clf.coef_[0], clf.coef_[0]])
        tables.append(_tab("Words that point to each category", ["Category", "Strongest words"], [[str(c), ", ".join(names[np.argsort(-coef[i])[:8]])] for i, c in enumerate(clf.classes_)]))
    wrong = np.where(pr != yte.to_numpy())[0][:6]
    if len(wrong):
        tables.append(_tab("Examples it got wrong", ["Text", "Real", "Predicted"], [[Xte.iloc[i][:140], yte.iloc[i], pr[i]] for i in wrong]))
    if query.strip():
        q = pipe.predict([query])[0]
        extra = {}
        if hasattr(pipe, "predict_proba"):
            p = pipe.predict_proba([query])[0]
            extra = {str(c): _r(v) for c, v in zip(pipe.classes_, p)}
        findings.append(f"Your sample text goes to: {q}." + (f" Chances: {', '.join(f'{k} {v * 100:.0f}%' for k, v in sorted(extra.items(), key=lambda kv: -kv[1])[:3])}." if extra else ""))
    notes.append(f"{len(Xte)} test texts is a small test, so treat the percentages as rough." if len(Xte) < 100 else "")
    plan = [{"who": "Planner", "did": f"Chose to classify '{text}' into '{label}' ({len(labels)} categories, {len(d)} rows)."},
            {"who": "Data checker", "did": f"Held out 25% as a test the models never see. {'Re-weighted rare categories. ' if balanced else ''}Cleaned the text and turned it into TF-IDF word and word-pair weights."},
            {"who": "Modeller", "did": f"Tried {len(rows) - 1} models plus a do-nothing baseline; ranked them by 3-fold cross-validation."},
            {"who": "Reviewer", "did": "Compared the best with the baseline on the held-out texts" + (" and found it useful." if useful else " and found it NOT clearly better.")}]
    return _out("nlp", "classify", plan, findings, tables, [n for n in notes if n] + ["Learns word patterns only: it can't read sarcasm or context, and it will repeat any mistakes in your labels."],
                nxt=["Add more labelled examples for the categories it confuses.", "Use 'find similar cases' to look up past tickets for a new one."])


def nlp_similar(df, text, query) -> dict:
    from sklearn.metrics.pairwise import cosine_similarity
    if not query.strip():
        raise StudioError("Add the text to look up, e.g. 'find cases similar to: printer shows paper jam after update'.")
    d = _clean(df, text)
    v = _vec(d[text], min_df=1)
    M = v.fit_transform(d[text])
    s = cosine_similarity(v.transform([query]), M).ravel()
    order = np.argsort(-s)[:8]
    others = [c for c in d.columns if c != text][:3]
    rows = [[_r(s[i], 3), d[text].iloc[i][:160]] + [str(d[c].iloc[i])[:30] for c in others] for i in order if s[i] > 0]
    f = [f"Found {len(rows)} similar texts; the closest is {rows[0][0] * 100:.0f}% similar." if rows else "Nothing in your data shares meaningful words with that text."]
    return _out("nlp", "similar", [{"who": "Planner", "did": f"Searched {len(d)} texts for the closest match to your sample."}, {"who": "Modeller", "did": "Weighted words by how rare they are (TF-IDF) and ranked by cosine similarity."}],
                f, [_tab("Closest matches", ["Similarity", "Text"] + [str(c) for c in others], rows)] if rows else [], ["Matches shared wording, not meaning: 'laptop won't start' and 'computer dead' may score low."])


def nlp_topics(df, text) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    d = _clean(df, text)
    if len(d) < 12:
        raise StudioError("Need at least 12 texts to find themes.")
    v = _vec(d[text])
    X = v.fit_transform(d[text])
    terms = np.array(v.get_feature_names_out())
    best, bs = None, -1
    for k in range(2, min(7, len(d) // 4) + 1):
        km = KMeans(n_clusters=k, n_init=5, random_state=1).fit(X)
        sc = silhouette_score(X, km.labels_, sample_size=min(2000, len(d)), random_state=1)
        if sc > bs:
            best, bs = km, sc
    rows = []
    for i in range(best.n_clusters):
        top = terms[np.argsort(-best.cluster_centers_[i])[:6]]
        members = np.where(best.labels_ == i)[0]
        rows.append([f"Theme {i + 1}", int(len(members)), f"{len(members) / len(d) * 100:.0f}%", ", ".join(top), d[text].iloc[members[0]][:120]])
    rows.sort(key=lambda r: -r[1])
    weak = bs < 0.05
    f = [f"The texts split into {best.n_clusters} themes; the biggest is '{rows[0][3].split(', ')[0]}' ({rows[0][2]} of rows)." if not weak else "The themes overlap heavily (low separation), so treat them as loose groupings."]
    return _out("nlp", "topics", [{"who": "Planner", "did": f"Grouping {len(d)} texts by shared wording."}, {"who": "Modeller", "did": f"Tried 2 to {min(7, len(d) // 4)} groups with KMeans on TF-IDF and kept the best separated (silhouette {bs:.2f})."}],
                f, [_tab("Themes", ["Theme", "Texts", "Share", "Defining words", "Example"], rows)], ["Themes are statistical groupings of words; name them yourself after reading the examples."])


def nlp_keywords(df, text) -> dict:
    d = _clean(df, text)
    v = _vec(d[text], ngram=(1, 2), min_df=2)
    X = v.fit_transform(d[text])
    terms = np.array(v.get_feature_names_out())
    w = np.asarray(X.sum(axis=0)).ravel()
    cnt = np.asarray((X > 0).sum(axis=0)).ravel()
    order = np.argsort(-w)[:20]
    rows = [[terms[i], int(cnt[i]), f"{cnt[i] / len(d) * 100:.0f}%"] for i in order]
    return _out("nlp", "keywords", [{"who": "Planner", "did": f"Counted meaningful words and word pairs across {len(d)} texts (common filler words removed)."}],
                [f"Most important terms: {', '.join(r[0] for r in rows[:6])}."], [_tab("Top terms", ["Term", "In texts", "Share"], rows)])


def nlp_sentiment(df, text, label=None) -> dict:
    d = _clean(df, text).head(3000)
    sc = []
    for t in d[text]:
        try:
            sc.append(nlp_lab.sentiment(t[:2900])["score"])
        except nlp_lab.NlpError:
            sc.append(0.0)
    d["_s"] = sc
    d["_l"] = np.where(d["_s"] > 0.5, "positive", np.where(d["_s"] < -0.5, "negative", "neutral"))
    dist = d["_l"].value_counts()
    rows = [[k, int(dist.get(k, 0)), f"{dist.get(k, 0) / len(d) * 100:.0f}%"] for k in ("positive", "neutral", "negative")]
    tables = [_tab("Mood of the texts", ["Mood", "Texts", "Share"], rows)]
    worst = d.nsmallest(5, "_s")
    tables.append(_tab("Most negative", ["Score", "Text"], [[_r(a, 1), b[:150]] for a, b in zip(worst["_s"], worst[text])]))
    f = [f"{rows[0][2]} positive, {rows[1][2]} neutral, {rows[2][2]} negative across {len(d)} texts."]
    if label and label in d.columns and d[label].nunique() <= 12:
        g = d.groupby(label)["_s"].mean().sort_values()
        tables.append(_tab(f"Average score by {label}", [str(label), "Average score"], [[str(k), _r(v, 2)] for k, v in g.items()]))
        f.append(f"Most negative group: {g.index[0]} (average {g.iloc[0]:.1f}).")
    return _out("nlp", "sentiment", [{"who": "Planner", "did": f"Scoring {len(d)} texts."}, {"who": "Modeller", "did": "Added up word scores, flipped them after negations like 'not', scaled after 'very'."}],
                f, tables, ["A word list can't read sarcasm or industry jargon ('kill the process' is not violent). Spot-check the examples."])


def nlp_entities(df, text) -> dict:
    d = _clean(df, text).head(1000)
    found: dict[str, dict[str, int]] = {}
    for t in d[text]:
        try:
            for e in nlp_lab.entities(t[:2900])["entities"]:
                found.setdefault(e["label"], {}).setdefault(e["text"], 0)
                found[e["label"]][e["text"]] += 1
        except nlp_lab.NlpError:
            pass
    rows = [[lab, sum(v.values()), ", ".join(f"{k} ({n})" for k, n in sorted(v.items(), key=lambda kv: -kv[1])[:6])] for lab, v in sorted(found.items(), key=lambda kv: -sum(kv[1].values()))]
    return _out("nlp", "entities", [{"who": "Planner", "did": f"Scanning {len(d)} texts for emails, phones, dates, money, places and names."}],
                [f"Found {sum(r[1] for r in rows)} mentions in {len(rows)} types." if rows else "No emails, phones, dates, money, places or known names were found."],
                [_tab("What was found", ["Type", "Mentions", "Most common"], rows)] if rows else [], ["Pattern and word-list matching only: it misses names it hasn't been given."])


def nlp_summary(df, text) -> dict:
    d = _clean(df, text)
    sents = [s.strip() for t in d[text].head(500) for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 25]
    if len(sents) < 4:
        raise StudioError("Not enough full sentences to summarise.")
    v = _vec(sents, ngram=(1, 1), min_df=1)
    X = v.fit_transform(sents)
    sc = np.asarray(X.sum(axis=1)).ravel() / np.maximum(1, np.asarray((X > 0).sum(axis=1)).ravel())
    top = sorted(np.argsort(-sc)[:4])
    return _out("nlp", "summary", [{"who": "Planner", "did": f"Scored {len(sents)} sentences by how many distinctive words they carry."}],
                ["Summary: " + " ".join(sents[i] for i in top)], [], ["Extractive: it picks existing sentences; it can't rephrase or reason about them."])


# ---------------------------------------------------------------- deep-learning agent


def _numeric_frame(df: pd.DataFrame, drop: list[str] | None = None) -> pd.DataFrame:
    X = df.select_dtypes("number").drop(columns=[c for c in (drop or []) if c in df.columns], errors="ignore")
    X = X.loc[:, X.nunique() > 1].replace([np.inf, -np.inf], np.nan)
    return X.dropna(axis=1, how="all")


def dl_tabular(df, target, prompt="") -> dict:
    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
    from sklearn.model_selection import cross_val_score
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    if not target or target not in df.columns:
        raise StudioError("Which column should the network predict? Pick a target column.")
    d = df.dropna(subset=[target]).copy()
    drop = [c for c in d.columns if str(c).lower() in ("id", "key") or str(c).lower().endswith("_id")]
    y = d[target]
    reg = pd.api.types.is_numeric_dtype(y) and y.nunique() > 12
    cols = [c for c in d.columns if c != target and c not in drop and (d[c].nunique() > 1) and not (d[c].dtype == object and d[c].nunique() > 40)]
    cols = [c for c in cols if not pd.api.types.is_datetime64_any_dtype(d[c])][:40]
    if not cols:
        raise StudioError("No usable input columns.")
    if not reg:
        y = y.astype(str)
        if y.nunique() > 12 or y.value_counts().min() < 3:
            raise StudioError(f"'{target}' has too many or too rare categories to classify.")
    if len(d) < 60:
        raise StudioError(f"Neural networks need more rows than {len(d)}; get at least 60 (hundreds is better).")
    d = d.head(30000)
    y = y.loc[d.index]
    num = [c for c in cols if pd.api.types.is_numeric_dtype(d[c])]
    cat = [c for c in cols if c not in num]
    split = int(len(d) * 0.8)
    idx = np.random.default_rng(1).permutation(len(d))
    tr, te = idx[:split], idx[split:]
    X = d[cols]

    def pre():
        return ColumnTransformer([("n", Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler())]), num),
                                  ("c", Pipeline([("i", SimpleImputer(strategy="most_frequent")), ("o", OneHotEncoder(handle_unknown="ignore", min_frequency=5, sparse_output=False))]), cat)])
    mk = MLPRegressor if reg else MLPClassifier
    sizes = [(16,), (32, 16), (64, 32)]
    scoring = "neg_mean_absolute_error" if reg else "f1_macro"
    rows, fit = [], {}
    base = Pipeline([("p", pre()), ("m", DummyRegressor() if reg else DummyClassifier(strategy="most_frequent"))]).fit(X.iloc[tr], y.iloc[tr])
    for h in sizes:
        pipe = Pipeline([("p", pre()), ("m", mk(hidden_layer_sizes=h, alpha=1e-3, max_iter=400, early_stopping=True, n_iter_no_change=15, random_state=1))])
        cvs = cross_val_score(pipe, X.iloc[tr], y.iloc[tr], cv=3, scoring=scoring)
        pipe.fit(X.iloc[tr], y.iloc[tr])
        fit[h] = pipe
        rows.append((h, float(cvs.mean()) * (-1 if reg else 1), pipe))
    best = sorted(rows, key=lambda r: r[1] if reg else -r[1])[0]
    pipe = best[2]
    pr, prb = pipe.predict(X.iloc[te]), base.predict(X.iloc[te])
    yt = y.iloc[te]
    if reg:
        m, b = mean_absolute_error(yt, pr), mean_absolute_error(yt, prb)
        gain = 100 * (b - m) / b if b else 0
        useful = gain >= 5
        f = [f"The best network {best[0]} is off by {m:,.2f} on average on rows it never saw, {gain:.0f}% {'better' if gain >= 0 else 'worse'} than always guessing the average ({b:,.2f}); R² {r2_score(yt, pr):.2f}."]
        tbl = [_tab("Network sizes tried", ["Hidden layers", "CV error (MAE)"], [[str(r[0]), _r(r[1], 2)] for r in rows])]
        ext = {"mae": _r(m, 3), "baseline_mae": _r(b, 3)}
    else:
        m, b = f1_score(yt, pr, average="macro"), f1_score(yt, prb, average="macro")
        useful = m - b >= 0.08
        f = [f"The best network {best[0]} gets {accuracy_score(yt, pr) * 100:.0f}% right (macro F1 {m:.2f}) against {accuracy_score(yt, prb) * 100:.0f}% for always guessing the most common."]
        tbl = [_tab("Network sizes tried", ["Hidden layers", "CV macro-F1"], [[str(r[0]), _r(r[1], 3)] for r in rows])]
        ext = {"macro_f1": _r(m), "baseline_macro_f1": _r(b)}
    if not useful:
        f.append("It did not clearly beat guessing, so these inputs don't explain the target well. Don't rely on it.")
    charts = []
    lc = getattr(pipe.named_steps["m"], "loss_curve_", None)
    if lc:
        step = max(1, len(lc) // 60)
        charts.append({"title": "Learning curve (training loss per round: should fall then flatten)", "x": list(range(0, len(lc), step)), "y": [_r(v, 4) for v in lc[::step]]})
    try:
        imp = permutation_importance(pipe, X.iloc[te], yt, n_repeats=3, random_state=1, n_jobs=1, scoring="neg_mean_absolute_error" if reg else "f1_macro")
        o = np.argsort(-imp.importances_mean)[:6]
        if useful:
            tbl.append(_tab("Inputs that matter most (shuffle one and watch the score drop)", ["Input", "Importance"], [[cols[i], _r(imp.importances_mean[i], 4)] for i in o if imp.importances_mean[i] > 0]))
    except Exception:  # noqa: BLE001
        pass
    plan = [{"who": "Planner", "did": f"Predict '{target}' from {len(cols)} inputs ({'a number' if reg else 'a category'}); {len(d):,} rows."},
            {"who": "Data checker", "did": "Filled blanks, scaled numbers, turned words into columns, kept 20% of rows aside for testing."},
            {"who": "Modeller", "did": f"Trained {len(sizes)} network sizes ({', '.join(str(s) for s in sizes)}), stopping early when learning stalled; picked by cross-validation."},
            {"who": "Reviewer", "did": "Compared with a do-nothing baseline on the held-out rows."}]
    return _out("dl", "tabular_net", plan, f, tbl, ["Neural networks usually need lots of rows; on a few hundred rows a simpler model (the ML Studio) often wins.", "Finds patterns, not causes."], charts, extra=ext,
                nxt=["Compare against boosting and forests in the ML Studio on the same table."])


def dl_text(df, text, label) -> dict:
    r = nlp_classify(df, text, label, "", deep=True)
    r.update(agent="dl", task="text_net")
    r["plan"][2]["did"] += " The neural network (one hidden layer of 64) was one of the contenders."
    r["caveats"].insert(0, "A small network on word counts rarely beats logistic regression with a few thousand texts; the leaderboard shows whether it did here.")
    return r


def dl_anomaly(df, prompt="") -> dict:
    from sklearn.ensemble import IsolationForest
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    X = _numeric_frame(df, [c for c in df.columns if str(c).lower() in ("id", "key") or str(c).lower().endswith("_id")])
    X = X.iloc[:, :20]
    if X.shape[1] < 2:
        raise StudioError("Need at least 2 numeric columns to judge what 'unusual' means.")
    X = X.fillna(X.median()).head(30000)
    if len(X) < 50:
        raise StudioError("Need at least 50 rows.")
    Z = StandardScaler().fit_transform(X)
    k = max(2, min(8, X.shape[1] // 2))
    ae = MLPRegressor(hidden_layer_sizes=(k,), activation="relu", max_iter=600, random_state=1, early_stopping=False).fit(Z, Z)
    err = ((ae.predict(Z) - Z) ** 2).mean(axis=1)
    thr = float(np.quantile(err, 0.98))
    iso = IsolationForest(n_estimators=150, contamination=0.02, random_state=1).fit(Z)
    iso_flag = iso.predict(Z) == -1
    ae_flag = err > thr
    agree = int((ae_flag & iso_flag).sum())
    order = np.argsort(-err)[:10]
    cols = list(X.columns)[:6]
    mu, sd = X.mean(), X.std().replace(0, 1)
    rows = []
    for i in order:
        z = ((X.iloc[i] - mu) / sd).abs().sort_values(ascending=False)
        rows.append([int(i), _r(err[i], 3), "yes" if iso_flag[i] else "no", f"{z.index[0]} ({X.iloc[i][z.index[0]]:,.4g}, {z.iloc[0]:.1f} SDs from normal)"])
    ch = [{"title": "How unusual each row is (sorted; flag line at the 98th percentile)", "x": list(range(0, len(err), max(1, len(err) // 80))), "y": [_r(v, 4) for v in np.sort(err)[::-1][::max(1, len(err) // 80)]]}]
    return _out("dl", "anomaly", [{"who": "Planner", "did": f"Looking for unusual rows across {X.shape[1]} numeric columns, {len(X):,} rows."},
                                   {"who": "Modeller", "did": f"Trained an autoencoder (squeezes each row to {k} numbers and rebuilds it); rows it can't rebuild well are unusual."},
                                   {"who": "Reviewer", "did": "Cross-checked with a second method (Isolation Forest)."}],
                [f"Flagged {int(ae_flag.sum())} unusual rows; {agree} also flagged by the second method; those are the strongest candidates."],
                [_tab("Most unusual rows", ["Row #", "Unusual score", "Also flagged by Isolation Forest", "Most abnormal input"], rows)], ["Unusual is not the same as wrong or fraudulent; check each row yourself.", "No labels were used, so this can't say what it missed."], ch)


def dl_forecast(df, target, prompt="") -> dict:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    dc = next((c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])), None) or next((c for c in df.columns if "date" in str(c).lower()), None)
    if not dc:
        raise StudioError("Forecasting needs a date column.")
    num = [c for c in df.select_dtypes("number").columns]
    if target not in df.columns or target not in num:
        target = next((c for c in num if not str(c).lower().endswith("id")), None)
    if not target:
        raise StudioError("Forecasting needs a numeric column to forecast.")
    dd = pd.to_datetime(df[dc], errors="coerce")
    s = df.assign(_d=dd.dt.normalize()).dropna(subset=["_d"]).groupby("_d")[target].sum()
    s.index = pd.to_datetime(s.index)
    s = s.asfreq("D").interpolate().dropna()
    if len(s) < 60:
        raise StudioError(f"Need at least 60 days of history; have {len(s)}.")
    L = 14
    v = s.to_numpy(float)
    dow = s.index.dayofweek.to_numpy()

    def feats(i):
        return np.r_[v[i - L:i], np.eye(7)[dow[i]]]
    idx = list(range(L, len(v)))
    Xa = np.array([feats(i) for i in idx])
    ya = v[idx]
    cut = int(len(idx) * 0.8)
    sc = StandardScaler().fit(Xa[:cut])
    mlp = MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=800, early_stopping=True, random_state=1).fit(sc.transform(Xa[:cut]), ya[:cut])
    hgb = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, random_state=1).fit(Xa[:cut], ya[:cut])
    yt = ya[cut:]
    naive = v[np.array(idx[cut:]) - 1]
    seas = v[np.array(idx[cut:]) - 7]
    res = {"Naive (same as yesterday)": naive, "Seasonal naive (same weekday last week)": seas, "Neural network (MLP on 14 lags)": mlp.predict(sc.transform(Xa[cut:])), "Gradient boosting on lags": hgb.predict(Xa[cut:])}
    rows = sorted([[k, _r(mean_absolute_error(yt, p), 2), _r(100 * np.mean(np.abs(yt - p) / np.maximum(np.abs(yt), 1e-9)), 1)] for k, p in res.items()], key=lambda r: r[1])
    win = rows[0]
    hist = list(v[-L:])
    d_hist = list(dow[-7:])
    fut, last_day = [], s.index[-1]
    for k in range(7):
        day = (last_day + pd.Timedelta(days=k + 1)).dayofweek
        x = np.r_[hist[-L:], np.eye(7)[day]]
        p = float(mlp.predict(sc.transform([x]))[0])
        hist.append(p)
        fut.append([str((last_day + pd.Timedelta(days=k + 1)).date()), _r(p, 2)])
    resid = np.std(yt - res["Neural network (MLP on 14 lags)"])
    useful_nn = win[0].startswith("Neural") or win[0].startswith("Gradient")
    f = [f"Best method on the last {len(yt)} days it never trained on: {win[0]} (average error {win[1]:,.2f}, {win[2]}%)."]
    if not useful_nn:
        f.append("The simple methods won, which is common with short or noisy history: a neural network isn't worth the extra complexity here.")
    return _out("dl", "forecast_net", [{"who": "Planner", "did": f"Forecasting daily '{target}' from {len(s)} days of history."},
                                        {"who": "Modeller", "did": "Compared 4 methods on the final 20% of days (a rolling out-of-sample test): two naive rules, a neural network and gradient boosting on the last 14 days plus weekday."},
                                        {"who": "Reviewer", "did": "Judged them on error against what actually happened."}],
                f, [_tab("Backtest (lower error is better)", ["Method", "Average error", "Error %"], rows), _tab("Neural network forecast, next 7 days", ["Date", "Forecast"], fut)],
                [f"Typical error is about ±{1.64 * resid:,.1f} (90% of recent misses were smaller than this). Forecasts assume tomorrow behaves like the past.", "Holidays, promotions and price changes aren't known to the model."])


def dl_demo() -> dict:
    from app.services import nn_lab
    r = nn_lab.train_mlp("xor", (4,), "tanh", 1500, 0.5, 1)
    keys = list(r.keys())
    return _out("dl", "demo", [{"who": "Planner", "did": "Trained a tiny network (2 inputs, 4 hidden neurons) on XOR, a pattern no straight line can separate."}],
                [f"The network {'learned' if r.get('accuracy', r.get('final_accuracy', 1)) in (1, 1.0) else 'trained'}. Open the Machine-learning labs for the step-by-step view."], [], ["A teaching demo on 4 data points, not a business model."], extra={"raw_keys": keys})


# ---------------------------------------------------------------- entry


def run(prompt: str, data: str = "", source: str = "", text_col: str = "", label_col: str = "", target: str = "", query: str = "", agent: str = "", task: str = "") -> dict:
    t0 = time.time()
    warnings.filterwarnings("ignore")
    has_data = bool((data or "").strip() or source)
    df = parse(data, source) if has_data else None
    text_like = df is not None and any(True for c in df.columns if df[c].dtype == object)
    r = route(prompt or task or "", has_text=bool(df is not None and text_like), has_table=bool(df is not None and len(df.select_dtypes("number").columns) >= 2))
    if agent in ("nlp", "dl"):
        r["agent"] = agent
    if task and task in {**NLP_TASKS, **DL_TASKS}:
        r["task"] = task
        r["agent"] = "nlp" if task in NLP_TASKS else "dl"
    tk = r["task"]
    if df is None and tk != "demo":
        if r["agent"] == "dl":
            tk = "demo"
        else:
            raise StudioError("I need some data to work on. Paste your texts (one per line, or a CSV with a header row), or choose a dashboard table.")
    if tk in ("classify", "sentiment", "similar", "topics", "keywords", "entities", "summary", "text_net"):
        text = _text_col(df, text_col)
        label = _label_col(df, text, label_col, prompt)
        out = {"classify": lambda: nlp_classify(df, text, label, query), "sentiment": lambda: nlp_sentiment(df, text, label), "similar": lambda: nlp_similar(df, text, query or prompt),
               "topics": lambda: nlp_topics(df, text), "keywords": lambda: nlp_keywords(df, text), "entities": lambda: nlp_entities(df, text), "summary": lambda: nlp_summary(df, text),
               "text_net": lambda: dl_text(df, text, label)}[tk]()
        out["used"] = {"text_column": text, "label_column": label}
    elif tk == "tabular_net":
        tg = target or _guess_target(df, prompt)
        out = dl_tabular(df, tg, prompt)
        out["used"] = {"target": tg}
    elif tk == "anomaly":
        out = dl_anomaly(df, prompt)
        out["used"] = {"columns": list(_numeric_frame(df).columns)[:20]}
    elif tk == "forecast_net":
        tg = target or _guess_target(df, prompt, numeric=True)
        out = dl_forecast(df, tg, prompt)
        out["used"] = {"target": tg}
    else:
        out = dl_demo()
        out["used"] = {}
    out["intent"] = {"prompt": prompt, "agent": out["agent"], "task": out["task"], "what": (NLP_TASKS if out["agent"] == "nlp" else DL_TASKS)[out["task"]][1]}
    out["rows"] = int(len(df)) if df is not None else 0
    out["seconds"] = _r(time.time() - t0, 1)
    return out


def _guess_target(df, prompt, numeric=False):
    low = (prompt or "").lower()
    cols = [c for c in df.columns if not str(c).lower().endswith("id")]
    for c in cols:
        if str(c).lower().replace("_", " ") in low and (not numeric or pd.api.types.is_numeric_dtype(df[c])):
            return c
    nums = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if numeric or not nums:
        return nums[-1] if nums else None
    return nums[-1]


def examples() -> list[dict]:
    return [
        {"agent": "nlp", "text": "Sort these support tickets by category", "needs": "A CSV with 'text' and 'category' columns (30+ rows)"},
        {"agent": "nlp", "text": "What are customers saying? Find the main themes", "needs": "Texts, one per line"},
        {"agent": "nlp", "text": "How do customers feel? Show sentiment by product", "needs": "Texts, optionally with a category column"},
        {"agent": "nlp", "text": "Find cases similar to: laptop will not charge after update", "needs": "Past cases as text"},
        {"agent": "dl", "text": "Find unusual rows in my sales", "needs": "A dashboard table or CSV with numbers"},
        {"agent": "dl", "text": "Train a neural network to predict price", "needs": "A dashboard table (60+ rows)"},
        {"agent": "dl", "text": "Forecast daily price with a neural network and compare it", "needs": "A table with dates"},
        {"agent": "dl", "text": "Show me how a neural network learns", "needs": "Nothing"},
    ]
