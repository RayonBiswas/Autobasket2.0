"""Photos of a shelf → what is in each slot. Uploaded by the household (phone) or the fridge device (camera)."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_device, current_household, get_db
from ..core.config import get_settings
from ..services import vision, vision_debug

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


def _analyze(db: Session, tray: models.Tray, data: bytes, mime: str, device_ip: str | None = None) -> dict:
    if not vision.configured():
        raise HTTPException(503, "Vision is not set up on this server: set OPENAI_API_KEY (and VISION_MODEL) to enable it")
    result = vision.analyze_tray_detail(db, tray, data, mime)
    if result is None:
        raise HTTPException(502, "The vision model didn't answer. Try again in a moment")
    _capture(db, tray, data, result, device_ip)
    return {
        "tray_id": tray.id,
        "position": tray.position,
        "slots": [
            {"slot_id": s.id, "position": s.position, "product_id": s.product_id, "vision": b}
            for s, b in zip(tray.slots, result.blocks, strict=True)
        ],
    }


def _capture(db: Session, tray: models.Tray, data: bytes, result: vision.Analysis, device_ip: str | None) -> None:
    """Dev-only: keep this photo and verdict for the /vision/debug page."""
    if not vision_debug.enabled():
        return
    s = get_settings()
    device = db.get(models.Device, tray.device_id)
    by_slot = {g.slot: g for g in result.guesses}
    slots = []
    for slot, block in zip(tray.slots, result.blocks, strict=True):
        guess = by_slot.get(slot.position)
        slots.append(
            {
                "slot": slot.position,
                "item": block["item"] if block else None,
                "confidence": block["confidence"] if block else None,
                "kind": block["kind"] if block else None,
                "matched_name": block["matched_name"] if block else None,
                "box": list(guess.box) if guess and guess.box else None,
            }
        )
    vision_debug.write_latest(
        data,
        {
            "device_id": device.id if device else None,
            "device_name": device.name if device else None,
            "device_ip": device_ip,
            "tray_id": tray.id,
            "tray_position": tray.position,
            "model": s.vision_model or s.openai_model,
            "provider": urlparse(s.openai_base_url).netloc,
            "elapsed_ms": result.elapsed_ms,
            "slots": slots,
        },
    )


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
    request: Request,
    image: UploadFile,
    device: models.Device = Depends(current_device),
    db: Session = Depends(get_db),
):
    """The fridge camera's photo of one tray after a weight change (device token)."""
    tray = db.query(models.Tray).filter_by(device_id=device.id, position=position).first()
    if tray is None:
        raise HTTPException(404, "No tray at that position")
    data, mime = await _read_image(image)
    ip = request.client.host if request.client else None
    vision_debug.remember_device_ip(device.id, ip)
    return _analyze(db, tray, data, mime, device_ip=ip)
