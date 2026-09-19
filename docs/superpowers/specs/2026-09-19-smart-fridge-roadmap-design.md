# AutoBasket 2.0 → Smart Fridge: Master Plan

Date: 2026-09-19
Status: DRAFT — waiting for approval
Audience: the founder (new to coding). Written in plain words. Every decision has a one-line "why".

---

## 1. What we are building (one paragraph)

A fridge that knows what is inside it, notices when something is about to run out, finds the best 3 places to buy it (local kirana shops *and* Blinkit / Zepto / Instamart), and sends the user one message: *"Milk runs out Thursday. Best option: Sharma Kirana, ₹58, 20 min. Order?"* The user taps **Yes**, pays, done. They never open the fridge to check stock. Hardware = a Raspberry Pi with a camera and weight sensors in the fridge trays. Software = this repo, grown up.

---

## 2. Where we are today (honest audit)

| Piece | Today | Verdict |
|---|---|---|
| Backend (FastAPI + SQLAlchemy) | Works. 8 routers, 5 SQLite tables | **Keep the framework, rebuild the schema.** No history, no devices, no users, no real orders. |
| Agent (LangGraph + Ollama/OpenAI + regex fallback) | Works, 5 tests pass in CI | **Keep.** Rewire its tools to the new modules. |
| Prediction (`predictor.py`) | Hardcoded usage for 5 items | **Rebuild.** Learn from real weight readings; keep the hardcoded numbers only as a cold-start guess. |
| Vendors / prices | 3 fake vendors typed by hand | **Rebuild.** Real kirana portal + real price lookup. |
| Ordering | Writes a DB row, sets stock to full | **Rebuild.** Real order lifecycle + payment + delivery confirmation by weight. |
| Vision (`Camera.jsx` + blue-pixel water level) | Laptop webcam toy | **Replace.** Pi camera → cloud vision model identifies items. |
| Frontend (React/Vite, dark UI) | Nice looking, but Dashboard uses fake `SEED_HISTORY` | **Keep the look, connect to real data.** |
| Notifications, hardware, deployment, auth | None | **Build from zero.** |

Known bug to fix on day 1: `build_shopping_list` filters on status `"danger"` but the predictor emits `"critical"`, so urgent items never appear in the shopping list (`backend/app/agent/tools.py:261`).

---

## 3. The big decisions (and why)

### 3.1 How an order actually reaches a shop
Three kinds of sellers, three different mechanics. This is the most important decision in the plan.

| Seller | How we get prices | What "Yes" does | Real end-to-end? |
|---|---|---|---|
| **Local kirana** | They list products in *our* vendor portal | Order created in our DB → kirana gets a Telegram/web notification → user pays via Razorpay/UPI → kirana delivers | **Yes, 100 %.** We own the whole flow. This is our moat. |
| **Blinkit / Zepto / Instamart** | Our "price scout" fetches their prices for the user's pincode (best-effort scraping, cached, marked fragile) | Opens their app at the product/cart via deep link; user pays there | **Partly.** No public API exists. We hand off at the last step. |
| **ONDC network** (later) | Official ONDC buyer-app API | Real order + payment through the network | **Yes**, but needs network registration (weeks). Planned as Phase 11. |

**Why:** kiranas make the product genuinely "one tap to order". Big platforms give price comparison credibility. ONDC is the scale path. We do not use browser automation to fake-checkout on Blinkit — it violates their terms and breaks every time they change a button; a startup cannot be built on that.

### 3.2 Weight sensors are the primary signal, camera is the secondary
- Each tray has **slots** (4 per tray). Each slot sits on its own load cell. `remaining % = (weight − empty weight) / (full weight − empty weight)`.
- The camera photographs the tray when the door closes. A cloud vision model answers "what is in slot 1, 2, 3, 4?" This **identifies** items and catches "someone put curd where milk was".
- **Why:** cameras alone cannot tell a full milk carton from an empty one. Weight can. Commercial smart fridges that rely only on cameras are famously useless. Weight + camera is what makes this real.
- **Honest limit:** loose vegetables and things not in a slot are camera-only ("there are tomatoes") with no quantity. That is acceptable for v1.

