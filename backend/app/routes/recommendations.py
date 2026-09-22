from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.inventory import find_product
from ..services.recommendations import recommend

router = APIRouter()


@router.get("/{product_name}")
def recommendations(
    product_name: str,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """The three best places to buy this product for this household, best first, each with a one-line reason."""
    product = find_product(db, product_name)
    if product is None:
        raise HTTPException(404, f"We don't know a product called '{product_name}'")
    return recommend(db, product, household)
