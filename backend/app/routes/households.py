from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.ranking import PRIORITIES
from .slots import slot_view

router = APIRouter()


class HouseholdPatch(BaseModel):
    name: str | None = None
    pincode: str | None = None
    adults: int | None = None
    children: int | None = None
    food_habit: str | None = None
    lat: float | None = None
    lng: float | None = None


class PriorityIn(BaseModel):
    priority: str


def _dump(h: models.Household) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "pincode": h.pincode,
        "adults": h.adults,
        "children": h.children,
        "food_habit": h.food_habit,
        "priority": h.priority,
        "lat": h.lat,
        "lng": h.lng,
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


@router.put("/me/priority")
def set_priority(
    body: PriorityIn,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """What matters most when we rank shops: balanced, price or speed."""
    if body.priority not in PRIORITIES:
        raise HTTPException(422, f"priority must be one of {', '.join(PRIORITIES)}")
    household.priority = body.priority
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
                    "slots": [slot_view(db, s) for s in tray.slots],
                }
            )
    return {"trays": trays}
