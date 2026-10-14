"""NLP lab: the steps a language system runs, in small readable rules you can inspect.

Built: tokenization, stemming, lemmatization, part-of-speech tagging, named entities, sentiment, spam cues, intent and slot
understanding and generation, a trainable text classifier, an intent chatbot, and a retrieval-augmented generation (RAG) demo.
Honest limits: these are rule-based or small statistical teaching tools with short word lists. They show the idea; they are not
production NLP. There is no speech-to-text, text-to-speech, translation or embedding model here.
"""
from __future__ import annotations

import re

import numpy as np


class NlpError(Exception):
    pass


MAX_TEXT = 3000


def _text(s, name="Text", mx=MAX_TEXT) -> str:
    t = str(s or "").strip()
    if not t:
        raise NlpError(f"{name} is empty.")
    if len(t) > mx:
        raise NlpError(f"{name} is too long (limit {mx} characters).")
    return t


_TOK = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:[.,]\d+)*|[^\sA-Za-z\d]")


def tokenize(text) -> dict:
    t = _text(text)
    toks = _TOK.findall(t)
    return {"tokens": toks, "count": len(toks), "words": sum(1 for x in toks if x[0].isalnum()),
            "lesson": "Tokenization splits a string into pieces (tokens) so each can be processed on its own. Punctuation is usually its own token. Modern language models split into sub-word tokens instead of whole words."}


IRREGULAR = {"ran": "run", "better": "good", "best": "good", "worse": "bad", "worst": "bad", "was": "be", "were": "be", "is": "be", "are": "be", "am": "be", "been": "be", "being": "be", "has": "have", "had": "have", "does": "do", "did": "do", "done": "do",
             "went": "go", "gone": "go", "goes": "go", "bought": "buy", "made": "make", "said": "say", "took": "take", "taken": "take", "saw": "see", "seen": "see", "came": "come", "got": "get", "gave": "give", "given": "give", "knew": "know", "known": "know",
             "mice": "mouse", "men": "man", "women": "woman", "children": "child", "feet": "foot", "teeth": "tooth", "people": "person", "geese": "goose", "wrote": "write", "written": "write", "ate": "eat", "eaten": "eat", "found": "find", "thought": "think", "left": "leave"}
_VOWELS = "aeiou"


def stem(word) -> str:
    """A small suffix stripper in the spirit of the Porter stemmer: crude on purpose."""
    w = str(word).lower()
    if len(w) <= 3:
        return w
    for suf, rep in (("ational", "ate"), ("ization", "ize"), ("ies", "i"), ("sses", "ss"), ("xes", "x"), ("ches", "ch"), ("shes", "sh"), ("ing", ""), ("edly", ""), ("ed", ""), ("ers", ""), ("er", ""), ("est", ""), ("ly", ""), ("ity", ""), ("al", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: len(w) - len(suf)] + rep
            if suf in ("ing", "ed", "edly"):
                if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
                    w = w[:-1]
                elif len(w) in (3, 4) and w[-1] not in _VOWELS + "wxy" and w[-2] in _VOWELS and w[-3] not in _VOWELS:
                    w += "e"
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def lemmatize(word) -> str:
    """Dictionary lookup for irregular words, then regular rules. Always returns a real-looking base form."""
    w = str(word).lower()
    if w in IRREGULAR:
        return IRREGULAR[w]
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("sses", "shes", "ches", "xes", "zes")):
        return w[:-2]
    if w.endswith("ing") and len(w) > 5:
        b = w[:-3]
        if len(b) > 2 and b[-1] == b[-2] and b[-1] not in "lsz":
            return b[:-1]
        return b + "e" if len(b) >= 3 and b[-1] not in _VOWELS and b[-2] in _VOWELS and b[-3] not in _VOWELS and not b.endswith(("w", "x", "y")) and len(b) <= 4 else b
    if w.endswith("ed") and len(w) > 4:
        b = w[:-2]
        if len(b) > 2 and b[-1] == b[-2] and b[-1] not in "lsz":
            return b[:-1]
        return b + "e" if b[-1] not in _VOWELS and b[-2] in _VOWELS and len(b) <= 4 and not b.endswith(("w", "x", "y")) else b
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def stem_vs_lemma(text) -> dict:
    toks = [t for t in tokenize(text)["tokens"] if t[0].isalpha()][:60]
    rows = [{"word": t, "stem": stem(t), "lemma": lemmatize(t), "differs": stem(t) != lemmatize(t.lower())} for t in toks]
    return {"rows": rows, "lesson": "Stemming chops endings by rule, so it is fast but can produce non-words or merge unrelated words (universal and university). Lemmatization looks the word up and returns its dictionary root: better becomes good, where a stemmer leaves 'bett' or 'bet'.",
            "caution": "This lemmatizer knows only about 60 irregular words plus regular rules. A real one (spaCy, NLTK) uses a full dictionary."}


