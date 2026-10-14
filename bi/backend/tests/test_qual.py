from tests.conftest import csv_file

EMAILS = """From: a
I ordered a Gadget and it never arrived. Very frustrated, this is the second delay.

---
Love the new subscription! Support was fast and helpful, saved us hours.

---
Charged twice on the 14th. Please refund, the billing error is not good.

---
Dashboard is slow on mobile. Would be great if reports could export to Excel.
"""


def test_schema_and_postmortem_roundtrip(client):
    r = client.get("/api/stats/qual").json()
    kinds = {s["kind"]: s for s in r["schema"]}
    assert set(kinds) == {"postmortem", "observation", "swot", "scenario", "premortem", "pivot", "requirements", "dataplan", "dsproject", "deployment", "feedback", "wrangle", "story", "report", "architecture", "warehouse", "dmplan", "dataops", "toolchoice", "virtplan", "srs", "designdoc", "testplan", "sop", "aiuse", "modelcard", "datacard", "aiincident", "modelrelease", "changereq", "vendorreview"}
    assert kinds["postmortem"]["horizon"] == "past" and kinds["scenario"]["horizon"] == "future"
    assert r["items"] == []
    pm = client.post("/api/stats/qual", json={"kind": "postmortem", "title": "Henderson delays", "tags": ["ops", "routing"],
                                              "data": {"when": "2026-10-01", "outcome": "failed", "why": "New routing ignored traffic", "went_wrong": ["late trucks", "", "no alerts"], "bogus": "x"}}).json()
    assert pm["horizon"] == "past" and pm["data"]["went_wrong"] == ["late trucks", "no alerts"] and "bogus" not in pm["data"]
    assert pm["data"]["outcome"] == "failed"
    up = client.put(f"/api/stats/qual/{pm['id']}", json={"data": {"outcome": "mixed", "lessons": "Test routing on one zone first"}}).json()
    assert up["data"]["outcome"] == "mixed" and up["title"] == "Henderson delays"
    assert len(client.get("/api/stats/qual").json()["items"]) == 1
    assert client.delete(f"/api/stats/qual/{pm['id']}").json()["deleted"] == pm["id"]
    assert client.delete(f"/api/stats/qual/{pm['id']}").status_code == 404


def test_scenario_expected_value_and_validation(client):
    sc = client.post("/api/stats/qual", json={"kind": "scenario", "title": "Price change", "data": {"options": [
        {"name": "Win", "probability": 30, "payoff": 100000}, {"name": "Flat", "probability": 50, "payoff": 10000}, {"name": "Lose", "probability": 20, "payoff": -50000}]}}).json()
    c = sc["computed"]
    assert c["expected_value"] == 25000.0 and c["balanced"] is True and c["best"] == "Win" and c["worst"] == "Lose" and c["spread"] == 150000.0
    off = client.post("/api/stats/qual", json={"kind": "scenario", "title": "Off", "data": {"options": [{"name": "A", "probability": 70, "payoff": 1}]}}).json()
    assert off["computed"]["balanced"] is False and "70" in off["computed"]["warning"]
    assert client.post("/api/stats/qual", json={"kind": "scenario", "title": "Bad", "data": {"options": [{"name": "A", "probability": 150, "payoff": 1}]}}).status_code == 400
    assert client.post("/api/stats/qual", json={"kind": "scenario", "title": "Bad", "data": {"options": [{"name": "A", "probability": "x", "payoff": 1}]}}).status_code == 400
    assert client.post("/api/stats/qual", json={"kind": "nope", "title": "x"}).status_code == 400
    assert client.post("/api/stats/qual", json={"kind": "swot", "title": "  "}).status_code in (400, 422)
    assert client.post("/api/stats/qual", json={"kind": "postmortem", "title": "x", "data": {"when": "yesterday"}}).status_code == 400
    assert client.post("/api/stats/qual", json={"kind": "postmortem", "title": "x", "data": {"outcome": "great"}}).status_code == 400


