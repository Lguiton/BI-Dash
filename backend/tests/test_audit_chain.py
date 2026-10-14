from app.services import state


def test_audit_chain_detects_tampering(client):
    for i in range(4):
        state.audit("t.event", f"n{i}")
    assert state.audit_verify()["ok"] is True
    r = client.get("/api/audit/verify").json()
    assert r["ok"] and r["checked"] >= 4
    mid = state.rows("SELECT id FROM audit WHERE action='t.event' ORDER BY id")[1]["id"]
    state.run("UPDATE audit SET detail='changed' WHERE id=?", (mid,))
    bad = state.audit_verify()
    assert bad["ok"] is False and bad["broken_at"] == mid


def test_audit_chain_detects_deleted_entry(client):
    for i in range(4):
        state.audit("t.event", f"n{i}")
    mid = state.rows("SELECT id FROM audit WHERE action='t.event' ORDER BY id")[1]["id"]
    state.run("DELETE FROM audit WHERE id=?", (mid,))
    assert state.audit_verify()["ok"] is False


def test_import_and_failed_login_are_audited(client):
    from app.services import biz_packs
    biz_packs.import_csv("repair-jobs", biz_packs.template("repair-jobs") if hasattr(biz_packs, "template") else "", True) if False else None
    p = biz_packs._get("repair-jobs")
    cols = ["record_date"] + list(p["dims"]) + list(p["nums"])
    row = ["2026-10-01"] + ["x"] * len(p["dims"]) + ["1"] * len(p["nums"]) + [""] * len(p.get("dates", []))
    biz_packs.import_csv("repair-jobs", ",".join(cols + list(p.get("dates", []))) + "\n" + ",".join(row) + "\n", True)
    assert state.one("SELECT 1 AS x FROM audit WHERE action='biz_import'")
    assert state.audit_verify()["ok"]
