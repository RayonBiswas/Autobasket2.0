from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db

router = APIRouter()


@router.get("")
def list_products(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    products = db.query(models.Product).order_by(models.Product.category, models.Product.name).all()
    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "unit": p.unit,
                "pack_size": p.pack_size,
                "typical_full_grams": p.typical_full_grams,
            }
            for p in products
        ]
    }