### 3.3 The Pi lives *outside* the fridge
Sensors and camera go inside; the Pi sits on top/behind. Thin flat cables pass through the rubber door gasket (standard DIY fridge practice). **Why:** condensation kills electronics; the Pi's official range starts at 0 °C but a cold, humid box is a bad home for it. Also keeps the power supply and Wi-Fi outside the metal box.

### 3.4 Cloud vision model instead of training our own
On each door-close, the Pi sends one photo per tray to our API, which asks an OpenAI-compatible vision model (the project already has that wiring) "list the grocery items visible, per slot". **Why:** training a custom YOLO model needs thousands of labelled fridge photos we don't have. A vision LLM recognises milk / curd / eggs / paneer / coriander out of the box, costs well under ₹1 per photo, and we can swap in a custom model later behind the same function.

### 3.5 Prediction = learned consumption rate, not a formula
Every weight reading becomes an **inventory event**. From the events we compute a per-item, per-household daily consumption rate (exponentially weighted average — recent weeks matter more). `days_left = remaining / rate`. `reorder when days_left ≤ delivery lead time + 1 safety day`. The existing hardcoded "adults × 0.4 L milk" numbers become the *starting guess* for a brand-new household with no history. **Why:** real data beats guesses, but the app must still work on day 1.

### 3.6 Top-3 ranking is deterministic; the LLM only explains it
`score = w₁·price + w₂·ETA + w₃·distance + w₄·rating + w₅·service_score`, weights configurable per household ("I care about speed" vs "I care about price"). The LLM writes the one-line human reason ("cheapest and arrives in 20 min"). **Why:** money decisions must be reproducible and testable. LLMs are for language, not arithmetic.

### 3.7 Notifications: Telegram first, WhatsApp later
Telegram bot = free, instant, supports inline "Yes / No" buttons, no approval needed. Web push (PWA) as second channel. WhatsApp Cloud API needs Meta business verification — add once the company is registered. **Why:** ship the "Yes" button this month, not next quarter.

### 3.8 Tech choices
- **Database:** PostgreSQL in production, SQLite for local tests (same SQLAlchemy code, URL from `.env`). Migrations via Alembic. *Why:* SQLite cannot handle a device posting every minute plus a vendor portal plus users at once.
- **Background jobs:** a `worker` process (APScheduler) for price refresh, prediction runs and notifications. *Why:* simple, no Redis/Celery to babysit.
- **Auth:** email/phone OTP → JWT. Households, users, vendors, devices each get their own token type. *Why:* multi-tenant from day 1 because a startup has more than one customer.
- **Frontend:** keep React/Vite, add routing (React Router) and PWA manifest so it installs like an app and receives push. Vendor portal = a second small React app in the same repo.
- **Device software:** Python on the Pi (`edge/` folder in this repo): reads HX711 load cells, watches the door reed switch, captures photos, posts to the API, buffers offline.
- **Deployment:** Docker Compose (api, worker, postgres, web, vendor-web) on a VPS (Hetzner/DigitalOcean ~₹1,500/month) or Railway. HTTPS via Caddy. CI already exists; extend it to build images.

---

## 4. Target architecture (what talks to what)

```
 FRIDGE                          CLOUD                                   PEOPLE
 ┌───────────────┐   HTTPS   ┌──────────────────────────────┐
 │ Raspberry Pi 5│ ────────► │ API (FastAPI)                │ ◄──── Web app / PWA (household)
 │  edge agent   │  readings │  /devices  /inventory        │ ◄──── Vendor portal (kirana)
 │               │  + photos │  /products /vendors /offers  │ ◄──── Telegram bot (Yes/No)
 │ HX711 ×8 ─────┤           │  /orders   /notify  /agent   │
 │ Camera ───────┤           ├──────────────────────────────┤
 │ Door switch ──┤           │ Worker (APScheduler)         │ ────► Vision model (cloud)
 │ LED strip ────┘           │  predict · scout prices ·    │ ────► Price sources (kirana DB,
 └───────────────┘           │  rank top-3 · notify         │        Blinkit/Zepto scrapers)
                             ├──────────────────────────────┤ ────► Razorpay (payment)
                             │ PostgreSQL                   │
                             └──────────────────────────────┘
```

