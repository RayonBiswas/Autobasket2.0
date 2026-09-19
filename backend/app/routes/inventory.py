from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.inventory import list_states, set_remaining, state_row

router = APIRouter()


class RemainingUpdate(BaseModel):
    remaining_fraction: float = Field(ge=0, le=1)


@router.get("")
def list_inventory(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    return {"inventory": list_states(db, household)}


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
