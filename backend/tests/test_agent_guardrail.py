"""The ₹50 guardrail: expensive orders wait for a confirmation before stock is replenished."""

import pytest

from app import models
from app.agent import tools


@pytest.fixture()
def pantry(db_session):
    household = models.Household(name="Test home", adults=2, children=1)
    rice = models.Product(name="rice", category="staples", unit="kg", pack_size=20)
    vendor = models.Vendor(name="FreshMart", kind=models.VendorKind.KIRANA, rating=4.8, review_count=120)
    db_session.add_all([household, rice, vendor])
    db_session.flush()
    db_session.add(models.VendorOffer(vendor_id=vendor.id, product_id=rice.id, price=80))
    db_session.add(models.InventoryState(household_id=household.id, product_id=rice.id, remaining_fraction=0.25))
    db_session.commit()
    return household, rice


def _remaining(db, household, product):
    return db.query(models.InventoryState).filter_by(household_id=household.id, product_id=product.id).first().remaining_fraction


def test_pending_order_requires_confirmation_before_replenishment(db_session, pantry):
    household, rice = pantry

    result = tools.place_pantry_order("rice", "FreshMart", db_session, household)

    assert result["success"] is True
    assert result["needs_confirmation"] is True
    assert db_session.query(models.Order).count() == 1
    assert _remaining(db_session, household, rice) == 0.25

    confirmed = tools.confirm_pending_order(result["order_id"], db_session, household)

    assert confirmed["success"] is True
    assert confirmed["needs_confirmation"] is False
    assert db_session.get(models.Order, result["order_id"]).status == models.OrderStatus.CONFIRMED
    assert _remaining(db_session, household, rice) == 1.0


def test_cheap_order_is_auto_approved(db_session, pantry):
    household, rice = pantry
    cheap = models.Vendor(name="Corner Shop", kind=models.VendorKind.KIRANA, rating=4.0)
    db_session.add(cheap)
    db_session.flush()
    db_session.add(models.VendorOffer(vendor_id=cheap.id, product_id=rice.id, price=40))
    db_session.commit()

    result = tools.place_pantry_order("rice", "Corner Shop", db_session, household)

    assert result["needs_confirmation"] is False
    assert _remaining(db_session, household, rice) == 1.0


def test_confirming_another_households_order_is_refused(db_session, pantry):
    household, _ = pantry
    other = models.Household(name="Other")
    db_session.add(other)
    db_session.commit()
    pending = tools.place_pantry_order("rice", "FreshMart", db_session, household)

    result = tools.confirm_pending_order(pending["order_id"], db_session, other)

    assert result["success"] is False
