import pytest

from app.services import sec_report as sr, seclogs, security

BAD_PC = "smb1=True\nps2=Enabled\nwdigest=1\n"


def fake_headers(h):
    return {"host": h, "findings": [{"level": "fail", "title": "No HSTS", "fix": "Add the header"}, {"level": "ok", "title": "x", "fix": ""}], "score": {"passed": 1, "total": 2, "pct": 50}}


def fake_cert(h):
    return {"host": h, "findings": [{"level": "fail", "title": "Expired 3 day(s) ago", "fix": "Renew it now."}], "score": {"passed": 0, "total": 1, "pct": 0}}


def test_report_combines_sources_and_orders(monkeypatch):
    monkeypatch.setattr(security, "check_headers", fake_headers)
    monkeypatch.setattr(security, "check_cert", fake_cert)
    r = sr.build("Acme", "Me", "One office", [{"label": "Front desk", "text": BAD_PC}], ["example.com"], seclogs.sample_log(), {"mfa_email": "no", "backups_exist": "partial", "antivirus": "yes"})
    assert r["band"] == "Needs attention now" and r["counts"]["high"] >= 3
    sev = [i["severity"] for i in r["items"]]
    assert sev == sorted(sev, key=["high", "medium", "low"].index)
    srcs = {i["source"] for i in r["items"]}
    assert {"Windows PC: Front desk", "Website: example.com", "Logs", "Checklist"} <= srcs
    assert any("Expired" in i["title"] and i["severity"] == "high" for i in r["items"])
    assert any(i["title"].startswith("Only partly in place") and i["severity"] == "medium" for i in r["items"])
    h = sr.to_html(r)
    assert "SAMPLE" in h and "Front desk" in h and "What this did not check" in h and "<script" not in h


def test_good_band_validation_and_escaping(monkeypatch):
    with pytest.raises(sr.ReportError):
        sr.build()
    with pytest.raises(sr.ReportError):
        sr.build(checklist={"mfa_email": "maybe"})
    r = sr.build(client="<script>x</script>", checklist={c[0]: "yes" for c in sr.CHECKLIST})
    assert r["band"].startswith("Good") and r["items"] == []
    assert "<script>x" not in sr.to_html(r)
    bad = sr.build(endpoints=[{"label": "PC", "text": "nonsense"}], checklist={"antivirus": "no"})
    assert bad["endpoints"][0]["error"] and bad["counts"]["medium"] == 1


def test_api(client, monkeypatch):
    monkeypatch.setattr(security, "check_headers", fake_headers)
    monkeypatch.setattr(security, "check_cert", fake_cert)
    assert len(client.get("/api/security/report/checklist").json()["items"]) == len(sr.CHECKLIST)
    r = client.post("/api/security/report", json={"hosts": ["example.com"], "checklist": {"mfa_email": "no"}})
    assert r.status_code == 200 and r.json()["start_with"]
    h = client.post("/api/security/report/html", json={"checklist": {"mfa_email": "no"}})
    assert h.status_code == 200 and "Security checkup" in h.text
    assert client.post("/api/security/report", json={}).status_code == 400
