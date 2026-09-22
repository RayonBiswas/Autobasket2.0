"""Kirana vendor portal: shop profile, listings, CSV upload, order inbox."""

import io

SHOP = {"name": "Sharma Kirana", "pincode": "560001", "phone": "9999999999", "eta_minutes": 20,
        "opens_at": "07:00", "closes_at": "22:00", "delivery_radius_km": 3}


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded_household(client, login, email="home@x.y"):
    h = _auth(client, login, email)
    client.post("/seed/dev", headers=h)
    return h


def _product_id(client, h, name):
    return {r["name"]: r for r in client.get("/products", headers=h).json()["products"]}[name]["id"]


def test_shop_profile_lifecycle(app_client, login):
    client, _ = app_client
    v = _auth(client, login, "sharma@x.y")
    r = client.get("/vendor/shop", headers=v)
    assert r.status_code == 200 and r.json() is None

    r = client.post("/vendor/shop", json=SHOP, headers=v)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Sharma Kirana"
    assert r.json()["kind"] == "kirana"

    assert client.post("/vendor/shop", json=SHOP, headers=v).status_code == 409

    r = client.put("/vendor/shop", json={"eta_minutes": 35}, headers=v)
    assert r.json()["eta_minutes"] == 35
    me = client.get("/auth/me", headers=v).json()
    assert me["user"]["role"] == "vendor"


def test_household_without_shop_cannot_list(app_client, login):
    client, _ = app_client
    h = _seeded_household(client, login)
    assert client.get("/vendor/offers", headers=h).status_code == 404


def test_listing_shows_up_in_household_compare(app_client, login):
    client, _ = app_client
    h = _seeded_household(client, login)
    v = _auth(client, login, "sharma@x.y")
    client.post("/vendor/shop", json=SHOP, headers=v)
    milk = _product_id(client, h, "milk")

    catalog = client.get("/vendor/catalog", params={"q": "mil"}, headers=v).json()["products"]
    assert [p["name"] for p in catalog] == ["milk"]
    assert catalog[0]["price"] is None

    r = client.put("/vendor/offers", json={"offers": [{"product_id": milk, "price": 58}]}, headers=v)
    assert r.status_code == 200 and r.json()["saved"] == 1

    rows = client.get("/vendors/compare/milk", headers=h).json()
    sharma = [x for x in rows if x["vendor_name"] == "Sharma Kirana"]
    assert sharma and sharma[0]["price"] == 58

    assert client.get("/vendor/offers", headers=v).json()["offers"][0]["price"] == 58

    client.delete(f"/vendor/offers/{milk}", headers=v)
    rows = client.get("/vendors/compare/milk", headers=h).json()
    assert not [x for x in rows if x["vendor_name"] == "Sharma Kirana"]


def test_csv_upload_reports_unknown_products(app_client, login):
    client, _ = app_client
    _seeded_household(client, login)
    v = _auth(client, login, "sharma@x.y")
    client.post("/vendor/shop", json=SHOP, headers=v)

    csv = "product,price,in_stock\nMilk,58,yes\ncurd,34,\nunicorn tears,999,yes\n"
    r = client.post("/vendor/offers/csv", files={"file": ("prices.csv", io.BytesIO(csv.encode()), "text/csv")}, headers=v)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 2 and body["unknown"] == ["unicorn tears"]

    r = client.post("/vendor/offers/csv", files={"file": ("prices.csv", io.BytesIO(b"product,price\nmilk,60\n"), "text/csv")}, headers=v)
    assert r.json()["updated"] == 1 and r.json()["added"] == 0


def test_order_inbox_accept_deliver(app_client, login):
    client, _ = app_client
    h = _seeded_household(client, login)
    v = _auth(client, login, "sharma@x.y")
    other = _auth(client, login, "gupta@x.y")
    shop_id = client.post("/vendor/shop", json=SHOP, headers=v).json()["id"]
    client.post("/vendor/shop", json={**SHOP, "name": "Gupta Stores"}, headers=other)
    milk = _product_id(client, h, "milk")
    client.put("/vendor/offers", json={"offers": [{"product_id": milk, "price": 58}]}, headers=v)

    order = client.post("/orders", json={"vendor_id": shop_id, "items": [{"product_id": milk, "qty": 2}]}, headers=h).json()
    oid = order["order_id"]
    assert order["status"] == "proposed"
    # Not visible to the shop until the household confirms.
    assert client.get("/vendor/orders", headers=v).json()["orders"] == []

    assert client.post(f"/orders/{oid}/confirm", headers=h).json()["status"] == "confirmed"
    inbox = client.get("/vendor/orders", headers=v).json()["orders"]
    assert [o["order_id"] for o in inbox] == [oid]
    assert inbox[0]["items"][0]["name"] == "milk"

    assert client.post(f"/vendor/orders/{oid}/accept", headers=other).status_code == 404
    assert client.post(f"/vendor/orders/{oid}/deliver", headers=v).status_code == 409  # confirmed -> delivered not allowed
    assert client.post(f"/vendor/orders/{oid}/accept", headers=v).json()["status"] == "accepted"
    assert client.post(f"/vendor/orders/{oid}/deliver", headers=v).json()["status"] == "delivered"

    mine = client.get("/orders", headers=h).json()["orders"]
    assert mine[0]["status"] == "delivered"
    assert client.get("/vendor/orders", headers=v).json()["orders"] == []
    assert client.get("/vendor/orders", params={"status": "all"}, headers=v).json()["orders"][0]["status"] == "delivered"


def test_reject_cancels(app_client, login):
    client, _ = app_client
    h = _seeded_household(client, login)
    v = _auth(client, login, "sharma@x.y")
    shop_id = client.post("/vendor/shop", json=SHOP, headers=v).json()["id"]
    milk = _product_id(client, h, "milk")
    client.put("/vendor/offers", json={"offers": [{"product_id": milk, "price": 58}]}, headers=v)
    oid = client.post("/orders", json={"vendor_id": shop_id, "items": [{"product_id": milk}]}, headers=h).json()["order_id"]
    client.post(f"/orders/{oid}/confirm", headers=h)
    assert client.post(f"/vendor/orders/{oid}/reject", headers=v).json()["status"] == "cancelled"
    assert client.get("/orders", headers=h).json()["orders"][0]["status"] == "cancelled"
