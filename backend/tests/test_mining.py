import random

import pytest

from tests.conftest import csv_file


@pytest.fixture()
def blobs(client):
    """Three clear groups in (x, y), plus a region and a label that depends on the group."""
    rnd = random.Random(3)
    lines = ["id,x,y,z,region,churn"]
    centers = {"A": (10, 10), "B": (50, 12), "C": (30, 60)}
    i = 0
    for name, (cx, cy) in centers.items():
        for _ in range(80):
            i += 1
            churn = "yes" if (name == "C" and rnd.random() < 0.85) or (name != "C" and rnd.random() < 0.08) else "no"
            lines.append(f"{i},{cx + rnd.gauss(0, 2):.3f},{cy + rnd.gauss(0, 2):.3f},{rnd.gauss(0, 1):.3f},{'W' if name == 'A' else 'E' if name == 'B' else 'N'},{churn}")
    assert client.post("/api/data/import", files=csv_file("\n".join(lines) + "\n", "blobs.csv"), data={"mode": "replace"}).status_code == 200
    return "blobs"


def test_cluster_finds_three_groups(client, blobs):
    r = client.post("/api/stats/cluster", json={"source": blobs, "features": ["x", "y"]}).json()
    assert r["k"] == 3 and r["silhouette"] > 0.6 and r["strength"] == "strong"
    assert sorted(g["size"] for g in r["groups"]) == [80, 80, 80] and sum(g["pct"] for g in r["groups"]) == pytest.approx(100, abs=0.5)
    assert len(r["points"]) == 240 // 1 or len(r["points"]) <= 600
    fixed = client.post("/api/stats/cluster", json={"source": blobs, "features": ["x", "y"], "k": 2}).json()
    assert fixed["k"] == 2 and len(fixed["groups"]) == 2
    assert client.post("/api/stats/cluster", json={"source": blobs, "features": ["x"]}).status_code == 422
    assert client.post("/api/stats/cluster", json={"source": blobs, "features": ["x", "region"]}).status_code == 400
    assert client.post("/api/stats/cluster", json={"source": blobs, "features": ["x", "y"], "filters": [{"column": "x", "op": "lt", "value": 0}]}).status_code == 400


