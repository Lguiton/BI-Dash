import pytest

from app.services import it_infra as ii, it_ops as io


def _win(r, name):
    return next(x for x in r["settings"] if x["setting"] == name)["winning_gpo"]


def _gpo(name, order, settings, enforced=False, **k):
    return {"name": name, "link_order": order, "enforced": enforced, "settings": settings, **k}


def test_gpo_ou_beats_domain_unless_enforced():
    obj = {"name": "PC1", "groups": []}
    chain = [{"level": "domain", "name": "d", "gpos": [_gpo("D", 1, {"wall": "blue"})]},
             {"level": "ou", "name": "o", "gpos": [_gpo("O", 1, {"wall": "red"})]}]
    r = ii.gpo_resolve(obj, chain)
    assert _win(r, "wall") == "O"
    chain[0]["gpos"][0]["enforced"] = True
    assert _win(ii.gpo_resolve(obj, chain), "wall") == "D"


def test_gpo_link_order_one_wins_and_block_inheritance():
    obj = {"name": "PC1", "groups": []}
    ou = {"level": "ou", "name": "o", "gpos": [_gpo("A", 1, {"x": "1"}), _gpo("B", 2, {"x": "2"})]}
    assert _win(ii.gpo_resolve(obj, [ou]), "x") == "A"
    dom = {"level": "domain", "name": "d", "gpos": [_gpo("D", 1, {"y": "9"}), _gpo("E", 2, {"z": "9"}, enforced=True)]}
    blocked = {"level": "ou", "name": "o", "block_inheritance": True, "gpos": []}
    r = ii.gpo_resolve(obj, [dom, blocked])
    names = {x["setting"] for x in r["settings"]}
    assert "y" not in names and _win(r, "z") == "E"


def test_gpo_rejects_bad_input():
    with pytest.raises(ii.InfraError):
        ii.gpo_resolve({"name": ""}, [{"level": "ou", "name": "o", "gpos": []}])
    with pytest.raises(ii.InfraError):
        ii.gpo_resolve({"name": "a"}, [])


def test_sample_gpo_runs():
    r = ii.gpo_resolve(ii.GPO_SAMPLE["object"], ii.GPO_SAMPLE["chain"])
    assert r["settings"] and r["order_applied"]


def test_ldif_sample_has_problems_and_builder_output_is_clean():
    r = ii.ldif_check(ii.LDIF_SAMPLE)
    assert r["problems"]
    b = ii.ldif_build("user", {"base_dn": "dc=example,dc=com", "given": "Ada", "sn": "Lovelace", "uid": "alovelace"})
    assert b["ldif"].startswith("dn: cn=Ada Lovelace,ou=People,dc=example,dc=com") and b["check"]["errors"] == 0


def test_ldif_flags_plaintext_password_and_missing_attrs():
    txt = "dn: uid=a,ou=P,dc=x,dc=com\nobjectClass: inetOrgPerson\nuid: a\nuserPassword: hunter2\n"
    r = ii.ldif_check(txt)
    blob = str(r["problems"]).lower()
    assert "password" in blob and ("sn" in blob or "cn" in blob)


def test_ldif_builder_validation():
    with pytest.raises(ii.InfraError):
        ii.ldif_build("user", {"base_dn": "nope", "sn": "x", "uid": "x"})
    with pytest.raises(ii.InfraError):
        ii.ldif_build("group", {"base_dn": "dc=x,dc=com", "name": "g"})
    with pytest.raises(ii.InfraError):
        ii.ldif_build("nope", {"base_dn": "dc=x,dc=com"})


def test_rbac_sample_finds_issues():
    r = ii.rbac_check(**ii.RBAC_SAMPLE)
    assert r["errors"] >= 3 and any("separation of duties" in f["issue"] for f in r["findings"])


def test_rbac_cycle_detected():
    roles = {"a": {"permissions": ["p"], "inherits": ["b"]}, "b": {"permissions": ["q"], "inherits": ["a"]}}
    assert any("cycle" in f["issue"].lower() or "loop" in f["issue"].lower() for f in ii.rbac_check(roles, {"u": {"roles": ["a"]}})["findings"])


def test_raid_risk_orders_levels():
    r5 = io.raid_risk("5", 8, 16)
    r6 = io.raid_risk("6", 8, 16)
    assert r5["chance_of_losing_data_in_one_rebuild_pct"] > r6["chance_of_losing_data_in_one_rebuild_pct"]
    assert r5["usable_tb"] == 112.0 and r6["usable_tb"] == 96.0
    with pytest.raises(io.OpsError):
        io.raid_risk("5", 2, 4)


def test_backup_plan_restore_chains():
    r = {x["scheme"]: x for x in io.backup_plan(500)["rows"]}
    assert r["full"]["worst_restore_gb"] == 500
    assert r["incremental"]["stored_gb"] < r["full"]["stored_gb"]
    assert r["incremental"]["worst_restore_gb"] <= r["differential"]["worst_restore_gb"] or r["incremental"]["worst_restore_chain"] >= r["differential"]["worst_restore_chain"]


def test_dr_sample_fails_payroll_and_passes_file_server():
    st = {s["system"]: s["status"] for s in io.dr_check(io.DR_SAMPLE)["systems"]}
    assert st["Payroll database"] == "fail" and st["File server"] == "pass"


def test_lb_failed_server_gets_nothing_and_is_repeatable():
    a = io.lb_sim([{"name": "a"}, {"name": "b", "weight": 2}], fail="a")
    assert all(x["share_pct"]["a"] == 0 for x in a["results"])
    assert a == io.lb_sim([{"name": "a"}, {"name": "b", "weight": 2}], fail="a")
    with pytest.raises(io.OpsError):
        io.lb_sim([{"name": "a"}])


def test_http_and_triage_and_log():
    assert io.http_status(502)["fault"] == "server" and io.http_status(404)["fault"] == "client"
    assert len(io.http_table()) >= 25
    t = io.site_triage(dns_resolves=True, tcp_connects=False)
    assert "TCP" in str(t)
    lg = io.access_log(io.LOG_SAMPLE)
    assert lg["requests"] == 12 and lg["status_classes"]["5xx"] == 2


def test_reference_lists_fifteen_slips():
    ref = io.reference()
    assert len(ref["slips"]) == 15 and ref["not_built"]


def test_api_endpoints(client):
    g = client.get("/api/infra/gpo/sample").json()
    assert client.post("/api/infra/gpo", json=g).status_code == 200
    assert client.post("/api/infra/raid-risk", json={"level": "5", "disks": 1, "size_tb": 1}).status_code == 400
    assert client.post("/api/infra/http-lookup", json={"code": 503}).json()["name"] == "Service Unavailable"
    d = client.get("/api/infra/dr/sample").json()
    assert client.post("/api/infra/dr", json=d).status_code == 200
    assert client.post("/api/infra/ldif/check", json={"text": client.get("/api/infra/ldif/sample").json()["text"]}).status_code == 200
    assert client.post("/api/infra/triage", json={"dns_resolves": False}).status_code == 200
    assert client.get("/api/infra/reference").status_code == 200
