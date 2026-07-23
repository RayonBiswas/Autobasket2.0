import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models
from app.agent import tools


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_pending_order_requires_confirmation_before_replenishment(db_session):
    item = models.Item(name="rice", total_qty=20, remaining_qty=5, min_threshold=2)
    vendor = models.Vendor(name="FreshMart", rating=4.8, vendor_type="grocery", review_count=120)
    vendor_item = models.VendorItem(vendor_id=1, item_name="rice", price=80)
    db_session.add_all([item, vendor, vendor_item])
    db_session.commit()

    result = tools.place_pantry_order("rice", "FreshMart", db_session)

    assert result["success"] is True
    assert result["needs_confirmation"] is True
    assert db_session.query(models.Order).count() == 1
    assert item.remaining_qty == 5

    confirmed = tools.confirm_pending_order(result["order_id"], db_session)

    assert confirmed["success"] is True
    assert confirmed["needs_confirmation"] is False
    assert db_session.query(models.Order).filter(models.Order.id == result["order_id"]).first().status == "confirmed"
    assert item.remaining_qty == item.total_qty
