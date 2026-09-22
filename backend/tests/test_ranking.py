"""Ranking v2: deterministic, priority-aware, with plain-English reasons."""

from app import models
from app.services.ranking import WEIGHTS, haversine_km, rank_offers


def _pair(name, kind, price, eta, rating=4.0, service=0.5, lat=None, lng=None, radius=None, vid=None):
    v = models.Vendor(
        id=vid or abs(hash(name)) % 10000, name=name, kind=kind, rating=rating, service_score=service,
        eta_minutes=eta, lat=lat, lng=lng, delivery_radius_km=radius,
    )
    o = models.VendorOffer(vendor_id=v.id, product_id=1, price=price, eta_minutes=eta, in_stock=True)
    return (v, o)


CHEAP_SLOW = _pair("Sharma Kirana", "kirana", 55, 40, rating=4.2, vid=1)
FAST_DEAR = _pair("Blinkit", "platform", 68, 10, rating=4.7, vid=2)
MIDDLE = _pair("Zepto", "platform", 62, 25, rating=4.5, vid=3)


def test_weights_sum_to_one():
    for name, w in WEIGHTS.items():
        assert abs(sum(w.values()) - 1) < 1e-9, name


def test_price_priority_prefers_cheapest():
    ranked = rank_offers([CHEAP_SLOW, FAST_DEAR, MIDDLE], priority="price")
    assert ranked[0]["vendor_name"] == "Sharma Kirana"


def test_speed_priority_prefers_fastest():
    ranked = rank_offers([CHEAP_SLOW, FAST_DEAR, MIDDLE], priority="speed")
    assert ranked[0]["vendor_name"] == "Blinkit"


def test_deterministic_and_keeps_phase1_keys():
    a = rank_offers([CHEAP_SLOW, FAST_DEAR, MIDDLE])
    b = rank_offers([MIDDLE, CHEAP_SLOW, FAST_DEAR])
    assert [r["vendor_id"] for r in a] == [r["vendor_id"] for r in b]
    assert {"vendor_id", "vendor_name", "vendor_kind", "rating", "price", "eta_minutes", "final_score",
            "recommendation", "reason", "distance_km", "in_stock", "stale"} <= set(a[0])


def test_reasons_present_and_distinct():
    ranked = rank_offers([CHEAP_SLOW, FAST_DEAR, MIDDLE])
    reasons = [r["reason"] for r in ranked]
    assert all(reasons)
    assert len(set(reasons)) == 3
    by_name = {r["vendor_name"]: r["reason"] for r in ranked}
    assert by_name["Sharma Kirana"].startswith("Cheapest")
    assert by_name["Blinkit"].startswith("Fastest")


def test_kirana_outside_radius_is_dropped():
    home = models.Household(name="h", lat=12.9716, lng=77.5946)
    near = _pair("Near Kirana", "kirana", 55, 30, lat=12.9750, lng=77.5990, radius=3, vid=10)   # ~0.6 km
    far = _pair("Far Kirana", "kirana", 50, 30, lat=13.0500, lng=77.5946, radius=3, vid=11)     # ~8.7 km
    app = _pair("Blinkit", "platform", 68, 10, vid=12)
    ranked = rank_offers([near, far, app], household=home)
    names = [r["vendor_name"] for r in ranked]
    assert "Far Kirana" not in names and {"Near Kirana", "Blinkit"} == set(names)
    near_row = next(r for r in ranked if r["vendor_name"] == "Near Kirana")
    assert 0.4 < near_row["distance_km"] < 0.8


def test_haversine_known_distance():
    # Bengaluru MG Road to Kempegowda airport is a little under 28 km as the crow flies.
    assert 26 < haversine_km(12.9757, 77.6063, 13.1989, 77.7068) < 29


def test_empty():
    assert rank_offers([]) == []
