from tests.test_readiness import _table


def test_issue_lifecycle(client):
    _table()
    r = client.post("/api/pipeline/issues", json={"role": "analyst", "table": "shop", "column": "label", "summary": "Labels are blank on some rows", "severity": "high", "expected": "No blanks"})
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    d = client.get("/api/pipeline/issues").json()
    assert d["open"] == 1 and d["issues"][0]["id"] == iid
    u = client.patch(f"/api/pipeline/issues/{iid}", json={"status": "fixed", "reply": "Fixed upstream"}).json()
    assert u["status"] == "fixed" and u["reply"] == "Fixed upstream"
    assert client.get("/api/pipeline/issues").json()["open"] == 0
    assert client.get("/api/pipeline/issues", params={"status": "open"}).json()["issues"] == []
    assert client.delete(f"/api/pipeline/issues/{iid}").status_code == 200
    assert client.get("/api/pipeline/issues").json()["total"] == 0


def test_issue_validation(client):
    _table()
    p = lambda **k: client.post("/api/pipeline/issues", json=k)
    assert p(summary="x").status_code == 400
    assert p(summary="long enough text", role="boss").status_code == 400
    assert p(summary="long enough text", severity="huge").status_code == 400
    assert p(summary="long enough text", table="nope").status_code == 404
    assert p(summary="long enough text", table="shop", column="zzz").status_code == 404
    assert p(summary="long enough text", column="label").status_code == 400
    assert client.patch("/api/pipeline/issues/missing", json={"status": "fixed"}).status_code == 404
    iid = p(summary="long enough text").json()["id"]
    assert client.patch(f"/api/pipeline/issues/{iid}", json={"status": "weird"}).status_code == 400


def test_open_issues_sort_by_severity(client):
    for sev in ("low", "high", "medium"):
        client.post("/api/pipeline/issues", json={"summary": f"issue {sev} case", "severity": sev})
    assert [i["severity"] for i in client.get("/api/pipeline/issues").json()["issues"]] == ["high", "medium", "low"]