DET = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their", "some", "any", "no", "every", "each", "what", "which"}
PRON = {"i", "you", "he", "she", "it", "we", "they", "me", "him", "us", "them", "who", "whom"}
ADP = {"in", "on", "at", "by", "for", "with", "about", "from", "of", "into", "over", "under", "to", "between", "through", "after", "before"}
CONJ = {"and", "or", "but", "so", "because", "if", "while", "than", "that"}
AUX = {"is", "are", "was", "were", "am", "be", "been", "do", "does", "did", "have", "has", "had", "will", "would", "can", "could", "should", "may", "might", "must", "shall", "'m", "i'm", "it's", "don't", "doesn't", "isn't"}
ADV = {"not", "very", "too", "really", "just", "also", "never", "always", "often", "now", "then", "here", "there", "quickly"}
ADJ = {"good", "bad", "great", "big", "small", "red", "yellow", "new", "old", "happy", "sad", "fast", "slow", "high", "low", "better", "best", "worse", "worst", "weak", "strong", "free", "easy", "hard", "rotten"}
VERBS = {"add", "buy", "make", "order", "go", "get", "see", "run", "take", "give", "want", "need", "like", "love", "hate", "know", "think", "say", "find", "use", "call", "show", "check", "book", "list", "open", "close", "work", "play", "ask", "tell", "send", "pay", "cancel"}
AMBIG = {"make", "run", "book", "list", "call", "show", "check", "order", "play", "work", "use", "need", "love", "cancel", "pay", "ask", "close", "open"}


def pos_tag(text) -> dict:
    toks = tokenize(text)["tokens"]
    tags = []
    for i, t in enumerate(toks):
        lo = t.lower()
        prev = tags[-1][1] if tags else None
        prev_lo = toks[i - 1].lower() if i else ""
        if not t[0].isalnum():
            tag = "PUNCT"
        elif t[0].isdigit():
            tag = "NUM"
        elif lo in DET:
            tag = "DET"
        elif lo in PRON:
            tag = "PRON"
        elif lo in AUX:
            tag = "AUX"
        elif lo in ADP:
            tag = "ADP"
        elif lo in CONJ:
            tag = "CONJ"
        elif lo in ADV or lo.endswith("ly"):
            tag = "ADV"
        elif lo in AMBIG:
            # context decides: after a determiner/adjective/possessive it is a noun; after to/pronoun/modal/aux/start it is a verb
            tag = "NOUN" if prev in ("DET", "ADJ") or prev_lo in ("what", "which") else "VERB"
        elif lo in VERBS or lo in IRREGULAR and IRREGULAR[lo] in VERBS:
            tag = "VERB"
        elif lo in ADJ or lo.endswith(("ous", "ful", "ive", "able", "ible", "less", "ish")):
            tag = "ADJ"
        elif lo.endswith(("ing", "ed")) and len(lo) > 4:
            tag = "VERB"
        elif t[0].isupper() and i > 0 and toks[i - 1] not in (".", "!", "?"):
            tag = "PROPN"
        else:
            tag = "NOUN"
        tags.append((t, tag))
    return {"tags": [{"token": a, "tag": b} for a, b in tags],
            "legend": {"NOUN": "thing or idea", "VERB": "action", "ADJ": "describes a noun", "ADV": "describes a verb", "DET": "a, the, my", "PRON": "I, you, they", "ADP": "preposition", "CONJ": "joins clauses", "AUX": "helper verb", "NUM": "number", "PROPN": "name", "PUNCT": "punctuation"},
            "lesson": "Part-of-speech tagging labels each token by its role in the sentence. The same word can be a verb ('I'll make dinner') or a noun ('what make is your laptop'), so context decides.",
            "caution": "A tiny rule-based tagger with a short lexicon. It gets simple sentences right and will miss unusual ones; real taggers are trained on millions of labelled words."}


