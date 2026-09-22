# Phase 5 — Price Scout + Top-3 Ranking: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For any product, return the three best places to buy it (kiranas and delivery apps mixed), ranked deterministically by price, speed, distance, rating and reliability according to what the household says matters, each with a one-line plain-English reason.

**Architecture:** `services/scout/` is a set of price sources behind one interface; every source ends up writing `vendor_offers` rows (plus a `price_snapshots` history row on change), so ranking only ever reads the DB. Kirana prices come from the portal (Phase 4). Platform adapters (Blinkit, Zepto, Instamart) are real classes with a live-fetch hook that is **not configured by default**: the platforms publish no API, and scraping them is fragile and against their terms, so the adapters serve last-known prices and mark them stale after 30 minutes. `services/ranking.py` becomes the weighted engine from spec §3.6; the LLM may rewrite the reason line, never the order.

**Tech Stack:** SQLAlchemy 2, Alembic, pytest, React.

**Spec:** roadmap §3.1, §3.6, §6 Phase 5.

## Global Constraints
Deterministic ranking (same input → same order); no browser automation; scrapers fail soft; every schema change via Alembic; plain-language copy.

---

### Task 1: Migration 0005
- [ ] `PriceSnapshot` table: id, vendor_id FK, product_id FK, price, in_stock, recorded_at (index vendor+product+time). `Household.priority: str = "balanced"` (String(12)). Autogenerate `0005_price_scout`. `test_migrations` green. Commit `feat(db): price snapshots and household priority`.

### Task 2: Scout package (TDD)
```python
# services/scout/base.py
@dataclass
class ScoutOffer: vendor_name: str; price: float; in_stock: bool = True; eta_minutes: int | None = None
class PriceSource(Protocol):
    name: str
    def fetch(self, product: models.Product, pincode: str | None) -> list[ScoutOffer] | None  # None = not configured / failed
# services/scout/platforms.py
class PlatformSource: name, vendor_name, fetcher: Callable | None; fetch() calls fetcher, catches every Exception, logs, returns None
SOURCES = [PlatformSource("blinkit", "Blinkit"), PlatformSource("zepto", "Zepto"), PlatformSource("instamart", "Instamart")]
# services/scout/__init__.py
STALE_AFTER = timedelta(minutes=30)
def upsert_offer(db, vendor, product, price, in_stock, eta, source) -> VendorOffer   # writes PriceSnapshot when price changes
def refresh_product(db, product, pincode, sources=SOURCES, now=None) -> dict   # {"refreshed": [names], "skipped": [names]}
def is_stale(offer, now) -> bool
```
- [ ] Tests `test_scout.py`: a fake fetcher returning ₹70 creates a Blinkit offer + one snapshot; calling again with ₹70 adds no snapshot, with ₹65 adds one; a fetcher that raises leaves the old offer untouched and is listed in `skipped`; a source with `fetcher=None` is skipped; `is_stale` true after 31 min.
- [ ] Commit `feat(scout): price sources with fail-soft refresh and price history`.

### Task 3: Ranking v2 (TDD)
```python
WEIGHTS = {"balanced": {...}, "price": {...}, "speed": {...}}   # each sums to 1
def haversine_km(lat1, lng1, lat2, lng2) -> float
def rank_offers(pairs, household=None, priority="balanced") -> list[dict]
```
Scores in 0..1: price = min-max inverted; eta = min-max inverted over known ETAs (unknown → 0.5); distance = 1 − min(d, 10)/10 (unknown → 0.5); rating = rating/5; service = service_score. Kirana outside its delivery radius (both coords known) is dropped. Output keys keep Phase 1 names (`vendor_id, vendor_name, vendor_kind, rating, price, eta_minutes, final_score, recommendation`) and add `distance_km, in_stock, stale, reason`. `reason` is templated: cheapest+fastest → "Cheapest and fastest"; cheapest → "Cheapest, about N min"; fastest → "Fastest, about N min"; highest rating → "Best rated, about N min"; else "Good all-round choice". Ties broken by price then vendor name.
- [ ] Tests: priority "price" puts the cheapest first even if slow; "speed" puts a 10-min Blinkit above a cheaper 40-min kirana; a kirana 8 km away with radius 3 km is excluded; same input twice → identical output; reasons are non-empty and unique among the top 3.
- [ ] Commit `feat(ranking): weighted top-3 with household priority and reasons`.

### Task 4: API + worker + agent
- [ ] `GET /recommendations/{product_name}` → `{product: {...}, priority, offers: top3, considered: n}`; refreshes stale platform prices first (fail-soft). `GET /vendors/compare/{name}` uses the same engine (all rows). `PUT /households/me/priority {priority}` (422 unless balanced|price|speed); `/auth/me` returns `priority`. Vendor portal upsert writes a snapshot via `upsert_offer`. Seed adds Zepto and Instamart platform vendors. Worker job `refresh_prices` every 30 min for products in any reorder list. Agent `compare_prices` → top 3 with reasons; new tool `why_vendor(item, vendor)`.
- [ ] Tests: recommendations returns ≤3 mixed kinds with reasons; priority update changes order for a crafted case.
- [ ] Commit `feat(api): recommendations endpoint, priority setting, price refresh job`.

### Task 5: UI
- [ ] Dashboard "Where to buy": three cards, first one larger with "Best for you" and the reason; each shows price, "about N min", distance when known, "Local shop"/"Delivery app", stale prices say "price from earlier today". Order button unchanged.
- [ ] New `/settings` page: "What matters most when we pick a shop" (three big radio cards: Balanced / Lowest price / Fastest), household size (adults/children/diet). Nav gets "Settings".
- [ ] Lint, build, live screenshot `docs/screenshots/phase-5-top3.png`, README section "How the top 3 are chosen". Commit, merge, push.

## Self-review
§3.6 formula → T3; PriceSource + adapters + cache + fail-soft → T2; distance/ETA/rating/service → T3; per-household weights → T1+T4; endpoint + one-liner → T4; done-when (3 ranked cards mixing kinds) → T5.
