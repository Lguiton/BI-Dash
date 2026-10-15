"""Known issues (CISA KEV) and support dates (endoflife.date), with fake network replies."""
import json
from datetime import date

from app.services import knownissues as ki

KEV = json.dumps({"catalogVersion": "2026.10.14", "vulnerabilities": [
    {"cveID": "CVE-2026-0001", "vendorProject": "Microsoft", "product": "Windows", "vulnerabilityName": "Windows SMB flaw", "dateAdded": "2026-10-01", "shortDescription": "bad", "requiredAction": "Patch", "dueDate": "2026-10-22", "knownRansomwareCampaignUse": "Known"},
    {"cveID": "CVE-2026-0002", "vendorProject": "Cisco", "product": "IOS XE", "vulnerabilityName": "Cisco web UI flaw", "dateAdded": "2026-10-10", "shortDescription": "bad", "requiredAction": "Update", "dueDate": "2026-10-31", "knownRansomwareCampaignUse": "Unknown"}]})
EOL_V1 = json.dumps({"result": {"name": "windows", "releases": [
    {"name": "10-22h2", "label": "10 22H2", "releaseDate": "2022-10-18", "eolFrom": "2025-10-14", "latest": {"name": "10.0.19045"}},
    {"name": "11-25h2", "label": "11 25H2", "releaseDate": "2025-09-30", "eolFrom": "2027-10-12", "latest": {"name": "10.0.26200"}},
    {"name": "future", "label": "Future", "releaseDate": "2026-01-01", "eolFrom": None}]}})
EOL_OLD = json.dumps([{"cycle": "22.04", "releaseDate": "2022-04-21", "eol": "2027-06-01", "latest": "22.04.5", "lts": True}, {"cycle": "14.04", "eol": True}])


def _fake(monkeypatch, routes):
    calls = []

    def get(url, timeout=15.0):
        calls.append(url)
        for k, v in routes.items():
            if k in url:
                return v
        return 0, ""
    monkeypatch.setattr(ki, "_get", get)
    return calls


def test_kev_search_is_local_and_cached(client, monkeypatch):
    calls = _fake(monkeypatch, {"known_exploited": (200, KEV)})
    r = client.get("/api/known-issues/kev", params={"q": "windows smb"}).json()
    assert r["total"] == 1 and r["results"][0]["cve"] == "CVE-2026-0001" and r["results"][0]["ransomware"] is True
    r2 = client.get("/api/known-issues/kev", params={"q": "cisco"}).json()
    assert r2["results"][0]["cve"] == "CVE-2026-0002" and len(calls) == 1          # one download, search words never sent
    assert all("windows" not in c and "cisco" not in c for c in calls)
    allr = client.get("/api/known-issues/kev").json()
    assert [x["cve"] for x in allr["results"]] == ["CVE-2026-0002", "CVE-2026-0001"]  # newest first


def test_kev_uses_saved_copy_when_unreachable_and_errors_when_none(client, monkeypatch):
    _fake(monkeypatch, {})
    assert client.get("/api/known-issues/kev").status_code == 502
    _fake(monkeypatch, {"known_exploited": (200, KEV)})
    client.get("/api/known-issues/kev")
    from app.services import state
    box = json.loads(state.kv_get("known_issues:kev")); box["at"] -= 3 * 24 * 3600; state.kv_set("known_issues:kev", json.dumps(box))
    _fake(monkeypatch, {})
    r = client.get("/api/known-issues/kev").json()
    assert r["total"] == 2 and "could not be reached" in r["warning"]


def test_eol_new_and_old_shapes_and_status(client, monkeypatch):
    _fake(monkeypatch, {"/api/v1/products/windows/": (200, EOL_V1)})
    r = ki.eol_lookup("Windows", today=date(2026, 10, 15))
    by = {x["cycle"]: x for x in r["releases"]}
    assert by["10-22h2"]["status"] == "ended" and "ended 2025-10-14" in by["10-22h2"]["says"]
    assert by["11-25h2"]["status"] == "supported" and by["future"]["status"] == "supported" and "no end date" in by["future"]["says"]
    assert [x["cycle"] for x in ki.eol_lookup("windows", "11", today=date(2026, 10, 15))["releases"]] == ["11-25h2"]
    _fake(monkeypatch, {"/api/v1/products/ubuntu/": (404, ""), "/api/ubuntu.json": (200, EOL_OLD)})
    u = {x["cycle"]: x for x in ki.eol_lookup("ubuntu", today=date(2026, 10, 15))["releases"]}
    assert u["22.04"]["lts"] and u["22.04"]["status"] == "supported" and u["14.04"]["status"] == "ended"


def test_eol_soon_flag_validation_and_unknown_product(client, monkeypatch):
    _fake(monkeypatch, {"/api/v1/products/windows/": (200, EOL_V1)})
    r = ki.eol_lookup("windows", today=date(2027, 8, 1))
    assert {x["cycle"]: x["status"] for x in r["releases"]}["11-25h2"] == "soon"
    assert client.get("/api/known-issues/eol", params={"product": "../etc/passwd"}).status_code == 400
    assert client.get("/api/known-issues/eol", params={"product": "a b/c"}).status_code == 400
    _fake(monkeypatch, {"/products/nothing": (404, ""), "/api/nothing.json": (404, "")})
    resp = client.get("/api/known-issues/eol", params={"product": "nothing"})
    assert resp.status_code == 404 and "no product called" in resp.json()["detail"]
    _fake(monkeypatch, {})
    assert client.get("/api/known-issues/eol", params={"product": "freebsd"}).status_code == 502
    assert "windows" in client.get("/api/known-issues/products").json()["products"]
