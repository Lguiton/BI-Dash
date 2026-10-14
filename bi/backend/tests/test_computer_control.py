import json
import time

import pytest

from app.services import settings_reset, sysactions, syscontrol, sysscan

PIN = "correct horse 42"


@pytest.fixture()
def cc(client, monkeypatch):
    """Computer control switched on, with a fake PowerShell so nothing real is ever run."""
    monkeypatch.setenv("BI_COMPUTER_CONTROL", "1")
    syscontrol._armed.update(token=None, until=0.0)
    syscontrol._fails.update(n=0, locked_until=0.0)
    syscontrol._jobs.clear()
    calls = []

    def fake(script, env, timeout):
        calls.append({"script": script, "env": dict(env)})
        if "BI_UNDO" in env:
            return {"rc": 0, "out": "restored", "err": "", "seconds": 0.1}
        if "Get-Service -Name $env:BI_P_name; @{name" in script:
            return {"rc": 0, "out": json.dumps({"name": "Spooler", "status": "Running", "start": "Automatic"}), "err": "", "seconds": 0.1}
        if script.lstrip().startswith("$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'\n@{adapter"):
            return {"rc": 0, "out": json.dumps({"adapter": env.get("BI_P_adapter"), "servers": ["192.168.1.1"]}), "err": "", "seconds": 0.1}
        if "Get-LocalUser -Name" in script and "@{name=$u.Name" in script:
            return {"rc": 0, "out": json.dumps({"name": "bob", "enabled": True}), "err": "", "seconds": 0.1}
        if "@{name=$env:BI_P_name}" in script:
            return {"rc": 0, "out": json.dumps({"name": env.get("BI_P_name")}), "err": "", "seconds": 0.1}
        return {"rc": 0, "out": "ok", "err": "", "seconds": 0.1}

    monkeypatch.setattr(syscontrol, "run_script", fake)
    monkeypatch.setattr(syscontrol, "find_shell", lambda: "powershell.exe")
    client.calls = calls
    return client


def go_real(c):
    c.post("/api/workspaces/active", json={"name": "real"})


def arm(c):
    assert c.post("/api/system/pin", json={"pin": PIN}).status_code == 200
    r = c.post("/api/system/arm", json={"pin": PIN})
    assert r.status_code == 200
    return {"X-Control-Token": r.json()["token"]}


def wait(c, job_id, tries=50):
    for _ in range(tries):
        j = c.get(f"/api/system/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job never finished")


def test_off_by_default_in_other_copies(client, monkeypatch):
    monkeypatch.delenv("BI_COMPUTER_CONTROL", raising=False)
    monkeypatch.setattr(syscontrol, "MARKER", syscontrol.MARKER.with_name("nope.enabled"))
    assert client.get("/api/system/status").json()["enabled"] is False
    assert client.get("/api/system/actions").status_code == 404
    assert client.post("/api/system/run", json={"action": "flush_dns"}).status_code == 404
    assert client.get("/api/system/settings").status_code == 404


def test_pin_arming_and_lockout(cc):
    assert cc.post("/api/system/pin", json={"pin": "123"}).status_code == 400
    assert cc.post("/api/system/arm", json={"pin": PIN}).status_code == 409          # no PIN yet
    cc.post("/api/system/pin", json={"pin": PIN})
    assert cc.post("/api/system/pin", json={"pin": "another long pin"}).status_code == 403      # changing needs the current one
    assert cc.post("/api/system/pin", json={"pin": "another long pin", "current": PIN}).status_code == 200
    for _ in range(4):                                        # the refused PIN change above was wrong try number one
        assert cc.post("/api/system/arm", json={"pin": "nope-nope"}).status_code == 403
    assert cc.post("/api/system/arm", json={"pin": "another long pin"}).status_code == 429
    syscontrol._fails["locked_until"] = 0
    r = cc.post("/api/system/arm", json={"pin": "another long pin"})
    assert r.status_code == 200 and len(r.json()["token"]) > 30
    s = cc.get("/api/system/status").json()
    assert s["armed_seconds"] > 800 and s["pin_set"]
    cc.post("/api/system/disarm")
    assert cc.get("/api/system/status").json()["armed_seconds"] == 0


