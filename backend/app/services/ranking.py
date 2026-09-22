"""Deterministic vendor ranking. The LLM may explain a ranking; it never computes one.

score = w_price·price + w_eta·eta + w_distance·distance + w_rating·rating + w_service·service, every term in 0..1,
weights chosen by the household's priority (balanced / price / speed). Same input always gives the same order.
"""

import math

from sqlalchemy.orm import Session

from .. import models
from .scout import is_stale

WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {"price": 0.35, "eta": 0.20, "distance": 0.15, "rating": 0.15, "service": 0.15},
    "price": {"price": 0.60, "eta": 0.10, "distance": 0.10, "rating": 0.10, "service": 0.10},
    "speed": {"price": 0.15, "eta": 0.45, "distance": 0.20, "rating": 0.10, "service": 0.10},
}
PRIORITIES = tuple(WEIGHTS)
FAR_KM = 10.0  # beyond this, distance stops mattering (the score bottoms out)
ETA_SCALE_MIN = 20.0  # ETA score decays as exp(-eta / 20 min): 10 min ≈ 0.61, 30 min ≈ 0.22, 2 h ≈ 0
ETA_UNKNOWN_MIN = 30  # a seller that promises no delivery time is scored as if it took 30 minutes


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def offers_for_product(db: Session, product: models.Product) -> list[tuple[models.Vendor, models.VendorOffer]]:
    """In-stock offers from active vendors for one product."""
    return (
        db.query(models.Vendor, models.VendorOffer)
        .join(models.VendorOffer, models.VendorOffer.vendor_id == models.Vendor.id)
        .filter(
            models.VendorOffer.product_id == product.id,
            models.VendorOffer.in_stock.is_(True),
            models.Vendor.is_active.is_(True),
        )
        .all()
    )


def _price_score(price: float, lo: float, hi: float) -> float:
    """1 for the cheapest offer, 0 for the dearest, linear in between."""
    return 1.0 if hi == lo else 1 - (price - lo) / (hi - lo)


def _eta_score(eta: int | None) -> float:
    """Absolute, not relative: a 2-hour delivery scores near zero even when nothing faster is on offer."""
    minutes = ETA_UNKNOWN_MIN if eta is None else max(eta, 0)
    return math.exp(-minutes / ETA_SCALE_MIN)


def _distance(vendor: models.Vendor, household) -> float | None:
    if household is None or household.lat is None or household.lng is None or vendor.lat is None or vendor.lng is None:
        return None
    return round(haversine_km(household.lat, household.lng, vendor.lat, vendor.lng), 2)


def _reason(row: dict, cheapest: float, fastest: int | None, best_rated: float) -> str:
    eta = row["eta_minutes"]
    about = f"about {eta} min" if eta is not None else "delivery time not known"
    is_cheapest = row["price"] == cheapest
    is_fastest = fastest is not None and eta == fastest
    if is_cheapest and is_fastest:
        return "Cheapest and fastest"
    if is_cheapest:
        return f"Cheapest, {about}"
    if is_fastest:
        return f"Fastest, {about}"
    if row["rating"] == best_rated:
        return f"Best rated, {about}"
    if row["vendor_kind"] == models.VendorKind.KIRANA:
        return f"Local shop, {about}"
    return f"Good all-round choice, {about}"


def rank_offers(
    pairs: list[tuple[models.Vendor, models.VendorOffer]],
    household=None,
    priority: str = "balanced",
) -> list[dict]:
    """Score (vendor, offer) pairs for one product and return them best-first."""
    weights = WEIGHTS.get(priority, WEIGHTS["balanced"])

    rows: list[dict] = []
    for vendor, offer in pairs:
        distance = _distance(vendor, household)
        if (
            vendor.kind == models.VendorKind.KIRANA
            and distance is not None
            and vendor.delivery_radius_km is not None
            and distance > vendor.delivery_radius_km
        ):
            continue
        rows.append(
            {
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "vendor_kind": vendor.kind,
                "rating": vendor.rating if vendor.rating is not None else 4.0,
                "service_score": vendor.service_score if vendor.service_score is not None else 0.5,
                "price": offer.price,
                "in_stock": offer.in_stock,
                "stale": is_stale(offer) if offer.fetched_at is not None else False,
                "eta_minutes": offer.eta_minutes if offer.eta_minutes is not None else vendor.eta_minutes,
                "distance_km": distance,
            }
        )
    if not rows:
        return []

    prices = [r["price"] for r in rows]
    etas = [r["eta_minutes"] for r in rows if r["eta_minutes"] is not None]
    lo_p, hi_p = min(prices), max(prices)
    best_rated = max(r["rating"] for r in rows)
    fastest = min(etas) if etas else None

    for r in rows:
        parts = {
            "price": _price_score(r["price"], lo_p, hi_p),
            "eta": _eta_score(r["eta_minutes"]),
            "distance": 0.5 if r["distance_km"] is None else 1 - min(r["distance_km"], FAR_KM) / FAR_KM,
            "rating": r["rating"] / 5,
            "service": r["service_score"],
        }
        r["final_score"] = round(sum(weights[k] * v for k, v in parts.items()), 4)
        r["price_score"] = round(parts["price"], 2)
        r["rating_score"] = round(parts["rating"], 2)
        r["reason"] = _reason(r, lo_p, fastest, best_rated)
        if r["final_score"] >= 0.8:
            r["recommendation"] = "Best Match"
        elif r["price"] == lo_p:
            r["recommendation"] = "Good Value"
        else:
            r["recommendation"] = "Standard"

    rows.sort(key=lambda r: (-r["final_score"], r["price"], r["vendor_name"]))
    return rows
