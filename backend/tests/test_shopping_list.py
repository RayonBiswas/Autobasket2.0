import sys
from datetime import datetime
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


def test_critical_item_appears_as_urgent_in_shopping_list(db_session):
    # 2 adults + 1 child drink ~1.15 L milk/day (predictor base table).
    # 1 L left -> < 1 day -> status "critical".
    db_session.add(models.Household(adults=2, children=1, food_habit="mixed"))
    db_session.add(models.Item(
        name="milk", total_qty=10, remaining_qty=1, min_threshold=2,
        last_updated=datetime.utcnow(),
    ))
    db_session.commit()

    result = tools.build_shopping_list(db_session)

    names = [row["name"] for row in result["shopping_list"]]
    assert names == ["milk"]
    assert result["shopping_list"][0]["priority"] == "urgent"
