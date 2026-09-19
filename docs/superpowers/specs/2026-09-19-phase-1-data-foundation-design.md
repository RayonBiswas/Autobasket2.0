# Phase 1 — Data Foundation + Auth: Design

Date: 2026-09-19
Status: IMPLEMENTED 2026-09-19 (branch phase-1-data-foundation). PostgreSQL verification pending Docker Desktop install; see docs/screenshots/phase-1-slots.png.
Parent: `2026-09-19-smart-fridge-roadmap-design.md` §3.8, §5, §6 Phase 1

## 1. Goal (plain words)

Replace the five toy tables with the real schema every later phase stands on, add login so the app knows *whose* fridge it is looking at, and rewire the existing screens and the chat agent so they keep working on the new tables. At the end you log in with your email, see your household, see 8 empty fridge slots, and the agent still answers "show pantry status".

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Old data | **Drop it.** No migration script. | The old tables only ever held seed data. Writing a migrator for fake data is wasted work. |
| ORM style | SQLAlchemy 2.0 `DeclarativeBase` + `Mapped[...]` typed columns, one `Base` in `database.py` | Today `models.py` and `database.py` each declare their own `Base` — a latent bug. Typed columns catch mistakes in the editor. |
| Migrations | Alembic, `backend/alembic/`, URL from `DATABASE_URL` | Industry standard; production DBs must never be changed by `create_all`. |
| Tests | SQLite in-memory via `create_all` (fast) **plus** one test that runs the Alembic migration on a temp SQLite file and checks it matches the models | Catches "forgot to write the migration" the day it happens. |
| Production DB | PostgreSQL 16 via Docker Compose (`docker-compose.yml` at repo root) | From the roadmap. Verified once Docker Desktop is installed; SQLite until then. |
| Login | **Email OTP** (6-digit code, 10-min expiry) → JWT (24 h). In dev mode (`AUTH_DEV_MODE=1`) the code is returned in the API response and printed to the log instead of emailed. | No SMS provider signup needed to start. Phone OTP (MSG91) slots in behind the same `send_otp()` function in Phase 6. |
| Multi-tenancy | Every data row belongs to a `household_id`. Every endpoint except `/auth/*` and `/` requires a JWT and scopes queries to the caller's household. | A startup has many customers from day one; retrofitting tenancy later is the classic painful migration. |
| Device auth | Each Pi gets a random 32-byte token; DB stores only its SHA-256 hash; Pi sends `Authorization: Bearer <token>`. | Same pattern as API keys everywhere. Phase 2 uses it. |
| IDs | Integer autoincrement | Simple, fast, readable in logs. UUIDs add nothing here. |
| Timestamps | `DateTime(timezone=True)`, always UTC, default `now()` | The current code uses naive `utcnow()`; mixing naive/aware is a common crash source. |
| Enums | Stored as short strings with a Python `StrEnum` in code (`order_status`, `vendor_kind`, …) | Portable across SQLite/Postgres; readable in the DB. |
| Agent memory | Stays in-process for now | Moving it to the DB is Phase 6 work (Telegram needs it). Not needed yet. |

## 3. Schema (Phase 1 creates exactly these 14 tables)

Column types: `int`, `str`, `float`, `bool`, `ts` (timezone-aware datetime), `json`. `?` = nullable. All tables have `id int PK` unless noted.

**users** — email `str` unique · phone `str?` unique · name `str?` · role `str` (`household` | `vendor` | `admin`) · created_at `ts`

**otp_codes** — email `str` indexed · code_hash `str` · expires_at `ts` · consumed_at `ts?` · created_at `ts`

**households** — name `str` · pincode `str?` · lat `float?` · lng `float?` · adults `int`=2 · children `int`=1 · food_habit `str`=`mixed` · created_at `ts`

**household_members** — user_id `int FK users` · household_id `int FK households` · role `str` (`owner` | `member`) · PK (user_id, household_id)

**devices** — household_id `FK` · name `str` · token_hash `str` unique · last_seen_at `ts?` · created_at `ts`

**trays** — device_id `FK` · position `int` · label `str?` · unique (device_id, position)

**slots** — tray_id `FK` · position `int` · product_id `int? FK products` · tare_grams `float?` · full_grams `float?` · unique (tray_id, position)

**products** — name `str` · brand `str?` · category `str` · unit `str` (`g` | `ml` | `pcs`) · pack_size `float` · typical_full_grams `float?` · created_at `ts` · unique (name, brand, pack_size)

**inventory_events** — household_id `FK` · product_id `FK` · slot_id `int? FK` · source `str` (`weight` | `vision` | `manual` | `order`) · weight_grams `float?` · remaining_fraction `float` (0–1) · recorded_at `ts` · index (household_id, product_id, recorded_at)

**inventory_state** — household_id `FK` · product_id `FK` · remaining_fraction `float` · daily_rate `float?` · days_left `float?` · status `str` (`safe` | `warning` | `critical` | `unknown`) · updated_at `ts` · unique (household_id, product_id)

**vendors** — name `str` · kind `str` (`kirana` | `platform`) · owner_user_id `int? FK users` · pincode `str?` · lat `float?` · lng `float?` · address `str?` · phone `str?` · rating `float`=4.0 · review_count `int`=0 · service_score `float`=0.5 · eta_minutes `int?` · delivery_radius_km `float?` · is_active `bool`=true · created_at `ts`

**vendor_offers** — vendor_id `FK` · product_id `FK` · price `float` · in_stock `bool`=true · eta_minutes `int?` · source `str` (`portal` | `scraper` | `seed`) · fetched_at `ts` · unique (vendor_id, product_id)

