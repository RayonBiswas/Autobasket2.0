import pytest

from app import models
from app.services.readings import fraction_from_weight, ingest_readings, latest_reading


@pytest.fixture()
def fridge(db_session):
    """household -> device -> tray 1 with slot 1 (milk, calibrated) and slot 2 (unassigned)."""
    household = models.Household(name="Home", adults=2, children=1)
    milk = models.Product(name="milk", category="dairy", unit="l", pack_size=1, typical_full_grams=1030)
    db_session.add_all([household, milk])
    db_session.flush()
    device = models.Device(household_id=household.id, name="Pi", token_hash="x" * 64)
    db_session.add(device)
    db_session.flush()
    tray = models.Tray(device_id=device.id, position=1)
    db_session.add(tray)
    db_session.flush()
    s1 = models.Slot(tray_id=tray.id, position=1, product_id=milk.id, tare_grams=50, full_grams=1080)
    s2 = models.Slot(tray_id=tray.id, position=2)
    db_session.add_all([s1, s2])
    db_session.commit()
    return household, device, milk, s1, s2


def test_fraction_from_weight():
    assert fraction_from_weight(565, 50, 1080) == 0.5
    assert fraction_from_weight(2000, 50, 1080) == 1.0
    assert fraction_from_weight(10, 50, 1080) == 0.0
    assert fraction_from_weight(500, 50, 50) is None
    assert fraction_from_weight(500, None, 1080) is None


def test_ingest_applies_calibrated_slot_and_stores_all(db_session, fridge):
    household, device, milk, s1, s2 = fridge

    result = ingest_readings(
        db_session, device,
        [{"tray": 1, "slot": 1, "weight_grams": 565}, {"tray": 1, "slot": 2, "weight_grams": 52}],
    )

    assert result["accepted"] == 2
    assert result["ignored"] == 0
    assert result["applied"] == [{"slot_id": s1.id, "product_id": milk.id, "remaining_fraction": 0.5}]

    state = db_session.query(models.InventoryState).filter_by(household_id=household.id, product_id=milk.id).one()
    assert state.remaining_fraction == 0.5
    event = db_session.query(models.InventoryEvent).filter_by(product_id=milk.id).one()
    assert event.source == "weight"
    assert event.slot_id == s1.id
    assert event.weight_grams == 565
    assert db_session.query(models.SlotReading).count() == 2
    assert device.last_seen_at is not None
    assert latest_reading(db_session, s2).weight_grams == 52


def test_unknown_position_is_ignored_not_raised(db_session, fridge):
    _, device, *_ = fridge
    result = ingest_readings(db_session, device, [{"tray": 9, "slot": 1, "weight_grams": 100}])
    assert result == {"accepted": 0, "applied": [], "ignored": 1}


def test_assigned_but_uncalibrated_slot_is_stored_not_applied(db_session, fridge):
    _, device, milk, s1, _ = fridge
    s1.full_grams = None
    db_session.commit()
    result = ingest_readings(db_session, device, [{"tray": 1, "slot": 1, "weight_grams": 600}])
    assert result["accepted"] == 1
    assert result["applied"] == []
    assert db_session.query(models.InventoryState).count() == 0
