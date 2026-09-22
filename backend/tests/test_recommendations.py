"""GET /recommendations/{product}: top 3, mixed kinds, reasons, priority-aware."""


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def test_top3_mixed_with_reasons(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "rec@x.y")
    client.post("/seed/dev", headers=h)
    body = client.get("/recommendations/milk", headers=h).json()
    assert body["product"]["name"] == "milk"
    assert body["priority"] == "balanced"
    assert 1 <= len(body["offers"]) <= 3
    assert body["considered"] >= 3
    assert all(o["reason"] for o in body["offers"])
    assert {o["vendor_kind"] for o in body["offers"]} == {"kirana", "platform"}


def test_priority_changes_order(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "prio@x.y")
    client.post("/seed/dev", headers=h)
    r = client.put("/households/me/priority", json={"priority": "speed"}, headers=h)
    assert r.status_code == 200 and r.json()["priority"] == "speed"
    fast = client.get("/recommendations/milk", headers=h).json()["offers"][0]
    client.put("/households/me/priority", json={"priority": "price"}, headers=h)
    cheap = client.get("/recommendations/milk", headers=h).json()["offers"][0]
    assert fast["vendor_name"] == "Zepto"  # 10 min
    assert cheap["vendor_name"] == "Local Kirana"  # cheapest
    assert client.put("/households/me/priority", json={"priority": "vibes"}, headers=h).status_code == 422
    assert client.get("/auth/me", headers=h).json()["household"]["priority"] == "price"


def test_unknown_product_404(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "nope@x.y")
    assert client.get("/recommendations/unobtainium", headers=h).status_code == 404
