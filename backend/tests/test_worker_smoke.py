from app import models, worker


def test_run_once_recomputes_every_state(session_factory, monkeypatch):
    with session_factory() as db:
        home = models.Household(name="H")
        milk = models.Product(name="milk", category="dairy", unit="l", pack_size=1)
        db.add_all([home, milk])
        db.flush()
        db.add(models.InventoryState(household_id=home.id, product_id=milk.id, remaining_fraction=0.3))
        db.commit()

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    assert worker.run_once() == 1

    with session_factory() as db:
        state = db.query(models.InventoryState).one()
        assert state.rate_method == "prior"
        assert state.days_left is not None
        assert state.status in {"safe", "warning", "critical"}
