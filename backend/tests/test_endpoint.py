import re

from app.services import endpoint_audit as ea


def test_script_is_read_only_and_covers_every_check(client):
    d = client.get("/api/endpoint/script").json()
    s = d["script"]
    assert d["checks"] == len(ea.CHECKS) >= 20
    for cid in ea.IDS:
        assert f"Out-Check '{cid}'" in s
    body = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    bad = re.findall(r"\b(Set|New|Remove|Disable|Enable|Add|Clear|Stop|Start|Restart|Install|Uninstall|Invoke|Import|Out-File|Reg(?:\.exe)? (?:add|delete))\b[-\s]", body)
    assert not bad, bad
    assert "wevtutil sl" not in body and "Set-ItemProperty" not in body


def test_sample_output_grades_with_expected_verdicts(client):
    r = client.post("/api/endpoint/grade", json={"text": ea.SAMPLE}).json()
    by = {x["id"]: x["status"] for x in r["rows"]}
    assert by["smb1"] == "pass" and by["ps2"] == "fail" and by["bitlocker"] == "fail" and by["fw_public"] == "fail"
    assert by["tls10"] == "warn" and by["tls11"] == "pass" and by["lmlevel"] == "warn" and by["wdigest"] == "pass"
    assert by["llmnr"] == "fail" and by["rdp"] == "warn" and by["credguard"] == "fail" and by["asr"] == "fail"
    assert by["admins"] == "warn" and by["patch_age"] == "warn" and by["seclog"] == "warn"
    assert 0 < r["score_pct"] < 100 and sum(r["counts"].values()) == len(ea.CHECKS)
    assert r["start_with"] and r["start_with"][0]["status"] == "fail"


def test_perfect_and_terrible_inputs():
    good = "\n".join(["smb1=False", "ps2=Disabled", "tls10=disabled", "tls11=disabled", "lmlevel=5", "wdigest=0", "secureboot=True", "bitlocker=On", "fw_domain=True", "fw_private=True", "fw_public=True",
                      "rdp=1", "nla=1", "llmnr=0", "netbios=2,2", "smnr=1", "uac=1", "admins=PC\\Admin", "credguard=True", "defender_rt=True", "asr=9", "patch_age=10", "seclog=512", "excel_macros=1"])
    assert ea.grade(good)["score_pct"] == 100
    bad = ea.grade("smb1=True\nwdigest=1\nlmlevel=1\nfw_public=False\nuac=0")
    assert bad["counts"]["fail"] == 5 and bad["score_pct"] == 0


def test_unreadable_values_are_unknown_not_failures():
    r = ea.grade("smb1=error\nsecureboot=unsupported\nbitlocker=unknown")
    assert r["counts"]["unknown"] == 3 and r["counts"]["fail"] == 0 and r["score_pct"] is None and r["counts"]["missing"] == len(ea.CHECKS) - 3


def test_parser_tolerates_noise_and_rejects_junk(client):
    t = "PS C:\\> .\\check.ps1\nsmb1 = False\nrandom text\nunknown_id=5\nUAC: 1\n"
    r = client.post("/api/endpoint/grade", json={"text": t}).json()
    assert {x["id"]: x["status"] for x in r["rows"]}["smb1"] == "pass" and r["ignored_lines"] == 1
    assert {x["id"]: x["status"] for x in r["rows"]}["uac"] == "pass"
    assert client.post("/api/endpoint/grade", json={"text": "hello world"}).status_code == 400
    assert client.post("/api/endpoint/grade", json={"text": "   "}).status_code == 400
    assert client.post("/api/endpoint/grade", json={"text": "x" * 200_000}).status_code == 422


def test_reference_lists_slips_and_process(client):
    r = client.get("/api/endpoint/reference").json()
    assert len(r["checks"]) == len(ea.CHECKS) and len(r["process"]) == 7 and len(r["slips"]) >= 8 and r["sample"].startswith("smb1=")
    assert any("Acer" in s for s in r["slips"])
