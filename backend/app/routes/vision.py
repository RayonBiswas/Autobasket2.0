"""Photos of a shelf → what is in each slot. Uploaded by the household (phone) or the fridge device (camera)."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_device, current_household, get_db
from ..services import vision

router = APIRouter()

MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {"image/jpeg", "image/png", "image/webp"}


async def _read_image(file: UploadFile) -> tuple[bytes, str]:
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED:
        raise HTTPException(415, "Send a JPEG, PNG or WebP photo")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "That photo is over 8 MB; use a smaller one")
    if not data:
        raise HTTPException(422, "The photo is empty")
    return data, mime


def _analyze(db: Session, tray: models.Tray, data: bytes, mime: str) -> dict:
    if not vision.configured():
        raise HTTPException(503, "Vision is not set up on this server: set OPENAI_API_KEY (and VISION_MODEL) to enable it")
    blocks = vision.analyze_tray(db, tray, data, mime)
    if blocks is None:
        raise HTTPException(502, "The vision model didn't answer. Try again in a moment")
    return {
        "tray_id": tray.id,
        "position": tray.position,
        "slots": [{"slot_id": s.id, "position": s.position, "product_id": s.product_id, "vision": b} for s, b in zip(tray.slots, blocks, strict=True)],
    }


@router.post("/trays/{tray_id}/photo")
async def household_photo(
    tray_id: int,
    image: UploadFile,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """A phone photo of one shelf. Returns what the camera thinks sits in each slot."""
    tray = (
        db.query(models.Tray)
        .join(models.Device, models.Device.id == models.Tray.device_id)
        .filter(models.Tray.id == tray_id, models.Device.household_id == household.id)
        .first()
    )
    if tray is None:
        raise HTTPException(404, "Shelf not found")
    data, mime = await _read_image(image)
    return _analyze(db, tray, data, mime)


@router.post("/device/trays/{position}/photo")
async def device_photo(
    position: int,
    image: UploadFile,
    device: models.Device = Depends(current_device),
    db: Session = Depends(get_db),
):
    """The fridge camera's photo of one tray after a weight change (device token)."""
    tray = db.query(models.Tray).filter_by(device_id=device.id, position=position).first()
    if tray is None:
        raise HTTPException(404, "No tray at that position")
    data, mime = await _read_image(image)
    return _analyze(db, tray, data, mime)
