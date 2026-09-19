def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded(client, login, email):
    h = _auth(client, login, email)
    seed = client.post("/seed/dev", headers=h).json()
    return h, {"Authorization": f"Bearer {seed['device_token']}"}


def test_create_and_list_devices_never_expose_token(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "dev@x.y")
    r = client.post("/devices", json={"name": "Kitchen Pi"}, headers=h)
    assert r.status_code == 201
    assert len(r.json()["token"]) > 20

    listed = client.get("/devices", headers=h).json()["devices"]
    assert listed[0]["name"] == "Kitchen Pi"
    assert "token" not in listed[0]
    assert listed[0]["trays"] == 0


def test_device_me_returns_layout(app_client, login):
    client, _ = app_client
    _, dh = _seeded(client, login, "layout@x.y")
    me = client.get("/devices/me", headers=dh).json()
    assert me["device"]["name"] == "Dev Fridge"
    assert len(me["trays"]) == 2
    slot1 = me["trays"][0]["slots"][0]
    assert slot1["product"]["name"] == "milk"
    assert slot1["tare_grams"] == 50
    assert slot1["full_grams"] == 1080


def test_readings_update_inventory(app_client, login):
    client, _ = app_client
    h, dh = _seeded(client, login, "read@x.y")
    r = client.post(
        "/devices/me/readings",
        json={"readings": [{"tray": 1, "slot": 1, "weight_grams": 565}, {"tray": 1, "slot": 4, "weight_grams": 51}]},
        headers=dh,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == 2
    assert body["applied"][0]["remaining_fraction"] == 0.5

    milk = next(x for x in client.get("/inventory", headers=h).json()["inventory"] if x["name"] == "milk")
    assert milk["remaining_fraction"] == 0.5
    assert client.get("/devices", headers=h).json()["devices"][0]["last_seen_at"] is not None


def test_device_routes_reject_bad_tokens(app_client, login):
    client, _ = app_client
    h, _ = _seeded(client, login, "bad@x.y")
    assert client.get("/devices/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/devices/me", headers=h).status_code == 401  # a user JWT is not a device token
    assert client.get("/devices/me").status_code == 401
