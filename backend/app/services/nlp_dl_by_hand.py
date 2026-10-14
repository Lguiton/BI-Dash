"""ML by hand, part 2: small NLP and deep-learning tasks worked step by step (same sandbox rules as ml_by_hand: in memory, nothing saved).

NLP: TF-IDF and cosine similarity, Naive Bayes text classification, bigram language model, edit distance.
Deep learning: perceptron, gradient descent, and a tiny 2-2-1 neural network with a forward pass, backpropagation and a numeric check."""
from __future__ import annotations

import math
import re
from collections import Counter

from app.services.ml_by_hand import HandError, _f, _step, parse_table

TOKEN = re.compile(r"[a-z0-9']+")
STOP = {"the", "a", "an", "and", "or", "of", "to", "is", "in", "it", "on", "for", "are", "was", "this", "that"}
MAX_DOCS, MAX_CHARS = 12, 400
NLP_METHODS = ("tfidf", "bayes", "ngram", "edit")
DL_METHODS = ("nn", "gd", "perceptron")


def _toks(s: str, stop: bool = False) -> list[str]:
    t = TOKEN.findall((s or "").lower())
    return [w for w in t if w not in STOP] if stop else t


def _docs(text: str) -> list[str]:
    docs = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(docs) < 2:
        raise HandError("Enter at least two documents, one per line.")
    if len(docs) > MAX_DOCS or any(len(d) > MAX_CHARS for d in docs):
        raise HandError(f"Keep it small enough to do by hand: {MAX_DOCS} lines of up to {MAX_CHARS} characters.")
    return docs


# ------------------------------------------------------------------ TF-IDF and cosine similarity
def tfidf(text: str, query: str, stop: bool = False) -> dict:
    docs = _docs(text)
    if not (query or "").strip():
        raise HandError("Enter a search phrase to compare with the documents.")
    toks = [_toks(d, stop) for d in docs]
    n = len(docs)
    vocab = sorted({w for t in toks for w in t})
    if not vocab:
        raise HandError("No words found in the documents.")
    counts = [Counter(t) for t in toks]
    df = {w: sum(1 for c in counts if w in c) for w in vocab}
    idf = {w: math.log((1 + n) / (1 + df[w])) + 1 for w in vocab}
    steps = [_step("Idea", "Turn each text into a list of numbers (one per word) so texts can be compared. A word counts for more when it is frequent in this document (TF) but rare across all documents (IDF)."),
             _step("Words in each document", "Lower-case words" + (" with common filler words removed" if stop else "") + ".", "\n".join(f"doc {i + 1}: {' '.join(t)}" for i, t in enumerate(toks))),
             _step("Vocabulary", f"{len(vocab)} different words, alphabetical.", ", ".join(vocab)),
             _step("TF: how often each word appears in each document (raw counts)", "", "\n".join(f"doc {i + 1}: " + ", ".join(f"{w}={c[w]}" for w in vocab if c[w]) for i, c in enumerate(counts))),
             _step("DF and IDF", f"DF = how many of the {n} documents contain the word. IDF = ln((1 + N) / (1 + DF)) + 1 (the smoothed form scikit-learn uses). Rare words get a bigger IDF.",
                   "\n".join(f"{w}: DF={df[w]}, IDF = ln({1 + n}/{1 + df[w]}) + 1 = {_f(idf[w])}" for w in vocab))]

    def vec(c: Counter) -> dict[str, float]:
        raw = {w: c[w] * idf[w] for w in vocab if c[w]}
        norm = math.sqrt(sum(v * v for v in raw.values()))
        return {w: v / norm for w, v in raw.items()} if norm else {}
    dvecs = [vec(c) for c in counts]
    steps.append(_step("TF x IDF, then scale each document to length 1", "Dividing by the vector's length (L2 norm) means long documents don't win just by being long.",
                       "\n".join(f"doc {i + 1}: " + ", ".join(f"{w}={_f(v)}" for w, v in d.items()) for i, d in enumerate(dvecs))))
    qt = _toks(query, stop)
    known = [w for w in qt if w in idf]
    unknown = sorted({w for w in qt if w not in idf})
    qc = Counter(known)
    qv = vec(qc)
    steps.append(_step("The search phrase gets the same treatment", "Words that aren't in the documents have no IDF and are ignored." + (f" Ignored here: {', '.join(unknown)}." if unknown else ""),
                       ", ".join(f"{w}={_f(v)}" for w, v in qv.items()) or "(no known words)"))
    sims = [sum(qv.get(w, 0) * v for w, v in d.items()) for d in dvecs]
    steps.append(_step("Cosine similarity = dot product of the two length-1 vectors", "1 means the same direction (very similar), 0 means no words in common.",
                       "\n".join(f"doc {i + 1}: " + (" + ".join(f"{_f(qv[w])}x{_f(d[w])}" for w in qv if w in d) or "0") + f" = {_f(s)}" for i, (d, s) in enumerate(zip(dvecs, sims)))))
    order = sorted(range(n), key=lambda i: (-sims[i], i))
    steps.append(_step("Ranking", "Best match first.", "\n".join(f"#{r + 1}: doc {i + 1}  ({_f(sims[i])})  {docs[i]}" for r, i in enumerate(order))))
    check = {"library": "scikit-learn TfidfVectorizer + cosine_similarity", "values": {}, "agrees": None}
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        v = TfidfVectorizer(token_pattern=r"[a-z0-9']+", stop_words=sorted(STOP) if stop else None)
        m = v.fit_transform(docs)
        lib = cosine_similarity(v.transform([query]), m)[0]
        check.update(values={f"doc{i + 1}": float(x) for i, x in enumerate(lib)}, agrees=bool(all(abs(a - float(b)) < 1e-9 for a, b in zip(sims, lib))))
    except Exception:  # noqa: BLE001
        pass
    return {"method": "tfidf", "steps": steps, "answer": {"best_match": f"doc {order[0] + 1}", "best_score": sims[order[0]]}, "check": check}


