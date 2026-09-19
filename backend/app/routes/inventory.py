from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..models.base import utcnow
from ..services.inventory import list_states, set_remaining, state_row

router = APIRouter()


class RemainingUpdate(BaseModel):
    remaining_fraction: float = Field(ge=0, le=1)


@router.get("")
def list_inventory(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    return {"inventory": list_states(db, household)}


@router.get("/{product_id}/history")
def inventory_history(
    product_id: int,
    days: int = Query(default=14, ge=1, le=365),
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    since = utcnow() - timedelta(days=days)
    events = (
        db.query(models.InventoryEvent)
        .filter(
            models.InventoryEvent.household_id == household.id,
            models.InventoryEvent.product_id == product_id,
            models.InventoryEvent.recorded_at >= since,
        )
        .order_by(models.InventoryEvent.recorded_at.asc())
        .all()
    )
    return {
        "product_id": product_id,
        "points": [
            {"recorded_at": e.recorded_at.isoformat(), "remaining_fraction": e.remaining_fraction, "source": e.source}
            for e in events
        ],
    }


@router.put("/{product_id}")
def update_inventory(
    product_id: int,
    body: RemainingUpdate,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    product = db.get(models.Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    state = set_remaining(db, household, product_id, body.remaining_fraction)
    return state_row(state, product, household)