**One full loop, in words:** door closes → weights settle → Pi posts 8 slot weights + 1 photo → API stores an inventory event per slot → vision model confirms slot contents → worker recomputes days_left → milk hits reorder point → worker asks the price scout for milk offers near the user's pincode → ranking picks top 3 → Telegram message with buttons → user taps "Yes #1" → kirana order created + Razorpay link (or deep link to Blinkit) → kirana marks delivered → next door-close shows milk slot back at 100 % → order auto-closed as "verified delivered".

---

## 5. New data model (plain-English)

| Table | Holds | Replaces |
|---|---|---|
| `users`, `households`, `household_members` | Who logs in, which fridge is theirs, adults/children/diet | `Household` |
| `devices` | One row per Pi: token, household, last_seen | — |
| `trays`, `slots` | Tray = physical shelf; slot = one load cell. Slot has assigned product, tare weight, full weight | — |
| `products` | Canonical catalog ("Amul Taaza 500 ml"), unit, category, typical full weight | `Item.name` |
| `inventory_events` | Every reading: slot, product, weight, remaining %, timestamp, source (weight / vision / manual / order) | — (this is the history the predictor needs) |
| `inventory_state` | Current remaining % per household×product, days_left, status | `Item` |
| `vendors` | Kirana (our platform) or platform (Blinkit…). Location, hours, delivery radius, rating, service score | `Vendor` |
| `vendor_offers` | Vendor × product × price × ETA × in_stock × fetched_at | `VendorItem` |
| `price_snapshots` | Historical prices for charts / "price dropped" alerts | — |
| `orders`, `order_items` | Real lifecycle: `proposed → confirmed → paid → accepted → delivering → delivered → verified` (or `handoff` for Blinkit) | `Order` |
| `notifications` | What we sent, on which channel, and what the user tapped | — |
| `vision_results` | Photo reference + model answer per slot, for audit | — |

Foreign keys everywhere (today there are none).

---

## 6. Phases — each ends with "run the app and see it work"

Rule we agreed: **don't over-polish a phase; get it running, move on.** Estimates assume ~4–6 focused hours/day.

### Phase 0 — Baseline & hardware order (Day 1)
**Purpose:** confirm everything runs on this Windows machine, fix the known bug, and order the hardware *now* so shipping time overlaps with software work.
- Run backend + frontend locally, run the 5 tests. Paste outputs.
- Fix `danger`→`critical` bug; add a test.
- Move `DATABASE_URL` to `.env`; add `docs/hardware/BOM.md` (see §7) and place the order.
- Commit the untracked `CLAUDE.md`, `.mcp.json`, `.claude/`.
**Done when:** app runs, tests green, hardware ordered.

### Phase 1 — Data foundation + auth (Days 2–4)
**Purpose:** the new tables from §5 and login. Everything later stands on this.
- Alembic set up; first migration creates the new schema; a script migrates the old 5 tables' data.
- Postgres via Docker Compose locally (SQLite stays for tests).
- Auth: OTP login → JWT; `households`, `users`; device tokens.
- Seed script: 1 household, 1 device, 2 trays × 4 slots, 20 products.
**Done when:** you can log in, see your household, see 8 empty slots.

### Phase 2 — Device ingestion + fridge simulator (Days 5–7)
**Purpose:** finish the *whole* software loop before the hardware arrives, using a fake Pi.
- `POST /devices/{id}/readings` (slot weights + optional photo).
- `edge/simulator.py`: pretends to be a fridge — 8 slots slowly draining, random "door close" events, sends readings every N seconds. Same code path the real Pi will use.
- Inventory events + inventory state computed on every reading.
- Slot assignment UI: click a slot → pick product → set "this is full now".
- Dashboard reads real `inventory_state`; delete `SEED_HISTORY`.
**Done when:** you watch the dashboard bars drop in real time while the simulator runs.

### Phase 3 — Prediction v2 (Days 8–9)
**Purpose:** turn history into "milk runs out Thursday".
- Consumption rate per household×product from `inventory_events` (EWMA). Cold-start from the old per-person table.
- `days_left`, `status`, `reorder_at`. Worker recomputes every 15 min and on every reading.
- Tests with synthetic histories (steady use, party spike, holiday gap).
**Done when:** the simulator's milk gets a correct "runs out on <date>" that moves as the rate changes.

