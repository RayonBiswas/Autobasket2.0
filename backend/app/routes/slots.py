"""Slot assignment and calibration. A slot belongs to the household that owns its device."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.readings import fraction_from_weight, latest_reading
from ..services.vision import vision_block

router = APIRouter()


class SlotUpdate(BaseModel):
    product_id: int | None = None
    tare_grams: float | None = None
    full_grams: float | None = None
    clear_product: bool = False


def owned_slot(db: Session, household: models.Household, slot_id: int) -> models.Slot:
    slot = (
        db.query(models.Slot)
        .join(models.Tray, models.Tray.id == models.Slot.tray_id)
        .join(models.Device, models.Device.id == models.Tray.device_id)
        .filter(models.Slot.id == slot_id, models.Device.household_id == household.id)
        .first()
    )
    if slot is None:
        raise HTTPException(404, "Slot not found")
    return slot


def slot_view(db: Session, slot: models.Slot) -> dict:
    reading = latest_reading(db, slot)
    product = db.get(models.Product, slot.product_id) if slot.product_id else None
    grams = reading.weight_grams if reading else None
    return {
        "slot_id": slot.id,
        "position": slot.position,
        "product_id": slot.product_id,
        "product_name": product.name if product else None,
        "tare_grams": slot.tare_grams,
        "full_grams": slot.full_grams,
        "latest_weight_grams": grams,
        "latest_at": reading.recorded_at.isoformat() if reading else None,
        "remaining_fraction": fraction_from_weight(grams, slot.tare_grams, slot.full_grams) if grams is not None else None,
        "vision": vision_block(db, slot),
    }


@router.put("/{slot_id}")
def update_slot(slot_id: int, body: SlotUpdate, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    slot = owned_slot(db, household, slot_id)
    if body.clear_product:
        slot.product_id = None
    elif body.product_id is not None:
        if db.get(models.Product, body.product_id) is None:
            raise HTTPException(404, "Product not found")
        slot.product_id = body.product_id
    if body.tare_grams is not None:
        slot.tare_grams = body.tare_grams
    if body.full_grams is not None:
        slot.full_grams = body.full_grams
    db.commit()
    return slot_view(db, slot)


def _require_reading(db: Session, slot: models.Slot) -> float:
    reading = latest_reading(db, slot)
    if reading is None:
        raise HTTPException(409, "No weight reading for this slot yet")
    return reading.weight_grams


@router.post("/{slot_id}/mark-empty")
def mark_empty(slot_id: int, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    slot = owned_slot(db, household, slot_id)
    slot.tare_grams = _require_reading(db, slot)
    db.commit()
    return slot_view(db, slot)


@router.post("/{slot_id}/mark-full")
def mark_full(slot_id: int, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    slot = owned_slot(db, household, slot_id)
    grams = _require_reading(db, slot)
    if slot.tare_grams is not None and grams <= slot.tare_grams:
        raise HTTPException(422, "Full weight must be greater than the empty (tare) weight")
    slot.full_grams = grams
    db.commit()
    return slot_view(db, slot)