STATES = {"alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming"}
COUNTRIES = {"canada", "mexico", "france", "germany", "india", "china", "japan", "brazil", "spain", "italy", "russia", "australia", "england", "ireland", "kenya", "nigeria", "egypt"}
MONTHS = "january february march april may june july august september october november december".split()
NAMES = {"ralph", "maria", "john", "jane", "alex", "sam", "james", "mary", "robert", "linda", "david", "susan", "michael", "sarah", "chris", "emma", "lamarcus", "morgan", "martin", "kate", "marina", "jeff", "alan", "philip"}
ORG_SUF = r"(?:Inc|LLC|Corp|Corporation|Ltd|Co|Company|Bank|University|Institute)\.?"
PATTERNS = [("EMAIL", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), ("URL", r"https?://[^\s]+"), ("MONEY", r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|trillion|k|m|bn))?"),
            ("PERCENT", r"\d+(?:\.\d+)?\s?%"), ("DATE", r"\b\d{4}-\d{2}-\d{2}\b|\b(?:" + "|".join(m.capitalize() for m in MONTHS) + r")\s+\d{1,2}(?:,\s*\d{4})?\b"),
            ("ORG", r"\b(?:[A-Z][A-Za-z&]+\s)+" + ORG_SUF), ("TIME", r"\b\d{1,2}:\d{2}\s?(?:[AaPp][Mm])?\b")]


