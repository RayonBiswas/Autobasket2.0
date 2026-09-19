from app import models
from app.agent import tools


def test_critical_item_appears_as_urgent_in_shopping_list(db_session):
    # 2 adults + 1 child drink ~1.15 L milk/day (predictor prior). 0.1 of a 1 L pack -> < 1 day -> "critical".
    household = models.Household(name="Home", adults=2, children=1, food_habit="mixed")
    milk = models.Product(name="milk", category="dairy", unit="l", pack_size=1)
    db_session.add_all([household, milk])
    db_session.flush()
    db_session.add(models.InventoryState(household_id=household.id, product_id=milk.id, remaining_fraction=0.1))
    db_session.commit()

    result = tools.build_shopping_list(db_session, household)

    names = [row["name"] for row in result["shopping_list"]]
    assert names == ["milk"]
    assert result["shopping_list"][0]["priority"] == "urgent"


def test_safe_items_are_not_listed(db_session):
    household = models.Household(name="Home", adults=1, children=0)
    water = models.Product(name="water", category="beverages", unit="l", pack_size=20)
    db_session.add_all([household, water])
    db_session.flush()
    db_session.add(models.InventoryState(household_id=household.id, product_id=water.id, remaining_fraction=1.0))
    db_session.commit()

    assert tools.build_shopping_list(db_session, household)["shopping_list"] == []
