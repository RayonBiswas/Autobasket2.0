from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.inventory import find_product
from ..services.ranking import offers_for_product, rank_offers

router = APIRouter()


@router.get("/compare/{product_name}")
def compare_item(
    product_name: str,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    product = find_product(db, product_name)
    if product is None:
        return []
    return rank_offers(offers_for_product(db, product), household=household, priority=household.priority)


@router.post("/review")
def submit_review(
    vendor_id: int,
    new_rating: float,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    vendor = db.get(models.Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    if not 1 <= new_rating <= 5:
        raise HTTPException(422, "Rating must be between 1 and 5")

    old_rating = vendor.rating
    old_count = vendor.review_count
    vendor.rating = round((old_rating * old_count + new_rating) / (old_count + 1), 2)
    vendor.review_count = old_count + 1
    db.commit()

    return {
        "message": "Review submitted",
        "old_rating": old_rating,
        "new_rating": vendor.rating,
        "total_reviews": vendor.review_count,
    }