def entities(text) -> dict:
    t = _text(text)
    found, taken = [], []

    def add(start, end, label):
        if any(not (end <= s or start >= e) for s, e in taken):
            return
        taken.append((start, end))
        found.append({"text": t[start:end], "label": label, "start": start})
    for label, pat in PATTERNS:
        for m in re.finditer(pat, t):
            add(m.start(), m.end(), label)
    low = t.lower()
    for place, label in ((STATES, "STATE"), (COUNTRIES, "COUNTRY")):
        for p in sorted(place, key=len, reverse=True):
            for m in re.finditer(r"\b" + re.escape(p) + r"\b", low):
                add(m.start(), m.end(), label)
    for m in re.finditer(r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", t):
        add(m.start(), m.end(), "PERSON")
    for m in re.finditer(r"\b[A-Za-z]+\b", t):
        if m.group().lower() in NAMES and m.group()[0].isupper():
            add(m.start(), m.end(), "PERSON")
    found.sort(key=lambda e: e["start"])
    return {"entities": found, "lesson": "Named entity recognition finds the things a sentence names (people, places, organisations, dates, money) and labels their type. Arizona is a US state; Ralph is a person's name.",
            "caution": "Rules and short word lists only: it will miss names it hasn't been told about and mislabel ambiguous ones (Washington the person, state or city). Real systems use trained models."}


POS = {"good": 2, "great": 3, "excellent": 3, "love": 3, "loved": 3, "amazing": 3, "awesome": 3, "happy": 2, "nice": 2, "fast": 1, "easy": 1, "helpful": 2, "perfect": 3, "recommend": 2, "best": 3, "fantastic": 3, "wonderful": 3, "like": 1, "liked": 1, "works": 1, "reliable": 2, "beautiful": 2, "thanks": 1}
NEG = {"bad": -2, "terrible": -3, "awful": -3, "hate": -3, "hated": -3, "poor": -2, "slow": -1, "broken": -3, "useless": -3, "worst": -3, "disappointed": -2, "disappointing": -2, "waste": -2, "rotten": -2, "refund": -1, "problem": -1, "problems": -1, "late": -1, "never": -1, "buggy": -2, "expensive": -1, "rude": -2, "angry": -2, "annoying": -2}
NEGATORS = {"not", "no", "never", "n't", "without", "hardly", "isn't", "wasn't", "don't", "doesn't", "didn't", "can't", "won't", "cannot"}
BOOST = {"very": 1.5, "really": 1.5, "extremely": 2.0, "so": 1.3, "too": 1.2, "absolutely": 2.0, "slightly": 0.6, "somewhat": 0.7}


def sentiment(text) -> dict:
    t = _text(text)
    toks = [x.lower() for x in _TOK.findall(t)]
    total, parts = 0.0, []
    for i, w in enumerate(toks):
        base = POS.get(w) or NEG.get(w)
        if not base:
            continue
        mult, neg = 1.0, False
        for back in toks[max(0, i - 3):i]:
            if back in NEGATORS or back.endswith("n't"):
                neg = True
            mult *= BOOST.get(back, 1.0)
        val = base * mult * (-0.8 if neg else 1)
        total += val
        parts.append({"word": w, "score": round(val, 2), "note": "flipped by a negation" if neg else ("boosted" if mult != 1 else "")})
    label = "positive" if total > 0.5 else "negative" if total < -0.5 else "neutral"
    return {"score": round(total, 2), "label": label, "contributions": parts,
            "lesson": "Sentiment analysis estimates whether text is positive or negative. This version adds up word scores, flips them after a negation and scales them after words like 'very'.",
            "caution": "A word list can't read sarcasm ('great, another outage'), context or mixed reviews. Trained models do better but also get sarcasm wrong."}


URGENT = ["urgent", "act now", "immediately", "last chance", "limited time", "expires", "final notice", "within 24 hours", "right away"]
MONEYY = ["free", "winner", "won", "prize", "cash", "lottery", "guaranteed", "risk-free", "no cost", "100%", "credit", "loan", "investment", "bitcoin", "earn $"]
PHISH = ["verify your account", "password", "click here", "confirm your", "suspended", "login", "social security", "gift card", "wire transfer", "update your payment"]


def spam_check(text) -> dict:
    t = _text(text)
    lo = t.lower()
    reasons, score = [], 0
    for lab, words, w in (("urgency", URGENT, 2), ("money or prize", MONEYY, 2), ("account or payment request", PHISH, 3)):
        hit = [x for x in words if x in lo]
        if hit:
            score += w * min(len(hit), 3)
            reasons.append({"cue": lab, "found": hit})
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.4 and len(letters) > 12:
        score += 2; reasons.append({"cue": "mostly capital letters", "found": []})
    if t.count("!") >= 3:
        score += 2; reasons.append({"cue": "many exclamation marks", "found": []})
    if re.search(r"https?://\S+", t):
        score += 1; reasons.append({"cue": "contains a link", "found": re.findall(r"https?://\S+", t)[:3]})
    verdict = "likely spam" if score >= 6 else "suspicious" if score >= 3 else "looks ordinary"
    return {"score": score, "verdict": verdict, "reasons": reasons,
            "lesson": "Spam detection looks for cues: invented urgency, offers that are too good, requests for credentials, shouting and links. Real filters learn weights for thousands of such cues from labelled mail.",
            "caution": "Cue lists are easy to evade and flag honest mail. Never judge a message only on a score: check the sender and don't click links you didn't expect."}


def understand(text) -> dict:
    t = _text(text, mx=300)
    lo = t.lower().strip(" .!?")
    NUMS = {"a dozen": 12, "dozen": 12, "two dozen": 24, "a couple": 2, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}
    m = re.match(r"^(?:please\s+)?(?:add|put)\s+(.+?)\s+(?:to|on|onto)\s+(?:my|the)\s+(.+?)$", lo)
    if m:
        items = [x.strip() for x in re.split(r",|\band\b", m.group(1)) if x.strip()]
        return _nlu("add_items", {"items": items, "list": m.group(2)}, t)
    m = re.match(r"^(?:please\s+)?(?:remove|delete)\s+(.+?)\s+from\s+(?:my|the)\s+(.+?)$", lo)
    if m:
        return _nlu("remove_items", {"items": [x.strip() for x in re.split(r",|\band\b", m.group(1)) if x.strip()], "list": m.group(2)}, t)
    m = re.search(r"(?:order|buy|purchase|get)\s+(?:me\s+)?(?:some\s+)?(?:(a dozen|two dozen|dozen|\d+|one|two|three|four|five|six|ten)\s+)?(.+)$", lo)
    if m and re.search(r"\b(?:order|buy|purchase|i(?:'d| would) like|i want)\b", lo):
        q = m.group(1)
        qty = NUMS.get(q, int(q) if q and q.isdigit() else None)
        return _nlu("place_order", {"quantity": qty, "item": m.group(2).strip()}, t)
    if re.search(r"\bwhat time\b.*\bopen\b|\bopening hours\b|\bwhen do you open\b", lo):
        return _nlu("ask_hours", {}, t)
    if re.search(r"\b(?:balance|how much money)\b", lo):
        return _nlu("check_balance", {}, t)
    return {"intent": None, "slots": {}, "structured": None, "text": t,
            "message": "No intent matched. A real system would ask a clarifying question or hand over to a person.", "supported": ["add X and Y to my shopping list", "remove X from my list", "order a dozen yellow roses", "what time do you open?", "what is my balance?"],
            "lesson": "Natural language understanding turns free text into structure: an intent (what the person wants) and slots (the details)."}


def _nlu(intent, slots, text) -> dict:
    return {"intent": intent, "slots": slots, "structured": {"intent": intent, **slots}, "text": text, "reply": generate(intent, slots),
            "lesson": "Natural language understanding (NLU) turns text into structure: an intent and its slots. Natural language generation (NLG) goes the other way. NLP is the translation between the two."}


def generate(intent, slots) -> str:
    if intent == "add_items":
        return "Added " + " and ".join(slots["items"]) + f" to your {slots['list']}."
    if intent == "remove_items":
        return "Removed " + " and ".join(slots["items"]) + f" from your {slots['list']}."
    if intent == "place_order":
        return f"Placing an order for {slots['quantity'] if slots.get('quantity') else 'some'} {slots['item']}. I'll check stock first."
    if intent == "ask_hours":
        return "We open Monday to Friday at 9:00 AM."
    if intent == "check_balance":
        return "I can help with that. What is your account number? (Never share a PIN in a chat unless you are sure of who is asking.)"
    return "Sorry, I didn't understand that."


# ------------------------------------------------------------------ a classifier you train yourself
def train_classifier(examples, tests) -> dict:
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.model_selection import LeaveOneOut, cross_val_score
    from sklearn.naive_bayes import MultinomialNB
    if not isinstance(examples, list) or not 4 <= len(examples) <= 300:
        raise NlpError("Give between 4 and 300 labelled examples.")
    X, y = [], []
    for e in examples:
        if not isinstance(e, dict) or not str(e.get("text", "")).strip() or not str(e.get("label", "")).strip():
            raise NlpError("Each example needs text and a label.")
        X.append(_text(e["text"], "An example", 500)); y.append(str(e["label"]).strip()[:30])
    classes = sorted(set(y))
    if len(classes) < 2 or len(classes) > 8:
        raise NlpError("Use between 2 and 8 different labels.")
    if min(y.count(c) for c in classes) < 2:
        raise NlpError("Give at least 2 examples of every label.")
    tests = [str(s).strip() for s in (tests or []) if str(s).strip()][:20]
    vec = CountVectorizer(lowercase=True, token_pattern=r"[A-Za-z']+")
    M = vec.fit_transform(X)
    clf = MultinomialNB().fit(M, y)
    cv = None
    if len(X) >= 6:
        from sklearn.pipeline import make_pipeline
        cv = round(float(cross_val_score(make_pipeline(CountVectorizer(token_pattern=r"[A-Za-z']+"), MultinomialNB()), X, y, cv=LeaveOneOut()).mean()), 3)
    words = np.array(vec.get_feature_names_out())
    top = {c: words[np.argsort(clf.feature_log_prob_[i])[::-1][:6]].tolist() for i, c in enumerate(clf.classes_)}
    preds = []
    for s in tests:
        p = clf.predict_proba(vec.transform([s]))[0]
        k = int(np.argmax(p))
        seen = sum(1 for w in re.findall(r"[A-Za-z']+", s.lower()) if w in vec.vocabulary_)
        preds.append({"text": s, "label": str(clf.classes_[k]), "confidence": round(float(p[k]), 3), "known_words": seen, "warning": "None of these words appeared in training: the guess is just the model's default and means nothing." if seen == 0 else None})
    return {"labels": classes, "counts": {c: y.count(c) for c in classes}, "top_words": top, "leave_one_out_accuracy": cv, "predictions": preds,
            "lesson": "Supervised learning on text: the model counts which words go with which label (naive Bayes) and picks the most likely label for new text. More and better-balanced examples help far more than a cleverer model.",
            "caution": "With a handful of examples the model mostly memorises them. Check on text it hasn't seen, and don't trust the confidence number as a probability."}


# ------------------------------------------------------------------ chatbot and RAG
def _tfidf(docs, query, ngram=(1, 1), stop="english"):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    v = TfidfVectorizer(stop_words=stop, ngram_range=ngram, lowercase=True)
    M = v.fit_transform(docs + [query])
    return cosine_similarity(M[-1], M[:-1])[0]


def chatbot(intents, utterance, threshold=0.25) -> dict:
    if not isinstance(intents, list) or not 1 <= len(intents) <= 30:
        raise NlpError("Give 1 to 30 intents.")
    u = _text(utterance, "The message", 300)
    thr = float(threshold)
    if not 0 <= thr <= 1:
        raise NlpError("The threshold is between 0 and 1.")
    docs, owner = [], []
    for it in intents:
        if not isinstance(it, dict) or not str(it.get("name", "")).strip() or not str(it.get("reply", "")).strip():
            raise NlpError("Each intent needs a name and a reply.")
        ex = [str(x).strip() for x in (it.get("examples") or []) if str(x).strip()][:30]
        if not ex:
            raise NlpError(f"Intent '{it['name']}' needs example phrases.")
        for e in ex:
            docs.append(e); owner.append(it)
    try:
        sims = _tfidf(docs, u, stop=None)
    except ValueError:
        sims = np.zeros(len(docs))
    best: dict[str, float] = {}
    for s, it in zip(sims, owner):
        best[it["name"]] = max(best.get(it["name"], 0.0), float(s))
    ranking = sorted(best.items(), key=lambda kv: -kv[1])
    top_name, top = ranking[0]
    reply = next(i["reply"] for i in intents if i["name"] == top_name) if top >= thr else None
    return {"matched": top_name if reply else None, "score": round(top, 3), "reply": reply or "Sorry, I'm not sure I understood. Let me pass you to a person.", "handed_over": reply is None,
            "ranking": [{"intent": k, "score": round(v, 3)} for k, v in ranking],
            "lesson": "A simple chatbot matches the message to the closest intent and sends its reply. Anything below the confidence threshold goes to a person, which is what keeps a bot from answering wrongly with confidence.",
            "caution": "Word overlap only: 'when are you open' and 'what are your hours' share almost no words. Add several phrasings per intent, and test messages you didn't write."}


def rag(docs, question, k=2, min_score=0.1) -> dict:
    if not isinstance(docs, list) or not 1 <= len(docs) <= 100:
        raise NlpError("Give 1 to 100 passages.")
    ps = []
    for d in docs:
        for part in re.split(r"\n\s*\n|\n", str(d)):
            if part.strip():
                ps.append(part.strip()[:800])
    if not ps:
        raise NlpError("The passages are empty.")
    q = _text(question, "The question", 300)
    kk, ms = max(1, min(int(k), 5)), float(min_score)
    try:
        sims = _tfidf(ps, q, ngram=(1, 2))
    except ValueError:
        sims = np.zeros(len(ps))
    order = [int(i) for i in np.argsort(-sims)[:kk]]
    hits = [{"rank": r + 1, "score": round(float(sims[i]), 3), "passage": ps[i]} for r, i in enumerate(order)]
    ok = bool(hits) and hits[0]["score"] >= ms
    context = "\n".join(f"[{h['rank']}] {h['passage']}" for h in hits if h["score"] >= ms)
    prompt = ("Answer the question using only the passages below. Cite the passage number. If the passages do not contain the answer, say you don't know.\n\n"
              f"Passages:\n{context or '(none found)'}\n\nQuestion: {q}\nAnswer:")
    return {"retrieved": hits, "grounded": ok, "prompt": prompt, "advice": "Send this prompt to a model in the AI Lab." if ok else "Nothing relevant was found, so the right answer is 'I don't know'. Add the missing document or rephrase the question.",
            "lesson": "Retrieval-augmented generation (RAG) fetches relevant passages from a content store and puts them in the prompt with the question. The answer can cite its source and be updated by editing the store, with no retraining. It also lets the model say 'I don't know'.",
            "caution": "Retrieval here is keyword weighting (TF-IDF), not meaning. A question about 'spend' will not find a passage that says 'cost'; production RAG uses embeddings. If the retriever misses, a question that could be answered goes unanswered."}


def reference() -> dict:
    return {"pipeline": [{"step": "Tokenization", "what": "Split text into tokens."}, {"step": "Stemming / lemmatization", "what": "Reduce words to a stem or dictionary root."}, {"step": "Part-of-speech tagging", "what": "Label each token's grammatical role."},
                         {"step": "Named entity recognition", "what": "Find and type names, places, dates, money."}, {"step": "Intent and slots", "what": "Work out what the person wants and the details (NLU)."}],
            "uses": [{"use": "Machine translation", "note": "Needs context: a literal word-for-word translation of 'the spirit is willing but the flesh is weak' can come back as 'the vodka is good but the meat is rotten'."}, {"use": "Virtual assistants and chatbots", "note": "Turn speech or text into a command or an answer."},
                     {"use": "Sentiment analysis", "note": "Positive or negative, with sarcasm as the hard case."}, {"use": "Spam detection", "note": "Cues in the content and sender."}],
            "speech": [{"name": "Speech-to-text (STT)", "what": "Neural networks learn how words sound from voice samples and their transcripts, then transcribe new audio."}, {"name": "Text-to-speech (TTS)", "what": "A model learns a voice; a second network generates audio that a checker compares with the real voice until it sounds natural."}],
            "vision": [{"name": "Image classification", "what": "Put an image in a category."}, {"name": "Object detection", "what": "Find and locate objects (YOLO, Faster R-CNN)."}, {"name": "Image segmentation", "what": "Label every pixel."}],
            "chatbot_flow": ["Message arrives by web, phone or messaging app", "Speech converted to text if needed", "Intent and details recognised", "Dialogue manager picks the action", "Back-end call (stock, balance, weather API)", "Reply generated and sent"],
            "chatbot_benefits": ["Saves time", "Simple to build (often no code)", "Fast to launch", "Available all day", "Scales without extra staff"],
            "example_intents": [{"name": "hours", "examples": ["what time do you open", "opening hours", "when do you close", "are you open on monday"], "reply": "We are open Monday to Friday, 9:00 AM to 6:00 PM."},
                                {"name": "stock", "examples": ["do you have yellow roses", "are tulips in stock", "do you sell succulents"], "reply": "Let me check our stock for you."},
                                {"name": "contact", "examples": ["how do I contact you", "what is your phone number", "email address"], "reply": "Call 555-0100 or email hello@example.com."}],
            "example_docs": ["Saturn has 146 confirmed moons, the most of any planet, as of the latest count.\nJupiter has 95 confirmed moons. Counts change as new moons are found.", "Refunds are issued to the original payment method within 5 business days.\nShipping is free on orders over $50."],
            "example_classifier": [{"text": "I love this, works great", "label": "positive"}, {"text": "fantastic and easy to use", "label": "positive"}, {"text": "really helpful and fast", "label": "positive"}, {"text": "terrible, it broke in a day", "label": "negative"}, {"text": "awful support, total waste", "label": "negative"}, {"text": "slow and buggy, very disappointed", "label": "negative"}],
            "not_built": ["Speech-to-text and text-to-speech, translation and embedding-based (semantic) search need trained models this app does not have.", "The lemmatizer, tagger and entity finder use short word lists: they teach the idea but are not production NLP."]}
