from datetime import date, timedelta

import pytest

from app.services import analyst_tools as at
from app.services import bi_tools as bt
from app.services import biz_packs


@pytest.fixture()
def pack(client):
    biz_packs.install_sample("repair-jobs")
    return "repair-jobs"


def _cols(pid):
    return {c["name"]: c["type"] for c in at.columns(pid)}


def test_query_pivot(pack):
    cs = _cols(pack)
    assert cs
    r = at.run_query(pack, "count")
    assert r["rows"] and r["rows"][0][0] > 0
    with pytest.raises(at.ToolError):
        at.run_query(pack, "bogus")
    with pytest.raises(at.ToolError):
        at.run_query(pack, "sum")
    cat = next(n for n, t in cs.items() if "VARCHAR" in t.upper())
    g = at.run_query(pack, "count", group_by=[cat])
    assert len(g["rows"]) >= 2
    p = at.pivot(pack, cat, None, None, "count")
    assert p


def test_ab_math():
    r = at.ab_proportions(120, 1000, 150, 1000)
    assert 0.04 < r["p_value"] < 0.06
    s = at.sample_size(0.12, 0.02)
    assert 4000 < s["per_group"] < 5000
    m = at.ab_means([1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 9])
    assert 0 < m["p_value"] < 1


def test_notebook_escapes(client):
    with pytest.raises(at.ToolError):
        at.nb_save({"title": ""})
    e = at.nb_save({"title": "T <script>x</script>", "finding": "<b>hi</b>", "result": {"columns": ["a"], "rows": [[1]]}})
    h = at.nb_html(e["id"])
    assert "<script>x</script>" not in h and "&lt;script&gt;" in h
    assert len(at.nb_list()) == 1
    at.nb_delete(e["id"])
    assert at.nb_list() == []


def test_bi_design_story_dictionary(pack):
    h = bt.design(pack, 30, title="Acme report", client="Acme")
    assert "Acme report" in h and "SAMPLE" in h
    assert "call back" in bt.story(pack, 30, headline="Good month", recommendation="Next step: call back")
    body, mime = bt.kpi_dictionary_export("csv")
    assert "csv" in mime and body.startswith("dashboard")
    with pytest.raises(bt.BiError):
        bt.sched_add(pack, 30, 0)


def test_schedule_catchup_and_alerts(pack):
    s = bt.sched_add(pack, 30, 7, client="Acme")
    today = date.today()
    r1 = bt.run_due(today)
    assert r1["ran"] == [s["id"]]
    assert bt.sched_output(s["id"], today.isoformat())
    assert bt.run_due(today)["ran"] == []
    assert bt.run_due(today + timedelta(days=8))["ran"] == [s["id"]]
    assert len(bt.sched_list()) == 1
    lab = [x["label"] for x in biz_packs.dashboard(pack, 30)["kpis"]][0]
    a = bt.alert_add(pack, lab, "above", -1e12)
    res = bt.alert_check()
    assert len(res["triggered"]) == 1 and res["triggered"][0]["kpi"] == lab
    with pytest.raises(bt.BiError):
        bt.alert_add(pack, "Nope", "above", 1)
    with pytest.raises(bt.BiError):
        bt.alert_add(pack, lab, "sideways", 1)
    bt.alert_remove(a["id"])
    bt.sched_remove(s["id"])
    assert bt.sched_list() == []