# ------------------------------------------------------------------ Naive Bayes text classifier
def bayes(text: str, query: str, stop: bool = False) -> dict:
    head, body = parse_table(text)
    if len(head) != 2:
        raise HandError("Two columns: label, then the text (put quotes around text that contains commas).")
    if not (query or "").strip():
        raise HandError("Enter the message to classify.")
    labels = [r[0] for r in body]
    docs = [_toks(r[1], stop) for r in body]
    classes = sorted(set(labels))
    if len(classes) < 2:
        raise HandError("Need at least two different labels.")
    vocab = sorted({w for d in docs for w in d})
    V = len(vocab)
    N = len(body)
    steps = [_step("Idea", "Naive Bayes asks: given these words, which label is most likely? It multiplies the label's overall frequency (prior) by how often each word shows up in that label. 'Naive' means it treats the words as independent."),
             _step("Priors: how common is each label?", "", "\n".join(f"P({c}) = {labels.count(c)}/{N} = {_f(labels.count(c) / N)}" for c in classes)),
             _step("Word counts per label", f"Vocabulary has {V} different words.", "\n".join(f"{c}: " + ", ".join(f"{w}={n}" for w, n in sorted(Counter(w for d, l in zip(docs, labels) if l == c for w in d).items())) for c in classes))]
    cnt = {c: Counter(w for d, l in zip(docs, labels) if l == c for w in d) for c in classes}
    tot = {c: sum(cnt[c].values()) for c in classes}
    steps.append(_step("Smoothed word probabilities (Laplace, add 1)", "A word never seen in a label would give probability 0 and wipe out the whole product, so add 1 to every count: P(word | label) = (count + 1) / (words in label + vocabulary size).",
                       "\n".join(f"{c}: total words {tot[c]}, so denominator {tot[c]} + {V} = {tot[c] + V}" for c in classes)))
    qt = [w for w in _toks(query, stop) if w in vocab]
    ignored = sorted({w for w in _toks(query, stop) if w not in vocab})
    steps.append(_step("Words of the new message", "Words never seen in training are ignored." + (f" Ignored: {', '.join(ignored)}." if ignored else ""), " ".join(qt) or "(none known)"))
    logs: dict[str, float] = {}
    lines = []
    for c in classes:
        s = math.log(labels.count(c) / N)
        parts = [f"ln P({c}) = {_f(s)}"]
        for w in qt:
            p = (cnt[c][w] + 1) / (tot[c] + V)
            s += math.log(p)
            parts.append(f"ln P({w}|{c}) = ln({cnt[c][w] + 1}/{tot[c] + V}) = {_f(math.log(p))}")
        logs[c] = s
        lines.append(f"{c}:\n  " + "\n  ".join(parts) + f"\n  total = {_f(s)}")
    steps.append(_step("Score each label (add logarithms instead of multiplying tiny numbers)", "Bigger (less negative) wins.", "\n".join(lines)))
    mx = max(logs.values())
    ex = {c: math.exp(v - mx) for c, v in logs.items()}
    z = sum(ex.values())
    post = {c: ex[c] / z for c in classes}
    win = max(classes, key=lambda c: (post[c], c))
    steps.append(_step("Turn scores into probabilities", "e^score for each label, divided by their sum.", "\n".join(f"P({c} | message) = {_f(post[c])}" for c in classes) + f"\n→ {win}"))
    check = {"library": "scikit-learn CountVectorizer + MultinomialNB", "values": {}, "agrees": None}
    try:
        from sklearn.feature_extraction.text import CountVectorizer
        from sklearn.naive_bayes import MultinomialNB
        cv = CountVectorizer(token_pattern=r"[a-z0-9']+", stop_words=sorted(STOP) if stop else None)
        X = cv.fit_transform([r[1] for r in body])
        m = MultinomialNB(alpha=1.0).fit(X, labels)
        pr = m.predict_proba(cv.transform([query]))[0]
        check.update(values={c: float(p) for c, p in zip(m.classes_, pr)}, agrees=bool(all(abs(post[c] - float(p)) < 1e-9 for c, p in zip(m.classes_, pr))))
    except Exception:  # noqa: BLE001
        pass
    return {"method": "bayes", "steps": steps, "answer": {"prediction": win, **{f"P({c})": post[c] for c in classes}}, "check": check}


