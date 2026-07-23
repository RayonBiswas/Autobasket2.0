"""
API-level smoke test for the AutoBasket agent chat endpoint.

Unlike test_agent_guardrail.py (which calls tools.py directly), this drives
the flow through the actual FastAPI router — /chat request/response shape,
session memory, and the confirm/cancel branches of the guardrail.

Runs standalone without importing the full app (app.main), so it isn't
blocked by the optional cv2 import in the vision route. Only mounts the
agent router.

Run: pytest test_agent_smoke.py -v
"""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models
from app.routers import agent as agent_router


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    seed_db = TestSession()
    seed_db.add_all([
        models.Item(name="rice", total_qty=20, remaining_qty=5, min_threshold=2, predicted_daily_usage=1.0),
        models.Vendor(name="FreshMart", rating=4.8, vendor_type="grocery", review_count=120),
        models.VendorItem(vendor_id=1, item_name="rice", price=80),
    ])
    seed_db.commit()
    seed_db.close()

    app = FastAPI()
    app.include_router(agent_router.router, prefix="/agent")

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[agent_router.get_db] = override_get_db
    yield TestClient(app), TestSession


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
    tc, TestSession = client
    session_id = "confirm-flow"

    r1 = tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["needs_confirmation"] is True
    assert body1["pending_confirmation"] is not None
    order_id = body1["pending_confirmation"]["order_id"]

    db = TestSession()
    order = db.query(models.Order).filter_by(id=order_id).first()
    item = db.query(models.Item).filter_by(name="rice").first()
    assert order.status == "pending_confirmation"
    assert item.remaining_qty == 5  # not replenished yet
    db.close()

    r2 = tc.post("/agent/chat", json={"message": "yes", "session_id": session_id})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["needs_confirmation"] is False
    assert "confirmed" in body2["response"].lower()

    db = TestSession()
    order = db.query(models.Order).filter_by(id=order_id).first()
    item = db.query(models.Item).filter_by(name="rice").first()
    assert order.status == "confirmed"
    assert item.remaining_qty == item.total_qty  # replenished
    db.close()


def test_order_reject_flow_via_api(client):
    """Cancel path: pending order is dropped, stock untouched."""
    tc, TestSession = client
    session_id = "reject-flow"

    r1 = tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    assert r1.json()["needs_confirmation"] is True

    r2 = tc.post("/agent/chat", json={"message": "cancel", "session_id": session_id})
    body2 = r2.json()
    assert body2["needs_confirmation"] is False
    assert "cancel" in body2["response"].lower()

    db = TestSession()
    item = db.query(models.Item).filter_by(name="rice").first()
    assert item.remaining_qty == 5  # untouched
    db.close()


def test_clear_endpoint_resets_pending_state(client):
    """/clear should drop pending confirmation along with history."""
    tc, _ = client
    session_id = "clear-flow"

    tc.post("/agent/chat", json={"message": "order rice from FreshMart", "session_id": session_id})
    tc.post("/agent/clear", params={"session_id": session_id})

    r = tc.post("/agent/chat", json={"message": "yes", "session_id": session_id})
    # with no pending state, a bare "yes" should NOT be treated as an order confirmation
    assert r.json()["needs_confirmation"] is False