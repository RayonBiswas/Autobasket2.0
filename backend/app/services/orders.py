"""Order lifecycle: the one place that knows which status may follow which.

proposed -> confirmed -> (paid) -> accepted -> delivering -> delivered -> verified
Any open order may be cancelled by either side; a platform order goes proposed -> handoff -> verified.
"""

from .. import models

S = models.OrderStatus

ALLOWED: dict[str, set[str]] = {
    S.PROPOSED: {S.CONFIRMED, S.HANDOFF, S.CANCELLED},
    S.PENDING_CONFIRMATION: {S.CONFIRMED, S.CANCELLED},
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


class IllegalTransition(ValueError):
    pass


def transition(order: models.Order, new_status: str) -> models.Order:
    """Move an order to new_status or raise IllegalTransition. Does not commit."""
    if new_status not in ALLOWED.get(order.status, set()):
        raise IllegalTransition(f"An order that is '{order.status}' cannot become '{new_status}'")
    order.status = new_status
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
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
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
