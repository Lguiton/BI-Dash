from app.services import it_repair, service_catalog


def test_catalog_covers_every_group_and_prices_follow_rates(client):
    c = client.get("/api/service-list").json()
    groups = {g["id"] for g in c["groups"]}
    assert {"bi", "ds", "data", "cpe", "net", "it", "sec", "ai", "pm", "fs", "biz", "devops", "mkt", "ux", "health", "stat"} == groups
    assert all(any(s["group"] == g for s in c["services"]) for g in groups)
    assert len({s["id"] for s in c["services"]}) == len(c["services"])
    s = next(x for x in c["services"] if x["id"] == "bi-setup")
    assert s["low"] == round(s["hours"][0] * s["rate"], 2)
    c2 = client.put("/api/service-list/rates", json={"bi": 100}).json()
    assert next(x for x in c2["services"] if x["id"] == "bi-setup")["rate"] == 100
    assert client.put("/api/service-list/rates", json={"bi": 99999}).status_code == 400


def test_quote_and_unknown_service(client):
    q = client.post("/api/service-list/quote", json={"lines": [{"id": "net-home", "qty": 2}, {"id": "it-printer", "qty": 1}], "client": "Acme", "discount_pct": 10}).json()
    assert q["lines"][0]["qty"] == 2 and q["total"][0] < q["subtotal"][0]
    assert client.post("/api/service-list/quote", json={"lines": [{"id": "nope"}]}).status_code == 400


def test_services_point_at_real_repair_areas():
    areas = {g["area"] for g in it_repair.GUIDES}
    assert {"Laptops by make", "Phones by make", "Wi-Fi mesh"} <= areas
    assert len(it_repair.GUIDES) >= 75
    assert service_catalog.SERVICES


def test_price_list_is_served_and_complete(client):
    p = client.get("/api/service-list/price-list").json()
    assert p["date"] and p["note"] and len(p["groups"]) == 5
    rows = [r for g in p["groups"] for r in g["rows"]]
    assert len(rows) >= 28
    assert all(r["service"] and r["market"] and r["price"].startswith("$") for r in rows)
    assert len({r["service"] for r in rows}) == len(rows)


def test_default_rates_follow_the_price_research(client):
    c = client.get("/api/service-list").json()
    rate = {g["id"]: g["rate"] for g in c["groups"]}
    assert rate["biz"] == 145 and rate["it"] == 75 and rate["ai"] == 105
    assert all(60 <= v <= 150 for v in rate.values())