### Phase 4 — Kirana vendor portal (Days 10–13)
**Purpose:** the sellers we fully control.
- Vendor signup (phone OTP), shop profile, location (pincode + GPS), hours, delivery radius, ETA promise.
- Product listing: pick from catalog, set price, in-stock toggle. Bulk CSV upload.
- Vendor order inbox: accept / reject / mark delivered.
- Separate small React app `vendor-web/`, mobile-first (kiranas use phones).
**Done when:** you create "Sharma Kirana", list milk at ₹58, and see it in the API as an offer.

### Phase 5 — Price scout + top-3 ranking (Days 14–17)
**Purpose:** compare kiranas with Blinkit/Zepto/Instamart and pick 3.
- `PriceSource` interface: `search(product, pincode) → [offer]`. Adapters: `KiranaDB` (real), `Blinkit`, `Zepto`, `Instamart` (Playwright scrapers, cached 30 min, fail soft — if a scraper breaks, the others still work and we log it).
- Distance (haversine from vendor GPS to household), ETA, rating, service score.
- Ranking engine with per-household weights; unit tests with fixed inputs.
- `GET /recommendations/{product}` returns top 3 + LLM one-liner.
**Done when:** for "milk" you see 3 ranked cards mixing a kirana and a platform, with a plain-English reason each.

### Phase 6 — Notifications, "Yes", payment, order lifecycle (Days 18–22)
**Purpose:** the moment the product exists.
- Telegram bot: link account, send top-3 with inline buttons *Yes #1 / Yes #2 / Yes #3 / Skip*.
- Web push for the PWA.
- "Yes" on a kirana → order `confirmed` → Razorpay payment link (test mode) → `paid` → vendor inbox → `delivered` → next reading refills slot → `verified`.
- "Yes" on a platform → deep link opens their app → order recorded as `handoff` → `verified` when the slot refills.
- Post-delivery 1-tap rating → updates vendor `service_score` (existing running-average code, reused).
- Agent tools rewired: "what's running out", "order milk", "why this vendor".
**Done when:** the simulator drains milk → your phone buzzes → you tap Yes → payment page opens → you mark delivered in the vendor portal → simulator refills → order shows *verified*.

### Phase 7 — Vision (Days 23–24)
**Purpose:** identify what is in each slot without the user typing it.
- `/devices/{id}/photo` → vision model prompt → per-slot product guess + confidence.
- Auto-suggest slot assignment ("Slot 2 looks like Amul curd — confirm?"). Mismatch alert when weight says "full" but the camera says "different item".
- Delete `Camera.jsx` water-level demo and `routes/vision.py` blue-pixel code.
**Done when:** you upload a phone photo of your real fridge tray and the app names the items.

### Phase 8 — Real hardware (Days 25–31, overlaps with shipping)
**Purpose:** replace the simulator with the fridge.
- `edge/agent.py` on the Pi: HX711 reading (median-filtered), tare/calibration CLI, door reed switch → wait 3 s for settle → read → photo (LED on) → POST; offline queue on SD card; auto-start with systemd.
- Physical build: slot platforms (acrylic or 3D-printed) on load cells, cables through gasket, camera on shelf underside, LED strip.
- Calibration: known 500 g weight per slot.
**Done when:** you take the milk out of the real fridge and the dashboard drops within 10 seconds.

### Phase 9 — Deployment (Days 32–34)
**Purpose:** it runs on the internet, not on your laptop.
- Docker images for api, worker, web, vendor-web. Compose + Caddy (HTTPS). Postgres with nightly backup.
- Domain, env secrets, CI builds and pushes images on merge to `main`.
- Device provisioning: QR on the Pi → household claims it in the app.
- Monitoring: health endpoint + uptime ping + error alerts to your Telegram.
**Done when:** the Pi in your kitchen talks to `api.<yourdomain>` and a friend can log in from their phone.

### Phase 10 — Pilot (Weeks 6–8)
3 households, 3 kiranas, one pincode. Measure: readings/day, prediction error, orders placed, "Yes" rate, scraper uptime. Fix what breaks.

