import random

from tests.conftest import csv_file


def _alloc_csv():
    # three channels with different return per unit of spend: A=2x, B=3x, C=1x; 20 rows each, 5 spend per row
    lines = ["channel,spend,revenue"]
    for ch, rate in (("A", 2.0), ("B", 3.0), ("C", 1.0)):
        for i in range(20):
            lines.append(f"{ch},5,{5 * rate}")
    return "\n".join(lines) + "\n"


def test_allocation_matches_hand_solution(client):
    client.post("/api/data/import", files=csv_file(_alloc_csv(), "ads.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "revenue", "effort_col": "spend"}).json()
    a = {x["group"]: x for x in r["allocation"]}
    # each channel spends 100 now; budget 300; limits 50..150. Best: B=150, A=100, C=50
    assert (a["B"]["recommended"], a["A"]["recommended"], a["C"]["recommended"]) == (150.0, 100.0, 50.0)
    assert r["return_now"] == 600.0 and r["return_new"] == 700.0 and r["gain"] == 100.0 and r["spent"] == 300.0
    assert a["B"]["change_pct"] == 50.0 and a["C"]["change_pct"] == -50.0
    # more budget: everything goes to its cap except the worst channel
    big = client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "revenue", "effort_col": "spend", "budget": 400}).json()
    assert {x["group"]: x["recommended"] for x in big["allocation"]} == {"B": 150.0, "A": 150.0, "C": 100.0}
    tight = client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "revenue", "effort_col": "spend", "budget": 100})
    assert tight.status_code == 400 and "minimum" in tight.json()["detail"]
    same = client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "spend", "effort_col": "spend"})
    assert same.status_code == 400
    assert client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "revenue", "effort_col": "spend", "min_mult": 2}).status_code == 422
    thin = client.post("/api/stats/allocate", json={"source": "ads", "group_col": "channel", "return_col": "revenue", "effort_col": "spend", "min_rows": 30}).json()
    assert all(x["thin"] for x in thin["allocation"]) and any("fewer than" in w for w in thin["warnings"])


def test_goal_seek_recovers_known_slope(client):
    rnd = random.Random(9)
    lines = ["price,ads,sales"]
    for _ in range(300):
        p, ad = rnd.uniform(5, 15), rnd.uniform(0, 100)
        lines.append(f"{p:.2f},{ad:.2f},{200 - 8 * p + 1.5 * ad + rnd.gauss(0, 5):.2f}")
    client.post("/api/data/import", files=csv_file("\n".join(lines) + "\n", "shop.csv"), data={"mode": "replace"})
    base = {"source": "shop", "y": "sales", "levers": ["price", "ads"]}
    cur = client.post("/api/stats/goal", json={**base, "target": 0}).json()["current"]
    r = client.post("/api/stats/goal", json={**base, "target": cur + 30}).json()
    o = {x["lever"]: x for x in r["options"]}
    assert abs(o["ads"]["change_needed"] - 30 / 1.5) < 1.5 and abs(o["price"]["change_needed"] - 30 / -8) < 0.5
    assert o["ads"]["reliable"] and o["ads"]["inside_observed_range"]
    assert r["plan"]["pct_each"] is not None and r["plan"]["levers"]
    far = client.post("/api/stats/goal", json={**base, "target": cur + 5000}).json()
    assert any(not x["inside_observed_range"] for x in far["options"]) and any("outside" in w for w in far["warnings"])
    assert client.post("/api/stats/goal", json={**base, "target": cur, "levers": []}).status_code == 422
    assert client.post("/api/stats/goal", json={"source": "shop", "y": "sales", "target": 1, "levers": ["sales"]}).status_code == 400


