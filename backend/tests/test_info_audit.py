import pytest

from app.services import info_audit as ia, known_errors


def test_systems_finds_manual_flows_islands_and_missing_master():
    r = ia.systems(ia.SAMPLE["systems"])
    assert {(f["from"], f["to"]) for f in r["manual_transfers"]} == {("CRM", "Quotes spreadsheet"), ("ERP", "Accounting")}
    assert set(r["isolated_systems"]) == {"Shop-floor tablet app", "Quality shared drive"}
    assert r["no_designated_master"] == ["invoices"]
    cust = next(x for x in r["information_in_several_systems"] if x["information"] == "customers")
    assert cust["master"] == "CRM" and len(cust["systems"]) == 4
    assert "Quotes spreadsheet" in r["spreadsheet_or_informal_systems"]
    assert r["integration_priorities"][0]["flow"] == "CRM -> Quotes spreadsheet"


def test_systems_conflicting_masters_and_validation():
    r = ia.systems("A | x* | B:auto\nB | x* | ")
    assert r["conflicting_masters"] == ["x"] and r["no_designated_master"] == []
    for bad in ("", "A", "A | x | B:auto", "A | x | A:sometimes", "A | x |\nA | y |"):
        with pytest.raises(ia.AuditError):
            ia.systems(bad)


def test_metrics_flags_each_problem():
    r = ia.metrics(ia.SAMPLE["metrics"])
    probs = " ".join(i["problem"] for i in r["issues"])
    for w in ("no decision", "No owner", "Never reviewed", "Not in any report", "Appears in 2 reports"):
        assert w.lower() in probs.lower()
    assert r["keep"] == ["On-time delivery", "Scrap rate"] and r["issues"][0]["severity"] == "high"
    assert "Quality report" in r["reports_nobody_reviews"] or "Sales dashboard" in r["reports_nobody_reviews"]
    with pytest.raises(ia.AuditError):
        ia.metrics("m | r | o | d | sometimes")


def test_metrics_crowded_decision():
    rows = "\n".join(f"m{i} | r | o | Pick suppliers | weekly" for i in range(6))
    assert any("6 metrics for one decision" in i["problem"] for i in ia.metrics(rows)["issues"])


def test_documents_duplicates_names_and_staleness(monkeypatch):
    from datetime import date
    monkeypatch.setattr(ia, "_today", lambda: date(2026, 10, 1))
    r = ia.documents(ia.SAMPLE["documents"])
    probs = " ".join(i["problem"] for i in r["issues"])
    assert "version words" in probs and "2 copies" in probs and "No owner" in probs and "Never reviewed" in probs and "days ago" in probs
    assert len(r["duplicate_or_multi_version"]) == 1 and "Quality shared drive" in r["locations"]
    fresh = ia.documents("Policy | Ana | Intranet | 2 | 2026-09-01")
    assert fresh["issues"] == []
    with pytest.raises(ia.AuditError):
        ia.documents("Policy | Ana | Intranet | 2 | last spring")


def test_normalising_names():
    assert ia._norm("Welding procedure WP-12 final v2 (1)") == ia._norm("Welding procedure WP-12")


def test_search_cost_arithmetic_and_limits():
    r = ia.search_cost(40, 3, 8, 35)
    assert r["hours_per_year"] == 3680.0 and r["cost_per_year"] == 128800.0 and r["full_time_equivalents"] == 2.0
    for bad in ((0, 3, 8, 35), (40, -1, 8, 35), (40, 3, 8, "x"), (40, 3, 8, 35, 0)):
        with pytest.raises(ia.AuditError):
            ia.search_cost(*bad)


def test_key_person_exposure_and_deadlines(monkeypatch):
    from datetime import date
    monkeypatch.setattr(ia, "_today", lambda: date(2026, 10, 13))
    r = ia.key_person(ia.SAMPLE["key_person"])
    priya = next(x for x in r["if_this_person_left_tomorrow"] if x["person"] == "Priya")
    assert priya["holds"] == 3 and set(priya["exposed_if_they_left"]) == {"ISO certification audits", "Supplier approval"}
    assert r["most_concentrated"] == "Priya"
    assert [d["responsibility"] for d in r["deadlines_within_90_days_at_risk"]] == ["Machine maintenance plan", "ISO certification audits"]
    assert r["deadlines_within_90_days_at_risk"][0]["days_left"] == 28
    same = ia.key_person("Backups | Tom | Tom | yes |")
    assert "no separate backup" in same["at_risk"][0]["risks"]
    for bad in ("x | a | b | maybe |", "x | a | b | yes | soon"):
        with pytest.raises(ia.AuditError):
            ia.key_person(bad)


def test_slips_registered_and_retrievable():
    texts = [i["text"] for i in known_errors.all_items()]
    assert any("single source of truth" in t.lower() for t in texts) and any("sales document" in t for t in texts)
    assert known_errors.relevant("sysanalyst", "does connecting systems give a single source of truth")


def test_endpoints(client):
    s = client.get("/api/infoaudit/sample").json()
    assert client.post("/api/infoaudit/systems", json={"text": s["systems"]}).json()["manual_transfers"]
    assert client.post("/api/infoaudit/metrics", json={"text": s["metrics"]}).json()["issues"]
    assert client.post("/api/infoaudit/documents", json={"text": s["documents"], "stale_days": 30}).json()["issues"]
    assert client.post("/api/infoaudit/key-person", json={"text": s["key_person"]}).json()["at_risk"]
    assert client.post("/api/infoaudit/search-cost", json={"people": 10, "searches_per_day": 2, "minutes_each": 6, "hourly_cost": 30}).json()["hours_per_year"] == 460.0
    assert client.post("/api/infoaudit/systems", json={"text": "oops"}).status_code == 400
    assert client.post("/api/infoaudit/documents", json={"text": "a | b", "stale_days": 0}).status_code == 422
    assert len(client.get("/api/infoaudit/reference").json()["tactics"]) == 5


def test_copy_number_in_title_is_flagged():
    r = ia.documents("Policy (1) | Ana | Intranet | 2 | 2099-01-01")
    assert any("version words" in i["problem"] for i in r["issues"])
