from sqlalchemy import inspect

from app import models
from app.database import Base

EXPECTED = {
    "users", "otp_codes", "households", "household_members", "devices", "trays", "slots",
    "products", "inventory_events", "inventory_state", "vendors", "vendor_offers", "orders", "order_items",
}


def test_all_fourteen_tables_exist(db_session):
    names = set(inspect(db_session.get_bind()).get_table_names())
    assert EXPECTED <= names


def test_metadata_has_exactly_expected_tables():
    assert set(Base.metadata.tables) == EXPECTED


def test_household_member_roundtrip(db_session):
    user = models.User(email="a@b.c")
    home = models.Household(name="Home")
    db_session.add_all([user, home])
    db_session.flush()
    db_session.add(models.HouseholdMember(user_id=user.id, household_id=home.id, role=models.MemberRole.OWNER))
    db_session.commit()
    assert db_session.get(models.Household, home.id).members[0].user.email == "a@b.c"