def test_associations_pairs_and_guards(client):
    rows = ["basket,item"]
    rnd = random.Random(5)
    for b in range(200):
        items = {"bread", "butter"} if b % 2 == 0 else {rnd.choice(["milk", "eggs", "jam"])}
        if rnd.random() < 0.3:
            items.add("coffee")
        rows += [f"B{b},{i}" for i in items]
    client.post("/api/data/import", files=csv_file("\n".join(rows) + "\n", "baskets.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/associations", json={"source": "baskets", "basket_col": "basket", "item_col": "item", "min_support_pct": 5}).json()
    top = r["rules"][0]
    assert {top["if"], top["then"]} == {"bread", "butter"} and top["confidence_pct"] == 100.0 and top["lift"] == 2.0
    assert r["baskets"] == 200 and r["multi_item_baskets"] >= 100
    assert client.post("/api/stats/associations", json={"source": "baskets", "basket_col": "item", "item_col": "item"}).status_code == 400
    assert client.post("/api/stats/associations", json={"source": "baskets", "basket_col": "basket", "item_col": "item", "min_support_pct": 0}).status_code == 422


def test_outliers_flags_planted_row(client, blobs):
    csv = "id,a,b\n" + "\n".join(f"{i},{random.Random(i).gauss(50, 3):.2f},{random.Random(i + 999).gauss(20, 2):.2f}" for i in range(200)) + "\n999,95,2\n"
    client.post("/api/data/import", files=csv_file(csv, "pts.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/outliers", json={"source": "pts", "features": ["a", "b"], "label_col": "id", "top": 5}).json()
    assert r["outliers"][0]["label"] == "999" and r["outliers"][0]["stranger_than_pct"] == 100.0
    assert r["flagged"] >= 1 and abs(r["outliers"][0]["z"]) > 3
    assert client.post("/api/stats/outliers", json={"source": "pts", "features": ["a"], "filters": [{"column": "a", "op": "gt", "value": 1000}]}).status_code == 400


def test_predict_classification_regression_and_guards(client, blobs):
    base = {"source": blobs, "target": "churn", "x_numeric": ["x", "y", "z"], "x_categorical": ["region"]}
    for model in ("logistic", "forest", "boosting"):
        r = client.post("/api/stats/predict", json={**base, "model": model, "positive": "yes"}).json()
        assert r["kind"] == "classification" and r["metrics"]["accuracy_test"] > r["metrics"]["baseline_accuracy"], model
    assert r["metrics"]["auc"] > 0.8 and r["confusion"]["labels"] == ["no", "yes"] or set(r["confusion"]["labels"]) == {"no", "yes"}
    assert r["importance"][0]["input"] in ("region", "x", "y")
    c = client.post("/api/stats/predict", json={**base, "model": "forest", "positive": "yes", "case": {"x": 30, "y": 60, "z": 0, "region": "N"}}).json()
    assert c["case"]["prediction"] == "yes" and c["case"]["probabilities"]["yes"] > 0.5
    reg = client.post("/api/stats/predict", json={"source": blobs, "target": "y", "x_numeric": ["x"], "x_categorical": ["region"], "model": "forest"}).json()
    assert reg["kind"] == "regression" and reg["metrics"]["r2_test"] > 0.8 and reg["metrics"]["better_than_baseline"]
    noise = client.post("/api/stats/predict", json={"source": blobs, "target": "z", "x_numeric": ["x"], "model": "linear"}).json()
    assert noise["metrics"]["better_than_baseline"] is False and noise["warnings"]
    assert client.post("/api/stats/predict", json={**base, "model": "nope"}).status_code == 400
    assert client.post("/api/stats/predict", json={**base, "x_numeric": ["churn"]}).status_code == 400
    assert client.post("/api/stats/predict", json={"source": blobs, "target": "x"}).status_code == 400
    assert client.post("/api/stats/predict", json={**base, "filters": [{"column": "y", "op": "gt", "value": 1000}]}).status_code == 400  # nothing left to learn from
    assert client.get("/api/stats/ml-models").json()["classification"]["forest"]


def _tree_data(client, name="tree_t"):
    import io
    import random
    random.seed(5)
    rows = ["age,income,region,bought,customer,step,day"]
    for i in range(300):
        age, inc = random.randint(18, 70), random.randint(20, 150)
        reg = random.choice(["N", "S", "E"])
        p = 0.85 if inc > 80 and age < 45 else 0.1
        rows.append(f"{age},{inc},{reg},{'yes' if random.random() < p else 'no'},c{i % 40},{['visit', 'cart', 'buy'][i // 40 % 3]},2024-01-{1 + i // 40 % 28:02d}")
    r = client.post("/api/data/import", data={"table": name, "mode": "replace"}, files={"file": ("t.csv", io.BytesIO("\n".join(rows).encode()), "text/csv")})
    assert r.status_code == 200, r.text


def test_decision_tree_is_readable_and_honest(client):
    _tree_data(client)
    r = client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age", "income"], "x_categorical": ["region"], "max_depth": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "classification" and d["tree"]["children"] and d["metrics"]["better_than_baseline"] is True
    assert d["importance"][0]["input"] in ("income", "age")
    assert client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["bought"]}).status_code in (400, 422)
    assert client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age"], "max_depth": 9}).status_code == 422
    assert 0 <= d["metrics"]["sensitivity"] <= 1 and 0 <= d["metrics"]["specificity"] <= 1 and [x["cost"] for x in d["cost_sweep"]] == [1, 2, 4, 9]
    assert 0.5 <= d["metrics"]["auc"] <= 1 and d["roc"][0] == {"fpr": 0.0, "tpr": 0.0} and 0 <= d["metrics"]["p_vs_baseline"] <= 1
    hi = client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age"], "max_depth": 2, "focus_cost": 9}).json()["metrics"]
    lo = client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age"], "max_depth": 2, "focus_cost": 1}).json()["metrics"]
    assert hi["sensitivity"] >= lo["sensitivity"]
    assert client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age"], "focus_cost": 50}).status_code == 422
    assert client.post("/api/stats/tree", json={"source": "tree_t", "target": "bought", "x_numeric": ["age"], "focus_class": "nope"}).status_code == 400
    reg = client.post("/api/stats/tree", json={"source": "tree_t", "target": "income", "x_numeric": ["age"], "max_depth": 2})
    assert reg.status_code == 200 and reg.json()["kind"] == "regression"


def test_sequences(client):
    _tree_data(client)
    r = client.post("/api/stats/sequences", json={"source": "tree_t", "entity_col": "customer", "event_col": "step", "date_col": "day"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["entities_used"] > 0 and d["steps"] and d["steps"][0]["probability"] <= 1
    assert client.post("/api/stats/sequences", json={"source": "tree_t", "entity_col": "step", "event_col": "step", "date_col": "day"}).status_code == 400
