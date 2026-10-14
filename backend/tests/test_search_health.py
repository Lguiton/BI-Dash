from app.services import health_check, repair_search


def test_repair_search_finds_by_words_typos_and_related():
    r = repair_search.search("printr offline wifi")
    ids = [x["id"] for x in r["results"]]
    assert "printer-network" in ids[:3]
    assert repair_search.search("laptop won't turn on")["results"]
    assert repair_search.search("")["results"] == []
    assert any(x["id"].startswith("cctv") for x in repair_search.search("camera no picture")["results"][:3])


def test_search_endpoint_and_health_check(client):
    d = client.get("/api/it/repair/search", params={"q": "dash cam battery drain"}).json()
    assert d["results"]
    h = client.get("/api/health-check").json()
    assert 0 <= h["score"] <= 100 and h["checks"] and "grade" in h
    assert any(c["name"] == "Activity log seal" and c["level"] == "ok" for c in h["checks"])


def test_health_flags_old_backup(client):
    h = health_check.run()
    assert any(c["name"] == "Backups" for c in h["checks"])


def test_health_login_off_on_plain_local_setup_is_ok(client, monkeypatch):
    monkeypatch.delenv("BI_AUTH", raising=False)
    monkeypatch.delenv("BI_ALLOWED_HOSTS", raising=False)
    h = health_check.run()
    assert next(c for c in h["checks"] if c["name"] == "Login")["level"] == "ok"
    monkeypatch.setenv("BI_ALLOWED_HOSTS", "bi.example.com")
    assert next(c for c in health_check.run()["checks"] if c["name"] == "Login")["level"] == "bad"


def test_laptop_safety_checks_and_backup_copy(client, tmp_path):
    from app.services import biz_packs
    h0 = client.get("/api/health-check").json()
    assert not any(c["name"].startswith("Laptop") for c in h0["checks"])
    client.put("/api/health-check/laptop", json={"laptop": True})
    h = client.get("/api/health-check").json()
    assert any(c["name"].startswith("Laptop: Disk encryption") and c["level"] == "bad" for c in h["checks"])
    client.put("/api/health-check/laptop", json={"encrypted": True})
    h = client.get("/api/health-check").json()
    assert next(c for c in h["checks"] if "Disk encryption" in c["name"])["level"] == "ok"
    # backup copy folder: bad path refused, good path receives a copy
    assert client.put("/api/backups/copy-folder", json={"folder": "/proc/nope/x"}).status_code == 400
    dest = tmp_path / "usb"
    assert client.put("/api/backups/copy-folder", json={"folder": str(dest)}).status_code == 200
    biz_packs.install_sample("repair-jobs")
    b = client.post("/api/backups", json={"note": "t"}).json()
    assert any(f.name.endswith(b["name"]) for f in dest.iterdir())
    assert client.get("/api/backups/copy-folder").json()["last"].endswith(" ok")


def test_backup_upload_moves_data_between_computers(client):
    import io
    from app.services import biz_packs
    biz_packs.install_sample("repair-jobs")
    b = client.post("/api/backups", json={"note": "move"}).json()
    raw = client.get(f"/api/backups/{b['name']}/download").content
    r = client.post("/api/backups/upload", files={"file": ("x.duckdb", io.BytesIO(raw))})
    assert r.status_code == 200 and r.json()["kind"] == "imported" and r.json()["tables"] > 0
    assert client.post("/api/backups/upload", files={"file": ("x.duckdb", io.BytesIO(b"not a db at all" * 10))}).status_code == 400
