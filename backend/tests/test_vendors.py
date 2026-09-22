from app import models
from app.services.ranking import rank_offers


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def test_rank_offers_prefers_cheap_and_well_rated():
    a = models.Vendor(id=1, name="A", rating=4.0)
    b = models.Vendor(id=2, name="B", rating=5.0)
    pairs = [
        (a, models.VendorOffer(vendor_id=1, product_id=1, price=30)),
        (b, models.VendorOffer(vendor_id=2, product_id=1, price=30)),
    ]
    ranked = rank_offers(pairs)
    assert [r["vendor_name"] for r in ranked] == ["B", "A"]
    assert ranked[0]["final_score"] > ranked[1]["final_score"]


def test_rank_offers_empty():
    assert rank_offers([]) == []


def test_compare_endpoint_shape(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "v@x.y")
    client.post("/seed/dev", headers=h)
    rows = client.get("/vendors/compare/milk", headers=h).json()
    assert len(rows) >= 3
    assert {"vendor_id", "vendor_name", "rating", "price", "final_score"} <= set(rows[0])
    assert rows == sorted(rows, key=lambda r: r["final_score"], reverse=True)


def test_compare_unknown_product_is_empty(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "u@x.y")
    client.post("/seed/dev", headers=h)
    assert client.get("/vendors/compare/unobtainium", headers=h).json() == []


def test_review_updates_running_average(app_client, login):
    client, _ = app_client
    h = _auth(client, login, "r@x.y")
    client.post("/seed/dev", headers=h)
    vid = client.get("/vendors/compare/milk", headers=h).json()[0]["vendor_id"]
    r = client.post("/vendors/review", params={"vendor_id": vid, "new_rating": 1}, headers=h).json()
    assert r["new_rating"] < r["old_rating"]
    assert r["total_reviews"] >= 2