def test_premortem_ranking_and_swot_counts(client):
    pre = client.post("/api/stats/qual", json={"kind": "premortem", "title": "Launch", "data": {"failures": [
        {"reason": "No customers", "likelihood": "high", "impact": "high"}, {"reason": "Bug", "likelihood": "low", "impact": "medium", "mitigation": "tests"}]}}).json()
    assert pre["computed"]["ranked"][0]["reason"] == "No customers" and pre["computed"]["unmitigated_high"] == 1
    sw = client.post("/api/stats/qual", json={"kind": "swot", "title": "Q4", "data": {"strengths": ["a", "b"], "threats": ["c"]}}).json()
    assert sw["computed"]["counts"] == {"strengths": 2, "weaknesses": 0, "opportunities": 0, "threats": 1}


def test_notes_are_per_workspace(client):
    client.post("/api/stats/qual", json={"kind": "observation", "title": "Dock is crowded at 9", "data": {"note": "queue"}})
    assert len(client.get("/api/stats/qual").json()["items"]) == 1
    active = client.get("/api/workspaces").json()["active"]
    other = "real" if active == "practice" else "practice"
    assert client.post("/api/workspaces/active", json={"name": other}).status_code == 200
    assert client.get("/api/stats/qual").json()["items"] == []
    client.post("/api/workspaces/active", json={"name": active})
    assert len(client.get("/api/stats/qual").json()["items"]) == 1


def test_themes_from_text_notes_and_column(client):
    r = client.post("/api/stats/themes", json={"text": EMAILS}).json()
    assert r["documents"] == 4
    words = {t["term"] for t in r["terms"]}
    assert {"delay", "refund"} & words or "charged" in words or "support" in words
    c = r["sentiment"]["counts"]
    assert c["positive"] >= 1 and c["negative"] >= 2 and sum(c.values()) == 4
    # negation: "not good" is negative, not positive
    n = client.post("/api/stats/themes", json={"text": "The product is not good at all."}).json()
    assert n["sentiment"]["counts"]["negative"] == 1 and n["sentiment"]["counts"]["positive"] == 0
    client.post("/api/data/import", files=csv_file("id,comment\n1,slow and broken app\n2,love it great support\n3,slow checkout again\n", "feedback.csv"), data={"mode": "replace"})
    col = client.post("/api/stats/themes", json={"source": "feedback", "text_col": "comment"}).json()
    assert col["documents"] == 3 and any(t["term"] == "slow" and t["docs"] == 2 for t in col["terms"])
    assert client.post("/api/stats/themes", json={"source": "feedback", "text_col": "id"}).status_code == 400
    assert client.post("/api/stats/themes", json={}).status_code == 400
    client.post("/api/stats/qual", json={"kind": "observation", "title": "Dock queue", "data": {"note": "trucks wait outside the dock"}})
    nn = client.post("/api/stats/themes", json={"include_notes": True}).json()
    assert nn["documents"] == 1 and "dock" in {t["term"] for t in nn["terms"]}


def test_theme_upload_txt_md_pdf(client):
    r = client.post("/api/stats/themes/upload", files={"file": ("emails.txt", EMAILS.encode(), "text/plain")}).json()
    assert r["documents"] == 4 and r["sentiment"]["counts"]["negative"] >= 2
    assert client.post("/api/stats/themes/upload", files={"file": ("x.docx", b"hi", "application/octet-stream")}).status_code == 400
    assert client.post("/api/stats/themes/upload", files={"file": ("empty.txt", b"   ", "text/plain")}).status_code == 400
    import pytest
    pytest.importorskip("pdfplumber")
    from reportlab.pdfgen import canvas
    import io
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 700, "The support team was slow and the invoice was wrong.")
    c.drawString(72, 680, "Support was friendly and helpful though.")
    c.save()
    p = client.post("/api/stats/themes/upload", files={"file": ("report.pdf", b.getvalue(), "application/pdf")})
    assert p.status_code == 200 and any(t["term"] == "support" for t in p.json()["terms"])
    assert client.post("/api/stats/themes/upload", files={"file": ("bad.pdf", b"nope", "application/pdf")}).status_code == 400


def test_requirements_document(client):
    r = client.post("/api/stats/qual", json={"kind": "requirements", "title": "Retail BI", "data": {
        "stakeholders": ["Head of marketing", " "], "kpis": ["Retention"], "status": "shared for feedback", "signed_on": "2026-10-01"}})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["stakeholders"] == ["Head of marketing"] and d["status"] == "shared for feedback" and d["risks"] == []
    assert client.post("/api/stats/qual", json={"kind": "requirements", "title": "x", "data": {"status": "approved-ish"}}).status_code == 400
    assert any(s["kind"] == "requirements" for s in client.get("/api/stats/qual").json()["schema"])