### Phase 11 — Growth path (after pilot)
ONDC buyer-app registration; WhatsApp Cloud API; custom vision model trained on pilot photos; ESP32 wireless trays to cut cabling; second fridge shelf.

---

## 7. Hardware bill of materials (dev kit, 1 fridge, 2 trays × 4 slots)

Prices are September 2026 India retail; confirm on the site before paying.

| # | Part | Qty | Approx ₹ | Where | Why this one |
|---|---|---|---|---|---|
| 1 | Raspberry Pi 5, 4 GB | 1 | 5,500–6,200 | robu.in / robocraze | Fast enough to run the edge agent + future on-device vision. 4 GB is plenty. |
| 2 | Official 27 W USB-C PSU, active cooler, case, 32 GB microSD (A2) | 1 set | ~2,500–3,500 | same | Pi 5 is picky about power; the cooler keeps it stable 24×7. |
| 3 | Raspberry Pi Camera Module 3 **Wide** (120°) | 1 (later 1 per shelf) | ~3,100 + GST ≈ 3,650 | electropi.in / robocraze | Wide lens sees a whole tray from 25 cm. Autofocus. |
| 4 | **Pi 5 camera FFC cable, 22-pin → 15-pin, 50 cm–1 m** | 1 | ~200–400 | same | ⚠ Pi 5 uses a smaller 22-pin connector; the cable in the camera box will not fit. Long cable needed to reach the shelf. |
| 5 | 5 kg single-point (bar) load cell + HX711 amplifier kit | 8 | ~250–400 each ≈ 2,500 | robu.in "5 kg load cell + HX711 kit" | One per slot. 5 kg covers a 2 L bottle with margin; bar type mounts cleanly under a platform. |
| 6 | Magnetic reed switch (door sensor) | 1 | ~50 | any | Tells the Pi when the door closes. |
| 7 | 5 V USB white LED strip, 30 cm | 1 | ~300 | any | Fridge light is off when door closes; we need light for the photo. |
| 8 | Jumper wires, perfboard, headers, heat-shrink, cable ties | — | ~400 | any | — |
| 9 | Slot platforms: 3 mm acrylic sheet cut to 10×10 cm ×8, M3 standoffs | — | ~500 | local laser-cut / online | Each load cell needs a rigid plate on top. |
| 10 | 500 g calibration weight (or a sealed 500 ml water bottle = ~520 g) | 1 | 0–200 | — | Calibration. |
| 11 | *(optional, Phase 11)* ESP32 dev boards for wireless trays | 2 | ~300–400 each | robu.in / robokits | Only if cabling through the gasket proves annoying. |

**Total dev kit ≈ ₹16,000–20,000.** Order items 1–9 on Day 1.

Notes:
- The Pi 5 has 26 usable GPIO pins; 8 HX711 boards need 16 (clock + data each) plus 1 for the door switch and 1 for the LED — fits.
- Keep the Pi outside the fridge (see §3.3). Run the camera FFC and the load-cell wires through the door gasket; a flat ribbon compresses fine without breaking the seal.
- Load cells drift slightly with temperature; we re-tare each slot whenever the camera sees it empty.

---

## 8. Things I decided so you don't have to (change any of them)

1. India-first: ₹, pincode-based delivery, Razorpay, Telegram.
2. Kirana marketplace is our own; big platforms via scraping + deep link; ONDC after pilot.
3. Weight sensors primary, camera secondary; cloud vision model, no custom training in v1.
4. Pi outside the fridge; wired sensors in v1.
5. PostgreSQL + Alembic; APScheduler worker; JWT OTP auth; Docker Compose on a VPS.
6. Keep the LangGraph agent and the dark UI; rewire, don't rewrite.
7. Order hardware on Day 1 so it arrives around Phase 7.

---

## 9. Risks we are accepting, eyes open

| Risk | Mitigation |
|---|---|
| Blinkit/Zepto scrapers break | Adapter interface; cached results; kirana offers still work; alert on failure. |
| Load-cell drift / condensation | Median filtering, auto re-tare, conformal-coat the HX711 boards, Pi outside. |
| Vision model misidentifies | Weight is the source of truth for quantity; user confirms slot assignment once; audit table. |
| Kiranas won't onboard | Portal is phone-first and takes 5 minutes; CSV upload; you onboard the first 3 by hand. |
| Payment compliance | Razorpay test mode until the company is registered; no card data ever touches our servers. |

