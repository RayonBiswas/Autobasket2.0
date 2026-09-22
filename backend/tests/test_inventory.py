from app import models


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def test_seed_then_inventory_and_slots(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "seed@x.y")
    seeded = client.post("/seed/dev", headers=h).json()
    assert seeded["products"] >= 20
    assert seeded["vendors"] == 5
    assert len(seeded["device_token"]) > 20

    inv = client.get("/inventory", headers=h).json()["inventory"]
    assert {row["name"] for row in inv} >= {"milk", "rice", "water"}
    assert all(row["status"] in {"safe", "warning", "critical", "unknown"} for row in inv)

    trays = client.get("/households/me/slots", headers=h).json()["trays"]
    assert len(trays) == 2
    assert all(len(t["slots"]) == 4 for t in trays)


def test_seed_is_idempotent(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "twice@x.y")
    first = client.post("/seed/dev", headers=h).json()
    second = client.post("/seed/dev", headers=h).json()
    assert first["products"] == second["products"]
    assert second["device_token"] is None


def test_manual_update_creates_event(app_client, login):
    client, factory = app_client
    h = _auth(client, login, "m@x.y")
    client.post("/seed/dev", headers=h)
    milk = next(r for r in client.get("/inventory", headers=h).json()["inventory"] if r["name"] == "milk")

    r = client.put(f"/inventory/{milk['product_id']}", json={"remaining_fraction": 0.1}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "critical"

    with factory() as s:
        assert s.query(models.InventoryEvent).filter_by(product_id=milk["product_id"]).count() >= 2


def test_inventory_is_scoped_to_household(app_client, login):
    client, _ = app_client
    h1 = _auth(client, login, "one@x.y")
    h2 = _auth(client, login, "two@x.y")
    client.post("/seed/dev", headers=h1)
    assert client.get("/inventory", headers=h2).json()["inventory"] == []


def test_household_settings_patch(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "p@x.y")
    r = client.patch(
        "/households/me", json={"adults": 3, "children": 0, "food_habit": "veg", "pincode": "560001"}, headers=h
    )
    assert r.json()["adults"] == 3
    assert r.json()["pincode"] == "560001"
