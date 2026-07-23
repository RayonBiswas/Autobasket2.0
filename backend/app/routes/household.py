from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/set")
def set_household(adults: int, children: int, food_habit: str, db: Session = Depends(get_db)):

    household = db.query(models.Household).first()

    if not household:
        household = models.Household(
            adults=adults,
            children=children,
            food_habit=food_habit
        )
        db.add(household)
    else:
        household.adults = adults
        household.children = children
        household.food_habit = food_habit

    db.commit()

    return {"message": "Household updated"}