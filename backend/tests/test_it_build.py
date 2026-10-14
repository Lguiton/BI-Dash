import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.services import backup_lab as bl, inventory_agent as ia, known_errors

ROOT = Path(__file__).resolve().parents[2]


def _mk(tmp_path):
    s = tmp_path / "src"
    (s / "d").mkdir(parents=True)
    (s / "a.txt").write_text("one")
    (s / "d" / "b.txt").write_text("two")
    return s, tmp_path / "repo"


def test_incremental_snapshots(tmp_path):
    s, r = _mk(tmp_path)
    first = bl.snapshot(s, r, "first")
    assert first["first_backup"] and sorted(first["added"]) == ["a.txt", "d/b.txt"] and first["new_bytes_stored"] == 6
    again = bl.snapshot(s, r)
    assert again["added"] == [] and again["changed"] == [] and again["unchanged"] == 2 and again["new_bytes_stored"] == 0
    (s / "a.txt").write_text("ONE!")
    (s / "c.txt").write_text("new")
    (s / "d" / "b.txt").unlink()
    third = bl.snapshot(s, r)
    assert third["changed"] == ["a.txt"] and third["added"] == ["c.txt"] and third["removed"] == ["d/b.txt"]
    assert len(bl.list_snapshots(r)) == 3


def test_restore_drill_and_verification(tmp_path):
    s, r = _mk(tmp_path)
    sid = bl.snapshot(s, r)["id"]
    (s / "a.txt").write_text("changed")
    (s / "new.txt").write_text("x")
    d = bl.drill(r, sid, s)
    assert d["restore_ok"] and d["changed_since"] == ["a.txt"] and d["new_since"] == ["new.txt"] and d["identical_to_live"] == 1
    out = tmp_path / "out"
    assert bl.restore(r, sid, out)["ok"] and (out / "a.txt").read_text() == "one"
    with pytest.raises(bl.BackupError):
        bl.restore(r, sid, out)
    assert bl.verify(r)["ok"]
    obj = next((r / "objects").glob("*/*"))
    obj.write_bytes(b"rot")
    assert not bl.verify(r)["ok"] and bl.verify(r)["corrupt"]
    bad = bl.restore(r, sid, tmp_path / "out2")
    assert not bad["ok"] and bad["failed"]


def test_unsafe_snapshot_paths_are_refused(tmp_path):
    s, r = _mk(tmp_path)
    sid = bl.snapshot(s, r)["id"]
    f = r / "snapshots" / f"{sid}.json"
    m = json.loads(f.read_text())
    m["files"]["../evil.txt"] = m["files"]["a.txt"]
    f.write_text(json.dumps(m))
    with pytest.raises(bl.BackupError):
        bl.restore(r, sid, tmp_path / "o")
    assert not (tmp_path / "evil.txt").exists()


def test_prune_and_guards(tmp_path):
    s, r = _mk(tmp_path)
    bl.snapshot(s, r)
    (s / "a.txt").write_text("v2")
    bl.snapshot(s, r)
    p = bl.prune(r, 1)
    assert p["snapshots_removed"] == 1 and p["objects_removed"] == 1 and bl.verify(r)["ok"]
    with pytest.raises(bl.BackupError):
        bl.prune(r, 0)
    with pytest.raises(bl.BackupError):
        bl.snapshot(s, s / "inside")
    with pytest.raises(bl.BackupError):
        bl.snapshot(tmp_path / "missing", r)


def test_backup_cli(tmp_path):
    s, r = _mk(tmp_path)
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts" / "backup_tool.py"), *a], capture_output=True, text=True)  # noqa: E731
    b = run("backup", str(s), str(r))
    assert b.returncode == 0 and json.loads(b.stdout)["files"] == 2
    sid = json.loads(run("list", str(r)).stdout)[0]["id"]
    assert run("verify", str(r)).returncode == 0
    assert run("drill", str(r), sid, str(s)).returncode == 0
    assert run("restore", str(r), sid, str(tmp_path / "x")).returncode == 0
    assert run("restore", str(r), "nope", str(tmp_path / "y")).returncode == 1


def test_backup_practice_area(client):
    assert client.post("/api/backuplab/reset").json()["ready"]
    assert client.post("/api/backuplab/edit", json={"action": "corrupt"}).status_code == 400
    s1 = client.post("/api/backuplab/snapshot", json={"label": "a"}).json()["result"]
    assert len(s1["added"]) == 5
    client.post("/api/backuplab/edit", json={"action": "modify"})
    client.post("/api/backuplab/edit", json={"action": "add"})
    client.post("/api/backuplab/edit", json={"action": "delete"})
    s2 = client.post("/api/backuplab/snapshot", json={}).json()["result"]
    assert len(s2["changed"]) == 1 and len(s2["added"]) == 1 and len(s2["removed"]) == 1
    snaps = client.get("/api/backuplab").json()["snapshots"]
    d = client.post("/api/backuplab/drill", json={"id": snaps[0]["id"]}).json()
    assert d["restore_ok"] and d["changed_since"]
    assert client.post("/api/backuplab/restore", json={"id": snaps[0]["id"]}).json()["ok"]
    assert client.post("/api/backuplab/verify").json()["ok"]
    client.post("/api/backuplab/edit", json={"action": "corrupt"})
    assert not client.post("/api/backuplab/verify").json()["ok"]
    assert client.post("/api/backuplab/edit", json={"action": "format_disk"}).status_code == 400
    assert client.post("/api/backuplab/drill", json={"id": "nope"}).status_code == 404
    assert client.post("/api/backuplab/prune", json={"keep": 1}).json()["result"]["snapshots_removed"] == 1


def test_inventory_agent_script_and_import(client):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "inventory_agent.py")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    rep = json.loads(out.stdout)
    assert rep["schema"] == 1 and rep["hostname"] and isinstance(rep["disks"], list)
    forbidden = {"users", "files", "software", "apps", "history", "passwords"}
    assert not forbidden & set(rep)
    rep["serial"] = "SN-TEST-1"
    r = client.post("/api/it-agent/import", json={"text": json.dumps(rep)}).json()
    assert r["created"] == [rep["hostname"]]
    rep["os"] = "Linux changed"
    r2 = client.post("/api/it-agent/import", json={"text": json.dumps([rep])}).json()
    assert r2["updated"] == [rep["hostname"]] and not r2["created"]
    rows = client.get("/api/it/assets").json()["assets"]
    assert len(rows) == 1 and rows[0]["os"] == "Linux changed" and rows[0]["serial"] == "SN-TEST-1" and "Agent:" in rows[0]["notes"]
    two = client.post("/api/it-agent/import", json={"text": json.dumps({"hostname": "pc-2", "kind": "laptop", "os": "Windows 11"}) + "\n" + json.dumps({"kind": "desktop"}) + "\n" + json.dumps({"hostname": "pc-3", "schema": 9})}).json()
    assert two["created"] == ["pc-2"] and len(two["skipped"]) == 2
    for bad in ("", "not json", "[1, 2]"):
        assert client.post("/api/it-agent/import", json={"text": bad}).status_code == 400
    sc = client.get("/api/it-agent/script")
    assert sc.status_code == 200 and "WHAT IT DOES NOT COLLECT" in sc.text


def test_sources_registered():
    assert "backup_lab" in known_errors.SOURCES and len(bl.SLIPS) == 3 and ia.SCRIPT.exists()
