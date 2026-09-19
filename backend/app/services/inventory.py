"""Read/write helpers for a household's inventory. Every change writes an InventoryEvent (the learning history)."""

from sqlalchemy.orm import Session

from .. import models
from .predictor import predict_state


def get_or_create_state(db: Session, household_id: int, product_id: int) -> models.InventoryState:
    state = (
        db.query(models.InventoryState)
        .filter_by(household_id=household_id, product_id=product_id)
        .first()
    )
    if state is None:
        state = models.InventoryState(household_id=household_id, product_id=product_id, remaining_fraction=1.0)
        db.add(state)
        db.flush()
    return state


def set_remaining(
    db: Session,
    household: models.Household,
    product_id: int,
    fraction: float,
    source: str = models.EventSource.MANUAL,
    slot_id: int | None = None,
    weight_grams: float | None = None,
) -> models.InventoryState:
    """Record a new remaining fraction for a product and refresh its prediction. Commits."""
    fraction = max(0.0, min(1.0, fraction))
    state = get_or_create_state(db, household.id, product_id)
    state.remaining_fraction = fraction
    db.add(
        models.InventoryEvent(
            household_id=household.id,
            product_id=product_id,
            slot_id=slot_id,
            source=source,
            weight_grams=weight_grams,
            remaining_fraction=fraction,
        )
    )
    product = db.get(models.Product, product_id)
    pred = predict_state(state, product, household)
    state.days_left = pred["days_left"]
    state.status = pred["status"]
    state.daily_rate = pred["estimated_daily_usage"]
    db.commit()
    db.refresh(state)
    return state


def state_row(state: models.InventoryState, product: models.Product, household: models.Household) -> dict:
    """API/agent-facing view of one inventory row."""
    pred = predict_state(state, product, household)
    return {
        "product_id": product.id,
        "name": product.name,
        "brand": product.brand,
        "unit": product.unit,
        "pack_size": product.pack_size,
        "remaining_fraction": state.remaining_fraction,
        "remaining_qty": round(state.remaining_fraction * product.pack_size, 2),
        "days_left": pred["days_left"],
        "status": pred["status"],
        "estimated_daily_usage": pred["estimated_daily_usage"],
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


def list_states(db: Session, household: models.Household) -> list[dict]:
    rows = (
        db.query(models.InventoryState, models.Product)
        .join(models.Product, models.Product.id == models.InventoryState.product_id)
        .filter(models.InventoryState.household_id == household.id)
        .order_by(models.Product.name)
        .all()
    )
    return [state_row(s, p, household) for s, p in rows]


def find_product(db: Session, name: str) -> models.Product | None:
    return db.query(models.Product).filter(models.Product.name.ilike(name.strip())).first()
