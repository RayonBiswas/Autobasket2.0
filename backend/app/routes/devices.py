"""Fridge devices. Household routes manage them; /me routes are called by the device itself with its token."""

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_device, current_household, get_db
from ..core.security import hash_device_token
from ..services.readings import ingest_readings

router = APIRouter()


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ReadingIn(BaseModel):
    tray: int
    slot: int
    weight_grams: float


class ReadingsIn(BaseModel):
    captured_at: datetime | None = None
    readings: list[ReadingIn] = Field(min_length=1)


@router.post("", status_code=201)
def create_device(body: DeviceIn, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    device = models.Device(household_id=household.id, name=body.name, token_hash=hash_device_token(token))
    db.add(device)
    db.commit()
    # The raw token is returned exactly once; only its hash is stored.
    return {"device_id": device.id, "name": device.name, "token": token}


@router.get("")
def list_devices(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    devices = db.query(models.Device).filter_by(household_id=household.id).all()
    return {
        "devices": [
            {
                "id": d.id,
                "name": d.name,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                "trays": len(d.trays),
            }
            for d in devices
        ]
    }


def _product_brief(db: Session, product_id: int | None) -> dict | None:
    if product_id is None:
        return None
    p = db.get(models.Product, product_id)
    return {"id": p.id, "name": p.name, "pack_size": p.pack_size, "unit": p.unit} if p else None


@router.get("/me")
def device_me(device: models.Device = Depends(current_device), db: Session = Depends(get_db)):
    """The slot layout a device needs to interpret its own load cells."""
    return {
        "device": {"id": device.id, "name": device.name},
        "trays": [
            {
                "position": tray.position,
                "label": tray.label,
                "slots": [
                    {
                        "slot_id": s.id,
                        "position": s.position,
                        "product": _product_brief(db, s.product_id),
                        "tare_grams": s.tare_grams,
                        "full_grams": s.full_grams,
                    }
                    for s in tray.slots
                ],
            }
            for tray in device.trays
        ],
    }


@router.post("/me/readings")
def post_readings(body: ReadingsIn, device: models.Device = Depends(current_device), db: Session = Depends(get_db)):
    return ingest_readings(db, device, [r.model_dump() for r in body.readings], body.captured_at)
