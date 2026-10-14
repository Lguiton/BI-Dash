import pytest

from app.services import fieldpacks as fp, field_howto as fh

EXPECTED = {"biz", "itpm", "mkt", "revops", "revsec", "ux", "devops", "cloud", "devsecops", "cv", "stat", "cds", "hana", "hbi", "hinf", "gen", "sci"}


def test_registry_complete_and_guides():
    assert set(fp.PACKS) == EXPECTED
    for pid, p in fp.PACKS.items():
        assert len(p["tools"]) >= 2, pid
        n = [g for g in fh.GUIDES if g["area"] == p["label"]]
        assert len(n) >= 5, (pid, len(n))
        assert p["label"] in fh.AREAS
        assert fp.PLACE[pid].startswith("/")
        for t in p["tools"].values():
            assert t["title"] and isinstance(t["inputs"], list)
    for g in fh.GUIDES:
        assert g["steps"] and g["verify"] and g["title"]
    assert len({g["id"] for g in fh.GUIDES}) == len(fh.GUIDES)


def test_every_result_is_json_safe_through_the_api(client):
    for pid, p in fp.PACKS.items():
        for tid, t in p["tools"].items():
            r = client.post(f"/api/fieldpacks/{pid}/{tid}", json={i["name"]: i["default"] for i in t["inputs"]})
            assert r.status_code == 200, (pid, tid, r.status_code, r.text[:100])


def test_every_tool_runs_on_its_example_values():
    n = 0
    for pid, p in fp.PACKS.items():
        for tid, t in p["tools"].items():
            out = fp.run(pid, tid, {i["name"]: i["default"] for i in t["inputs"]})
            assert isinstance(out, dict) and out.get("caution"), (pid, tid)
            n += 1
    assert n >= 60


def test_missing_input_message_uses_the_field_label():
    with pytest.raises(fp.PackError) as e:
        fp.run("itpm", "evm", {"bac": "", "pv": 1, "ev": 1, "ac": 1})
    assert "Budget at completion" in e.value.message


def test_known_answers():
    r = fp.run
    assert r("ux", "contrast", {"fg": "#000", "bg": "#fff"})["ratio"] == 21.0
    assert r("ux", "contrast", {"fg": "#767676", "bg": "#fff"})["normal_text_aa"] is True
    assert r("ux", "contrast", {"fg": "#999", "bg": "#fff"})["normal_text_aa"] is False
    e = r("itpm", "evm", {"bac": 1000, "pv": 500, "ev": 400, "ac": 500})
    assert e["cpi"] == 0.8 and e["spi"] == 0.8 and e["forecast_total_cost"] == 1250
    c = r("itpm", "critical", {"tasks": "A, a, 2,\nB, b, 3, A\nC, c, 1, A\nD, d, 1, B;C"})
    assert "6 days" in c["says"] and [t["slack"] for t in c["tasks"] if t["id"] == "C"] == [2.0]
    assert r("revops", "econ", {"arpa": 100, "margin": 50, "churn": 5, "cac": 400})["ltv"] == 1000.0
    assert r("devops", "slo", {"target": 99.9, "days": 30, "down": 0})["allowed_downtime_minutes"] == 43.2
    assert abs(r("cloud", "avail", {"parts": "a, 99, x\nb, 99, x"})["overall_pct"] - 99.99) < 0.001
    assert r("stat", "multi", {"p": "0.01 0.02", "alpha": 0.05})["results"][0]["bonferroni"] == 0.02
    assert r("stat", "power", {"kind": "means", "a": 5, "b": 10})["per_group"] in range(62, 67)
    assert r("hana", "prop", {"x": 50, "n": 100})["percent"] == 50.0
    assert r("hbi", "kpi", {"kpi": "falls", "a": 3, "b": 1500})["value"] == 2.0
    assert r("gen", "hwe", {"aa": 25, "ab": 50, "bb": 25})["chi_square"] == 0.0
    assert r("cv", "iou", {"a": "0,0,10,10", "b": "0,0,10,10"})["iou"] == 1.0
    assert r("hinf", "codes", {"kind": "npi", "codes": "1234567893"})["results"][0]["format_ok"] is True


def test_safety_findings():
    assert any("AWS" in f["says"] for f in fp.run("devsecops", "secrets", {"text": "k=AKIA" + "ABCDEFGHIJKLMNOP"})["findings"])
    full = "AKIA" + "ABCDEFGHIJKLMNOP"
    assert full not in str(fp.run("devsecops", "secrets", {"text": "k=" + full}))
    assert any(f["severity"] == "high" for f in fp.run("devsecops", "pipeline", {"text": "on: pull_request_target\njobs: {}"})["findings"])
    assert any("root" in f["says"] for f in fp.run("devops", "dockercheck", {"text": "FROM python:3.12\nRUN echo hi"})["findings"])
    assert fp.run("revsec", "access", {"grants": "ana, billing, create_invoice\nana, billing, approve_refund"})["findings"]
    assert not fp.run("revsec", "access", {"grants": "ana, billing, create_invoice\nben, billing, approve_refund"})["findings"]
    out = fp.run("hinf", "hl7", {"msg": "MSH|^~\\&|A|B|C|D|2026||ADT^A01|1|P|2.5\rPID|1||SECRETID||DOE^JANE"})
    assert "SECRETID" not in str(out) and "JANE" not in str(out)
    assert fp.run("cds", "phi", {"text": "SSN 123-45-6789"})["results"]
    assert "123-45-6789" not in str(fp.run("cds", "phi", {"text": "SSN 123-45-6789"}))


@pytest.mark.parametrize("pid,tid,bad", [("stat", "compare", {"a": "1", "b": "2 3"}), ("hana", "rate", {"events": "x", "pop": 5}), ("cloud", "cost", {"hours": 9999}), ("devops", "cicd", {"test": "rm -rf /; echo"}), ("cv", "detect", {"truth": "x", "pred": "y"}), ("sci", "random", {"groups": "A", "n": 5})])
def test_bad_input_is_plain_error(pid, tid, bad):
    with pytest.raises(fp.PackError):
        fp.run(pid, tid, bad)


def test_api(client):
    ls = client.get("/api/fieldpacks").json()["packs"]
    assert {p["id"] for p in ls} == EXPECTED and all(p["href"] for p in ls)
    sc = client.get("/api/fieldpacks/stat").json()
    assert sc["tools"] and sc["tools"][0]["inputs"]
    assert client.get("/api/fieldpacks/nope").status_code == 404
    r = client.post("/api/fieldpacks/ux/contrast", json={"fg": "#000000", "bg": "#ffffff"})
    assert r.status_code == 200 and r.json()["ratio"] == 21.0
    assert client.post("/api/fieldpacks/ux/contrast", json={"fg": "red", "bg": "#fff"}).status_code == 400
    assert client.post("/api/fieldpacks/ux/nope", json={}).status_code == 404
    s = client.get("/api/fieldbox/howto/search", params={"q": "key committed by mistake", "area": "DevSecOps"}).json()["results"]
    assert s and s[0]["id"] == "dso-secret"
    s = client.get("/api/fieldbox/howto/search", params={"q": "sensitivity specificity test", "area": "Clinical data science"}).json()["results"]
    assert s[0]["id"] == "cds-diag"


def test_concierge_finds_packs(client):
    r = client.get("/api/concierge", params={"q": "hl7 message"}) if False else None
    from app.services import concierge
    out = concierge.route("read an hl7 message")
    assert any("health" in x["href"] or "fields" in x["href"] for x in out["results"])
    out = concierge.route("scan for leaked secrets in my pipeline")
    assert any("devsecops" in x["href"] for x in out["results"])
