import io


def _load(client, name="messy"):
    csv = ("id,city,amount,joined\n1, NY ,10,2024-01-01\n2,ny,12,2024-01-02\n3,Boston,11,2024-01-03\n4,Boston,,2024-01-04\n5,Boston,13,2024-01-05\n"
           "5,Boston,13,2024-01-05\n6,Dallas,11,2024-01-06\n7,Dallas,12,2024-01-07\n8,Dallas,10,2024-01-08\n9,NY,9000,2024-01-09\n")
    r = client.post("/api/data/import", data={"table": name, "mode": "replace"}, files={"file": ("m.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert r.status_code == 200, r.text


def test_inspect_finds_the_usual_problems(client):
    _load(client)
    r = client.get("/api/stats/clean/inspect", params={"table": "messy"})
    assert r.status_code == 200
    d = r.json()
    kinds = {(i["kind"], i.get("column")) for i in d["issues"]}
    assert d["duplicate_rows"] == 1 and ("case", "city") in kinds and ("missing", "amount") in kinds and ("outliers", "amount") in kinds
    assert d["health"] < 100 and client.get("/api/stats/clean/inspect", params={"table": "nope"}).status_code == 404


def test_clean_makes_new_table_and_logs(client):
    _load(client)
    steps = [{"op": "dedupe"}, {"op": "trim"}, {"op": "upper", "column": "city"}, {"op": "fill_missing", "column": "amount", "method": "median"},
             {"op": "remove_outliers", "column": "amount"}, {"op": "standardize", "column": "city", "mapping": {"NY": "New York"}}]
    r = client.post("/api/stats/clean", json={"table": "messy", "new_table": "messy_clean", "steps": steps, "note": "demo"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["rows_before"] == 10 and d["rows_after"] == 8 and d["health_after"] >= d["health_before"]
    assert [x["rows_removed"] for x in d["log"]][:1] == [1]
    desc = client.post("/api/stats/describe", json={"source": "messy_clean"}).json()
    city = next(c for c in desc["categories"] if c["column"] == "city")
    assert {t["value"] for t in city["top"]} == {"NEW YORK", "BOSTON", "DALLAS"} or {t["value"] for t in city["top"]} == {"New York", "BOSTON", "DALLAS"}
    assert next(n for n in desc["numbers"] if n["column"] == "amount")["missing"] == 0 and desc["rows"] == 8
    assert client.get("/api/stats/clean/inspect", params={"table": "messy"}).json()["rows"] == 10      # original untouched
    notes = client.get("/api/stats/qual").json()["items"]
    assert any(i["kind"] == "wrangle" and i["data"]["published_as"] == "messy_clean" for i in notes)


def test_clean_validation(client):
    _load(client)
    bad = lambda steps, new="x_clean": client.post("/api/stats/clean", json={"table": "messy", "new_table": new, "steps": steps}).status_code  # noqa: E731
    assert bad([{"op": "drop_table"}]) == 400
    assert bad([{"op": "trim", "column": "amount"}]) == 400
    assert bad([{"op": "fill_missing", "column": "amount", "method": "value", "value": "abc"}]) == 400
    assert bad([{"op": "dedupe"}], new="messy") == 400
    assert bad([{"op": "convert", "column": "no_such", "to": "number"}]) == 400
    assert bad([{"op": "drop_missing", "columns": ["id"]}], new="events_clean") in (200, 400)


def test_agent_analyze_tool(client):
    from app.services import agents
    _load(client)
    res = agents.ChatResult()
    out, err = agents._tool("analyst", "analyze", {"kind": "distribution", "source": "messy", "column": "amount"}, res)
    assert not err and '"n": 9' in out
    out, err = agents._tool("analyst", "analyze", {"kind": "correlation", "source": "messy", "columns": ["id", "amount"]}, res)
    assert not err and "pearson" in out
    out, err = agents._tool("analyst", "analyze", {"kind": "drop_everything", "source": "messy"}, res)
    assert err
    out, err = agents._tool("pm", "analyze", {"kind": "describe", "source": "messy"}, res)
    assert err
    assert "analyze" in [t["name"] for t in [agents.TOOL_ANALYZE]] and "analyst" in agents.ANALYZE_TRACKS


def test_rollup_one_row_per_entity(client):
    csv = "customer,amount,day,vip,city\nA,10,2026-01-01,true,X\nA,30,2026-02-01,true,Y\nB,5,2026-01-05,false,X\nC,7,2026-03-01,false,X\n"
    r = client.post("/api/data/import", files={"file": ("orders.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    t = r.json()["table"]
    j = client.post("/api/stats/rollup", json={"table": t, "entity_col": "customer", "new_table": "per_customer"}).json()
    assert j["entities"] == 3 and j["records_used"] == 4
    j2 = client.post("/api/stats/rollup", json={"table": t, "entity_col": "customer", "new_table": "per_customer2",
                                                "cohort": [{"column": "amount", "op": "gte", "value": 10}]}).json()
    assert j2["entities"] == 1 and j2["records_used"] == 2
    assert client.post("/api/stats/rollup", json={"table": t, "entity_col": "nope", "new_table": "x"}).status_code == 400
    assert client.post("/api/stats/rollup", json={"table": t, "entity_col": "customer", "new_table": "x",
                                                  "cohort": [{"column": "amount", "op": "gt", "value": 999}]}).status_code == 400


def test_placeholder_and_many_levels(client):
    import io
    rows = ["id,age,city"] + [f"{i},{20 + i % 50 if i % 20 else 999},{'c' + str(i % 30) if i % 7 else 'Big'}" for i in range(200)]
    r = client.post("/api/data/import", data={"table": "ph", "mode": "replace"}, files={"file": ("ph.csv", io.BytesIO("\n".join(rows).encode()), "text/csv")})
    assert r.status_code == 200, r.text
    ins = client.get("/api/stats/clean/inspect", params={"table": "ph"}).json()
    kinds = {(i["kind"], i.get("column")) for i in ins["issues"]}
    assert ("placeholder", "age") in kinds and ("many_levels", "city") in kinds
    ph = next(i for i in ins["issues"] if i["kind"] == "placeholder")
    assert ph["value"] == 999
    j = client.post("/api/stats/clean", json={"table": "ph", "new_table": "ph_clean", "steps": [
        {"op": "set_missing", "column": "age", "value": 999}, {"op": "group_rare", "column": "city", "min_share": 0.05}]}).json()
    after = j["verification"]
    assert not any(i["kind"] == "placeholder" for i in after["issues"])
    assert not any(i["kind"] == "many_levels" for i in after["issues"])
    assert client.post("/api/stats/clean", json={"table": "ph", "new_table": "z", "steps": [{"op": "group_rare", "column": "city", "min_share": 0.9}]}).status_code == 400


def test_feature_engineering_steps(client):
    import io
    csv = "id,rev,cost,day\n" + "\n".join(f"{i},{100 + i},{50 + i % 7},2026-0{1 + i % 9}-1{i % 9}" for i in range(40))
    assert client.post("/api/data/import", data={"table": "fe", "mode": "replace"}, files={"file": ("fe.csv", io.BytesIO(csv.encode()), "text/csv")}).status_code == 200
    steps = [{"op": "add_feature", "how": "ratio", "name": "margin_ratio", "a": "cost", "b": "rev"},
             {"op": "add_feature", "how": "date_part", "name": "month", "a": "day", "part": "month"},
             {"op": "add_feature", "how": "bucket", "name": "rev_group", "a": "rev", "bins": 4},
             {"op": "add_feature", "how": "flag", "name": "big", "a": "rev", "op2": "gt", "value": 120},
             {"op": "add_feature", "how": "log", "name": "log_rev", "a": "rev"}]
    j = client.post("/api/stats/clean", json={"table": "fe", "new_table": "fe_feat", "steps": steps})
    assert j.status_code == 200, j.text
    names = {c["name"] for c in j.json()["verification"]["columns"]}
    assert {"margin_ratio", "month", "rev_group", "big", "log_rev"} <= names
    assert client.post("/api/stats/clean", json={"table": "fe", "new_table": "x", "steps": [{"op": "add_feature", "how": "ratio", "name": "rev", "a": "cost", "b": "rev"}]}).status_code == 400
    from app.services import agents
    out = agents._analyze({"kind": "inspect", "source": "fe"}, True)
    assert "health" in out


def test_repeat_within_outcome(client):
    import io
    csv = "cust,day\nA,2026-01-01\nA,2026-01-20\nA,2026-06-01\nB,2026-02-01\nC,2026-03-01\nC,2026-05-01\n"
    assert client.post("/api/data/import", data={"table": "rw", "mode": "replace"}, files={"file": ("rw.csv", io.BytesIO(csv.encode()), "text/csv")}).status_code == 200
    j = client.post("/api/stats/clean", json={"table": "rw", "new_table": "rw2", "steps": [{"op": "add_feature", "how": "repeat_within", "name": "back30", "entity": "cust", "a": "day", "days": 30}]})
    assert j.status_code == 200, j.text
    r = client.post("/api/stats/rollup", json={"table": "rw2", "entity_col": "cust", "new_table": "rw3"}).json()
    assert r["entities"] == 3
    assert client.post("/api/stats/clean", json={"table": "rw", "new_table": "x", "steps": [{"op": "add_feature", "how": "repeat_within", "name": "z", "entity": "cust", "a": "day", "days": 0}]}).status_code == 400


def test_before_after_column(client):
    import io
    csv = "day,v\n" + "\n".join(f"2026-0{1 + i % 6}-1{i % 9},{i}" for i in range(30))
    assert client.post("/api/data/import", data={"table": "ba", "mode": "replace"}, files={"file": ("ba.csv", io.BytesIO(csv.encode()), "text/csv")}).status_code == 200
    j = client.post("/api/stats/clean", json={"table": "ba", "new_table": "ba2", "steps": [{"op": "add_feature", "how": "before_after", "name": "period", "a": "day", "cutoff": "2026-04-01"}]})
    assert j.status_code == 200, j.text
    c = client.post("/api/stats/compare", json={"source": "ba2", "value_col": "v", "group_col": "period"})
    assert c.status_code == 200, c.text
    assert client.post("/api/stats/clean", json={"table": "ba", "new_table": "x", "steps": [{"op": "add_feature", "how": "before_after", "name": "p", "a": "day", "cutoff": "soon"}]}).status_code == 400
