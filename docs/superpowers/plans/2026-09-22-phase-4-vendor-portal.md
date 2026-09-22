# Phase 4 — Kirana Vendor Portal: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A kirana owner can sign in, create a shop with location/hours/ETA, list products with prices, and work an order inbox (accept / reject / delivered), so the household side sees real kirana offers.

**Architecture:** Same FastAPI app, new `routes/vendor.py` (prefix `/vendor`) guarded by a `current_vendor` dependency that resolves the caller's shop via `Vendor.owner_user_id`. Vendor auth reuses the email-OTP login (phone OTP swaps in once an SMS provider is configured; the token and dependency do not change). The portal is a route group (`/shop/*`) inside the existing Vite app, mobile-first, sharing the "fridge light" design system. React Router replaces the page state switch.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest, React 19, react-router-dom 7.

**Spec:** `docs/superpowers/specs/2026-09-19-smart-fridge-roadmap-design.md` §3.1, §6 Phase 4.

## Global Constraints
Python 3.12, ruff clean, every schema change via Alembic, all endpoints household- or vendor-scoped, plain-language UI copy, mobile-first for the shop pages. Deviation from spec noted here: the vendor portal lives at `/shop/*` in the same React app instead of a second `vendor-web/` app (one build, one design system, one deploy; route-isolated so it can be split later).

---

### Task 1: Migration 0004 (shop hours, one shop per owner)
- [ ] `Vendor` gains `opens_at: str|None` (String(5), "HH:MM"), `closes_at: str|None`, `min_order_amount: float` default 0. Unique index on `owner_user_id` (one shop per login). Autogenerate `0004_vendor_portal`. `test_migrations` green.
- [ ] Commit `feat(db): vendor hours and one-shop-per-owner`.

### Task 2: Vendor identity + shop profile API (TDD)
**Interface:** `api/deps.current_vendor(user=current_user, db) -> models.Vendor` (404 "You have not created a shop yet" if none).
Routes in `routes/vendor.py`:
- `POST /vendor/shop` body `{name, pincode, address?, phone?, lat?, lng?, opens_at?, closes_at?, eta_minutes?, delivery_radius_km?, min_order_amount?}` → creates vendor (kind kirana, owner=user, user.role=vendor). 409 if user already owns one.
- `GET /vendor/shop` → profile + `offer_count`, `open_orders`.
- `PUT /vendor/shop` partial update of the same fields.
- [ ] Tests `tests/test_vendor_portal.py`: create → 201 with id; second create → 409; GET without shop → 404; PUT changes eta; a household user without a shop cannot hit `/vendor/offers` (404).
- [ ] Commit `feat(vendor): shop profile endpoints`.

### Task 3: Listings API
- `GET /vendor/catalog?q=` → products (id, name, brand, pack_size, unit, category) with the shop's current price if any.
- `PUT /vendor/offers` body `{offers: [{product_id, price, in_stock=true, eta_minutes?}]}` → upsert VendorOffer rows (source=portal, fetched_at=now). Returns count.
- `DELETE /vendor/offers/{product_id}`.
- `POST /vendor/offers/csv` (multipart file) columns `product,price,in_stock?` matched by product name (case-insensitive); returns `{added, updated, unknown: [names]}`.
- [ ] Tests: upsert milk 58 → `/vendors/compare/milk` (as a household) lists the shop at 58; CSV with one unknown product reports it; delete removes it from compare.
- [ ] Commit `feat(vendor): product listings and CSV upload`.

### Task 4: Vendor order inbox + lifecycle hooks
`services/orders.py`:
```python
ALLOWED = {proposed:{confirmed,cancelled}, confirmed:{paid,accepted,cancelled}, paid:{accepted,cancelled}, accepted:{delivering,delivered,cancelled}, delivering:{delivered}, delivered:{verified}}
def transition(order, new_status) -> None  # raises ValueError on an illegal jump
def order_row(order) -> dict  # moved here from routes/orders.py, adds vendor_kind, updated_at
```
Routes:
- `GET /vendor/orders?status=open|all` (open = confirmed/paid/accepted/delivering).
- `POST /vendor/orders/{id}/accept | reject | deliver` (reject → cancelled; deliver → delivered). 404 if the order is not this shop's. 409 on illegal transition.
- Household `POST /orders/{id}/confirm` (proposed → confirmed) so the demo can run end to end before Phase 6 adds payment.
- [ ] Tests: household seeds + orders milk from the shop → confirm → vendor sees it in inbox → accept → deliver → household `/orders` shows delivered; a second shop cannot accept it; deliver from proposed → 409.
- [ ] Commit `feat(vendor): order inbox with accept/reject/deliver`.

### Task 5: Frontend — router + shop portal
- [ ] Add `react-router-dom`. `App.jsx` becomes a `BrowserRouter` with `/` (Your fridge), `/shelves`, `/camera`, `/shop/*`. Nav uses `NavLink`. Vite `historyApiFallback` is default in dev; add `frontend/public/_redirects`-style note in README for static hosting.
- [ ] `src/pages/shop/ShopHome.jsx` (`/shop`): if no shop → "Set up your shop" form (name, pincode, phone, address, opens/closes, ETA, radius). Else summary card + two tabs: **Orders** and **Products**.
- [ ] `src/pages/shop/ShopProducts.jsx`: search catalog, inline price input + in-stock toggle per row, "Save" per row (PUT upsert), CSV upload button.
- [ ] `src/pages/shop/ShopOrders.jsx`: list open orders newest first with Accept / Can't do / Delivered buttons; "Show all" toggle. Polls every 10 s.
- [ ] Household side: Dashboard order list shows "Confirm" on proposed orders (calls `/orders/{id}/confirm`) and a `pill` per status with plain words (proposed → "Waiting for you", confirmed → "Sent to shop", accepted → "Shop is packing", delivering → "On the way", delivered → "Delivered", cancelled → "Shop couldn't do it").
- [ ] Lint + build. Commit `feat(web): shop portal at /shop, React Router`.

### Task 6: Verify live + docs
- [ ] Run API + web. Create "Sharma Kirana" via `/shop`, list milk at ₹58, confirm `GET /vendors/compare/milk` shows it. Screenshot `docs/screenshots/phase-4-shop.png`. Playwright console: 0 errors.
- [ ] README: "Kirana shop portal" section (how a shop signs in, lists, works orders; CSV format). Update memory. Commit, ff-merge to main, push.

## Self-review
Spec Phase 4 bullets: signup+profile → T2; listing+CSV → T3; inbox → T4; mobile-first app → T5; done-when → T6. Names consistent: `current_vendor`, `transition`, `order_row`.
