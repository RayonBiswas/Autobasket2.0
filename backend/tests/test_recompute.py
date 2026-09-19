from datetime import UTC, datetime, timedelta

from app import models


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded(client, login, email):
    h = _auth(client, login, email)
    seed = client.post("/seed/dev", headers=h).json()
    return h, {"Authorization": f"Bearer {seed['device_token']}"}


def _post_history(client, dh, days: int, rate_l_per_day: float, tare=50.0, full=1080.0):
    """Backdated milk readings twice a day; refill when nearly empty. Returns the last fraction."""
    now = datetime.now(UTC)
    fraction = 1.0
    for half in range(days * 2, -1, -1):
        when = now - timedelta(hours=12 * half)
        grams = tare + fraction * (full - tare)
        r = client.post(
            "/devices/me/readings",
            json={"captured_at": when.isoformat(), "readings": [{"tray": 1, "slot": 1, "weight_grams": round(grams, 1)}]},
            headers=dh,
        )
        assert r.status_code == 200
        fraction -= rate_l_per_day / 2
        if fraction < 0.1:
            fraction = 1.0
    return fraction


def test_history_produces_a_learned_rate(app_client, login):
    client, _ = app_client
    h, dh = _seeded(client, login, "learn@x.y")
    _post_history(client, dh, days=12, rate_l_per_day=0.4)  # 1 L pack, 0.4 L/day -> refill every ~2.5 days

    milk = next(x for x in client.get("/inventory", headers=h).json()["inventory"] if x["name"] == "milk")
    assert milk["rate_method"] == "learned"
    assert milk["observed_days"] >= 7
    assert abs(milk["estimated_daily_usage"] - 0.4) < 0.08
    assert milk["rate_confidence"] == 1.0


def test_recompute_endpoint_and_worker_function(app_client, login, monkeypatch):
    client, factory = app_client
    h, _ = _seeded(client, login, "recompute@x.y")
    assert client.post("/inventory/recompute", headers=h).json()["recomputed"] >= 3

    from app import worker

    monkeypatch.setattr(worker, "SessionLocal", factory)
    assert worker.run_once() >= 3


def test_reorder_list_reflects_days_left(app_client, login):
    client, _ = app_client
    h, dh = _seeded(client, login, "reorder@x.y")
    inv = {r["name"]: r for r in client.get("/inventory", headers=h).json()["inventory"]}

    client.put(f"/inventory/{inv['water']['product_id']}", json={"remaining_fraction": 1.0}, headers=h)
    client.put(f"/inventory/{inv['milk']['product_id']}", json={"remaining_fraction": 0.05}, headers=h)

    names = [r["name"] for r in client.get("/inventory/reorder", headers=h).json()["reorder"]]
    assert "milk" in names
    assert "water" not in names
    assert names[0] == "milk"


def test_events_carry_captured_at(app_client, login):
    client, factory = app_client
    _, dh = _seeded(client, login, "ts@x.y")
    when = datetime.now(UTC) - timedelta(days=3)
    client.post("/devices/me/readings", json={"captured_at": when.isoformat(), "readings": [{"tray": 1, "slot": 1, "weight_grams": 600}]}, headers=dh)
    with factory() as s:
        ev = s.query(models.InventoryEvent).filter_by(source="weight").order_by(models.InventoryEvent.id.desc()).first()
        assert abs((ev.recorded_at.replace(tzinfo=UTC) - when).total_seconds()) < 5
