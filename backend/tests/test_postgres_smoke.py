"""Runs the real app against a real PostgreSQL when AB_PG_URL is set (e.g. the docker-compose db).

Skipped otherwise, so the default test run stays SQLite-only and fast.
    AB_PG_URL=postgresql+psycopg://autobasket:autobasket@localhost:5433/autobasket pytest backend/tests/test_postgres_smoke.py
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

PG_URL = os.environ.get("AB_PG_URL")
BACKEND = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(not PG_URL, reason="AB_PG_URL not set")


@pytest.fixture()
def pg_client(monkeypatch):
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    command.upgrade(cfg, "head")

    engine = create_engine(PG_URL)
    with engine.begin() as conn:  # start from a clean slate every run
        conn.execute(text(
            "TRUNCATE slot_readings, inventory_events, inventory_state, order_items, orders, vendor_offers, "
            "slots, trays, devices, household_members, otp_codes, vendors, products, households, users "
            "RESTART IDENTITY CASCADE"
        ))
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    engine.dispose()


def test_full_round_trip_on_postgres(pg_client, login):
    h = {"Authorization": f"Bearer {login(pg_client, 'pg@x.y')}"}
    seed = pg_client.post("/seed/dev", headers=h).json()
    assert seed["products"] == 20

    dh = {"Authorization": f"Bearer {seed['device_token']}"}
    r = pg_client.post("/devices/me/readings", json={"readings": [{"tray": 1, "slot": 1, "weight_grams": 565}]}, headers=dh)
    assert r.json()["applied"][0]["remaining_fraction"] == 0.5

    milk = next(x for x in pg_client.get("/inventory", headers=h).json()["inventory"] if x["name"] == "milk")
    assert milk["remaining_fraction"] == 0.5

    offers = pg_client.get("/vendors/compare/milk", headers=h).json()
    order = pg_client.post("/orders", json={"vendor_id": offers[0]["vendor_id"], "items": [{"product_id": milk["product_id"]}]}, headers=h)
    assert order.status_code == 201

    chat = pg_client.post("/agent/chat", json={"message": "show pantry status", "session_id": "pg"}, headers=h).json()
    assert "milk" in chat["response"].lower()