def test_practice_only_simulates(cc):
    j = cc.post("/api/system/run", json={"action": "flush_dns"}).json()
    assert j["simulated"] and "nothing was run" in j["output"] and cc.calls == []
    s = cc.post("/api/system/scan-all").json()
    assert s["simulated"] and s["analysis"]["counts"]["high"] + s["analysis"]["counts"]["medium"] >= 3 and cc.calls == []


def test_real_needs_the_token_and_validates(cc):
    go_real(cc)
    assert cc.post("/api/system/run", json={"action": "flush_dns"}).status_code == 403
    h = arm(cc)
    assert cc.post("/api/system/run", json={"action": "flush_dns"}, headers={"X-Control-Token": "wrong"}).status_code == 403
    assert cc.post("/api/system/run", json={"action": "service_stop", "params": {"name": "RpcSs"}}, headers=h).status_code == 400
    assert cc.post("/api/system/run", json={"action": "service_stop", "params": {"name": "x; Remove-Item C:\\ -Recurse"}}, headers=h).status_code == 400
    assert cc.post("/api/system/run", json={"action": "dns_set", "params": {"adapter": "Wi-Fi", "servers": "not-an-ip"}}, headers=h).status_code == 400
    assert cc.post("/api/system/run", json={"action": "hosts_add", "params": {"ip": "0.0.0.0", "hostname": "bad host!"}}, headers=h).status_code == 400
    assert cc.post("/api/system/run", json={"action": "winget_install", "params": {"id": "a b; calc"}}, headers=h).status_code == 400
    assert cc.post("/api/system/run", json={"action": "nope"}, headers=h).status_code == 404
    assert cc.post("/api/system/run", json={"action": "firewall_set", "params": {"profile": "All", "state": "off"}}, headers=h).status_code == 400   # needs CONFIRM
    assert cc.post("/api/system/run", json={"action": "flush_dns"}, headers={"X-Control-Token": h["X-Control-Token"], "Origin": "https://evil.example"}).status_code == 403
    j = wait(cc, cc.post("/api/system/run", json={"action": "flush_dns"}, headers=h).json()["id"])
    assert j["status"] == "ok" and not j["simulated"]


def test_params_travel_as_environment_not_script_text(cc):
    go_real(cc)
    h = arm(cc)
    r = cc.post("/api/system/run", json={"action": "user_create", "params": {"name": "bob", "password": "S3cret-Pass!"}, "confirm": "confirm"}, headers=h).json()
    wait(cc, r["id"])
    used = [c for c in cc.calls if c["env"].get("BI_P_password")]
    assert used and all("S3cret-Pass!" not in c["script"] for c in cc.calls)
    hist = cc.get("/api/system/changes").json()["changes"][0]
    assert hist["params"]["password"] == "***" and "S3cret" not in json.dumps(hist)
    audit = " ".join(a["detail"] for a in cc.get("/api/audit").json()["entries"]) if cc.get("/api/audit").status_code == 200 else ""
    assert "S3cret" not in audit


def test_undo_keep_and_auto_revert(cc):
    go_real(cc)
    h = arm(cc)
    r = wait(cc, cc.post("/api/system/run", json={"action": "service_stop", "params": {"name": "Spooler"}}, headers=h).json()["id"])
    assert r["status"] == "ok"
    ch = cc.get("/api/system/changes").json()["changes"][0]
    assert ch["undoable"] and ch["action"] == "service_stop"
    assert cc.post(f"/api/system/changes/{ch['id']}/undo").status_code == 403           # undo needs arming too
    u = cc.post(f"/api/system/changes/{ch['id']}/undo", headers=h)
    assert u.status_code == 200
    restore_call = [c for c in cc.calls if "BI_UNDO" in c["env"]][-1]
    assert json.loads(restore_call["env"]["BI_UNDO"])["status"] == "Running"
    assert cc.post(f"/api/system/changes/{ch['id']}/undo", headers=h).status_code == 409
    # auto-revert path: dns_set carries a timer; make it due and let the scheduler hook process it
    r = wait(cc, cc.post("/api/system/run", json={"action": "dns_set", "params": {"adapter": "Wi-Fi", "servers": "1.1.1.1,1.0.0.1"}}, headers=h).json()["id"])
    assert r["status"] == "ok" and r["revert_in"] == 180
    cid = r["change_id"]
    from app.services import state
    state.run("UPDATE sys_changes SET revert_at = ? WHERE id = ?", (time.time() - 1, cid))
    n_before = len([c for c in cc.calls if "BI_UNDO" in c["env"]])
    assert syscontrol.process_due_reverts() == 1
    assert len([c for c in cc.calls if "BI_UNDO" in c["env"]]) == n_before + 1
    row = next(c for c in cc.get("/api/system/changes").json()["changes"] if c["id"] == cid)
    assert row["undone_at"] and not row["undoable"]
    # Keep cancels the timer
    r2 = wait(cc, cc.post("/api/system/run", json={"action": "dns_set", "params": {"adapter": "Wi-Fi", "servers": "9.9.9.9"}}, headers=h).json()["id"])
    cc.post(f"/api/system/changes/{r2['change_id']}/keep")
    state.run("UPDATE sys_changes SET revert_at = ? WHERE id = ?", (time.time() - 1, r2["change_id"]))
    assert syscontrol.process_due_reverts() == 0


