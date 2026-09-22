"""Confirm → pay → accept → deliver → refill → verified; handoff for delivery apps; ratings; payment callbacks."""

import hashlib
import hmac
import json

from app.services.handoff import handoff_url
from app.services.payments import verify_razorpay_signature

SHOP = {"name": "Sharma Kirana", "pincode": "560001", "eta_minutes": 20}


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _setup(client, login):
    h = _auth(client, login, "flow@x.y")
    client.post("/seed/dev", headers=h)
    v = _auth(client, login, "sharma@x.y")
    shop_id = client.post("/vendor/shop", json=SHOP, headers=v).json()["id"]
    milk = {p["name"]: p for p in client.get("/products", headers=h).json()["products"]}["milk"]["id"]
    client.put("/vendor/offers", json={"offers": [{"product_id": milk, "price": 58}]}, headers=v)
    return h, v, shop_id, milk


def test_kirana_full_loop_ends_verified(app_client, login):
    client, _ = app_client
    h, v, shop_id, milk = _setup(client, login)
    oid = client.post("/orders", json={"vendor_id": shop_id, "items": [{"product_id": milk}]}, headers=h).json()["order_id"]

    confirmed = client.post(f"/orders/{oid}/confirm", headers=h).json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["payment_url"].startswith("http://localhost:5173/pay/") and "ref=dev_" in confirmed["payment_url"]

    paid = client.post("/payments/dev/complete", json={"order_id": oid}, headers=h).json()
    assert paid["status"] == "paid"
    assert client.post("/payments/dev/complete", json={"order_id": oid}, headers=h).status_code == 409

    assert client.post(f"/vendor/orders/{oid}/accept", headers=v).json()["status"] == "accepted"
    delivered = client.post(f"/vendor/orders/{oid}/deliver", headers=v).json()
    assert delivered["status"] == "delivered" and delivered["delivered_at"]

    # A small reading does not count as the delivery arriving; a refill does.
    client.put(f"/inventory/{milk}", json={"remaining_fraction": 0.3}, headers=h)
    assert client.get("/orders", headers=h).json()["orders"][0]["status"] == "delivered"
    client.put(f"/inventory/{milk}", json={"remaining_fraction": 0.95}, headers=h)
    final = client.get("/orders", headers=h).json()["orders"][0]
    assert final["status"] == "verified" and final["verified_at"]


def test_platform_yes_is_a_handoff(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "hand@x.y")
    client.post("/seed/dev", headers=h)
    milk = {p["name"]: p for p in client.get("/products", headers=h).json()["products"]}["milk"]["id"]
    blinkit = next(o for o in client.get("/vendors/compare/milk", headers=h).json() if o["vendor_name"] == "Blinkit")
    oid = client.post("/orders", json={"vendor_id": blinkit["vendor_id"], "items": [{"product_id": milk}]}, headers=h).json()["order_id"]
    body = client.post(f"/orders/{oid}/confirm", headers=h).json()
    assert body["status"] == "handoff"
    assert body["handoff_url"] == "https://blinkit.com/s/?q=milk"
    assert body["payment_url"] is None
    client.put(f"/inventory/{milk}", json={"remaining_fraction": 1.0}, headers=h)
    assert client.get("/orders", headers=h).json()["orders"][0]["status"] == "verified"


def test_rating_moves_vendor_scores(app_client, login):
    client, _ = app_client
    h, v, shop_id, milk = _setup(client, login)
    oid = client.post("/orders", json={"vendor_id": shop_id, "items": [{"product_id": milk}]}, headers=h).json()["order_id"]
    client.post(f"/orders/{oid}/confirm", headers=h)
    assert client.post(f"/orders/{oid}/rate", json={"stars": 5}, headers=h).status_code == 409  # not delivered yet
    client.post(f"/vendor/orders/{oid}/accept", headers=v)
    client.post(f"/vendor/orders/{oid}/deliver", headers=v)
    before = client.get("/vendor/shop", headers=v).json()

    rated = client.post(f"/orders/{oid}/rate", json={"stars": 5}, headers=h).json()
    assert rated["rating"] == 5
    after = client.get("/vendor/shop", headers=v).json()
    assert after["review_count"] == before["review_count"] + 1
    assert after["rating"] > before["rating"] and after["service_score"] > before["service_score"]
    assert client.post(f"/orders/{oid}/rate", json={"stars": 4}, headers=h).status_code == 409


def test_razorpay_webhook_marks_paid(app_client, login, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "whsec")
    from app.core.config import get_settings

    get_settings.cache_clear()
    h, v, shop_id, milk = _setup(client, login)
    oid = client.post("/orders", json={"vendor_id": shop_id, "items": [{"product_id": milk}]}, headers=h).json()["order_id"]
    client.post(f"/orders/{oid}/confirm", headers=h)

    event = {"event": "payment_link.paid", "payload": {"payment_link": {"entity": {"id": "plink_1", "reference_id": str(oid)}}}}
    raw = json.dumps(event).encode()
    bad = client.post("/payments/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": "nope", "Content-Type": "application/json"})
    assert bad.status_code == 403
    sig = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
    ok = client.post("/payments/razorpay/webhook", content=raw, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
    assert ok.status_code == 200 and ok.json()["status"] == "paid"
    assert client.get("/orders", headers=h).json()["orders"][0]["payment_ref"] == "plink_1"


def test_helpers():
    assert handoff_url("Zepto", "paneer") == "https://www.zeptonow.com/search?query=paneer"
    assert handoff_url("Sharma Kirana", "milk") is None
    assert verify_razorpay_signature(b"x", hmac.new(b"s", b"x", hashlib.sha256).hexdigest(), "s")
    assert not verify_razorpay_signature(b"x", "deadbeef", "s")
