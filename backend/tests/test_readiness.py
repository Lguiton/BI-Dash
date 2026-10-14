from app.services import datasets, readiness
from app.services.db import get_cursor


def _table(name="shop", dup=False):
    datasets.ensure_registry()
    rows = "(1,'a',DATE '2020-01-01'),(2,'b',DATE '2020-01-02'),(3,NULL,DATE '2020-01-03')" + (",(3,NULL,DATE '2020-01-03')" if dup else "")
    with get_cursor() as cur:
        cur.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM (VALUES {rows}) t(id,label,day)")
        cur.execute("DELETE FROM user_tables WHERE table_name = ?", [name])
        cur.execute("INSERT INTO user_tables VALUES (?, ?, 'test', 3, '[]', now(), now())", [name, name])


def test_scorecard_scores_and_explains(client):
    _table()
    d = client.get("/api/pipeline/readiness").json()
    t = next(x for x in d["tables"] if x["table"] == "shop")
    assert 0 <= t["score"] < 80 and not t["ready"]
    assert any("owner" in f for f in t["fix"]) and any("old" in f for f in t["fix"])
    assert set(t["by_word"]) == {"accurate", "reliable", "compliant", "accessible"}
    assert sum(w["weight"] for w in d["weights"]) == 100
    # fixing the catalog gaps raises the score
    before = t["score"]
    client.put("/api/governance/assets/shop", json={"owner": "Ops", "steward": "Lam", "description": "test", "classification": "internal"})
    after = next(x for x in client.get("/api/pipeline/readiness").json()["tables"] if x["table"] == "shop")["score"]
    assert after > before


def test_review_detects_changes_and_keeps_history(client):
    _table()
    first = client.post("/api/pipeline/readiness/review").json()
    assert first["first_review"] is True and first["worse"] == []
    client.put("/api/governance/assets/shop", json={"owner": "Ops", "steward": "Lam", "description": "d", "classification": "internal"})
    second = client.post("/api/pipeline/readiness/review").json()
    assert any(b["table"] == "shop" for b in second["better"])
    _table(dup=True)   # duplicate row appears
    third = client.post("/api/pipeline/readiness/review").json()
    assert any(w["table"] == "shop" for w in third["worse"]) and "Got worse" in third["summary"]
    assert len(client.get("/api/pipeline/readiness").json()["reviews"]) == 3


def test_weekly_tick(client):
    _table()
    assert readiness.due() is True
    assert readiness.tick() == ["health_review"]
    assert readiness.due() is False and readiness.tick() == []
    client.put("/api/pipeline/readiness/schedule", json={"enabled": False})
    assert readiness.due() is False
