"""Payment links for kirana orders.

With Razorpay keys configured we create a Payment Link (test mode works). Without keys we hand out a link to the
web app's dev payment page, which marks the order paid through a dev-only endpoint. The rest of the flow cannot
tell the difference, which is the point: the loop runs locally with zero credentials.
"""

import hashlib
import hmac
import logging
import secrets

import httpx

from .. import models
from ..core.config import get_settings

log = logging.getLogger("autobasket.payments")
RAZORPAY_LINKS = "https://api.razorpay.com/v1/payment_links"


def _dev_link(order: models.Order) -> tuple[str, str]:
    ref = f"dev_{secrets.token_urlsafe(8)}"
    return f"{get_settings().web_url.rstrip('/')}/pay/{order.id}?ref={ref}", ref


def _razorpay_link(order: models.Order, household: models.Household) -> tuple[str, str] | None:
    s = get_settings()
    body = {
        "amount": int(round(order.total_amount * 100)),
        "currency": "INR",
        "reference_id": str(order.id),
        "description": f"AutoBasket order #{order.id}",
        "callback_url": f"{s.web_url.rstrip('/')}/orders",
        "callback_method": "get",
        "notes": {"household_id": str(household.id)},
    }
    try:
        r = httpx.post(RAZORPAY_LINKS, json=body, auth=(s.razorpay_key_id, s.razorpay_key_secret), timeout=10)
        r.raise_for_status()
        data = r.json()
        return data["short_url"], data["id"]
    except Exception as exc:  # fail soft: the order still exists, the user can retry payment
        log.warning("razorpay payment link failed for order %s: %s", order.id, exc)
        return None


def create_payment_link(order: models.Order, household: models.Household) -> tuple[str, str]:
    """(url, reference). Razorpay when configured, otherwise the dev page."""
    if get_settings().razorpay_enabled:
        link = _razorpay_link(order, household)
        if link:
            return link
    return _dev_link(order)


def verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
