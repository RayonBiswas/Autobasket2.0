"""Price scout: sources write vendor_offers + price_snapshots; failures never break the others."""

from datetime import UTC, datetime, timedelta

from app import models
from app.services.scout import STALE_AFTER, is_stale, refresh_product, upsert_offer
from app.services.scout.base import ScoutOffer
from app.services.scout.platforms import PlatformSource


def _product(db):
    p = models.Product(name="milk", category="dairy", unit="l", pack_size=1)
    db.add(p)
    db.commit()
    return p


def _vendor(db, name, kind=models.VendorKind.PLATFORM):
    v = models.Vendor(name=name, kind=kind)
    db.add(v)
    db.commit()
    return v


def test_upsert_writes_snapshot_only_when_price_changes(db_session):
    milk, blinkit = _product(db_session), _vendor(db_session, "Blinkit")
    upsert_offer(db_session, blinkit, milk, price=70, in_stock=True, eta=12, source=models.OfferSource.SCRAPER)
    upsert_offer(db_session, blinkit, milk, price=70, in_stock=True, eta=12, source=models.OfferSource.SCRAPER)
    upsert_offer(db_session, blinkit, milk, price=65, in_stock=True, eta=12, source=models.OfferSource.SCRAPER)
    db_session.commit()

    assert db_session.query(models.VendorOffer).count() == 1
    assert db_session.query(models.VendorOffer).one().price == 65
    prices = [s.price for s in db_session.query(models.PriceSnapshot).order_by(models.PriceSnapshot.id)]
    assert prices == [70, 65]


def test_refresh_uses_fetcher_and_skips_failures(db_session):
    milk = _product(db_session)
    _vendor(db_session, "Blinkit")
    _vendor(db_session, "Zepto")

    def blinkit_ok(product, pincode):
        return [ScoutOffer(vendor_name="Blinkit", price=66, eta_minutes=10)]

    def zepto_broken(product, pincode):
        raise RuntimeError("layout changed")

    sources = [
        PlatformSource("blinkit", "Blinkit", fetcher=blinkit_ok),
        PlatformSource("zepto", "Zepto", fetcher=zepto_broken),
        PlatformSource("instamart", "Instamart", fetcher=None),
    ]
    result = refresh_product(db_session, milk, "560001", sources=sources)
    assert result["refreshed"] == ["blinkit"]
    assert set(result["skipped"]) == {"zepto", "instamart"}

    offers = {o.vendor.name: o for o in db_session.query(models.VendorOffer).all()}
    assert offers["Blinkit"].price == 66 and offers["Blinkit"].source == "scraper"
    assert "Zepto" not in offers


def test_refresh_keeps_old_price_when_fetch_fails(db_session):
    milk, zepto = _product(db_session), _vendor(db_session, "Zepto")
    upsert_offer(db_session, zepto, milk, price=60, in_stock=True, eta=15, source=models.OfferSource.SEED)
    db_session.commit()

    def broken(product, pincode):
        raise TimeoutError

    refresh_product(db_session, milk, None, sources=[PlatformSource("zepto", "Zepto", fetcher=broken)])
    assert db_session.query(models.VendorOffer).one().price == 60


def test_is_stale():
    now = datetime.now(UTC)
    fresh = models.VendorOffer(price=1, fetched_at=now - timedelta(minutes=5))
    old = models.VendorOffer(price=1, fetched_at=now - STALE_AFTER - timedelta(minutes=1))
    naive = models.VendorOffer(price=1, fetched_at=(now - timedelta(hours=2)).replace(tzinfo=None))
    assert not is_stale(fresh, now)
    assert is_stale(old, now)
    assert is_stale(naive, now)
