"""Order lifecycle: the one place that knows which status may follow which, and what each step triggers.

proposed -> confirmed -> (paid) -> accepted -> delivering -> delivered -> verified
Any open order may be cancelled by either side; a platform order goes proposed -> handoff -> verified.
"""

from sqlalchemy.orm import Session

from .. import models
from ..models.base import utcnow
from .handoff import handoff_url
from .payments import create_payment_link

S = models.OrderStatus

ALLOWED: dict[str, set[str]] = {
    S.PROPOSED: {S.CONFIRMED, S.HANDOFF, S.CANCELLED},
    S.PENDING_CONFIRMATION: {S.CONFIRMED, S.HANDOFF, S.CANCELLED},
    S.CONFIRMED: {S.PAID, S.ACCEPTED, S.CANCELLED},
    S.PAID: {S.ACCEPTED, S.CANCELLED},
    S.ACCEPTED: {S.DELIVERING, S.DELIVERED, S.CANCELLED},
    S.DELIVERING: {S.DELIVERED, S.CANCELLED},
    S.DELIVERED: {S.VERIFIED},
    S.HANDOFF: {S.VERIFIED, S.CANCELLED},
    S.VERIFIED: set(),
    S.CANCELLED: set(),
}

# What a kirana sees in its inbox: confirmed by the household, not yet handed over.
OPEN_FOR_VENDOR = {S.CONFIRMED, S.PAID, S.ACCEPTED, S.DELIVERING}
# Still in flight from the household's point of view.
OPEN_FOR_HOUSEHOLD = OPEN_FOR_VENDOR | {S.PROPOSED, S.PENDING_CONFIRMATION, S.HANDOFF, S.DELIVERED}
# A refill of the slot after one of these means the order really arrived.
AWAITING_REFILL = {S.DELIVERED, S.HANDOFF}
REFILL_FRACTION = 0.6

# Post-delivery rating moves the vendor's service score by this much of the gap (an EWMA).
SERVICE_ALPHA = 0.2


class IllegalTransition(ValueError):
    pass


def transition(order: models.Order, new_status: str) -> models.Order:
    """Move an order to new_status or raise IllegalTransition. Does not commit."""
    if new_status not in ALLOWED.get(order.status, set()):
        raise IllegalTransition(f"An order that is '{order.status}' cannot become '{new_status}'")
    order.status = new_status
    if new_status == S.DELIVERED:
        order.delivered_at = utcnow()
    if new_status == S.VERIFIED:
        order.verified_at = utcnow()
    return order


def confirm(db: Session, order: models.Order, household: models.Household) -> models.Order:
    """The household's yes. Kirana: send to the shop with a payment link. Platform: hand off to their app. Commits."""
    if order.vendor.kind == models.VendorKind.KIRANA:
        transition(order, S.CONFIRMED)
        order.payment_url, order.payment_ref = create_payment_link(order, household)
    else:
        transition(order, S.HANDOFF)
        first = order.items[0].product.name if order.items and order.items[0].product else ""
        order.handoff_url = handoff_url(order.vendor.name, first)
    db.commit()
    db.refresh(order)
    return order


def mark_paid(db: Session, order: models.Order, reference: str | None = None) -> models.Order:
    transition(order, S.PAID)
    if reference:
        order.payment_ref = reference
    db.commit()
    db.refresh(order)
    return order


def verify_refill(db: Session, household: models.Household, product_id: int, fraction: float) -> list[models.Order]:
    """Called after every inventory event: a refill closes any delivered/handed-off order for that product. Does not commit."""
    if fraction < REFILL_FRACTION:
        return []
    orders = (
        db.query(models.Order)
        .join(models.OrderItem)
        .filter(
            models.Order.household_id == household.id,
            models.Order.status.in_(AWAITING_REFILL),
            models.OrderItem.product_id == product_id,
        )
        .all()
    )
    for order in orders:
        transition(order, S.VERIFIED)
    return orders


def rate(db: Session, order: models.Order, stars: int) -> models.Order:
    """One-tap rating after delivery. Updates the vendor's star average and its reliability score. Commits."""
    if order.status not in {S.DELIVERED, S.VERIFIED}:
        raise IllegalTransition("You can rate an order once it has been delivered")
    if order.rating is not None:
        raise IllegalTransition("This order is already rated")
    if not 1 <= stars <= 5:
        raise ValueError("stars must be 1 to 5")
    order.rating = stars
    vendor = order.vendor
    vendor.rating = round((vendor.rating * vendor.review_count + stars) / (vendor.review_count + 1), 2)
    vendor.review_count += 1
    vendor.service_score = round((1 - SERVICE_ALPHA) * vendor.service_score + SERVICE_ALPHA * (stars / 5), 3)
    db.commit()
    db.refresh(order)
    return order


def order_row(order: models.Order) -> dict:
    return {
        "order_id": order.id,
        "household_id": order.household_id,
        "vendor_id": order.vendor_id,
        "vendor_name": order.vendor.name if order.vendor else None,
        "vendor_kind": order.vendor.kind if order.vendor else None,
        "status": order.status,
        "channel": order.channel,
        "total_amount": order.total_amount,
        "payment_ref": order.payment_ref,
        "payment_url": order.payment_url,
        "handoff_url": order.handoff_url,
        "rating": order.rating,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "verified_at": order.verified_at.isoformat() if order.verified_at else None,
        "items": [
            {
                "product_id": i.product_id,
                "name": i.product.name if i.product else None,
                "unit": i.product.unit if i.product else None,
                "pack_size": i.product.pack_size if i.product else None,
                "qty": i.qty,
                "unit_price": i.unit_price,
            }
            for i in order.items
        ],
    }
