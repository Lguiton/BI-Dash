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
