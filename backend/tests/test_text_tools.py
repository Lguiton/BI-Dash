import pytest

from app.services import text_tools as tt

BILL = ["invoice charged twice", "refund my payment please", "wrong amount on my bill", "billing error on invoice", "charged me after cancel", "payment failed but charged", "need receipt for payment", "overcharged on my invoice"]
TECH = ["app crashes on launch", "cannot log in password reset", "error message when saving", "page will not load", "login button does nothing", "app freezes on upload", "bug in the export feature", "crash when opening settings"]


@pytest.fixture()
def ready(client):
    tt.set_create("tickets", ["billing", "tech"])
    rows = "\n".join([f"billing,{t}" for t in BILL] + [f"tech\t{t}" for t in TECH])
    tt.add_from_text("tickets", rows)
    return "tickets"


def test_labeling_and_report(ready):
    s = tt.set_list()[0]
    assert s["examples"] == 16 and s["per_label"] == {"billing": 8, "tech": 8}
    r = tt.train_report(ready)
    assert r["accuracy"] > r["baseline_accuracy"] and r["useful"] and r["failures"] is not None and "Only 16 examples" in r["caution"]
    assert {p["label"] for p in r["per_label"]} == {"billing", "tech"} and r["top_words"]
    c = tt.classify(ready, ["I was charged twice on my invoice", "the app crashes when I log in", "zzz qqq"])
    assert c["results"][0]["label"] == "billing" and c["results"][1]["label"] == "tech"
    assert "needs_human" in c["results"][2]


def test_set_validation(client):
    with pytest.raises(tt.TextError):
        tt.set_create("x", ["only"])
    tt.set_create("x", ["a", "b"])
    with pytest.raises(tt.TextError):
        tt.set_create("x", ["a", "b"])
    assert tt.add_examples("x", [{"text": "hi", "label": "zzz"}, {"text": "", "label": "a"}])["skipped"] == 2
    with pytest.raises(tt.TextError):
        tt.train_report("x")
    with pytest.raises(tt.TextError):
        tt.add_from_text("x", "no separator here")


def test_extraction_scoring():
    rules = [{"field": "invoice", "pattern": r"invoice\s*#?\s*(\d+)"}, {"field": "total", "pattern": r"total[: ]+\$?([\d.]+)"}]
    docs = [{"text": "Invoice #123\nTotal: $45.50", "expected": {"invoice": "123", "total": "45.50"}}, {"text": "Invoice 77\nTotal due 9", "expected": {"invoice": "77", "total": "9.00"}}, {"text": "nothing", "expected": {"invoice": "5"}}]
    r = tt.extract_test(rules, docs)
    inv = next(s for s in r["summary"] if s["field"] == "invoice")
    assert inv["correct"] == 2 and inv["missed"] == 1 and inv["recall_pct"] == 66.7
    tot = next(s for s in r["summary"] if s["field"] == "total")
    assert tot["correct"] == 1 and tot["missed"] == 1
    with pytest.raises(tt.TextError):
        tt.extract_test([{"field": "x", "pattern": "(a+)+"}], docs)
    with pytest.raises(tt.TextError):
        tt.extract_test([], docs)


def test_experiments(client):
    tt.exp_log("tfidf", {"ngram": "1-2"}, {"f1": 0.8})
    tt.exp_log("tfidf2", {"ngram": "1-3"}, {"f1": 0.85}, "better")
    assert [e["name"] for e in tt.exp_list("f1")] == ["tfidf2", "tfidf"]
    assert "metric:f1" in tt.exp_csv() and "param:ngram" in tt.exp_csv()
    with pytest.raises(tt.TextError):
        tt.exp_log("x", {}, {"f1": "abc"})
    with pytest.raises(tt.TextError):
        tt.exp_log("x", {}, {})