# ------------------------------------------------------------------ bigram language model
def ngram(text: str, query: str) -> dict:
    docs = _docs(text) if "\n" in (text or "").strip() else [(text or "").strip()]
    if not docs or not docs[0]:
        raise HandError("Enter some sentences, one per line.")
    sents = [["<s>"] + _toks(d) + ["</s>"] for d in docs]
    uni = Counter(w for s in sents for w in s[:-1])
    bi = Counter((a, b) for s in sents for a, b in zip(s, s[1:]))
    steps = [_step("Idea", "A bigram model predicts the next word from the one before it: P(next | previous) = count(previous next) / count(previous). Predictive text works this way (with far more data)."),
             _step("Sentences with start and end markers", "", "\n".join(" ".join(s) for s in sents)),
             _step("Bigram counts", "How many times each pair of neighbouring words occurs.", "\n".join(f"({a} {b}) = {c}" for (a, b), c in sorted(bi.items())))]
    q = _toks(query)
    answer: dict = {}
    if q:
        prev = q[-1]
        nxt = sorted(((c / uni[prev], b, c) for (a, b), c in bi.items() if a == prev), key=lambda t: (-t[0], t[1])) if uni[prev] else []
        steps.append(_step(f"What comes after '{prev}'?", f"'{prev}' appears {uni[prev]} time(s) followed by another word." if uni[prev] else f"'{prev}' never appears in the training sentences, so the model has no guess (this is why real models use smoothing and much more text).",
                           "\n".join(f"P({b} | {prev}) = {c}/{uni[prev]} = {_f(p)}" for p, b, c in nxt) or "(no data)"))
        answer["next_word"] = nxt[0][1] if nxt else "unknown"
        if len(q) >= 2:
            p = 1.0
            lines = []
            for a, b in zip(["<s>"] + q[:-1], q):
                pr = bi[(a, b)] / uni[a] if uni[a] else 0.0
                lines.append(f"P({b} | {a}) = {bi[(a, b)]}/{uni[a]} = {_f(pr)}")
                p *= pr
            steps.append(_step("Probability of the whole phrase", "Multiply the bigram probabilities. One unseen pair makes it 0, which is the model's weakness.", "\n".join(lines) + f"\nproduct = {_f(p)}"))
            answer["phrase_probability"] = p
    return {"method": "ngram", "steps": steps, "answer": answer, "check": {"library": "recount with collections.Counter", "values": {}, "agrees": None, "note": "No library does this exact count, but every number above can be checked by counting pairs by eye."}}


