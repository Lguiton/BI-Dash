import pytest

from app.services import pm, pm_tools as pt


def test_sow_and_validation(client):
    h = pt.sow({"client": "Acme <b>Co</b>", "project": "Dashboard", "deliverables": ["Dashboard", "Training <i>session</i>"], "price": 2400, "weeks": "4", "provider": "Lam"})
    assert "<b>Co</b>" not in h and "$2,400.00" in h and "not legal advice" in h and "change request" in h and "SAMPLE" in h
    assert "per hour" in pt.sow({"client": "A", "project": "P", "deliverables": ["x"], "price_model": "hourly", "rate": 80})
    for bad in ({"client": "", "project": "P", "deliverables": ["x"]}, {"client": "A", "project": "P", "deliverables": []}, {"client": "A", "project": "P", "deliverables": ["x"], "price": 0}):
        with pytest.raises(pt.PmToolError):
            pt.sow(bad)


def test_estimate_arithmetic():
    r = pt.estimate([{"name": "a", "optimistic": 2, "likely": 4, "pessimistic": 12}, {"name": "b", "optimistic": 1, "likely": 2, "pessimistic": 3}])
    assert r["tasks"][0]["expected"] == 5.0 and r["expected_total"] == 7.0
    assert abs(r["sd_total"] - ((10 / 6) ** 2 + (2 / 6) ** 2) ** 0.5) < 0.01 and r["range_80"][1] > r["expected_total"]
    with pytest.raises(pt.PmToolError):
        pt.estimate([{"optimistic": 5, "likely": 2, "pessimistic": 9}])
    with pytest.raises(pt.PmToolError):
        pt.estimate([])


def test_stories_flags():
    r = pt.stories([{"role": "owner", "want": "to see sales fast and export them", "benefit": ""}, {"role": "admin", "want": "to reset a password", "benefit": "staff can get back in"}])
    assert r["stories"][0]["story"].startswith("As an owner, I want to see sales")
    f = " ".join(r["stories"][0]["flags"])
    assert "No benefit" in f and "two stories" in f and "Vague word" in f and not r["stories"][1]["flags"]
    assert len(r["stories"][1]["criteria"]) == 4 and "### As an admin" in r["markdown"]
    with pytest.raises(pt.PmToolError):
        pt.stories([{"role": "", "want": "x"}])


def test_roadmap_log_and_status(client):
    a = pt.roadmap_add("Invoices", "now", "cash flow")
    pt.roadmap_move(a["id"], "next")
    h = pt.roadmap_html()
    assert "Invoices" in h and pt.roadmap_list()[0]["lane"] == "next"
    with pytest.raises(pt.PmToolError):
        pt.roadmap_add("x", "soon")
    pt.log_add("decision", {"decision": "Use Postgres", "context": "multi-user", "owner": "Lam"})
    pt.log_add("retro", {"went_well": "shipped", "improve": "testing"})
    assert "Use Postgres" in pt.log_markdown() and len(pt.log_list()) == 2
    with pytest.raises(pt.PmToolError):
        pt.log_add("retro", {})
    with pytest.raises(pt.PmToolError):
        pt.status_report()
    pm.load_example()
    s = pt.status_report("Dash <b>", "Acme")
    assert "Weekly status" in s and "&lt;b&gt;" in s and "Top risks" in s and "Overall" in s
