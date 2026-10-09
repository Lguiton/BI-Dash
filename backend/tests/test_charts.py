import pytest


def test_breakdown_pie_data(client):
    r = client.get("/api/charts/breakdown?by=category&measure=revenue").json()
    assert r["rows"] and r["total"] == pytest.approx(sum(x["value"] for x in r["rows"]))
    kpi = client.get("/api/analytics/summary").json()["total_revenue"]
    assert r["total"] == pytest.approx(kpi)


@pytest.mark.parametrize("by", ["entity", "category", "status", "weekday", "month"])
@pytest.mark.parametrize("measure", ["revenue", "cost", "profit", "units", "duration"])
def test_breakdown_all_combinations(client, by, measure):
    r = client.get(f"/api/charts/breakdown?by={by}&measure={measure}")
    assert r.status_code == 200 and r.json()["rows"]


def test_breakdown_rejects_unknown_column(client):
    assert client.get("/api/charts/breakdown?by=revenue;DROP").status_code == 422
    assert client.get("/api/charts/breakdown?measure=bogus").status_code == 422


def test_breakdown_respects_filters(client):
    ents = client.get("/api/analytics/by-entity").json()
    eid = ents[0]["entity_id"]
    r = client.get(f"/api/charts/breakdown?by=entity&measure=revenue&entity_id={eid}").json()
    assert len(r["rows"]) == 1


def test_histogram_counts_every_record(client):
    r = client.get("/api/charts/distribution?measure=revenue&bins=10").json()
    assert sum(b["count"] for b in r["histogram"]) == r["count"] > 0
    assert len(r["histogram"]) == 10


def test_boxplot_stats_are_ordered(client):
    r = client.get("/api/charts/distribution?measure=profit&by=category").json()
    assert r["boxes"]
    for b in r["boxes"]:
        assert b["whisker_low"] <= b["q1"] <= b["median"] <= b["q3"] <= b["whisker_high"]


def test_distribution_empty_selection(client):
    r = client.get("/api/charts/distribution?measure=revenue&date_from=2999-01-01").json()
    assert r["count"] == 0 and r["histogram"] == [] and r["boxes"] == []


def test_bubble(client):
    assert client.get("/api/charts/bubble").json()["rows"]


def test_outliers_are_detected(client, tmp_path):
    rows = ["record_date,entity_id,revenue,operational_cost,units_processed"]
    rows += [f"2026-01-{d:02d},E1,{100 + d},50,10" for d in range(1, 21)] + ["2026-01-25,E1,5000,50,10"]
    r = client.post("/api/ingest/csv?mode=replace", files={"file": ("t.csv", "\n".join(rows), "text/csv")})
    assert r.status_code == 200, r.text
    b = client.get("/api/charts/distribution?measure=revenue").json()["boxes"][0]
    assert b["outlier_count"] == 1 and 5000 in b["outliers"]
