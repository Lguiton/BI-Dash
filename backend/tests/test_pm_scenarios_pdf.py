import io

import pytest

from app.services import agents, fileformats, intake, pm, pm_scenarios
from app.services.providers import Call, Turn
from tests.test_math_and_shortcuts import Fake


def board(client):
    a = pm.create_item({"kind": "task", "title": "Design", "status": "todo", "duration_days": 4, "start_date": "2026-03-02", "planned_cost": 1000})["id"]
    b = pm.create_item({"kind": "task", "title": "Build", "status": "todo", "duration_days": 10, "deps": [a], "planned_cost": 5000})["id"]
    c = pm.create_item({"kind": "task", "title": "Docs", "status": "todo", "duration_days": 3, "deps": [a], "planned_cost": 600})["id"]
    d = pm.create_item({"kind": "task", "title": "Ship", "status": "todo", "duration_days": 1, "deps": [b, c], "planned_cost": 200})["id"]
    return a, b, c, d


def test_slip_on_critical_task_moves_the_finish_one_for_one(client):
    a, b, c, d = board(client)
    r = pm_scenarios.run_schedule([{"kind": "slip", "item_id": b, "days": 4}])
    assert r["before"]["days"] == 15 and r["after"]["days"] == 19 and r["delta_days"] == 4 and r["board_changed"] is False
    assert pm.get_item(b)["duration_days"] == 10                       # the board itself is untouched


def test_slip_on_slack_task_is_absorbed_until_it_becomes_critical(client):
    a, b, c, d = board(client)
    assert pm_scenarios.run_schedule([{"kind": "slip", "item_id": c, "days": 5}])["delta_days"] == 0       # Docs has 7 days of float
    r = pm_scenarios.run_schedule([{"kind": "slip", "item_id": c, "days": 9}])
    assert r["delta_days"] == 2 and "Docs" in r["newly_critical"]


def test_capacity_scope_and_cost_changes(client):
    a, b, c, d = board(client)
    r = pm_scenarios.run_schedule([{"kind": "capacity_loss", "pct": 50}])
    assert r["after"]["days"] == 30                                      # everything takes twice as long
    r = pm_scenarios.run_schedule([{"kind": "add_work", "title": "Security review", "duration_days": 3, "deps": [b], "blocks": [d], "cost": 900}])
    assert r["delta_days"] == 3 and r["after"]["cost"] == r["before"]["cost"] + 900
    r = pm_scenarios.run_schedule([{"kind": "remove", "item_id": b}])
    assert r["after"]["days"] == 8                                       # design 4 + docs 3 + ship 1
    r = pm_scenarios.run_schedule([{"kind": "cost_overrun", "pct": 10}])
    assert r["after"]["cost"] == pytest.approx(r["before"]["cost"] * 1.1)
    with pytest.raises(pm.PmError):
        pm_scenarios.run_schedule([{"kind": "slip", "item_id": 9999, "days": 1}])
    with pytest.raises(pm.PmError):
        pm_scenarios.run_schedule([])


def test_simulation_gives_a_range_and_deadline_chance(client):
    board(client)
    r = pm_scenarios.simulate(1000, 20, 50, "2026-03-30")
    assert r["p50_days"] <= r["p80_days"] <= r["p90_days"] and r["p80_days"] > r["plan_days"] * 0.9
    assert sum(r["histogram"]["counts"]) == 1000 and 0 <= r["chance_by_deadline_pct"] <= 100
    assert r["most_often_critical"][0]["title"] in ("Design", "Build", "Ship")
    assert pm_scenarios.simulate(1000, 20, 50, "2026-03-30")["p80_days"] == r["p80_days"]          # same seed, same answer
    wide = pm_scenarios.simulate(1000, 20, 150)
    assert wide["p90_days"] > r["p90_days"]


def test_product_reprioritisation(client):
    for t, r, i, c, e in [("A", 1000, 2, 0.8, 4), ("B", 500, 3, 0.9, 2), ("C", 200, 1, 0.5, 1)]:
        pm.create_item({"kind": "story", "title": t, "reach": r, "impact": i, "confidence": c, "effort": e})
    base = pm_scenarios.run_product([], capacity=6)
    assert [x["title"] for x in base["ranking"]][0] == "B" and base["ships_before"] == ["B", "A"] or base["ships_before"][0] == "B"
    r = pm_scenarios.run_product([{"item_id": next(x["id"] for x in base["ranking"] if x["title"] == "B"), "field": "effort", "multiplier": 4}], capacity=6)
    assert r["ranking"][0]["title"] != "B" and any(x["moved"] != 0 for x in r["ranking"])
    assert pm_scenarios.run_product([], capacity=6, capacity_pct=50)["capacity_after"] == 9


