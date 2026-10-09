import pytest

from app.routers.glossary import TERMS
from app.services.sql_lab import run_query


def test_glossary_endpoint(client):
    j = client.get("/api/glossary").json()
    assert len(j["terms"]) >= 15 and {"Metric", "KPI", "Concept", "Method"} <= set(j["kinds"])
    assert len({t["id"] for t in j["terms"]}) == len(j["terms"])
    assert all(t["definition"] and t["formula"] and t["sql"] and t["pitfall"] for t in j["terms"])


@pytest.mark.parametrize("term", TERMS, ids=lambda t: t["id"])
def test_every_example_runs(client, term):
    r = run_query(term["sql"])
    assert r.row_count > 0 and r.rows[0][0] is not None


def test_margin_example_is_a_ratio_of_sums(client):
    sums = run_query("SELECT SUM(revenue - operational_cost) / SUM(revenue) * 100 FROM fact_operations").rows[0][0]
    ex = run_query(next(t for t in TERMS if t["id"] == "margin")["sql"]).rows[0][0]
    assert abs(ex - sums) < 1e-9
