from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal

router = APIRouter()


# ==============================
# DB Dependency
# ==============================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================
# COMPARE & RANK VENDORS
# ==============================

@router.get("/compare/{item_name}")
def compare_item(item_name: str, db: Session = Depends(get_db)):

    vendor_items = db.query(models.VendorItem).filter(
        models.VendorItem.item_name == item_name.lower()
    ).all()

    if not vendor_items:
        return []

    prices = [vi.price for vi in vendor_items]
    min_price = min(prices)
    max_price = max(prices)

    results = []

    for vi in vendor_items:

        vendor = db.query(models.Vendor).filter(
            models.Vendor.id == vi.vendor_id
        ).first()

        if not vendor:
            continue

        # --------------------------
        # Normalize rating (0–1)
        # --------------------------
        rating_score = vendor.rating / 5

        # --------------------------
        # Normalize price (lower price = higher score)
        # --------------------------
        if max_price != min_price:
            price_score = 1 - ((vi.price - min_price) / (max_price - min_price))
        else:
            price_score = 1

        # --------------------------
        # FINAL SCORE (Balanced Weight)
        # --------------------------
        final_score = (0.4 * price_score) + (0.6 * rating_score)

        results.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "rating": vendor.rating,
            "price": vi.price,
            "price_score": round(price_score, 2),
            "rating_score": round(rating_score, 2),
            "final_score": round(final_score, 2)
        })

    # Sort highest score first
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return results


# ==============================
# SUBMIT REVIEW (Running Average)
# ==============================

@router.post("/review")
def submit_review(vendor_id: int, new_rating: float, db: Session = Depends(get_db)):

    vendor = db.query(models.Vendor).filter(
        models.Vendor.id == vendor_id
    ).first()

    if not vendor:
        return {"error": "Vendor not found"}

    old_rating = vendor.rating
    old_count = vendor.review_count

    # Running average formula
    updated_rating = ((old_rating * old_count) + new_rating) / (old_count + 1)

    vendor.rating = round(updated_rating, 2)
    vendor.review_count = old_count + 1

    db.commit()

    return {
        "message": "Review submitted",
        "old_rating": old_rating,
        "new_rating": vendor.rating,
        "total_reviews": vendor.review_count
    }
