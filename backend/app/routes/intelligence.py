from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from ..services.predictor import predict_status

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{item_id}")
def get_intelligence(item_id: int, db: Session = Depends(get_db)):

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return {"error": "Item not found"}

    household = db.query(models.Household).first()

    if not household:
        household = models.Household(
            adults=2,
            children=1,
            food_habit="mixed"
        )

    result = predict_status(item, household)

    return result
