import io

import numpy as np
import pytest

from app.services import biz_packs, datasets, intake


def sales_csv(n=160):
    rng = np.random.default_rng(2)
    rows = ["Order Date,Region,Units,Revenue,Customer Email"]
    for i in range(n):
        reg = ["East ", "east", "West", "North"][i % 4]
        rows.append(f"2026-{1 + (i // 28) % 9:02d}-{1 + i % 28:02d},{reg},{int(rng.integers(1, 30))},{100 + 12 * (i % 30) + rng.normal(0, 5):.2f},c{i}@example.com")
    rows.append(rows[1])        # a duplicate row
    return "\n".join(rows).encode()


def go(raw, fn, **kw):
    r = intake.start(raw, fn, **kw)
    return intake.run_all(r["id"])


def test_preview_writes_nothing_and_apply_does_the_work(client):
    r = go(sales_csv(), "sales.csv", name="Sales test", preview=True)
    assert r["status"] == "preview_done" and r["stages"][-1]["key"] == "preview_plan"
    assert not any("sales_test" in str(t) for t in datasets.list_tables())
    full = intake.apply(r["id"])
    f = intake.run_all(full["id"])
    assert f["status"] == "done", [(s["key"], s["status"], s["summary"]) for s in f["stages"]]
    by = {s["key"]: s for s in f["stages"]}
    assert by["security_gate"]["status"] == "ok" and by["structure"]["details"]["rows"] == 161
    assert by["clean"]["details"]["rows_after"] == 160            # duplicate removed, raw untouched
    assert any(s.startswith("lower:") for s in by["clean"]["details"]["steps"])
    assert by["privacy"]["details"]["blocked_from_ai"] == ["customer_email"]
    assert by["model"]["status"] == "skipped"
    assert by["bi"]["status"] == "ok" and by["bi"]["details"]["pack_id"]
    assert "customer_email" not in by["bi"]["details"]["measures"] + by["bi"]["details"]["categories"]
    assert f["created_objects"]["tables"] and f["created_objects"]["packs"]
    assert by["report"]["details"]["links"]


def test_report_reads_sensibly(client, capsys):
    r = go(sales_csv(), "sales.csv", name="Readable", target="revenue", preview=False)
    for st in r["stages"]:
        print(st["key"], st["status"], "|", st["summary"][:230])
    print(r["supervisor"])


def test_target_runs_the_model_stage_with_a_baseline(client):
    r = go(sales_csv(), "sales.csv", name="Sales model", target="revenue", preview=False)
    m = {s["key"]: s for s in r["stages"]}["model"]
    assert m["details"]["model_id"] and "baseline" in m["summary"].lower() or "guess" in m["summary"].lower() or "off by" in m["summary"].lower()


def test_unstructured_text_becomes_a_table(client):
    txt = "\n".join(f"Ticket {i}: customer bob{i}@example.com said the printer jammed on 2026-03-{1 + i % 27:02d} and wants a $45 refund" for i in range(40)).encode()
    r = go(txt, "notes.txt", name="Notes", preview=False)
    s = {x["key"]: x for x in r["stages"]}
    assert s["structure"]["details"]["unstructured"] is True
    cols = [c["name"] for c in s["structure"]["details"]["columns"]]
    assert {"line_no", "text", "emails", "dates", "amounts"} <= set(cols)
    assert s["privacy"]["status"] == "warn" and s["science"]["status"] in ("ok", "skipped")


def test_security_gate_stops_everything(client):
    r = go(b"MZ\x90\x00" + b"x" * 100, "payload.csv", name="Bad", preview=False)
    assert r["status"] == "stopped" and r["stages"][0]["status"] == "stopped" and r["stages"][1]["status"] == "not_run"
    assert r["created_objects"] == {"tables": [], "packs": [], "rules": []}


def test_formula_cells_warn_but_continue(client):
    csv = b"order_date,note,amount\n2026-01-01,=cmd|' /C calc'!A0,5\n2026-01-02,fine,6\n2026-01-03,ok,7\n"
    r = intake.run_all(intake.start(csv, "f.csv", preview=True)["id"])
    assert r["stages"][0]["status"] == "warn" and r["status"] == "preview_done"


def test_undo_removes_only_what_the_run_made(client):
    r = go(sales_csv(), "sales.csv", name="Undo me", preview=False)
    n_packs = len(biz_packs.custom_defs())
    u = intake.undo(r["id"])
    assert u["status"] == "undone" and u["created_objects"]["tables"] == []
    assert len(biz_packs.custom_defs()) == n_packs - 1


def test_api_flow(client):
    files = {"file": ("sales.csv", io.BytesIO(sales_csv()), "text/csv")}
    r = client.post("/api/intake/start", files=files, data={"name": "Api run", "preview": "true"})
    assert r.status_code == 200
    rid = r.json()["id"]
    for _ in range(5):
        j = client.post(f"/api/intake/{rid}/next").json()
        if j["status"] != "running":
            break
    assert j["status"] == "preview_done"
    a = client.post(f"/api/intake/{rid}/apply").json()
    for _ in range(12):
        j = client.post(f"/api/intake/{a['id']}/next").json()
        if j["status"] != "running":
            break
    assert j["status"] == "done"
    assert client.get("/api/intake").json()["runs"][0]["id"] == a["id"]
    assert client.get("/api/intake/agents").json()["stages"]
    assert client.get("/api/intake/zzzzzzzzzz").status_code == 404
    assert client.post("/api/intake/start", files={"file": ("x.exe", io.BytesIO(b"abc"), "application/octet-stream")}).status_code == 400
