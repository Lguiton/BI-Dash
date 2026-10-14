import time

from app.services import bigdata


def _wait(client, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        j = client.get("/api/stats/bigdata/job").json()
        if j["status"] != "running":
            return j
        time.sleep(0.3)
    raise AssertionError("job did not finish")


def test_plan_reports_machine_and_caps(client):
    s = client.get("/api/stats/bigdata").json()
    assert s["machine"]["cpus"] and s["machine"]["disk_free_bytes"] > 0 and s["max_rows"] <= bigdata.MAX_ROWS
    assert [p["rows"] for p in s["presets"]] == bigdata.PRESETS and s["dataset"] is None
    assert "cluster" in s["honest_note"]
    assert client.post("/api/stats/bigdata/generate", json={"rows": 100}).status_code == 422
    assert client.post("/api/stats/bigdata/generate", json={"rows": bigdata.MAX_ROWS + 1}).status_code == 422
    assert client.post("/api/stats/bigdata/benchmark").status_code == 400  # no data yet


def test_disk_guard_refuses_too_many_rows(client, monkeypatch):
    monkeypatch.setattr(bigdata, "_machine", lambda: {"cpus": 2, "ram_bytes": 1, "disk_free_bytes": 50_000_000, "disk_total_bytes": 1})
    r = client.post("/api/stats/bigdata/generate", json={"rows": 1_000_000})
    assert r.status_code == 400 and "free" in r.json()["detail"] and "most I'll make" in r.json()["detail"]
    assert bigdata.max_rows_for_disk(0) == 0


def test_generate_benchmark_and_cleanup(client):
    r = client.post("/api/stats/bigdata/generate", json={"rows": 60_000})
    assert r.status_code == 200
    assert client.post("/api/stats/bigdata/generate", json={"rows": 60_000}).status_code in (409, 200)  # second start is refused while running (or already done)
    j = _wait(client)
    assert j["status"] == "done" and j["error"] is None and j["result"]["rows"] == 60_000
    d = client.get("/api/stats/bigdata").json()["dataset"]
    assert d["rows"] == 60_000 and d["parquet_bytes"] < d["csv_bytes"] and d["partitions"] >= 20 and d["partition_files"] >= 20
    assert client.post("/api/stats/bigdata/benchmark").status_code == 200
    jj = _wait(client); assert jj["error"] is None, jj; b = jj["result"]
    assert b["all_formats_agree"] is True and b["rows"] == 60_000 and len(b["queries"]) == 4
    assert all(set(q["ms"]) == {"csv", "parquet", "partitioned"} for q in b["queries"])
    assert b["compression_vs_csv"] > 1.5 and b["sample"]["error_pct"] < 5
    month = b["queries"][1]["result"][0]
    assert 0 < month[0] < 60_000 / 10  # one month of ~24 holds a small slice of the rows
    freed = client.delete("/api/stats/bigdata").json()["freed_bytes"]
    assert freed > 0 and client.get("/api/stats/bigdata").json()["dataset"] is None
    assert not bigdata.folder().exists()
