def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded(client, login, email):
    h = _auth(client, login, email)
    seed = client.post("/seed/dev", headers=h).json()
    return h, {"Authorization": f"Bearer {seed['device_token']}"}


def _slots(client, h):
    trays = client.get("/households/me/slots", headers=h).json()["trays"]
    return {(t["position"], s["position"]): s for t in trays for s in t["slots"]}


def test_seeded_slots_are_calibrated_with_a_reading(app_client, login):
    client, _ = app_client
    h, _ = _seeded(client, login, "cal@x.y")
    s = _slots(client, h)
    assert s[(1, 1)]["product_name"] == "milk"
    assert s[(1, 1)]["latest_weight_grams"] == 565
    assert abs(s[(1, 1)]["remaining_fraction"] - 0.5) < 1e-6
    assert s[(2, 1)]["product_name"] is None
    assert s[(2, 1)]["latest_weight_grams"] is None


def test_assign_product_and_calibrate(app_client, login):
    client, _ = app_client
    h, dh = _seeded(client, login, "assign@x.y")
    curd = next(p for p in client.get("/products", headers=h).json()["products"] if p["name"] == "curd")
    slot4 = _slots(client, h)[(1, 4)]

    r = client.put(f"/slots/{slot4['slot_id']}", json={"product_id": curd["id"]}, headers=h)
    assert r.json()["product_name"] == "curd"

    assert client.post(f"/slots/{slot4['slot_id']}/mark-empty", headers=h).status_code == 409  # no reading yet

    client.post("/devices/me/readings", json={"readings": [{"tray": 1, "slot": 4, "weight_grams": 48}]}, headers=dh)
    assert client.post(f"/slots/{slot4['slot_id']}/mark-empty", headers=h).json()["tare_grams"] == 48

    assert client.post(f"/slots/{slot4['slot_id']}/mark-full", headers=h).status_code == 422  # 48 <= tare

    client.post("/devices/me/readings", json={"readings": [{"tray": 1, "slot": 4, "weight_grams": 470}]}, headers=dh)
    full = client.post(f"/slots/{slot4['slot_id']}/mark-full", headers=h).json()
    assert full["full_grams"] == 470
    assert abs(full["remaining_fraction"] - 1.0) < 1e-6


def test_slot_of_other_household_is_404(app_client, login):
    client, _ = app_client
    h1, _ = _seeded(client, login, "own@x.y")
    h2 = _auth(client, login, "other@x.y")
    slot = _slots(client, h1)[(1, 1)]
    assert client.put(f"/slots/{slot['slot_id']}", json={"clear_product": True}, headers=h2).status_code == 404


def test_products_and_history(app_client, login):
    client, _ = app_client
    h, dh = _seeded(client, login, "hist@x.y")
    assert len(client.get("/products", headers=h).json()["products"]) == 20

    milk = next(x for x in client.get("/inventory", headers=h).json()["inventory"] if x["name"] == "milk")
    client.post("/devices/me/readings", json={"readings": [{"tray": 1, "slot": 1, "weight_grams": 300}]}, headers=dh)
    points = client.get(f"/inventory/{milk['product_id']}/history?days=7", headers=h).json()["points"]
    assert len(points) >= 2
    assert {p["source"] for p in points} >= {"manual", "weight"}
    assert points == sorted(points, key=lambda p: p["recorded_at"])
