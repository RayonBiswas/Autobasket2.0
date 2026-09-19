# Phase 2 — Device Ingestion + Fridge Simulator: Design

Date: 2026-09-19
Status: DRAFT
Parent: `2026-09-19-smart-fridge-roadmap-design.md` §3.2, §6 Phase 2

## 1. Goal (plain words)

Make the whole software loop work **before the hardware arrives**. A small Python program pretends to be the
Raspberry Pi: it reads the slot layout from the API, "drains" each slot's weight over time, and posts readings
exactly the way the real Pi will. The API turns weights into "milk is 43 % left", the Slots page lets you say
"slot 1 holds milk, this is what empty/full weighs", and the Dashboard shows real bars dropping, real top-3
offers, and real orders.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Raw readings are kept | New table `slot_readings` (slot, grams, time) | Calibration ("this is full") needs the last raw weight; Phase 3 learning and debugging need history. |
| Weight → remaining | `fraction = clamp((grams − tare) / (full − tare), 0, 1)` per slot; only applied when the slot has a product **and** both tare/full | A slot with no product is just a scale; we still store its weight but never guess what it holds. |
| Calibration UX | Two buttons per slot: **Mark empty** (tare = last reading) and **Mark full** (full = last reading) | No typing grams; you put the empty container in, tap, fill it, tap. |
| Device identity | Device bearer token (`current_device`), created by the household via `POST /devices` (token shown once) | The Pi never holds a user login; a lost Pi can be revoked without touching the user. |
| Simulator | `edge/simulator.py`, stdlib + `requests`, config by env vars, `--once` for tests | The same folder later holds the real Pi agent; the API contract is shared. |
| Dashboard | **Rewritten** on real endpoints; fake timers, seeded orders, commission maths and `VendorRadar.jsx` deleted | The demo code cannot show real data; keeping it means two dashboards. Visual language stays. |
| Readings cadence | Whatever the device sends; API is idempotent per reading (no dedupe needed — each reading is a fact) | Real Pi posts on door-close; simulator posts every N seconds. |

## 3. Schema change (migration 0002)

**slot_readings** — id · slot_id `FK slots` · weight_grams `float` · recorded_at `ts` · index (slot_id, recorded_at)

## 4. API

Device-authenticated (bearer = device token):
```
GET  /devices/me                    → {device:{id,name}, trays:[{position,label,slots:[{slot_id,position,product:{id,name,pack_size,unit}|null,tare_grams,full_grams}]}]}
POST /devices/me/readings           {captured_at?, readings:[{tray:int, slot:int, weight_grams:float}]}
                                     → {accepted:int, applied:[{slot_id, product_id, remaining_fraction}], ignored:int}
```
Household-authenticated:
```
GET  /products                      catalog list (id, name, brand, category, unit, pack_size, typical_full_grams)
GET  /devices                       list household devices (never the token)
POST /devices        {name}         → {device_id, token}  (token shown once)
GET  /households/me/slots           (extended) each slot also has product_name, latest_weight_grams, latest_at, remaining_fraction
PUT  /slots/{id}     {product_id|null, tare_grams?, full_grams?}
POST /slots/{id}/mark-empty         tare_grams = latest reading (409 if no reading yet)
POST /slots/{id}/mark-full          full_grams = latest reading (409 if no reading; 422 if ≤ tare)
GET  /inventory/{product_id}/history?days=14 → {points:[{recorded_at, remaining_fraction, source}]}
```
All slot routes verify the slot belongs to the caller's household (slot → tray → device.household_id).

## 5. Simulator behaviour

- Env: `AB_API_URL` (default `http://127.0.0.1:8000`), `AB_DEVICE_TOKEN` (required), `AB_INTERVAL` seconds (default 5), `AB_SEED` (optional, deterministic).
- Start: fetch `/devices/me`. For each calibrated slot, start at `full_grams` (or at `tare + (full − tare) × AB_START_FRACTION` when set).
- Each tick: assigned slots lose 0.5–3 % of (full − tare), with ±3 g noise; when below tare + 5 % there is a 25 % chance per tick of a "refill" back to full (someone shopped). Unassigned slots report tare-like weight 50 g ± 2 g.
- POST readings; log one line per tick: `tick 12 | milk 43% | rice 71% | water 12% (refilled)`.
- `--once` posts a single tick and exits (used by the test and by CI smoke).

## 6. Frontend

- **Slots page:** slot card shows product name, latest grams, remaining %, and two buttons (Mark empty / Mark full) plus an "Assign product" select (from `/products`). Refreshes every 5 s. "Add device" button creates a device and shows the token once with a copy hint.
- **Dashboard (new):** inventory cards (name, remaining bar, days left, status pill, 14-day sparkline from history); clicking a card loads top-3 offers; "Order" on an offer creates a real `POST /orders` (status `proposed`) and shows it in a "Recent orders" list; `AgentChatPanel` kept at the top. Removed: `SEED_HISTORY`, `SEED_ORDERS`, commission maths, "Smart Automator" countdown, `VendorRadar.jsx`.

## 7. Done when

1. `POST /seed/dev` assigns milk/rice/water to Tray 1 slots 1–3 with calibration and a first reading.
2. Simulator runs against the dev server; within 30 s the Dashboard bars visibly drop and `/inventory` reflects it.
3. Marking a slot empty/full through the UI changes `tare_grams`/`full_grams`.
4. Ordering from a top-3 card creates an order visible in "Recent orders".
5. `pytest` green (device auth, readings→inventory, unassigned slot ignored, calibration, history, simulator tick), ruff/eslint/build clean.
6. PostgreSQL: `alembic upgrade head` + full test run with `DATABASE_URL` pointing at the Docker Postgres (once Docker Desktop is installed).

## 8. Not in Phase 2

Learned consumption rates and the background worker (3) · vendor portal (4) · scrapers (5) · notifications/payment (6) · photos/vision (7) · real Pi GPIO code (8).
