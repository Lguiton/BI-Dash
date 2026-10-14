import io
import random


def _load(client):
    random.seed(3)
    rows = ["g,x,y,z"]
    for i in range(120):
        g = "A" if i % 3 == 0 else "B" if i % 3 == 1 else "C"
        x = random.gauss(10 + (3 if g == "A" else 0), 2)
        rows.append(f"{g},{x:.3f},{2 * x + random.gauss(0, 1):.3f},{random.gauss(0, 1):.3f}")
    r = client.post("/api/data/import", data={"table": "inf", "mode": "replace"}, files={"file": ("i.csv", io.BytesIO("\n".join(rows).encode()), "text/csv")})
    assert r.status_code == 200


def test_distribution(client):
    _load(client)
    d = client.post("/api/stats/distribution", json={"source": "inf", "column": "x"}).json()
    assert d["n"] == 120 and d["interval"]["low"] < d["central"]["mean"] < d["interval"]["high"]
    assert sum(h["count"] for h in d["histogram"]) == 120 and d["dispersion"]["range"] > 0
    assert client.post("/api/stats/distribution", json={"source": "inf", "column": "g"}).status_code == 400
    assert client.post("/api/stats/distribution", json={"source": "inf", "column": "x", "confidence": 0.5}).status_code == 400


def test_compare_two_and_many(client):
    _load(client)
    two = client.post("/api/stats/compare", json={"source": "inf", "value_col": "x", "group_col": "g", "groups": ["A", "B"]}).json()
    assert two["test"]["name"].startswith("Welch") and two["test"]["p"] < 0.001 and two["test"]["difference"] > 1
    many = client.post("/api/stats/compare", json={"source": "inf", "value_col": "x", "group_col": "g"}).json()
    assert many["test"]["name"].startswith("One-way ANOVA") and many["test"]["p"] < 0.001
    assert client.post("/api/stats/compare", json={"source": "inf", "value_col": "x", "group_col": "g", "groups": ["A"]}).status_code == 400
    assert client.post("/api/stats/compare", json={"source": "inf", "value_col": "g", "group_col": "g"}).status_code == 400


def test_correlation(client):
    _load(client)
    c = client.post("/api/stats/correlation", json={"source": "inf", "columns": ["x", "y", "z"]}).json()
    top = c["pairs"][0]
    assert {top["a"], top["b"]} == {"x", "y"} and top["pearson"] > 0.9 and top["ci_low"] < top["pearson"] < top["ci_high"]
    assert c["scatter"] is None
    two = client.post("/api/stats/correlation", json={"source": "inf", "columns": ["x", "y"]}).json()
    assert len(two["scatter"]) == 120 or len(two["scatter"]) <= 500
    assert client.post("/api/stats/correlation", json={"source": "inf", "columns": ["x", "x"]}).status_code == 400
