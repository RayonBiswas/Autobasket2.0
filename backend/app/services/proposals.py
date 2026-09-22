"""Turn 'milk runs out tomorrow' into a message with three offers and Yes buttons, and turn a Yes into an order."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import models
from ..models.base import utcnow
from . import notify
from .inventory import reorder_list
from .orders import OPEN_FOR_HOUSEHOLD, confirm
from .recommendations import recommend

REPEAT_AFTER = timedelta(hours=24)
CHOICES = ("1", "2", "3")


def _open_proposal(db: Session, household_id: int, product_id: int, since: datetime) -> models.Notification | None:
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.household_id == household_id,
            models.Notification.product_id == product_id,
            models.Notification.kind == notify.KIND_REORDER,
            models.Notification.responded_at.is_(None),
            models.Notification.sent_at >= since,
        )
        .first()
    )


def _open_order(db: Session, household_id: int, product_id: int) -> bool:
    return (
        db.query(models.Order)
        .join(models.OrderItem)
        .filter(
            models.Order.household_id == household_id,
            models.Order.status.in_(OPEN_FOR_HOUSEHOLD),
            models.OrderItem.product_id == product_id,
        )
        .first()
        is not None
    )


def _runs_out(days: float) -> str:
    if days < 1:
        return "runs out today"
    if days < 2:
        return "runs out tomorrow"
    return f"runs out in {round(days)} days"


def propose_reorders(db: Session, household: models.Household, now: datetime | None = None) -> list[models.Notification]:
    """One open proposal per product that needs reordering. Skips products with an open order or a recent unanswered ask."""
    now = now or utcnow()
    created: list[models.Notification] = []
    for row in reorder_list(db, household):
        pid = row["product_id"]
        if _open_order(db, household.id, pid) or _open_proposal(db, household.id, pid, now - REPEAT_AFTER):
            continue
        product = db.get(models.Product, pid)
        rec = recommend(db, product, household)
        offers = rec["offers"]
        if not offers:
            continue
        lines = [f"{i + 1}. {o['vendor_name']} ₹{o['price']}, {o['reason'].lower()}" for i, o in enumerate(offers)]
        note = notify.send(
            db,
            household,
            kind=notify.KIND_REORDER,
            title=f"{product.name.capitalize()} {_runs_out(row['days_left'])}",
            body="\n".join(lines),
            payload={"product_id": pid, "offers": offers, "days_left": row["days_left"]},
            buttons=[(f"Yes #{i + 1}", str(i + 1)) for i in range(len(offers))] + [("Skip", "skip")],
            product_id=pid,
        )
        created.append(note)
    return created


def respond(db: Session, household: models.Household, note: models.Notification, choice: str) -> models.Order | None:
    """Answer a proposal. '1'..'3' orders from that offer and confirms it; 'skip' just closes the ask. Commits."""
    if note.household_id != household.id or note.kind != notify.KIND_REORDER:
        raise ValueError("Not your proposal")
    if note.responded_at is not None:
        raise ValueError("Already answered")
    if choice not in CHOICES + ("skip",):
        raise ValueError("choice must be 1, 2, 3 or skip")

    note.response = choice
    note.responded_at = utcnow()
    if choice == "skip":
        db.commit()
        return None

    payload = notify.payload_of(note)
    offers = payload.get("offers", [])
    index = int(choice) - 1
    if index >= len(offers):
        raise ValueError("That option is not available")
    offer = offers[index]
    vendor = db.get(models.Vendor, offer["vendor_id"])
    product = db.get(models.Product, payload["product_id"])
    current = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product.id).first()
    price = current.price if current else offer["price"]

    order = models.Order(
        household_id=household.id,
        vendor_id=vendor.id,
        status=models.OrderStatus.PROPOSED,
        channel=models.OrderChannel.KIRANA if vendor.kind == models.VendorKind.KIRANA else models.OrderChannel.HANDOFF,
        total_amount=round(price, 2),
    )
    order.items.append(models.OrderItem(product_id=product.id, qty=1, unit_price=price))
    db.add(order)
    db.flush()
    return confirm(db, order, household)
