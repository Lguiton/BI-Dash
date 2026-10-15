"""Business-data backup (make, restore test, restore, tamper) and the Today screen."""
import json
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

from app.services import bizbackup as bb


def _client(client, name="Backup Co"):
    return client.post("/api/clients", json={"name": name}).json()


def test_backup_includes_business_records_and_passes_restore_test(client):
    c = _client(client)
    client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Job A"})
    client.post("/api/leads", json={"name": "L1"})
    r = client.post("/api/biz-backup").json()
    assert r["counts"]["clients"] == 1 and r["counts"]["jobs"] == 1 and r["counts"]["leads"] == 1
    assert r["test"]["ok"] and [c["name"] for c in r["test"]["checks"]] == ["Opens as a backup", "Checksum matches", "Database is healthy", "Records are all there"]
    listing = client.get("/api/biz-backup").json()
    assert listing["backups"][0]["tested"]["ok"] and listing["status"]["warning"] == ""


def test_restore_brings_back_deleted_records_and_takes_safety_bundle(client):
    c = _client(client)
    name = client.post("/api/biz-backup").json()["name"]
    client.delete(f"/api/clients/{c['id']}")
    assert client.get("/api/clients").json()["clients"] == []
    assert client.post(f"/api/biz-backup/{name}/restore", json={}).status_code == 400          # needs confirm
    assert client.post(f"/api/biz-backup/{name}/restore", json={"confirm": True}).status_code == 200
    assert [x["name"] for x in client.get("/api/clients").json()["clients"]] == ["Backup Co"]
    kinds = [b["kind"] for b in client.get("/api/biz-backup").json()["backups"]]
    assert "safety-before-restore" in kinds


def test_tampered_backup_fails_test_and_is_not_restored(client):
    _client(client)
    name = client.post("/api/biz-backup").json()["name"]
    p = bb._dir() / name
    # rewrite the zip with a different database but the old manifest
    other = p.with_name("other.sqlite")
    other.write_bytes(b"not a database at all, just bytes")
    man = zipfile.ZipFile(p).read("manifest.json")
    p.unlink()
    with zipfile.ZipFile(p, "w") as z:
        z.write(other, "state.sqlite")
        z.writestr("manifest.json", man)
    other.unlink()
    res = client.post(f"/api/biz-backup/{name}/test").json()
    assert res["ok"] is False and any(not c["ok"] for c in res["checks"])
    r = client.post(f"/api/biz-backup/{name}/restore", json={"confirm": True})
    assert r.status_code == 409 and "failed its restore test" in r.json()["detail"]
    assert len(client.get("/api/clients").json()["clients"]) == 1               # live data untouched
    assert "FAILED" in client.get("/api/biz-backup").json()["status"]["warning"]


def test_damaged_zip_and_bad_names(client):
    name = "20250101-000000_manual.zip"
    (bb._dir() / name).write_bytes(b"junk")
    assert client.post(f"/api/biz-backup/{name}/test").json()["ok"] is False
    assert client.post("/api/biz-backup/..%2Fx.zip/test").status_code in (404, 405)
    assert client.post("/api/biz-backup/nope.zip/test").status_code == 404
    assert client.get("/api/biz-backup/20250101-000001_manual.zip/download").status_code == 404


def test_download_and_delete(client):
    name = client.post("/api/biz-backup").json()["name"]
    r = client.get(f"/api/biz-backup/{name}/download")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert client.delete(f"/api/biz-backup/{name}").json() == {"deleted": name}
    assert client.get("/api/biz-backup").json()["backups"] == []


def test_copy_goes_to_chosen_folder(client, tmp_path):
    from app.services import state
    dest = tmp_path / "usb"
    state.kv_set("backup_copy_dir", str(dest))
    name = client.post("/api/biz-backup").json()["name"]
    assert (dest / f"business_{name}").exists()
    assert state.kv_get("bizbackup_copy_last", "").endswith("ok")
    state.kv_set("backup_copy_dir", str(tmp_path / "usb" / "business_" / "x.zip" / "nope"))      # a folder that can't be made must not break the backup
    (tmp_path / "usb" / "business_").write_text("a file, so the folder can't be created")
    assert (bb._dir() / client.post("/api/biz-backup").json()["name"]).exists()
    assert "failed" in state.kv_get("bizbackup_copy_last", "")


def test_status_warns_when_missing_old_or_untested(client):
    assert "no business-data backup" in bb.status()["warning"]
    b = bb.create("manual")
    assert "restore test" in bb.status()["warning"]
    bb.verify(b["name"])
    assert bb.status()["warning"] == ""
    later = datetime.now(timezone.utc) + timedelta(days=9)
    assert "days old" in bb.status(later)["warning"]


def test_tick_makes_at_most_one_per_20_hours_and_tests_it(client):
    assert bb.tick() == ["business-backup"]
    assert bb.tick() == []
    assert bb.listing()[0]["tested"]["ok"]
    assert bb.tick(datetime.now(timezone.utc) + timedelta(hours=21)) == ["business-backup"]


def test_prune_keeps_newest(client, monkeypatch):
    first = bb.path_of(bb.create("manual")["name"])
    for i in range(4):
        shutil.copy(first, bb._dir() / f"2025010{i + 1}-000000_manual.zip")
    monkeypatch.setattr(bb, "KEEP", 2)
    bb.create("manual")                                           # making one prunes down to the newest two
    manual = [b["name"] for b in bb.listing() if b["kind"] == "manual"]
    assert len(manual) == 2 and "20250101-000000_manual.zip" not in manual and manual[0] > "2026"


def test_today_extras_on_empty_workspace(client):
    t = client.get("/api/today").json()
    assert [x["href"] for x in t["todo"]] == ["/settings"]            # only the business-backup warning
    assert t["money"]["owed"] == 0


def test_today_extras_list_only_what_home_does_not(client):
    from datetime import date
    c = _client(client, "Late Co")
    past = (date.today() - timedelta(days=5)).isoformat()
    j = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Done job", "status": "active"}).json()
    client.post("/api/clients/time/add", json={"job_id": j["id"], "hours": 2})
    q = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Quoted job", "status": "quoted", "quote": 300}).json()
    inv = client.post("/api/clients/invoices/create", json={"client_id": c["id"], "extra": [{"desc": "Setup", "qty": 1, "rate": 50}], "from_time": False}).json()
    client.post("/api/leads", json={"name": "Hot lead", "next_date": past})
    paid = client.post("/api/clients/invoices/create", json={"client_id": c["id"], "extra": [{"desc": "Visit", "qty": 1, "rate": 80}], "from_time": False}).json()
    client.put(f"/api/clients/invoices/{paid['id']}", json={"status": "paid"})
    t = client.get("/api/today").json()
    texts = " | ".join(x["text"] for x in t["todo"])
    assert "Hot lead" in texts and "haven't been invoiced" in texts and "draft invoice" in texts and "Quoted job" in texts and "no thank-you" in texts
    assert "past due" not in texts and "follow-up" not in texts           # Home's own panel covers those
    assert t["jobs"]["quoted"][0]["id"] == q["id"] and t["leads_due"][0]["name"] == "Hot lead"
