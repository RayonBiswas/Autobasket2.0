"""Payment callbacks: the Razorpay webhook, and a dev-only 'pretend it was paid' endpoint."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..core.config import get_settings
from ..services.orders import IllegalTransition, mark_paid, order_row
from ..services.payments import verify_razorpay_signature

router = APIRouter()


class DevComplete(BaseModel):
    order_id: int


@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
):
    s = get_settings()
    raw = await request.body()
    if not s.razorpay_webhook_secret or not verify_razorpay_signature(raw, signature or "", s.razorpay_webhook_secret):
        raise HTTPException(403, "Bad signature")
    event = await request.json()
    if event.get("event") != "payment_link.paid":
        return {"ok": True, "ignored": event.get("event")}
    link = event.get("payload", {}).get("payment_link", {}).get("entity", {})
    try:
        order_id = int(link.get("reference_id", ""))
    except ValueError:
        return {"ok": True, "ignored": "no reference"}
    order = db.get(models.Order, order_id)
    if order is None:
        return {"ok": True, "ignored": "unknown order"}
    if order.status == models.OrderStatus.CONFIRMED:
        mark_paid(db, order, link.get("id"))
    return {"ok": True, "order_id": order.id, "status": order.status}


@router.post("/dev/complete")
def dev_complete(
    body: DevComplete,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """Stands in for Razorpay while no keys are configured. Refused outside dev mode."""
    if not get_settings().auth_dev_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only available in dev mode")
    order = db.get(models.Order, body.order_id)
    if order is None or order.household_id != household.id:
        raise HTTPException(404, "Order not found")
    if not (order.payment_ref or "").startswith("dev_"):
        raise HTTPException(409, "This order uses a real payment link")
    try:
        mark_paid(db, order)
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return order_row(order)
