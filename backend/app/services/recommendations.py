"""Top-3 places to buy a product for one household: refresh platform prices (fail-soft), rank, keep three."""

from sqlalchemy.orm import Session

from .. import models
from .ranking import offers_for_product, rank_offers
from .scout import is_stale, refresh_product

TOP_N = 3


def product_view(p: models.Product) -> dict:
    return {"id": p.id, "name": p.name, "brand": p.brand, "unit": p.unit, "pack_size": p.pack_size, "category": p.category}


def recommend(db: Session, product: models.Product, household: models.Household, refresh: bool = True) -> dict:
    """Ranked offers for the household. Stale platform prices are refreshed first when a source is configured."""
    if refresh:
        pairs = offers_for_product(db, product)
        if any(v.kind == models.VendorKind.PLATFORM and is_stale(o) for v, o in pairs) or not pairs:
            refresh_product(db, product, household.pincode)
    ranked = rank_offers(offers_for_product(db, product), household=household, priority=household.priority)
    return {
        "product": product_view(product),
        "priority": household.priority,
        "offers": ranked[:TOP_N],
        "considered": len(ranked),
    }
