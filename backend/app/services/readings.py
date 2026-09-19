"""Turns raw load-cell weights into inventory: store every reading, apply the calibrated ones."""

from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from .inventory import set_remaining


def fraction_from_weight(grams: float, tare: float | None, full: float | None) -> float | None:
    """Remaining fraction for a calibrated slot, clamped to 0..1. None when the slot is not calibrated."""
    if tare is None or full is None or full <= tare:
        return None
    return max(0.0, min(1.0, (grams - tare) / (full - tare)))


def latest_reading(db: Session, slot: models.Slot) -> models.SlotReading | None:
    return (
        db.query(models.SlotReading)
        .filter(models.SlotReading.slot_id == slot.id)
        .order_by(models.SlotReading.recorded_at.desc(), models.SlotReading.id.desc())
        .first()
    )


def _slot_index(device: models.Device) -> dict[tuple[int, int], models.Slot]:
    return {(tray.position, slot.position): slot for tray in device.trays for slot in tray.slots}


def ingest_readings(
    db: Session,
    device: models.Device,
    readings: list[dict],
    captured_at: datetime | None = None,
) -> dict:
    """Store readings for known (tray, slot) positions and update inventory for calibrated, assigned slots."""
    slots = _slot_index(device)
    household = db.get(models.Household, device.household_id)
    now = captured_at or models.base.utcnow()

    accepted = 0
    ignored = 0
    applied: list[dict] = []

    for reading in readings:
        slot = slots.get((int(reading["tray"]), int(reading["slot"])))
        if slot is None:
            ignored += 1
            continue
        grams = float(reading["weight_grams"])
        db.add(models.SlotReading(slot_id=slot.id, weight_grams=grams, recorded_at=now))
        accepted += 1

        if slot.product_id is None:
            continue
        fraction = fraction_from_weight(grams, slot.tare_grams, slot.full_grams)
        if fraction is None:
            continue
        state = set_remaining(
            db, household, slot.product_id, fraction,
            source=models.EventSource.WEIGHT, slot_id=slot.id, weight_grams=grams, recorded_at=now,
        )
        applied.append({"slot_id": slot.id, "product_id": slot.product_id, "remaining_fraction": state.remaining_fraction})

    device.last_seen_at = now
    db.commit()
    return {"accepted": accepted, "applied": applied, "ignored": ignored}
