from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db

router = APIRouter()


class HouseholdPatch(BaseModel):
    name: str | None = None
    pincode: str | None = None
    adults: int | None = None
    children: int | None = None
    food_habit: str | None = None


def _dump(h: models.Household) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "pincode": h.pincode,
        "adults": h.adults,
        "children": h.children,
        "food_habit": h.food_habit,
    }


@router.get("/me")
def get_me(household: models.Household = Depends(current_household)):
    return _dump(household)


@router.patch("/me")
def patch_me(
    body: HouseholdPatch,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(household, field, value)
    db.commit()
    return _dump(household)


@router.get("/me/slots")
def slots(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    devices = db.query(models.Device).filter_by(household_id=household.id).all()
    trays = []
    for device in devices:
        for tray in device.trays:
            trays.append(
                {
                    "device": device.name,
                    "tray_id": tray.id,
                    "position": tray.position,
                    "label": tray.label,
                    "slots": [
                        {
                            "slot_id": s.id,
                            "position": s.position,
                            "product_id": s.product_id,
                            "tare_grams": s.tare_grams,
                            "full_grams": s.full_grams,
                        }
                        for s in tray.slots
                    ],
                }
            )
    return {"trays": trays}
