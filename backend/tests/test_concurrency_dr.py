"""Two drills a reviewer asked for: the pipeline and the SQL Lab running at the same time, and a disaster-recovery round trip."""
import threading

from tests.conftest import csv_file

WINDOW_SQL = ("SELECT entity_id, record_date, revenue, "
              "SUM(revenue) OVER (PARTITION BY entity_id ORDER BY record_date) AS running, "
              "RANK() OVER (PARTITION BY entity_id ORDER BY revenue DESC) AS rk FROM fact_operations LIMIT 500")


def test_pipeline_runs_while_sql_lab_and_dashboard_read(client, load_clean):
    load_clean()
    codes, errors, stop = [], [], threading.Event()

    def reader(path, method="get", body=None):
        while not stop.is_set():
            try:
                r = client.post(path, json=body) if method == "post" else client.get(path)
                codes.append(r.status_code)
                if r.status_code >= 500:
                    errors.append((path, r.text[:200]))
            except Exception as e:                      # a crash or lock error that escaped as an exception
                errors.append((path, repr(e)))

    ts = [threading.Thread(target=reader, args=("/api/sql/run", "post", {"sql": WINDOW_SQL})),
          threading.Thread(target=reader, args=("/api/analytics/summary",))]
    for t in ts:
        t.start()
    try:
        for _ in range(3):
            r = client.post("/api/pipeline/run", json={"source": "clean", "reset": False})
            assert r.status_code == 200, r.text
    finally:
        stop.set()
        for t in ts:
            t.join(timeout=30)
    assert not errors, errors[:3]
    assert len(codes) > 5 and all(c == 200 for c in codes)


def test_disaster_recovery_round_trip(client):
    csv = "tier,mrr\nBasic,10\nPlus,25\nPro,60\n"
    assert client.post("/api/data/import", files=csv_file(csv, "dr_test.csv")).status_code == 200
    before = client.get("/api/data/tables/dr_test/rows").json()
    b = client.post("/api/backups", json={"note": "drill"}).json()
    assert client.delete("/api/data/tables/dr_test").status_code == 200       # the disaster
    assert all(t["table_name"] != "dr_test" for t in client.get("/api/data/tables").json()["tables"])
    assert client.post("/api/backups/restore", json={"name": b["name"]}).status_code == 200
    after = client.get("/api/data/tables/dr_test/rows").json()
    assert after == before                                                    # same rows, same order
    kinds = [x["kind"] for x in client.get("/api/backups").json()["backups"]]
    assert "safety-before-restore" in kinds        # the restore itself can be undone (Practice takes no safety copy before a delete; Real does)
