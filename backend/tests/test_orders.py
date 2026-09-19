def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def test_create_and_list_order(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "o@x.y")
    client.post("/seed/dev", headers=h)
    milk = client.get("/vendors/compare/milk", headers=h).json()[0]
    inv = {r["name"]: r for r in client.get("/inventory", headers=h).json()["inventory"]}

    r = client.post(
        "/orders",
        json={"vendor_id": milk["vendor_id"], "items": [{"product_id": inv["milk"]["product_id"], "qty": 2}]},
        headers=h,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "proposed"
    assert body["total_amount"] == round(milk["price"] * 2, 2)
    assert body["items"][0]["name"] == "milk"

    listed = client.get("/orders", headers=h).json()["orders"]
    assert listed[0]["order_id"] == body["order_id"]


def test_orders_are_scoped_to_household(app_client, login):
    client, _ = app_client
    h1 = _auth(client, login, "a1@x.y")
    h2 = _auth(client, login, "a2@x.y")
    client.post("/seed/dev", headers=h1)
    milk = client.get("/vendors/compare/milk", headers=h1).json()[0]
    inv = {r["name"]: r for r in client.get("/inventory", headers=h1).json()["inventory"]}
    client.post("/orders", json={"vendor_id": milk["vendor_id"], "items": [{"product_id": inv["milk"]["product_id"]}]}, headers=h1)

    assert client.get("/orders", headers=h2).json()["orders"] == []


def test_order_from_vendor_without_offer_is_rejected(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "bad@x.y")
    client.post("/seed/dev", headers=h)
    milk = client.get("/vendors/compare/milk", headers=h).json()[0]
    r = client.post("/orders", json={"vendor_id": milk["vendor_id"], "items": [{"product_id": 999999}]}, headers=h)
    assert r.status_code == 422
