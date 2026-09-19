"""
API-level smoke test for the AutoBasket agent chat endpoint.

Unlike test_agent_guardrail.py (which calls tools.py directly), this drives
the flow through the actual FastAPI router — /chat request/response shape,
session memory, and the confirm/cancel branches of the guardrail.

Mounts only the agent router on a bare app, with the DB and the
authenticated household swapped for test fixtures.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import models
from app.api.deps import current_household, get_db
from app.routes import agent as agent_router


@pytest.fixture()
def client(session_factory):
    seed_db = session_factory()
    household = models.Household(name="Smoke home", adults=2, children=1)
    rice = models.Product(name="rice", category="staples", unit="kg", pack_size=20)
    vendor = models.Vendor(name="FreshMart", kind=models.VendorKind.KIRANA, rating=4.8, review_count=120)
    seed_db.add_all([household, rice, vendor])
    seed_db.flush()
    seed_db.add(models.VendorOffer(vendor_id=vendor.id, product_id=rice.id, price=80))
    seed_db.add(models.InventoryState(household_id=household.id, product_id=rice.id, remaining_fraction=0.25))
    seed_db.commit()
    household_id = household.id
    seed_db.close()

    app = FastAPI()
    app.include_router(agent_router.router, prefix="/agent")

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_household():
        session = session_factory()
        try:
            yield session.get(models.Household, household_id)
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_household] = override_household
    yield TestClient(app), session_factory


def _rice_remaining(factory):
    with factory() as db:
        return db.query(models.InventoryState).join(models.Product).filter(models.Product.name == "rice").first().remaining_fraction


def test_status_query_smoke(client):
    """Basic liveness: endpoint responds with pantry info, no crash."""
    tc, _ = client
    r = tc.post("/agent/chat", json={"message": "show pantry status", "session_id": "s1"})
    assert r.status_code == 200
    body = r.json()
    assert "rice" in body["response"].lower()
    assert body["needs_confirmation"] is False


def test_order_confirm_flow_via_api(client):
    """Full guardrail round trip through the real endpoint: order -> pending -> confirm -> replenished."""
    tc, factory = client
    session_id = "confirm-flow"

    r1 = tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["needs_confirmation"] is True
    assert body1["pending_confirmation"] is not None
    order_id = body1["pending_confirmation"]["order_id"]

    with factory() as db:
        assert db.get(models.Order, order_id).status == models.OrderStatus.PENDING_CONFIRMATION
    assert _rice_remaining(factory) == 0.25  # not replenished yet

    r2 = tc.post("/agent/chat", json={"message": "yes", "session_id": session_id})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["needs_confirmation"] is False
    assert "confirmed" in body2["response"].lower()

    with factory() as db:
        assert db.get(models.Order, order_id).status == models.OrderStatus.CONFIRMED
    assert _rice_remaining(factory) == 1.0  # replenished


def test_order_reject_flow_via_api(client):
    """Cancel path: pending order is dropped, stock untouched."""
    tc, factory = client
    session_id = "reject-flow"

    r1 = tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    assert r1.json()["needs_confirmation"] is True

    r2 = tc.post("/agent/chat", json={"message": "cancel", "session_id": session_id})
    body2 = r2.json()
    assert body2["needs_confirmation"] is False
    assert "cancel" in body2["response"].lower()

    assert _rice_remaining(factory) == 0.25  # untouched


def test_clear_endpoint_resets_pending_state(client):
    """/clear should drop pending confirmation along with history."""
    tc, _ = client
    session_id = "clear-flow"

    tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    tc.post("/agent/clear", params={"session_id": session_id})

    r = tc.post("/agent/chat", json={"message": "yes", "session_id": session_id})
    # with no pending state, a bare "yes" should NOT be treated as an order confirmation
    assert r.json()["needs_confirmation"] is False
