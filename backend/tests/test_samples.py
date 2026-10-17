import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    for it in client.get("/api/samples").json()["items"]:
        client.delete(f"/api/samples/items/{it['id']}")
    yield


def test_starters_build_a_labelled_page():
    for n in range(4):
        assert client.post(f"/api/samples/starters/{n}").status_code == 200
    client.put("/api/samples/profile", json={"name": "Practice Tech", "services": [{"name": "IT repair", "blurb": "Fixes that last."}], "contact": "hello@example.com"})
    h = client.get("/api/samples/html").text
    assert h.count("Sample · practice work · made-up data") == 4
    assert "Practice Tech" in h and "$382.50" in h
    assert "No client information" in h and "<script" not in h and "http://" not in h and "https://" not in h
    assert "hello@example.com" in h                      # the owner's own contact line is allowed
    assert "attachment" in client.get("/api/samples/html?download=true").headers["content-disposition"]


def test_quote_total_is_computed_not_trusted():
    r = client.post("/api/samples/items", json={"kind": "quote", "title": "Q", "lines": [{"desc": "A", "qty": 2, "rate": 10.5}, {"desc": "B", "qty": 1, "rate": 4}], "total": 99999})
    assert r.status_code == 200 and r.json()["items"][0]["total"] == 25.0


def test_client_data_and_reviews_are_refused():
    base = {"kind": "before_after", "title": "x", "before": "b", "after": "a", "what_i_did": "w"}
    assert client.post("/api/samples/items", json={**base, "before": "Customer jane@acme.com had a slow PC"}).status_code == 400
    assert client.post("/api/samples/items", json={**base, "what_i_did": "Called 702-555-0134 first"}).status_code == 400
    assert client.post("/api/samples/items", json={**base, "after": "A five-star testimonial"}).status_code == 400
    assert client.post("/api/samples/items", json={**base, "kind": "testimonial"}).status_code == 400
    assert client.put("/api/samples/profile", json={"about": "Email me at a@b.com"}).status_code == 400


def test_html_escapes_everything():
    client.post("/api/samples/items", json={"kind": "checklist", "title": "<script>alert(1)</script>", "steps": ["<img src=x onerror=1>"]})
    h = client.get("/api/samples/html").text
    assert "<script>alert" not in h and "&lt;script&gt;" in h and "<img src=x" not in h


def test_edit_move_delete_and_limits():
    a = client.post("/api/samples/starters/0").json()["items"][0]["id"]
    b = client.post("/api/samples/starters/2").json()["items"][1]["id"]
    assert [i["id"] for i in client.post(f"/api/samples/items/{b}/move/-1").json()["items"]] == [b, a]
    upd = {"kind": "checklist", "title": "New", "steps": ["one"]}
    assert client.put(f"/api/samples/items/{a}", json=upd).json()["items"][1]["title"] == "New"
    assert client.delete(f"/api/samples/items/{a}").status_code == 200
    assert client.delete(f"/api/samples/items/{a}").status_code == 404
    assert client.post("/api/samples/starters/9").status_code == 404
    assert client.post("/api/samples/items", json={"kind": "quote", "title": "q", "lines": [{"desc": "x", "qty": 0, "rate": 1}]}).status_code == 400
