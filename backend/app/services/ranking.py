"""Deterministic vendor ranking. The LLM may explain a ranking; it never computes one.

Phase 1 keeps the original 40% price / 60% rating blend. Phase 5 adds distance, ETA and service score
with per-household weights.
"""

from .. import models

PRICE_WEIGHT = 0.4
RATING_WEIGHT = 0.6


def rank_offers(pairs: list[tuple[models.Vendor, models.VendorOffer]]) -> list[dict]:
    """Score (vendor, offer) pairs for one product and return them best-first."""
    if not pairs:
        return []

    prices = [offer.price for _, offer in pairs]
    min_price, max_price = min(prices), max(prices)

    ranked = []
    for vendor, offer in pairs:
        rating_score = vendor.rating / 5
        price_score = 1.0 if max_price == min_price else 1 - (offer.price - min_price) / (max_price - min_price)
        final_score = PRICE_WEIGHT * price_score + RATING_WEIGHT * rating_score
        if final_score >= 0.8:
            recommendation = "Best Match"
        elif offer.price == min_price:
            recommendation = "Good Value"
        else:
            recommendation = "Standard"
        ranked.append(
            {
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "vendor_kind": vendor.kind,
                "rating": vendor.rating,
                "price": offer.price,
                "eta_minutes": offer.eta_minutes or vendor.eta_minutes,
                "price_score": round(price_score, 2),
                "rating_score": round(rating_score, 2),
                "final_score": round(final_score, 2),
                "recommendation": recommendation,
            }
        )

    ranked.sort(key=lambda row: row["final_score"], reverse=True)
    return ranked
