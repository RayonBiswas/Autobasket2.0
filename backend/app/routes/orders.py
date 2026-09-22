from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.orders import IllegalTransition, order_row, transition

router = APIRouter()


class OrderItemIn(BaseModel):
    product_id: int
    qty: float = Field(gt=0, default=1)


class OrderIn(BaseModel):
    vendor_id: int
    items: list[OrderItemIn] = Field(min_length=1)


@router.get("")
def list_orders(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    orders = (
        db.query(models.Order)
        .filter(models.Order.household_id == household.id)
        .order_by(models.Order.id.desc())
        .all()
    )
    return {"orders": [order_row(o) for o in orders]}


@router.post("", status_code=201)
def create_order(body: OrderIn, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    vendor = db.get(models.Vendor, body.vendor_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(404, "Vendor not found")

    order = models.Order(
        household_id=household.id,
        vendor_id=vendor.id,
        status=models.OrderStatus.PROPOSED,
        channel=models.OrderChannel.KIRANA if vendor.kind == models.VendorKind.KIRANA else models.OrderChannel.HANDOFF,
    )
    total = 0.0
    for line in body.items:
        offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=line.product_id).first()
        if offer is None:
            raise HTTPException(422, f"Vendor does not sell product {line.product_id}")
        order.items.append(models.OrderItem(product_id=line.product_id, qty=line.qty, unit_price=offer.price))
        total += offer.price * line.qty
    order.total_amount = round(total, 2)

    db.add(order)
    db.commit()
    db.refresh(order)
    return order_row(order)


def _own_order(db: Session, household: models.Household, order_id: int) -> models.Order:
    order = db.get(models.Order, order_id)
    if order is None or order.household_id != household.id:
        raise HTTPException(404, "Order not found")
    return order


def _move(db: Session, order: models.Order, new_status: str) -> dict:
    try:
        transition(order, new_status)
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(order)
    return order_row(order)


@router.post("/{order_id}/confirm")
def confirm_order(order_id: int, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    """The household's yes: sends the order to the shop."""
    return _move(db, _own_order(db, household, order_id), models.OrderStatus.CONFIRMED)


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    return _move(db, _own_order(db, household, order_id), models.OrderStatus.CANCELLED)