def test_undo_everything_replays_newest_first(cc):
    go_real(cc)
    h = arm(cc)
    for name in ("Spooler",):
        wait(cc, cc.post("/api/system/run", json={"action": "service_stop", "params": {"name": name}}, headers=h).json()["id"])
    wait(cc, cc.post("/api/system/run", json={"action": "user_disable", "params": {"name": "bob"}}, headers=h).json()["id"])
    assert cc.post("/api/system/undo-all").status_code == 403
    r = cc.post("/api/system/undo-all", headers=h).json()
    assert len(r["undone"]) == 2 and r["undone"] == sorted(r["undone"], reverse=True) and not r["failed"]


def test_every_action_is_constant_text_driven_by_environment():
    for a in sysactions.ACTIONS:
        for s in (a["script"], a["capture"], a["restore"]):
            if not s:
                continue
            assert "Invoke-Expression" not in s and "iex " not in s.lower() and "{BI_" not in s, a["id"]
        for p in a["params"]:
            assert f"$env:BI_P_{p['name']}" in a["script"], (a["id"], p["name"])
        if a["restore"]:
            assert a["capture"], a["id"]
        assert a["risk"] in ("low", "medium", "high")
        if a["risk"] == "high":
            assert a["typed"] or a["id"] in ("restore_point",), a["id"]


def test_scan_analysis_finds_the_planted_leads():
    f = sysscan.analyze("scan_startup", syscontrol.SAMPLE["scan_startup"])["findings"]
    assert f[0]["severity"] == "medium" and "ExampleSync" in f[0]["title"]
    f = sysscan.analyze("scan_privacy", syscontrol.SAMPLE["scan_privacy"])["findings"]
    assert f and "In use right now" in f[0]["title"]
    f = sysscan.analyze("scan_system", syscontrol.SAMPLE["scan_system"])["findings"]
    titles = " | ".join(x["title"] for x in f)
    assert "definitions are 12 days old" in titles and "Public firewall profile is off" in titles and "hosts file" in titles
    f = sysscan.analyze("scan_accounts", syscontrol.SAMPLE["scan_accounts"])["findings"]
    assert any("Guest" in x["title"] for x in f)
    f = sysscan.analyze("scan_remote", syscontrol.SAMPLE["scan_remote"])["findings"]
    assert any("Remote Desktop" in x["title"] for x in f)
    f = sysscan.analyze("scan_startup", [{"name": "x", "where": "w", "exe": "C:\\a.exe", "sig": "HashMismatch"}])["findings"]
    assert f[0]["severity"] == "high"
    assert sysscan.analyze("scan_system", {"defender": {"antivirus": True, "realtime": False}, "uac_enabled": False})["counts"]["high"] == 2


def test_settings_reset_and_restore(cc):
    cc.put("/api/workspaces/practice/settings", json={"backup_keep": 3, "auto_backup": True})
    assert cc.get("/api/workspaces/practice/settings").json()["backup_keep"] == 3
    r = cc.post("/api/system/settings/reset", json={"scope": "practice"}).json()
    assert r["removed"] >= 1 and r["settings"]["practice"]["backup_keep"] == 14
    snaps = cc.get("/api/system/settings").json()["snapshots"]
    assert snaps and snaps[0]["label"].startswith("before reset")
    back = cc.post("/api/system/settings/restore", json={"id": r["snapshot"]["id"]}).json()
    assert back["settings"]["practice"]["backup_keep"] == 3
    assert cc.post("/api/system/settings/reset", json={"scope": "mars"}).status_code == 400
    assert cc.post("/api/system/settings/restore", json={"id": 999}).status_code == 404