---

## 10. Tools, accounts, models — what to install and when

All free unless marked. "Now" = before Phase 0. Install only when the phase needs it; nothing earlier.

### Install on this PC
| When | What | Why | How |
|---|---|---|---|
| Now | **Docker Desktop** (Windows, WSL2 backend) | Runs PostgreSQL locally; builds the deployment images | docker.com/products/docker-desktop → install → reboot |
| Now | **uv** (already present — `uvx` runs the graph MCP) | Manages Python versions & venvs; lets me pin Python 3.12 if 3.14 breaks a library | nothing to do |
| Now | **VS Code** (if not already) | Editing, viewing the app | code.visualstudio.com |
| Phase 5 | **Playwright + Chromium** | Price scout scrapers | `pip install playwright && playwright install chromium` (I run this) |
| Phase 6 | **Telegram** on your phone | You receive the "Order?" messages and tap Yes | app store |
| Phase 8 | **Raspberry Pi Imager** | Flash Raspberry Pi OS to the microSD | raspberrypi.com/software |
| Phase 8 | **Tailscale** (PC + Pi) | Reach the Pi from anywhere without port-forwarding | tailscale.com |
| Phase 9 | **Cloudflare account** (free) | HTTPS tunnel during testing; DNS for the domain | cloudflare.com |

### Accounts to create (free tiers)
| When | Account | Why |
|---|---|---|
| Phase 6 | Telegram bot via **@BotFather** | 2-minute setup; gives a bot token |
| Phase 6 | **Razorpay** (test mode) | Payment links for kirana orders; no company docs needed for test mode |
| Phase 9 | **Hetzner** or **Railway** | Hosting. Hetzner CX22 ≈ €4/mo needs a card; Railway has a free trial |
| Phase 9 | A **domain** (~₹800/yr, e.g. from Namecheap/GoDaddy) | `api.yourbrand.in` for the Pi and the PWA |
| Phase 11 | **ONDC** buyer-app registration, **Meta WhatsApp Cloud API** | After the company is registered |

### Models and APIs — my picks
| Job | Pick | Why | Fallback |
|---|---|---|---|
| Agent reasoning (chat, "why this vendor", tool calls) | **Claude Sonnet 5** | Best tool-use reliability at the price; the LangGraph loop expects JSON tool calls and Sonnet follows that strictly | GPT-4o-mini via the existing OpenAI-compatible path |
| Vision (identify items in a tray photo) | **Claude Sonnet 5** with images | Strong at reading packaged Indian grocery brands; one call per photo | GPT-4o vision |
| Cheap classification (is this message a yes/no? which product name is this?) | **Claude Haiku 4.5** | Fast, fraction of the cost, runs thousands of times a day | regex heuristics (already in the code) |
| Local/offline dev with no API key | **Ollama** (already installed) with `llama3.1:8b` | Free, lets tests run without spending | — |

The code already speaks the OpenAI-compatible protocol (`OPENAI_BASE_URL`). If your "omniroute" is an OpenAI-compatible router that fronts Claude, we point `OPENAI_BASE_URL` at it and everything above works with zero code changes. I'll add a native Anthropic client in Phase 6/7 only if the router cannot pass images through.

### Libraries I will add (you don't install these; they go in `requirements.txt` / `package.json`)
Backend: `alembic`, `psycopg[binary]`, `python-jose` (JWT), `apscheduler`, `httpx`, `playwright`, `python-telegram-bot`, `razorpay`, `pywebpush`, `pydantic-settings`. Edge (Pi): `gpiozero`, `hx711`, `picamera2`, `requests`. Frontend: `react-router-dom`, `vite-plugin-pwa`, `recharts` (replaces hand-drawn SVG charts).

## 11. What happens after you approve

1. I write the detailed implementation plan for **Phase 0 only** (tiny) and we run it today.
2. Each later phase gets its own short plan when we reach it, so plans never go stale.
3. You will see the app run at the end of every phase — that is the definition of done.
