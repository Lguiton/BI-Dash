import ipaddress

import pytest

from app.services import net_design as nd, sec_frame as sf, known_errors


# ---------------------------------------------------------------- principles
def test_review_finds_each_principle_breach():
    r = sf.review("Admin page lives at a hidden URL so nobody will find it. All staff have full access to the file server. Security will be added before launch.")
    names = {f["principle"] for f in r["findings"]}
    assert {"Security by obscurity (the anti-principle)", "Least privilege", "Security by design"} <= names
    assert not r["clean"] and all(f["quote"] and f["fix"] for f in r["findings"])


def test_review_separation_of_duties_and_depth_and_clean():
    r = sf.review("The same user requests the payment and approves it. We rely on the firewall only.")
    assert {"Separation of duties", "Defense in depth"} <= {f["principle"] for f in r["findings"]}
    ok = sf.review("Staff use MFA, roles are reviewed quarterly and every change needs a second reviewer.")
    assert ok["clean"] and len(ok["questions"]) == 6


@pytest.mark.parametrize("bad", ["", "short", "x" * 20_001])
def test_review_rejects_bad_input(bad):
    with pytest.raises(sf.FrameError):
        sf.review(bad)


def test_cia_classifies_and_handles_unknown():
    r = sf.classify("A SYN flood caused downtime for the booking site")
    assert r["affected"][0]["property"] == "availability"
    assert r["affected"][0]["controls"]
    both = sf.classify("Attackers stole the customer list and modified the records")
    assert {a["property"] for a in both["affected"]} >= {"confidentiality", "integrity"}
    none = sf.classify("The weather is nice today")
    assert none["affected"] == []
    with pytest.raises(sf.FrameError):
        sf.classify("hi")


# ---------------------------------------------------------------- CSF
def test_csf_has_six_functions_with_govern_flagged():
    q = sf.csf_questions()
    assert [f["name"] for f in q["functions"]] == ["Govern", "Identify", "Protect", "Detect", "Respond", "Recover"]
    assert q["functions"][0]["added"].startswith("CSF 2.0")


def test_csf_score_math_and_actions():
    ans = {"p1": "yes", "p2": "no", "p3": "partly", "c1": "no"}
    r = sf.csf_score(ans)
    prot = next(f for f in r["functions"] if f["function"] == "Protect")
    assert prot["score"] == 50 and prot["answered"] == 3 and prot["level"] == "developing"
    assert next(f for f in r["functions"] if f["function"] == "Recover")["level"] == "weak"
    assert next(f for f in r["functions"] if f["function"] == "Detect")["level"] == "not answered"
    assert r["next_actions"][0]["severity"] == 2 and r["all_gaps"] == 3
    assert r["overall"] == round((50 + 0) / 2)


@pytest.mark.parametrize("ans", [{}, {"zz": "yes"}, {"p1": "maybe"}, ["p1"]])
def test_csf_score_rejects_bad_answers(ans):
    with pytest.raises(sf.FrameError):
        sf.csf_score(ans)


# ---------------------------------------------------------------- design
SPEC = {"groups": [{"name": "Office", "hosts": 40}, {"name": "Warehouse", "hosts": 15}], "growth_pct": 25, "guest_wifi": True, "remote_access": True}


def test_plan_sizes_subnets_with_growth_and_no_overlap():
    r = nd.plan(SPEC)
    office = next(a for a in r["addressing"] if a["name"] == "Office")
    assert office["hosts_needed"] == 50 and office["network"].endswith("/26")
    nets = [ipaddress.ip_network(a["network"]) for a in r["addressing"]]
    assert not any(a.overlaps(b) for i, a in enumerate(nets) for b in nets[i + 1:])
    assert {"Management", "Servers", "Guest wifi"} <= {a["name"] for a in r["addressing"]}
    assert any("Guest" in z for z in r["zones"]) and any("VPN" in z for z in r["zones"])
    assert len(r["checklist"]) == 9 and r["devices"][0]["count"] == 1


def test_plan_redundancy_and_risks():
    none = nd.plan({**SPEC, "redundancy": "none"})
    full = nd.plan({**SPEC, "redundancy": "full"})
    assert any("No redundancy" in x for x in none["risks"])
    assert full["devices"][0]["count"] == 2 and full["devices"][1]["count"] == 2 * none["devices"][1]["count"]
    assert next(a for a in nd.plan({**SPEC, "growth_pct": 0})["addressing"] if a["name"] == "Office")["hosts_needed"] == 40
    assert any("overlapping" in x or "non-overlapping" in x for x in nd.plan({**SPEC, "sites": 3})["risks"])


@pytest.mark.parametrize("spec", [{}, {"groups": []}, {"groups": [{"name": "A", "hosts": 0}]}, {"groups": [{"name": "A", "hosts": 5}, {"name": "a", "hosts": 5}]},
                                  {"groups": [{"name": "A", "hosts": 500}], "base": "10.0.0.0/28"}, {"groups": [{"name": "A", "hosts": 5}], "redundancy": "x"}, {"groups": [{"name": "A", "hosts": "x"}]}])
def test_plan_rejects_bad_requirements(spec):
    with pytest.raises(nd.DesignError):
        nd.plan(spec)


def test_glossary_has_the_corrections():
    g = {t["term"]: t for t in nd.glossary()["terms"]}
    assert "MAC" in g["ARP"]["meaning"] and "802.16" in g["WMAN"]["meaning"] and "clear text" in g["Telnet"]["meaning"] and "service provider" in g["WISP"]["full"].lower() + g["WISP"]["meaning"].lower()
    assert [t["term"] for t in nd.glossary("wireless")["terms"]] and nd.glossary("zzzz")["count"] == 0


def test_ports_table_values():
    p = {x["port"]: x for x in nd.ports()["ports"]}
    assert p[445]["service"].startswith("SMB") and p[22]["service"] == "SSH, SFTP" and p[23]["service"].startswith("Telnet")


# ---------------------------------------------------------------- registry + http
def test_slips_are_registered_for_agents():
    items = known_errors.all_items()
    text = " ".join(i["text"] for i in items)
    assert "Govern" in text and "802.16" in text
    hit = known_errors.relevant("security", "what are the NIST CSF functions")
    assert any("CSF" in i["text"] for i in hit)


def test_endpoints(client):
    assert client.get("/api/frames/principles").json()["principles"][0]["id"] == "depth"
    assert client.post("/api/frames/principles/review", json={"text": "hidden url so nobody will find it"}).json()["findings"]
    assert client.post("/api/frames/principles/review", json={"text": "x"}).status_code == 400
    assert client.post("/api/frames/cia", json={"text": "ransomware encrypted the files"}).json()["affected"]
    assert client.get("/api/frames/csf").json()["options"] == ["yes", "partly", "no"]
    assert client.post("/api/frames/csf/score", json={"answers": {"g1": "yes"}}).json()["overall"] == 100
    assert client.post("/api/frames/csf/score", json={"answers": {"g1": "nope"}}).status_code == 400
    s = client.get("/api/frames/design/sample").json()
    assert client.post("/api/frames/design/plan", json={"spec": s["spec"]}).json()["addressing"]
    assert client.post("/api/frames/design/plan", json={"spec": {"groups": []}}).status_code == 400
    assert client.get("/api/frames/glossary?q=arp").json()["count"] >= 1
    assert client.get("/api/frames/ports").json()["ports"] and len(client.get("/api/frames/design/steps").json()["steps"]) == 9


def test_cheats_added():
    from app.services import itlab
    assert "Linux services and run levels" in itlab.CHEATS and "Microsoft Defender Antivirus (PowerShell)" in itlab.CHEATS