# ------------------------------------------------------------------ edit distance
def edit(text: str, query: str) -> dict:
    a = (text or "").strip().splitlines()[0].strip().lower() if (text or "").strip() else ""
    b = (query or "").strip().lower()
    if not a or not b:
        raise HandError("Put the first word in the data box and the second word in the new-word box.")
    if len(a) > 20 or len(b) > 20:
        raise HandError("Keep each word to 20 letters or fewer.")
    n, m = len(a), len(b)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        D[i][0] = i
    for j in range(m + 1):
        D[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    grid = "      " + "  ".join(f"{c:>2}" for c in " " + b) + "\n" + "\n".join(f"{c:>2}  " + "  ".join(f"{v:>2}" for v in D[i]) for i, c in enumerate(" " + a))

    def rec(i, j, memo={}):  # noqa: B006 - independent check, memo reset per call below
        if (i, j) in memo:
            return memo[(i, j)]
        r = max(i, j) if i == 0 or j == 0 else min(rec(i - 1, j) + 1, rec(i, j - 1) + 1, rec(i - 1, j - 1) + (a[i - 1] != b[j - 1]))
        memo[(i, j)] = r
        return r
    steps = [_step("Idea", "Edit distance (Levenshtein) is the fewest single-letter changes (insert, delete, replace) that turn one word into another. Spell checkers use it to find the closest real word."),
             _step("Fill a grid", f"Cell (i, j) = the distance between the first i letters of '{a}' and the first j letters of '{b}'. The first row and column are just 0, 1, 2, … because turning a word into nothing needs one delete per letter. Every other cell is 1 + the smallest of: the cell above (delete), the cell to the left (insert), or the diagonal cell (replace, plus 0 if the letters are the same).", grid),
             _step("Answer", "The bottom-right cell.", f"distance('{a}', '{b}') = {D[n][m]}")]
    ok = rec(n, m, {}) == D[n][m]
    return {"method": "edit", "steps": steps, "answer": {"distance": D[n][m]}, "check": {"library": "independent recursive calculation", "values": {"distance": rec(n, m, {})}, "agrees": bool(ok)}}


# ------------------------------------------------------------------ deep learning
def _sig(z: float) -> float:
    return 1 / (1 + math.exp(-max(-60.0, min(60.0, z))))


DEFAULT_NET = {"wh": [0.15, 0.20, 0.25, 0.30], "bh": [0.35, 0.35], "wo": [0.40, 0.45], "bo": 0.60, "lr": 0.5, "steps": 1}


def _net_params(p: dict) -> dict:
    out = {}
    for k, n in (("wh", 4), ("bh", 2), ("wo", 2)):
        v = p.get(k, DEFAULT_NET[k])
        v = [float(x) for x in (v if isinstance(v, list) else str(v).split(","))]
        if len(v) != n:
            raise HandError(f"{k} needs {n} numbers.")
        out[k] = v
    out["bo"] = float(p.get("bo", DEFAULT_NET["bo"]))
    out["lr"] = float(p.get("lr", DEFAULT_NET["lr"]))
    out["steps"] = max(1, min(int(p.get("steps", 1)), 50))
    if not 0 < out["lr"] <= 10:
        raise HandError("The learning rate must be between 0 and 10.")
    return out


def _forward(x, w):
    z1 = w["wh"][0] * x[0] + w["wh"][1] * x[1] + w["bh"][0]
    z2 = w["wh"][2] * x[0] + w["wh"][3] * x[1] + w["bh"][1]
    h1, h2 = _sig(z1), _sig(z2)
    zo = w["wo"][0] * h1 + w["wo"][1] * h2 + w["bo"]
    return z1, z2, h1, h2, zo, _sig(zo)


def nn(text: str, params: dict | None = None) -> dict:
    head, body = parse_table(text)
    if len(head) != 3 or not body:
        raise HandError("One data row with three numbers: input 1, input 2, target (0 to 1).")
    try:
        x1, x2, t = (float(v) for v in body[0])
    except ValueError as e:
        raise HandError("The first data row must be three numbers.") from e
    w = _net_params(params or {})
    x = [x1, x2]
    steps = [_step("The network", "2 inputs → 2 hidden neurons (sigmoid) → 1 output neuron (sigmoid). Sigmoid squashes any number into 0..1: σ(z) = 1 / (1 + e^-z). 9 numbers (weights and biases) are learned.",
                   f"hidden 1: weights {_f(w['wh'][0])}, {_f(w['wh'][1])}, bias {_f(w['bh'][0])}\nhidden 2: weights {_f(w['wh'][2])}, {_f(w['wh'][3])}, bias {_f(w['bh'][1])}\noutput: weights {_f(w['wo'][0])}, {_f(w['wo'][1])}, bias {_f(w['bo'])}\ninput ({_f(x1)}, {_f(x2)}), target {_f(t)}, learning rate {_f(w['lr'])}")]
    z1, z2, h1, h2, zo, y = _forward(x, w)
    loss0 = 0.5 * (t - y) ** 2
    steps += [_step("Forward pass: hidden layer", "Weighted sum of the inputs plus bias, then sigmoid.",
                    f"z1 = {_f(w['wh'][0])}x{_f(x1)} + {_f(w['wh'][1])}x{_f(x2)} + {_f(w['bh'][0])} = {_f(z1)};  h1 = σ({_f(z1)}) = {_f(h1)}\nz2 = {_f(w['wh'][2])}x{_f(x1)} + {_f(w['wh'][3])}x{_f(x2)} + {_f(w['bh'][1])} = {_f(z2)};  h2 = σ({_f(z2)}) = {_f(h2)}"),
              _step("Forward pass: output", "", f"zo = {_f(w['wo'][0])}x{_f(h1)} + {_f(w['wo'][1])}x{_f(h2)} + {_f(w['bo'])} = {_f(zo)};  ŷ = σ({_f(zo)}) = {_f(y)}"),
              _step("Loss: how wrong is it?", "Squared error with a ½ so the derivative is tidy: L = ½ (target - ŷ)².", f"L = ½ ({_f(t)} - {_f(y)})² = {_f(loss0, 6)}")]
    losses = [loss0]
    cur = {k: (v[:] if isinstance(v, list) else v) for k, v in w.items()}
    first_grads = None
    for step in range(w["steps"]):
        z1, z2, h1, h2, zo, y = _forward(x, cur)
        d_out = (y - t) * y * (1 - y)                              # dL/dzo
        g = {"wo": [d_out * h1, d_out * h2], "bo": d_out}
        d1 = d_out * cur["wo"][0] * h1 * (1 - h1)
        d2 = d_out * cur["wo"][1] * h2 * (1 - h2)
        g["wh"] = [d1 * x1, d1 * x2, d2 * x1, d2 * x2]
        g["bh"] = [d1, d2]
        if step == 0:
            first_grads = g
            steps.append(_step("Backpropagation: how much does each number affect the loss?", "Work backwards with the chain rule. dL/dŷ = (ŷ - t). The sigmoid's slope is ŷ(1 - ŷ).",
                               f"δ_out = dL/dzo = (ŷ - t) x ŷ(1-ŷ) = ({_f(y)} - {_f(t)}) x {_f(y)}({_f(1 - y)}) = {_f(d_out, 6)}\n"
                               f"output weights: dL/dwo1 = δ_out x h1 = {_f(g['wo'][0], 6)};  dL/dwo2 = δ_out x h2 = {_f(g['wo'][1], 6)};  dL/dbo = {_f(d_out, 6)}"))
            steps.append(_step("Push the error back to the hidden neurons", "Each hidden neuron's share of the blame = δ_out x its weight to the output x its own sigmoid slope h(1-h).",
                               f"δ1 = {_f(d_out, 6)} x {_f(cur['wo'][0])} x {_f(h1)}({_f(1 - h1)}) = {_f(d1, 6)}\nδ2 = {_f(d_out, 6)} x {_f(cur['wo'][1])} x {_f(h2)}({_f(1 - h2)}) = {_f(d2, 6)}\n"
                               f"hidden weights: dL/dw = δ x input → {', '.join(_f(v, 6) for v in g['wh'])};  biases: {_f(d1, 6)}, {_f(d2, 6)}"))
        cur["wo"] = [a - w["lr"] * b for a, b in zip(cur["wo"], g["wo"])]
        cur["bo"] -= w["lr"] * g["bo"]
        cur["wh"] = [a - w["lr"] * b for a, b in zip(cur["wh"], g["wh"])]
        cur["bh"] = [a - w["lr"] * b for a, b in zip(cur["bh"], g["bh"])]
        yy = _forward(x, cur)[5]
        losses.append(0.5 * (t - yy) ** 2)
        if step == 0:
            steps.append(_step("Update: move every number a small step downhill", "new = old - learning rate x gradient.",
                               f"output weights → {_f(cur['wo'][0], 6)}, {_f(cur['wo'][1], 6)};  output bias → {_f(cur['bo'], 6)}\nhidden weights → {', '.join(_f(v, 6) for v in cur['wh'])};  hidden biases → {', '.join(_f(v, 6) for v in cur['bh'])}\n"
                               f"new prediction ŷ = {_f(yy, 6)}, new loss = {_f(losses[-1], 8)} (was {_f(loss0, 8)})"))
    if w["steps"] > 1:
        show = list(range(0, w["steps"] + 1, max(1, w["steps"] // 10)))
        if w["steps"] not in show:
            show.append(w["steps"])
        steps.append(_step(f"Repeat for {w['steps']} steps", "Each step does the same forward pass, backpropagation and update. The loss should keep falling.", "\n".join(f"step {s}: loss {_f(losses[s], 8)}" for s in show)))
    # numeric check of the first step's gradients: nudge each weight a tiny bit and see how the loss changes
    def loss_at(mod):
        ww = {k: (v[:] if isinstance(v, list) else v) for k, v in w.items()}
        mod(ww)
        return 0.5 * (t - _forward(x, ww)[5]) ** 2
    eps, worst = 1e-6, 0.0
    num = {}
    for key, idx in (("wo", 0), ("wo", 1), ("wh", 0), ("wh", 1), ("wh", 2), ("wh", 3), ("bh", 0), ("bh", 1)):
        def up(ww, key=key, idx=idx, s=1):
            ww[key][idx] += s * eps
        g_num = (loss_at(lambda ww: up(ww, s=1)) - loss_at(lambda ww: up(ww, s=-1))) / (2 * eps)
        num[f"d{key}{idx + 1}"] = g_num
        worst = max(worst, abs(g_num - first_grads[key][idx]))
    steps.append(_step("Check the calculus without calculus", "Nudge each number up and down by a tiny amount and watch the loss move. That slope should equal the backprop gradient.", f"largest difference over 8 gradients: {worst:.2e}"))
    return {"method": "nn", "steps": steps, "answer": {"first_prediction": _forward(x, w)[5], "initial_loss": loss0, "final_loss": losses[-1], "final_prediction": _forward(x, cur)[5]},
            "check": {"library": "numerical gradient (finite differences)", "values": {"largest_gradient_difference": worst}, "agrees": bool(worst < 1e-7)}}


def gd(text: str, params: dict | None = None) -> dict:
    p = params or {}
    head, body = parse_table(text)
    if len(head) != 2:
        raise HandError("Two columns: x then y.")
    try:
        pts = [(float(r[0]), float(r[1])) for r in body]
    except ValueError as e:
        raise HandError("x and y must be numbers.") from e
    n = len(pts)
    if n < 2:
        raise HandError("Give at least 2 rows.")
    lr = float(p.get("lr", 0.01))
    iters = max(1, min(int(p.get("steps", 20)), 5000))
    if not 0 < lr <= 5:
        raise HandError("The learning rate must be between 0 and 5.")
    m = c = 0.0
    steps = [_step("Idea", "Instead of solving for the line with formulas, start with a guess (m = 0, c = 0) and repeatedly nudge m and c downhill on the error until it stops improving. This is how neural networks learn, with millions of numbers instead of two."),
             _step("The error being reduced", "Mean squared error: MSE = average of (y - (m x + c))².  Its slopes: dMSE/dm = -2 x average of x(y - ŷ),  dMSE/dc = -2 x average of (y - ŷ).", f"{n} points, learning rate {_f(lr)}, starting at m = 0, c = 0.")]
    hist = []
    for i in range(iters):
        pr = [m * x + c for x, _ in pts]
        err = [y - q for (_, y), q in zip(pts, pr)]
        mse = sum(e * e for e in err) / n
        dm = -2 * sum(x * e for (x, _), e in zip(pts, err)) / n
        dc = -2 * sum(err) / n
        hist.append((i, m, c, mse))
        if i < 3:
            steps.append(_step(f"Step {i + 1}", "Predict, measure the error, compute the slopes, then move against them.",
                               f"MSE now = {_f(mse, 6)}\ndMSE/dm = {_f(dm, 6)},  dMSE/dc = {_f(dc, 6)}\nm = {_f(m, 6)} - {_f(lr)} x {_f(dm, 6)} = {_f(m - lr * dm, 6)}\nc = {_f(c, 6)} - {_f(lr)} x {_f(dc, 6)} = {_f(c - lr * dc, 6)}"))
        m, c = m - lr * dm, c - lr * dc
        if not (math.isfinite(m) and math.isfinite(c)) or abs(m) > 1e12:
            raise HandError("The numbers blew up: the learning rate is too big for this data. Try a smaller one (for example 0.01 or 0.001).")
    mse_end = sum((y - (m * x + c)) ** 2 for x, y in pts) / n
    show = sorted({0, 1, 2, 5, 10, iters // 4, iters // 2, iters - 1} & set(range(iters)))
    steps.append(_step(f"After {iters} steps", "The error should be shrinking. If it isn't, the learning rate is too large or too small.", "\n".join(f"after {i} steps: m = {_f(hist[i][1], 5)}, c = {_f(hist[i][2], 5)}, MSE = {_f(hist[i][3], 6)}" for i in show) + f"\nafter {iters} steps: m = {_f(m, 5)}, c = {_f(c, 5)}, MSE = {_f(mse_end, 6)}"))
    import numpy as np
    sl, ic = np.polyfit([x for x, _ in pts], [y for _, y in pts], 1)
    steps.append(_step("Compare with the exact answer", "Least squares gives the best possible line directly; gradient descent creeps toward it.", f"exact: m = {_f(sl, 5)}, c = {_f(ic, 5)}"))
    close = abs(m - sl) < max(0.05, 0.02 * abs(sl)) and abs(c - ic) < max(0.5, 0.05 * abs(ic) + 0.05)
    return {"method": "gd", "steps": steps, "answer": {"m": m, "c": c, "mse": mse_end}, "check": {"library": "numpy.polyfit (exact least squares)", "values": {"m": float(sl), "c": float(ic)}, "agrees": bool(close),
            "note": "Gradient descent only gets close. More steps or a better learning rate gets closer." if not close else ""}}


def perceptron(text: str, params: dict | None = None) -> dict:
    p = params or {}
    head, body = parse_table(text)
    if len(head) != 3:
        raise HandError("Three columns: x1, x2, then the class (0 or 1).")
    try:
        pts = [(float(r[0]), float(r[1]), int(float(r[2]))) for r in body]
    except ValueError as e:
        raise HandError("x1 and x2 must be numbers and the class must be 0 or 1.") from e
    if any(c not in (0, 1) for *_, c in pts):
        raise HandError("The class must be 0 or 1.")
    lr = float(p.get("lr", 1.0))
    epochs = max(1, min(int(p.get("epochs", 10)), 30))
    w1 = w2 = b = 0.0
    steps = [_step("Idea", "The perceptron is the simplest neuron: output 1 if w1 x1 + w2 x2 + b > 0, else 0. Learning rule: for every wrongly classified point, nudge the weights toward it (if it should be 1) or away from it (if it should be 0).",
                   f"Start at w1 = 0, w2 = 0, b = 0. Learning rate {_f(lr)}. Update: w = w + lr x (target - output) x input; b = b + lr x (target - output).")]
    log, converged = [], False
    for e in range(epochs):
        wrong = 0
        for x1, x2, t in pts:
            out = 1 if w1 * x1 + w2 * x2 + b > 0 else 0
            if out != t:
                wrong += 1
                d = lr * (t - out)
                if len(log) < 12:
                    log.append(f"epoch {e + 1}: point ({_f(x1)}, {_f(x2)}) should be {t} but output {out} → w1 {_f(w1)}→{_f(w1 + d * x1)}, w2 {_f(w2)}→{_f(w2 + d * x2)}, b {_f(b)}→{_f(b + d)}")
                w1, w2, b = w1 + d * x1, w2 + d * x2, b + d
        if wrong == 0:
            converged = True
            steps.append(_step("Updates (first 12)", "", "\n".join(log) or "none needed"))
            steps.append(_step(f"Converged after {e + 1} pass(es)", "A full pass with no mistakes: the line separates the two classes.", f"w1 = {_f(w1)}, w2 = {_f(w2)}, b = {_f(b)}\ndecision line: {_f(w1)} x1 + {_f(w2)} x2 + {_f(b)} = 0"))
            break
    else:
        steps.append(_step("Updates (first 12)", "", "\n".join(log)))
        steps.append(_step(f"Did not settle in {epochs} passes", "If no straight line can separate the classes (XOR is the classic case), the perceptron never stops making mistakes. That limit is why multi-layer networks were invented.", f"w1 = {_f(w1)}, w2 = {_f(w2)}, b = {_f(b)}"))
    acc = sum((1 if w1 * x1 + w2 * x2 + b > 0 else 0) == t for x1, x2, t in pts) / len(pts)
    steps.append(_step("Training accuracy", "", f"{_f(acc)}"))
    return {"method": "perceptron", "steps": steps, "answer": {"w1": w1, "w2": w2, "b": b, "training_accuracy": acc, "converged": converged},
            "check": {"library": "direct re-check of every point", "values": {"training_accuracy": acc}, "agrees": bool(converged == (acc == 1.0))}}


PRESETS = [
    {"id": "tfidf", "method": "tfidf", "title": "Which document matches my search? (TF-IDF)", "data": "printer is offline and will not print\nwifi keeps dropping in the bedroom\nlaptop screen is cracked and flickers\nprinter paper jam in the tray", "query": "printer offline", "params": {}, "note": ""},
    {"id": "bayes", "method": "bayes", "title": "Spam or not? (Naive Bayes)", "data": "label,text\nspam,win free money now\nspam,free prize claim now\nspam,cheap offer win now\nham,meeting at noon tomorrow\nham,invoice attached for the project\nham,lunch tomorrow at noon", "query": "free prize tomorrow", "params": {}, "note": ""},
    {"id": "ngram", "method": "ngram", "title": "Predict the next word (bigrams)", "data": "the printer is offline\nthe printer is jammed\nthe router is offline\nthe laptop is slow", "query": "the printer is", "params": {}, "note": ""},
    {"id": "edit", "method": "edit", "title": "How far apart are two words? (edit distance)", "data": "kitten", "query": "sitting", "params": {}, "note": "Answer: 3."},
    {"id": "nn", "method": "nn", "title": "One training step of a tiny neural network", "data": "x1,x2,target\n0.5,0.8,1", "query": "", "params": {"wh": [0.15, 0.2, 0.25, 0.3], "bh": [0.35, 0.35], "wo": [0.4, 0.45], "bo": 0.6, "lr": 0.5, "steps": 1}, "note": ""},
    {"id": "nn50", "method": "nn", "title": "Train it for 50 steps", "data": "x1,x2,target\n0.5,0.8,1", "query": "", "params": {"steps": 50, "lr": 0.5}, "note": "Watch the loss fall."},
    {"id": "gd", "method": "gd", "title": "Gradient descent finds the taxi-fare line", "data": "distance_km,fare\n2,100\n4,150\n6,200\n8,250\n10,300", "query": "", "params": {"lr": 0.02, "steps": 4000}, "note": "It creeps toward slope 25, intercept 50. Try 100 steps, or a learning rate of 0.05, to see it stall or blow up."},
    {"id": "perc", "method": "perceptron", "title": "Perceptron learns AND", "data": "x1,x2,class\n0,0,0\n0,1,0\n1,0,0\n1,1,1", "query": "", "params": {"lr": 1, "epochs": 10}, "note": ""},
    {"id": "xor", "method": "perceptron", "title": "Perceptron fails on XOR", "data": "x1,x2,class\n0,0,0\n0,1,1\n1,0,1\n1,1,0", "query": "", "params": {"lr": 1, "epochs": 10}, "note": "No straight line separates XOR."},
]


def run(method: str, data: str, query: str = "", params: dict | None = None) -> dict:
    params = params or {}
    if method == "tfidf":
        return tfidf(data, query, bool(params.get("stop", False)))
    if method == "bayes":
        return bayes(data, query, bool(params.get("stop", False)))
    if method == "ngram":
        return ngram(data, query)
    if method == "edit":
        return edit(data, query)
    if method == "nn":
        return nn(data, params)
    if method == "gd":
        return gd(data, params)
    if method == "perceptron":
        return perceptron(data, params)
    raise HandError("Unknown method.")
