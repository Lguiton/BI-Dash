import pytest

from app.services import dnsmasq_gen as dg, ticket_coach as tc

GOOD = {"interface": "eth0", "subnet": "192.168.50.0/24", "range_start": "192.168.50.100", "range_end": "192.168.50.200", "domain": "lab.local", "upstream": ["1.1.1.1"],
        "reservations": [{"mac": "AA-BB-CC-DD-EE-01", "ip": "192.168.50.20", "host": "printer"}], "records": [{"name": "nas.lab.local", "ip": "192.168.50.30"}]}


def test_vague_ticket_scores_low_and_good_ticket_scores_high():
    bad = tc.review_report(**tc.SAMPLE_REPORT)
    good = tc.review_report(**tc.SAMPLE_GOOD)
    assert bad["score"] < 40 and bad["band"] == "Needs more detail" and not bad["title"]["good"] and len(bad["questions_a_technician_would_ask"]) >= 5
    assert good["score"] >= 90 and good["band"] == "Ready to work" and not good["missing"]


def test_each_missing_item_is_reported_individually():
    r = tc.review_report("Printer offline", "The printer on floor 2 is offline for everyone since this morning.")
    ids = {m["id"] for m in r["missing"]}
    assert "who" not in ids and "when" not in ids and {"error", "tried"} <= ids


def test_password_in_ticket_is_flagged():
    r = tc.review_report("Cannot log in to VPN", "I cannot log in since today. My password is Summer2024! please reset it, I tried twice.")
    assert any("password" in n.lower() for n in r["notes"])


def test_resolution_rewards_cause_fix_and_check():
    ok = tc.review_resolution(tc.SAMPLE_RESOLUTION["note"])
    assert ok["score"] >= 75 and ok["band"] == "Useful to the next person"
    assert tc.review_resolution("fixed")["score"] == 0
    r = tc.review_resolution("Restarted the PC and it works now")
    assert any("cause is unknown" in n for n in r["notes"])


def test_priority_matrix():
    assert tc.priority(1, True)["priority"] == "P4"
    assert tc.priority(40, False, deadline=True)["priority"] == "P1"
    assert tc.priority(1, False, security=True)["priority"] == "P1"
    for bad in (0, "x", 10**7):
        with pytest.raises(tc.CoachError):
            tc.priority(bad, True)


def test_coach_input_validation():
    with pytest.raises(tc.CoachError):
        tc.review_report("t", "short")
    with pytest.raises(tc.CoachError):
        tc.review_resolution("")


def test_dnsmasq_generates_valid_config_that_checks_clean():
    r = dg.generate(GOOD)
    c = r["config"]
    assert "dhcp-range=192.168.50.100,192.168.50.200,255.255.255.0,12h" in c and "dhcp-host=aa:bb:cc:dd:ee:01,printer,192.168.50.20" in c
    assert "dhcp-option=option:router,192.168.50.1" in c and "host-record=nas.lab.local,192.168.50.30" in c and "interface=eth0" in c
    assert dg.check(c)["errors"] == 0


@pytest.mark.parametrize("change,msg", [
    ({"subnet": "nonsense"}, "CIDR"), ({"subnet": "10.0.0.0/31"}, "between /16 and /29"), ({"range_end": "192.168.60.5"}, "not a usable address"),
    ({"range_start": "192.168.50.210"}, "before"), ({"lease": "soon"}, "Lease time"), ({"interface": "bad name!"}, "Interface"),
    ({"reservations": [{"mac": "zz", "ip": "192.168.50.5", "host": "a"}]}, "MAC"),
    ({"reservations": [{"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.50.1", "host": "a"}]}, "already used"),
    ({"reservations": [{"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.50.5"}, {"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.50.6"}]}, "twice"),
    ({"reservations": [{"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.99.5"}]}, "not a usable"), ({"cache_size": 99999}, "Cache"), ({"domain": "bad domain!"}, "domain"),
])
def test_dnsmasq_rejects_bad_input(change, msg):
    with pytest.raises(dg.DnsmasqError, match=msg):
        dg.generate({**GOOD, **change})


def test_dnsmasq_warns_about_range_over_gateway_and_missing_interface():
    r = dg.generate({"subnet": "192.168.50.0/24", "gateway": "192.168.50.150", "range_start": "192.168.50.100", "range_end": "192.168.50.200", "lease": "30s"})
    w = " ".join(r["warnings"])
    assert "gateway" in w and "interface" in w.lower() and "2 minutes" in w


def test_dnsmasq_checker_finds_the_planted_problems():
    r = dg.check(dg.SAMPLE_CHECK)
    msgs = " ".join(p["message"] for p in r["problems"])
    assert r["errors"] == 3 and "overlaps" in msgs and "already has a reservation" in msgs and "already reserved" in msgs and r["verdict"] == "Fix the errors first."
    with pytest.raises(dg.DnsmasqError):
        dg.check("   ")


def test_api(client):
    assert client.post("/api/infra/ticket/review", json=client.get("/api/infra/ticket/sample").json()["good"]).json()["band"] == "Ready to work"
    assert client.post("/api/infra/ticket/review", json={"title": "x", "body": "no"}).status_code == 400
    assert client.post("/api/infra/ticket/resolution", json={"note": "fixed"}).json()["score"] == 0
    assert client.post("/api/infra/ticket/priority", json={"users_affected": 30, "workaround": False}).json()["priority"] in ("P1", "P2")
    assert client.post("/api/infra/dnsmasq/generate", json=GOOD).status_code == 200
    assert client.post("/api/infra/dnsmasq/generate", json={**GOOD, "subnet": "x"}).status_code == 400
    t = client.get("/api/infra/dnsmasq/sample").json()["text"]
    assert client.post("/api/infra/dnsmasq/check", json={"text": t}).json()["errors"] == 3