def test_dataplan(client):
    r = client.post("/api/stats/qual", json={"kind": "dataplan", "title": "Age-group campaign", "data": {"timeframe": "ongoing", "sources": ["CRM", "", "survey"]}})
    assert r.status_code == 200 and r.json()["data"]["sources"] == ["CRM", "survey"]
    assert client.post("/api/stats/qual", json={"kind": "dataplan", "title": "x", "data": {"timeframe": "whenever"}}).status_code == 400


def test_wrangle_log(client):
    r = client.post("/api/stats/qual", json={"kind": "wrangle", "title": "Orders prep", "data": {"cleaning": ["dropped 3 duplicate orders", ""]}})
    assert r.status_code == 200 and r.json()["data"]["cleaning"] == ["dropped 3 duplicate orders"] and r.json()["horizon"] == "past"


def test_story(client):
    r = client.post("/api/stats/qual", json={"kind": "story", "title": "West margin", "data": {"headline": "West margin fell 4 points", "evidence": ["a", ""]}})
    assert r.status_code == 200 and r.json()["data"]["evidence"] == ["a"] and r.json()["data"]["review_on"] == ""


def test_report(client):
    r = client.post("/api/stats/qual", json={"kind": "report", "title": "Q3 findings", "data": {"format": "detailed", "results": ["a", " "], "check_one_point": "checked"}})
    assert r.status_code == 200 and r.json()["data"]["results"] == ["a"] and r.json()["data"]["check_relevant"] == "not checked"
    assert client.post("/api/stats/qual", json={"kind": "report", "title": "x", "data": {"check_readable": "maybe"}}).status_code == 400


def test_dsproject(client):
    r = client.post("/api/stats/qual", json={"kind": "dsproject", "title": "Cut churn", "data": {"approach": "predictive", "objectives": ["a", "", "b"]}})
    assert r.status_code == 200
    assert client.post("/api/stats/qual", json={"kind": "dsproject", "title": "x", "data": {"approach": "guess"}}).status_code == 400


def test_deployment_plan(client):
    assert client.post("/api/stats/qual", json={"kind": "deployment", "title": "Churn score", "data": {"rollout": "pilot", "stakeholders": ["sales", ""]}}).status_code == 200
    assert client.post("/api/stats/qual", json={"kind": "deployment", "title": "x", "data": {"rollout": "yolo"}}).status_code == 400


def test_feedback_note(client):
    assert client.post("/api/stats/qual", json={"kind": "feedback", "title": "Q1 review", "data": {"method": "before and after", "verdict": "mixed"}}).status_code == 200
    assert client.post("/api/stats/qual", json={"kind": "feedback", "title": "x", "data": {"verdict": "great"}}).status_code == 400


def test_data_engineering_notes(client):
    for kind, data in (("architecture", {"repository": "warehouse", "sources": ["crm", "", "web"]}),
                       ("warehouse", {"load": "incremental", "grain": "one row per order line"}),
                       ("dmplan", {"owner": "Ops", "quality_rules": ["no duplicate ids"]}),
                       ("dataops", {"phase": "iterate", "tests": ["row counts match"]}), ("toolchoice", {"category": "backup", "shortlist": ["restic"]}), ("virtplan", {"status": "planning", "hosts": ["esxi01"]}), ("srs", {"status": "draft", "functional": ["As a user I want X so that Y"]}), ("designdoc", {"status": "draft"}), ("testplan", {"status": "planning", "levels": ["unit"]}), ("sop", {"steps": ["open the app"]}), ("aiuse", {"status": "idea", "approach": "classic ML"}), ("modelcard", {"status": "draft"}), ("datacard", {"sensitive": ["email"]}), ("aiincident", {"status": "open"}), ("modelrelease", {"status": "draft", "rollout": "canary"}), ("changereq", {"status": "draft", "ctype": "normal"}), ("vendorreview", {"phase": "delivery", "terms": ["SLA checked"]})):
        r = client.post("/api/stats/qual", json={"kind": kind, "title": "t", "data": data})
        assert r.status_code == 200, r.text
    assert client.post("/api/stats/qual", json={"kind": "warehouse", "title": "x", "data": {"load": "guess"}}).status_code == 400
