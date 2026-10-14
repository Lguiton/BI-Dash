import json

import pytest

from app.services import agents, ml_by_hand as h
from app.services.providers import Call, Turn
from tests.test_math_and_shortcuts import Fake


def test_every_preset_runs_and_agrees_with_the_library():
    for p in h.PRESETS:
        if p["id"] == "lathe3":
            continue
        r = h.run(p["method"], p["data"], p.get("query", ""), p.get("params"))
        assert r["steps"] and r["check"]["agrees"] in (True, None), p["id"]
        assert r["check"]["agrees"] is True or p["method"] == "forest", p["id"]


def test_taxi_and_lathe_numbers():
    t = h.run("linear", "x,y\n2,100\n4,150\n6,200\n8,250\n10,300", "15")
    assert t["answer"] == {"slope": 25.0, "intercept": 50.0, "prediction": 425.0} and t["metrics"]["R2"] == 1.0
    m = h.run("multiple", [p for p in h.PRESETS if p["id"] == "lathe"][0]["data"], "160,0.4,1.6")
    assert [round(m["answer"][k], 6) for k in ("a1", "a2", "a3", "b")] == [2, 100, 50, -40] and round(m["answer"]["prediction"], 6) == 400


def test_course_example_with_too_few_rows_is_explained():
    with pytest.raises(h.HandError) as e:
        h.run("multiple", "speed,feed,depth,force\n100,0.2,1.0,200\n120,0.25,1.2,250\n140,0.3,1.5,300")
    assert "3 equations" in e.value.message and "4 unknowns" in e.value.message


def test_dependent_features_are_caught_and_inputs_validated():
    with pytest.raises(h.HandError):
        h.run("multiple", "a,b,y\n1,2,5\n2,4,6\n3,6,9\n4,8,12")           # b is always 2*a
    for bad in (("linear", "x,y\n1,2\n1,3"), ("knn", "a,b\n1,x"), ("linear", "x\n1"), ("nope", "x,y\n1,2"), ("linear", "x,y\n1,abc\n2,3")):
        with pytest.raises(h.HandError):
            h.run(bad[0], bad[1], "1")
    with pytest.raises(h.HandError):
        h.run("linear", "x,y\n" + "\n".join(f"{i},{i}" for i in range(80)))


def test_knn_tie_rule_and_tree_words():
    r = h.run("knn", "a,c\n1,x\n2,y\n3,x\n4,y", "2.5", {"k": 2})
    assert "Tie" in json.dumps(r["steps"])
    t = h.run("tree", "weather,windy,play\nsunny,no,yes\nsunny,yes,no\nrain,no,yes\nrain,yes,no", "rain,no")
    assert t["answer"]["prediction"] == "yes" and t["check"]["agrees"] is None


def test_endpoints_and_sandbox_does_not_write(client):
    d = client.get("/api/ml-hand/presets").json()
    assert len(d["presets"]) >= 6 and d["limits"]["rows"] == 60
    before = client.get("/api/audit").json()
    r = client.post("/api/ml-hand/run", json={"method": "linear", "data": "x,y\n1,2\n2,4\n3,6", "query": "4"})
    assert r.status_code == 200 and r.json()["answer"]["prediction"] == 8
    assert client.post("/api/ml-hand/run", json={"method": "linear", "data": "x\n1"}).status_code == 400
    client.post("/api/biz-packs/repair-jobs/sample")
    cols = client.get("/api/biz-packs/repair-jobs/browse").json()["columns"]
    fp = client.get("/api/ml-hand/from-pack", params={"pid": "repair-jobs", "columns": ",".join(cols[:2]), "rows": 5})
    assert fp.status_code == 200 and fp.json()["rows"] == 5
    assert client.get("/api/ml-hand/from-pack", params={"pid": "repair-jobs", "columns": "nope,zip"}).status_code == 400


def test_ml_agent_uses_the_tool_and_others_do_not(client):
    f = Fake([Turn("", [Call("1", "ml_by_hand", {"method": "linear", "data": "x,y\n2,100\n4,150\n6,200", "query": "8"})]), Turn("The fare for 8 km is 250.")])
    r = agents.chat("ml", "work the taxi example by hand", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "ml_by_hand" in [t["name"] for t in f.tools] and "250" in str(f.results[0]) and r.reply.startswith("The fare")
    g = Fake([Turn("ok")])
    agents.chat("itsupport", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "ml_by_hand" not in [t["name"] for t in g.tools]