def test_practice_cases_have_hidden_answers_that_match_the_engine(client):
    for kind in ("website", "app_mvp", "repair_shop", "product_roadmap"):
        hidden = pm_scenarios.practice(kind, 3)
        assert hidden["answers_hidden"] and all("answer" not in q for q in hidden["questions"])
        shown = pm_scenarios.practice(kind, 3, True)
        assert all(q["answer"] for q in shown["questions"])
    w = pm_scenarios.practice("website", 1, True)
    items = pm_scenarios._case_items("website", 1)
    cp = pm.critical_path(items, pm.today())
    assert f"{cp['duration_days']:g} days" in w["questions"][0]["answer"]
    assert pm_scenarios.practice("website", 1)["tasks"] == pm_scenarios.practice("website", 1)["tasks"]
    with pytest.raises(pm.PmError):
        pm_scenarios.practice("nope")


def test_load_case_only_in_practice(client):
    from app.services import workspaces
    if workspaces.active() == "practice":
        r = pm_scenarios.load_case("website", 1)
        assert r["loaded"] == 8 and len(pm.list_items()) == 8
        assert pm.critical_path(pm.list_items(), pm.today())["available"]


def test_pm_agent_runs_scenarios_and_other_agents_cannot(client):
    a, b, c, d = board(client)
    f = Fake([Turn("", [Call("1", "pm_scenario", {"action": "schedule", "changes": [{"kind": "slip", "item_id": b, "days": 4}]})]), Turn("It slips four days.")])
    r = agents.chat("pm", "what if Build slips 4 days?", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "pm_scenario" in [t["name"] for t in f.tools] and "19" in str(f.results[0]) and r.reply.startswith("It slips")
    g = Fake([Turn("ok")])
    agents.chat("analyst", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "pm_scenario" not in [t["name"] for t in g.tools]


def test_api(client):
    board(client)
    assert client.get("/api/pm/scenarios/kinds").status_code == 200
    r = client.post("/api/pm/scenarios/schedule", json={"changes": [{"kind": "slip", "item_id": 2, "days": 1}]})
    assert r.status_code == 200 and "says" in r.json()
    assert client.post("/api/pm/scenarios/schedule", json={"changes": [{"kind": "wat"}]}).status_code == 400
    assert client.post("/api/pm/scenarios/simulate", json={"deadline": "2026-04-01"}).status_code == 200
    assert client.get("/api/pm/scenarios/practice", params={"kind": "app_mvp", "seed": 2}).json()["answers_hidden"] is True


# ------------------------------------------------------------------ PDF text with no table


def make_pdf(lines_per_page):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for lines in lines_per_page:
        y = 740
        for ln in lines:
            c.drawString(60, y, ln)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


def test_pdf_words_without_a_table_become_rows():
    raw = make_pdf([["Service report for Acme", "Contact bob@example.com on 2026-03-04", "Total due $450 for the printer repair"], ["Second page note about the router"]])
    rows, info = fileformats.read_pdf_lines(raw)
    assert rows[0] == ["page", "line_no", "text"] and len(rows) == 5 and rows[-1][0] == "2" and info["text_only"] is True
    from app.services import datasets
    header, data, inf = datasets.read_table(raw, "report.pdf")
    assert header == ["page", "line_no", "text"] and len(data) == 4 and inf["text_only"]


def test_blank_pdf_says_ocr_is_needed():
    raw = make_pdf([[]])
    with pytest.raises(Exception, match="OCR"):
        fileformats.read_pdf_lines(raw)


def test_intake_reads_a_text_pdf(client):
    raw = make_pdf([[f"Ticket {i}: customer bob{i}@example.com reported a jam on 2026-03-{1 + i:02d} and wants a $45 refund" for i in range(20)]])
    r = intake.run_all(intake.start(raw, "tickets.pdf", name="Pdf tickets", preview=False)["id"])
    s = {x["key"]: x for x in r["stages"]}
    assert s["structure"]["status"] == "ok" and s["structure"]["details"]["unstructured"] is True
    cols = [c["name"] for c in s["structure"]["details"]["columns"]]
    assert cols[:3] == ["page", "line_no", "text"] and "emails" in cols
    assert s["privacy"]["status"] == "warn"


def test_concierge_finds_scenarios(client):
    from app.services import concierge
    assert concierge.route("what if the deadline slips, simulate the schedule")["primary"]["href"].startswith("/tracks/pm")
