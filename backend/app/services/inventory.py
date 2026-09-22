"""Read/write helpers for a household's inventory. Every change writes an InventoryEvent (the learning history)
and refreshes the learned rate + prediction for that product."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import models
from ..models.base import utcnow
from .consumption import estimate_rate
from .predictor import estimate_daily_usage, predict_state

LEARNING_WINDOW_DAYS = 30


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


def recompute_state(
    db: Session,
    state: models.InventoryState,
    product: models.Product,
    household: models.Household,
    now: datetime | None = None,
) -> models.InventoryState:
    """Re-learn the daily rate from recent events and refresh days_left/status. Does not commit."""
    now = now or utcnow()
    since = now - timedelta(days=LEARNING_WINDOW_DAYS)
    events = (
        db.query(models.InventoryEvent.recorded_at, models.InventoryEvent.remaining_fraction)
        .filter(
            models.InventoryEvent.household_id == household.id,
            models.InventoryEvent.product_id == product.id,
            models.InventoryEvent.recorded_at >= since,
        )
        .all()
    )
    estimate = estimate_rate(
        [(t, f) for t, f in events],
        pack_size=product.pack_size,
        prior_rate=estimate_daily_usage(product.name, household),
        now=now,
    )
    state.daily_rate = estimate.daily_rate
    state.rate_confidence = estimate.confidence
    state.rate_method = estimate.method
    state.observed_days = estimate.observed_days

    pred = predict_state(state, product, household)
    state.days_left = pred["days_left"]
    state.status = pred["status"]
    return state


def set_remaining(
    db: Session,
    household: models.Household,
    product_id: int,
    fraction: float,
    source: str = models.EventSource.MANUAL,
    slot_id: int | None = None,
    weight_grams: float | None = None,
    recorded_at: datetime | None = None,
) -> models.InventoryState:
    """Record a new remaining fraction for a product, re-learn its rate and refresh its prediction. Commits."""
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
            recorded_at=recorded_at or utcnow(),
        )
    )
    db.flush()
    product = db.get(models.Product, product_id)
    recompute_state(db, state, product, household)
    # A refill after a delivery proves the order arrived (imported here to avoid an import cycle).
    from .orders import verify_refill

    verify_refill(db, household, product_id, fraction)
    db.commit()
    db.refresh(state)
    return state


def recompute_all(db: Session, now: datetime | None = None) -> int:
    """Refresh every household's predictions (the worker calls this). Commits. Returns rows touched."""
    rows = (
        db.query(models.InventoryState, models.Product, models.Household)
        .join(models.Product, models.Product.id == models.InventoryState.product_id)
        .join(models.Household, models.Household.id == models.InventoryState.household_id)
        .all()
    )
    for state, product, household in rows:
        recompute_state(db, state, product, household, now=now)
    db.commit()
    return len(rows)


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
        "needs_reorder": pred["needs_reorder"],
        "estimated_daily_usage": pred["estimated_daily_usage"],
        "rate_confidence": state.rate_confidence,
        "rate_method": state.rate_method or "prior",
        "observed_days": state.observed_days,
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


def reorder_list(db: Session, household: models.Household) -> list[dict]:
    """Items that will not outlast a delivery, soonest first. Phase 6 notifies from this."""
    rows = [r for r in list_states(db, household) if r["needs_reorder"]]
    rows.sort(key=lambda r: (r["days_left"], r["remaining_qty"]))
    return rows


def find_product(db: Session, name: str) -> models.Product | None:
    return db.query(models.Product).filter(models.Product.name.ilike(name.strip())).first()