def test_decision_brief_chains_the_four_steps(client):
    rnd = random.Random(4)
    from datetime import date, timedelta
    lines = ["day,region,qty,revenue"]
    for i in range(90):
        for reg, k in (("West", 12), ("East", 10), ("North", 6)):
            q = rnd.randint(5, 15)
            lines.append(f"{date(2026, 1, 1) + timedelta(days=i)},{reg},{q},{q * k + i * 0.5 + rnd.gauss(0, 3):.2f}")
    client.post("/api/data/import", files=csv_file("\n".join(lines) + "\n", "reg.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/brief", json={"source": "reg", "metric": "revenue", "group_col": "region", "date_col": "day"}).json()
    kinds = [s["kind"] for s in r["sections"]]
    assert kinds[0] == "descriptive" and "diagnostic" in kinds and "predictive" in kinds and kinds[-1] == "prescriptive"
    assert any("North" in " ".join(s["lines"]) for s in r["sections"] if s["kind"] == "prescriptive")
    soft = client.post("/api/stats/brief", json={"source": "reg", "metric": "revenue"}).json()
    assert "prescriptive" not in [s["kind"] for s in soft["sections"]] and any("group column" in n for n in soft["notes"])
    assert client.post("/api/stats/brief", json={"source": "reg", "metric": "region"}).status_code == 400


def _series_csv(first_days, jump_from=None, jump=0.0, name="m"):
    rnd = random.Random(8)
    from datetime import date, timedelta
    lines = ["day,region,sales"]
    for i in range(first_days):
        v = 100 + rnd.gauss(0, 4) + (jump if jump_from is not None and i >= jump_from else 0)
        lines.append(f"{date(2026, 1, 1) + timedelta(days=i)},W,{v:.2f}")
    return "\n".join(lines) + "\n"


def test_input_check_flags_problems(client):
    rows = ["day,region,price,qty"]
    rnd = random.Random(2)
    from datetime import date, timedelta
    for i in range(40):
        rows.append(f"{date(2026, 1, 1) + timedelta(days=i)},{'W' if i % 20 else 'E'},{rnd.gauss(10, 1):.2f},{'' if i % 4 == 0 else rnd.randint(1, 5)}")
    rows.append("2026-02-15,W,9999,3")
    client.post("/api/data/import", files=csv_file("\n".join(rows) + "\n", "chk.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/input-check", json={"source": "chk", "columns": ["price", "qty"], "date_col": "day", "group_col": "region"}).json()
    by = {c["check"]: c for c in r["checks"]}
    assert r["verdict"] in ("amber", "red") and r["reminders"]
    assert by["Gaps in qty"]["level"] in ("warn", "bad") and by["Extreme values in price"]["level"] == "warn"
    assert by["Fresh data"]["level"] == "bad"  # 2026-02-15 is long before "today" in the test clock
    assert by["Group sizes in region"]["level"] == "warn"
    assert client.post("/api/stats/input-check", json={"source": "chk", "columns": ["nope"]}).status_code == 400
    good = random.Random(1)
    from datetime import date as D
    today = D.today()
    rows = ["day,region,v"] + [f"{today - timedelta(days=i)},{'A' if i % 2 else 'B'},{100 + good.gauss(0, 3):.2f}" for i in range(200)]
    client.post("/api/data/import", files=csv_file("\n".join(rows) + "\n", "fresh.csv"), data={"mode": "replace"})
    ok = client.post("/api/stats/input-check", json={"source": "fresh", "columns": ["v"], "date_col": "day", "group_col": "region"}).json()
    assert ok["verdict"] == "green"


def test_tracking_a_decision(client):
    client.post("/api/data/import", files=csv_file(_series_csv(60), "tr.csv"), data={"mode": "replace"})
    t = client.post("/api/stats/track", json={"source": "tr", "metric": "sales", "date_col": "day", "title": "Raise price 5%", "action": "Price test", "target": 110}).json()
    assert t["status"] == "waiting" and 95 < t["baseline"] < 105 and t["start"] == "2026-03-02"
    # newer data arrives after the decision: +12 on average
    from datetime import date, timedelta
    more = ["day,region,sales"] + [f"{date(2026, 3, 2) + timedelta(days=i)},W,{112 + (i % 3) - 1}" for i in range(20)]
    client.post("/api/data/import", files=csv_file("\n".join(more) + "\n", "tr.csv"), data={"mode": "append"})
    items = client.get("/api/stats/track").json()["items"]
    assert len(items) == 1 and items[0]["status"] == "on target" and items[0]["unusual"] is True and items[0]["progress_pct"] >= 100
    assert client.post("/api/stats/track", json={"source": "tr", "metric": "sales", "date_col": "day", "title": "  ", "baseline_days": 30}).status_code in (400, 422)
    assert client.post("/api/stats/track", json={"source": "tr", "metric": "region", "date_col": "day", "title": "x"}).status_code == 400
    assert client.delete(f"/api/stats/track/{t['id']}").json()["deleted"] == t["id"]
    assert client.delete(f"/api/stats/track/{t['id']}").status_code == 404
    assert client.get("/api/stats/track").json()["items"] == []
