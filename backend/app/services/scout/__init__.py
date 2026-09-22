"""Price scout: pulls prices from every source into vendor_offers so ranking only ever reads the database.

Kirana prices arrive through the vendor portal (routes/vendor.py) and go through upsert_offer too, so every
price change, from any source, leaves a price_snapshots row behind.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ... import models
from ...models.base import utcnow
from .base import PriceSource, ScoutOffer
from .platforms import SOURCES, PlatformSource

STALE_AFTER = timedelta(minutes=30)

__all__ = ["STALE_AFTER", "ScoutOffer", "PriceSource", "PlatformSource", "SOURCES", "upsert_offer", "refresh_product", "is_stale"]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_stale(offer: models.VendorOffer, now: datetime | None = None) -> bool:
    now = now or utcnow()
    fetched = _aware(offer.fetched_at)
    return fetched is None or now - fetched > STALE_AFTER


def upsert_offer(
    db: Session,
    vendor: models.Vendor,
    product: models.Product,
    price: float,
    in_stock: bool,
    eta: int | None,
    source: str,
    now: datetime | None = None,
) -> models.VendorOffer:
    """Create or update the current price and record a snapshot when it changed. Does not commit."""
    now = now or utcnow()
    price = round(float(price), 2)
    offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product.id).first()
    changed = offer is None or offer.price != price or offer.in_stock != in_stock
    if offer is None:
        offer = models.VendorOffer(vendor_id=vendor.id, product_id=product.id)
        db.add(offer)
    offer.price = price
    offer.in_stock = in_stock
    offer.eta_minutes = eta
    offer.source = source
    offer.fetched_at = now
    if changed:
        db.add(models.PriceSnapshot(vendor_id=vendor.id, product_id=product.id, price=price, in_stock=in_stock, recorded_at=now))
    db.flush()
    return offer


def refresh_product(
    db: Session,
    product: models.Product,
    pincode: str | None,
    sources: list[PlatformSource] | None = None,
    now: datetime | None = None,
) -> dict:
    """Ask every platform source for this product; keep old prices for any source that is off or fails. Commits."""
    now = now or utcnow()
    refreshed: list[str] = []
    skipped: list[str] = []
    for source in sources if sources is not None else SOURCES:
        offers = source.fetch(product, pincode)
        if offers is None:
            skipped.append(source.name)
            continue
        vendor = db.query(models.Vendor).filter_by(name=source.vendor_name).first()
        if vendor is None:
            vendor = models.Vendor(name=source.vendor_name, kind=models.VendorKind.PLATFORM)
            db.add(vendor)
            db.flush()
        for o in offers:
            upsert_offer(db, vendor, product, o.price, o.in_stock, o.eta_minutes, models.OfferSource.SCRAPER, now=now)
        refreshed.append(source.name)
    db.commit()
    return {"refreshed": refreshed, "skipped": skipped}
