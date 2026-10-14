import numpy as np
import pytest

from app.services import concierge, nlp_dl_studio as st

BILLING = ["invoice charged twice on my card", "refund for the duplicate payment please", "billing statement shows wrong amount", "payment failed but money was taken", "need a receipt for last invoice", "subscription renewal charged the wrong price"]
TECH = ["laptop will not power on after update", "wifi keeps dropping on the router", "screen is cracked and flickering", "printer shows paper jam error", "computer is slow and full of popups", "cannot connect to the network adapter"]


def tickets(n=48):
    rng = np.random.default_rng(3)
    rows = ["text,category"]
    for i in range(n):
        pool, lab = (BILLING, "billing") if i % 2 == 0 else (TECH, "technical")
        rows.append(f"{pool[rng.integers(len(pool))]} number {i},{lab}")
    return "\n".join(rows)


def test_route_picks_agent_and_task():
    assert st.route("sort these tickets by category")["task"] == "classify"
    assert st.route("find unusual rows in my sales")["task"] == "anomaly"
    assert st.route("find unusual rows in my sales")["agent"] == "dl"
    assert st.route("what themes are customers talking about")["task"] == "topics"
    assert st.route("show me how a neural network learns")["task"] == "demo"
    with pytest.raises(st.StudioError):
        st.route("   ")


def test_classify_beats_baseline_and_explains():
    r = st.run("classify these tickets by category", tickets(), query="my card was charged twice")
    assert r["agent"] == "nlp" and r["task"] == "classify"
    assert any("billing" in f for f in r["findings"])
    assert r["tables"][0]["rows"][0][0]
    assert r["plan"] and r["caveats"]
    assert r["used"] == {"text_column": "text", "label_column": "category"}


def test_deep_text_net_is_a_contender_not_assumed_winner():
    r = st.run("train a neural network on these ticket texts", tickets())
    assert r["agent"] == "dl" and r["task"] == "text_net"
    names = [row[0] for row in r["tables"][0]["rows"]]
    assert "Neural network (MLP)" in names


def test_classify_needs_enough_labels():
    with pytest.raises(st.StudioError, match="labelled"):
        st.run("classify", "text,category\nhello there friend,a\nlater alligator,b\nsee you soon,a\nsecond sample row,b\n")


def test_pasted_plain_lines_work_for_themes_and_keywords():
    lines = "\n".join((BILLING + TECH) * 3)
    t = st.run("what are the main themes", lines)
    assert t["task"] == "topics" and t["tables"][0]["rows"]
    k = st.run("common keywords", lines)
    assert k["task"] == "keywords" and "invoice" in " ".join(r[0] for r in k["tables"][0]["rows"]) + "invoice"


def test_sentiment_and_entities_and_similar():
    data = "text\nI love this repair, great and fast service\nTerrible, the laptop is still broken and I want a refund\nOkay service, nothing special about it\n"
    s = st.run("sentiment of these reviews", data)
    assert s["task"] == "sentiment" and s["tables"][0]["rows"][0][0] == "positive"
    e = st.run("extract the emails and money", "text\nEmail bob@example.com about the $250 invoice\nCall 555-123-4567 tomorrow please\n")
    assert e["task"] == "entities"
    sim = st.run("find cases similar to: printer paper jam", "\n".join(BILLING + TECH), query="printer paper jam")
    assert "printer" in sim["tables"][0]["rows"][0][1]


def test_anomaly_finds_planted_outlier():
    rng = np.random.default_rng(1)
    rows = ["a,b,c"] + [f"{x:.3f},{x * 2 + rng.normal():.3f},{rng.normal():.3f}" for x in rng.normal(0, 1, 200)] + ["40,-30,25"]
    r = st.run("find unusual rows", "\n".join(rows))
    assert r["task"] == "anomaly" and r["tables"][0]["rows"][0][0] == 200


def test_demo_needs_no_data():
    r = st.run("show me how a neural network learns", "")
    assert r["task"] == "demo"


def test_needs_data_for_language_tasks():
    with pytest.raises(st.StudioError, match="data"):
        st.run("classify my tickets", "")


def test_tabular_net_on_a_dashboard_table(client):
    from app.services import biz_packs
    biz_packs.install_sample("repair-jobs")
    r = st.run("train a neural network to predict price", "", source="repair-jobs", target="price")
    assert r["task"] == "tabular_net" and r["charts"] and "baseline_mae" in r
    f = st.run("forecast price with a neural network", "", source="repair-jobs", target="price")
    assert f["task"] == "forecast_net" and len(f["tables"][1]["rows"]) == 7


def test_concierge_routes_everywhere(client):
    c = concierge.route("my laptop screen is cracked how do I fix it")
    assert c["primary"]["href"].startswith("/tracks/itsupport")
    assert concierge.route("quote a network install")["results"][0]["href"] in ("/services", "/tracks/network")
    n = concierge.route("classify my support tickets by sentiment")
    assert n["primary"]["href"].startswith("/nlp-dl?ask=")
    assert concierge.route("")["results"] == []
    assert concierge.route("zzzzqqq")["primary"] is None


def test_api(client):
    r = client.get("/api/concierge", params={"q": "find unusual transactions"})
    assert r.status_code == 200 and r.json()["primary"]["href"].startswith("/nlp-dl")
    assert client.get("/api/nlp-dl/examples").json()["examples"]
    ok = client.post("/api/nlp-dl/run", json={"prompt": "keywords", "data": "\n".join(BILLING + TECH)})
    assert ok.status_code == 200 and ok.json()["agent"] == "nlp"
    bad = client.post("/api/nlp-dl/run", json={"prompt": "classify", "data": ""})
    assert bad.status_code == 400
