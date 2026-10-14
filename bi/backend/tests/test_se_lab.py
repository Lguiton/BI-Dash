from app.services import se_lab as s
import pytest


def test_versions():
    assert s.compare("1.2.3", "1.10.0")["result"] == -1
    assert s.compare("1.0.0-alpha", "1.0.0")["result"] == -1
    assert s.bump("1.2.3", "minor")["to"] == "1.3.0"
    assert s.bump("1.2.3", "major")["to"] == "2.0.0"
    assert s.satisfies("1.4.2", "^1.2.0")["matches"] is True
    assert s.satisfies("2.0.0", "^1.2.0")["matches"] is False
    assert s.satisfies("1.2.9", "~1.2")["matches"] is True
    with pytest.raises(s.SeError):
        s.parse_version("banana")


def test_story_and_trace():
    r = s.check_story("As a user I want fast login so that I save time")
    assert not r["ok"] and "fast" in r["issues"][0]
    t = s.traceability([{"id": "R1", "priority": "must"}, {"id": "R2", "priority": "must"}], [{"id": "T1", "covers": ["R1"]}, {"id": "T2", "covers": []}, {"id": "T3", "covers": ["R9"]}])
    assert t["coverage_pct"] == 50.0 and t["must_have_gaps"] == ["R2"] and len(t["orphan_tests"]) == 2


def test_choices():
    assert s.choose_method("high", "often", False, False, "weeks", "small")["pick"] == "Agile"
    assert s.choose_method("low", "rare", True, True, "years", "large")["pick"] in ("V-model", "Waterfall")
    assert s.choose_method("low", "rare", True, False, "years", "large")["pick"] == "V-model"
    with pytest.raises(s.SeError):
        s.choose_method("x", "often", False, False, "weeks", "small")
    o = s.prioritize_regression([{"id": "a"}, {"id": "b", "uses_changed_code": True, "failed_recently": True}])
    assert o["order"][0]["id"] == "b"
    assert s.recommend_architecture("hundreds", "solo", False, False, False, False)["pick"] in ("2-tier (client-server)", "3-tier")
    assert s.recommend_architecture("millions", "small", False, True, False, False)["pick"] == "Peer-to-peer"


def test_topology():
    one = s.topology(web_servers=1, app_servers=1, db_replicas=0, load_balancer=False)
    two = s.topology(web_servers=2, app_servers=2, db_replicas=1)
    assert one["single_points_of_failure"] and len(two["single_points_of_failure"]) <= len(one["single_points_of_failure"])
    assert two["illustrative_availability_pct"] >= one["illustrative_availability_pct"]


def test_states_classes():
    st = s.check_states(["A", "B", "C"], [{"from": "A", "event": "go", "to": "B"}], "A", ["B"])
    assert any("'C'" in i["text"] for i in st["issues"]) and not st["ok"]
    with pytest.raises(s.SeError):
        s.check_states(["A", "B"], [{"from": "A", "event": "", "to": "B"}], "A")
    c = s.class_diagram([{"name": "Animal", "methods": ["speak"]}, {"name": "Dog", "parent": "Animal"}])
    assert "Animal <|-- Dog" in c["mermaid"]
    with pytest.raises(s.SeError):
        s.class_diagram([{"name": "A", "parent": "B"}, {"name": "B", "parent": "A"}])


def test_flow():
    r = s.pseudocode_to_flow(s.reference()["example_pseudocode"])
    assert r["mermaid"].startswith("flowchart TD") and any(n["kind"] == "decision" for n in r["nodes"])
    assert "n7 --> n5" in r["mermaid"]
    with pytest.raises(s.SeError):
        s.pseudocode_to_flow("IF x > 1 THEN\nPRINT 1")
    with pytest.raises(s.SeError):
        s.pseudocode_to_flow("END IF")


def test_reference_and_routes(client):
    ref = client.get("/api/se").json()
    assert len(ref["phases"]) == 6 and ref["slips"]
    assert client.post("/api/se/version/compare", json={"a": "1.0.0", "b": "1.0.1"}).json()["result"] == -1
    assert client.post("/api/se/version/compare", json={"a": "x", "b": "1.0.1"}).status_code == 400
    ex = ref["example_states"]
    assert client.post("/api/se/states", json=ex | {"start": ex["start"]}).json()["ok"]
    assert client.post("/api/se/flow", json={"src": ref["example_pseudocode"]}).status_code == 200
    assert client.post("/api/se/topology", json={}).status_code == 200