**orders** — household_id `FK` · vendor_id `FK` · status `str` (`proposed` | `pending_confirmation` | `confirmed` | `paid` | `accepted` | `delivering` | `delivered` | `verified` | `handoff` | `cancelled`) · channel `str` (`kirana` | `handoff`) · total_amount `float` · payment_ref `str?` · created_at `ts` · updated_at `ts`

**order_items** — order_id `FK` · product_id `FK` · qty `float` · unit_price `float`

Deferred to their own phases: `price_snapshots` (5), `notifications` (6), `vision_results` (7).

## 4. Auth flow

```
POST /auth/request-otp  {email}            → 204   (dev mode: 200 {"dev_code": "123456"})
POST /auth/verify-otp   {email, code}      → 200 {access_token, user:{id,email,name}, household:{id,name}}
GET  /auth/me                              → 200 {user, household, memberships}
```
- First successful login creates the user, a household named "<email>'s home", and an `owner` membership.
- JWT payload: `{sub: user_id, hid: household_id, exp}`; signed HS256 with `JWT_SECRET` from `.env`.
- FastAPI dependency `current_household(db, token) -> Household` used by every protected router.
- OTP hashing: SHA-256 of `code + JWT_SECRET`. 5 wrong attempts per email per 10 min → 429.

## 5. What gets rewired (same URLs where the frontend uses them)

| Endpoint | Before | After |
|---|---|---|
| `GET /vendors/compare/{product_name}` | reads `VendorItem` | reads `vendor_offers ⋈ vendors ⋈ products`, same response shape (`vendor_id, vendor_name, rating, price, final_score, …`) so `Dashboard.jsx` and `Camera.jsx` need no change |
| `POST /vendors/review` | running average on `Vendor` | same, on new `vendors` |
| `POST /agent/chat` | `session_id` only | also requires JWT; tools receive `household_id` |
| `POST /seed/vendors` | fake vendors | **dev-only** (`AUTH_DEV_MODE=1`): 20 products, 3 vendors (1 kirana, 2 platforms), offers, 2 trays × 4 slots on a dev device |
| `/items`, `/intelligence`, `/orders`, `/household` | five ad-hoc routers | merged into `/inventory` (list state, manual set), `/orders` (list, create with items), `/households/me` (get/patch settings) |
| `/vision/water-level` | untouched | untouched (Phase 7 replaces it) |
| `app/routes/__init__.py` | dead orders router referencing non-existent `vendor.price` | deleted (empty package file) |

Agent tools keep their names and JSON shapes; internals switch to `inventory_state`/`products`/`vendor_offers` and take `household_id`. Guardrail (`> ₹50 → pending_confirmation`) unchanged. All 8 existing tests keep passing (fixtures updated to new models).

## 6. Frontend (minimum to stay usable)

- `src/pages/Login.jsx`: email → code → stores JWT in `localStorage`.
- `src/services/api.js`: attaches `Authorization: Bearer` from storage; on 401 clears it and shows Login.
- `src/pages/Slots.jsx`: shows the household's trays/slots (empty in Phase 1; assignment UI is Phase 2).
- Dashboard/Camera untouched beyond the auth header.

## 7. Files

```
backend/
  alembic.ini, alembic/env.py, alembic/versions/0001_initial.py
  app/database.py        Base, engine, SessionLocal, get_db()      (get_db centralised — 7 copies today)
  app/models/__init__.py re-exports
  app/models/auth.py     User, OtpCode, Household, HouseholdMember
  app/models/device.py   Device, Tray, Slot
  app/models/catalog.py  Product, Vendor, VendorOffer
  app/models/inventory.py InventoryEvent, InventoryState
  app/models/orders.py   Order, OrderItem
  app/core/config.py     Settings (pydantic-settings): DATABASE_URL, JWT_SECRET, AUTH_DEV_MODE, …
  app/core/security.py   hash/verify OTP, create/decode JWT
  app/api/deps.py        get_db, current_user, current_household, current_device
  app/routes/auth.py, inventory.py, vendors.py, orders.py, households.py, seed.py, agent.py, vision.py
  app/services/ranking.py     score offers (moved from vendor_engine.py + routes/vendors.py duplicate)
  app/services/predictor.py   unchanged in Phase 1 (Phase 3 rewrites it), adapted to InventoryState
  tests/conftest.py           shared in-memory DB + authed client fixtures
  tests/test_auth.py, test_migrations.py, test_inventory.py, test_vendors.py (+ existing 4 files updated)
docker-compose.yml            postgres:16 with a named volume
frontend/src/pages/Login.jsx, Slots.jsx; src/services/api.js; App.jsx (login gate + nav entry)
```

## 8. Done when

1. `alembic upgrade head` on a fresh Postgres (or SQLite) creates the 14 tables.
2. `pytest` green, including the migration-vs-models check.
3. Log in with an email in dev mode, `GET /auth/me` returns your household.
4. `POST /seed/vendors` then `GET /vendors/compare/milk` returns ranked offers.
5. Chat "show pantry status" answers with seeded products.
6. Frontend: login screen → dashboard → Slots page shows 2 trays × 4 empty slots.

## 9. Not in Phase 1

Device readings endpoint and simulator (2) · consumption learning (3) · vendor portal (4) · scrapers (5) · notifications/payment (6) · vision (7) · phone OTP, real email delivery, refresh tokens, rate-limit storage beyond in-memory.
