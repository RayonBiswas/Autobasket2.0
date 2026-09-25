# AutoBasket 2.0

AutoBasket 2.0 is an AI-assisted pantry intelligence platform that helps households and small teams manage inventory, compare vendor prices, place orders safely, and interact with an agentic assistant through a modern web app.

## Why this project exists

The platform combines a FastAPI backend, a React/Vite frontend, and a conversational agent that can:

- track pantry stock levels and predict restock urgency
- compare prices across vendors
- build shopping lists from low-stock items
- place orders with a confirmation guardrail for higher-value purchases
- expose the experience through a dashboard and camera-oriented workflow

## Tech stack

- Backend: FastAPI, SQLAlchemy 2 + Alembic, Pydantic, APScheduler worker, LangGraph-style agent orchestration
- Frontend: React 19, React Router, Vite, Axios; installable PWA
- Data: SQLite by default for local development
- AI: Ollama or OpenAI-compatible chat endpoints with a heuristic fallback

## Project structure

- backend/app: FastAPI application, database models, routes, and agent logic
- backend/tests: smoke and guardrail tests for the agent workflow
- frontend/src: React pages and UI components

## Screenshots

| | |
|---|---|
| ![Your fridge](docs/screenshots/gauge-fridge.png) | ![Needs your yes](docs/screenshots/phase-6-proposal.png) |
| ![Orders with the delivery timeline](docs/screenshots/phase-6-orders.png) | ![Camera naming each slot](docs/screenshots/phase-7-camera.png) |
| ![Shop portal, product prices](docs/screenshots/phase-4-shop-products.png) | ![Shelves, one gauge per scale](docs/screenshots/gauge-shelves.png) |

The app has two sides in one build: the household app (leaf green) and the kirana shop portal at `/shop`
(turmeric), so a shopkeeper always knows which side they are on. Both work on a phone; the household app installs
as a PWA.

## Quick start

### Prerequisites

- Python 3.12 (managed with [uv](https://docs.astral.sh/uv/) — `uv` installs it for you)
- Node.js 20+
- Optional: Ollama for local LLM-backed agent mode
- Optional: Docker Desktop (PostgreSQL from Phase 1 onward)

### 1. Clone and enter the repository

```bash
git clone https://github.com/RayonBiswas/Autobasket2.0.git
cd Autobasket2.0
```

### 2. Backend setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r backend/requirements-dev.txt   # Windows: .venv\Scripts\python.exe
cp .env.example .env
```

Then update the environment values in .env as needed. `requirements-dev.txt` pulls in `requirements.txt` plus the linter; production images install only `requirements.txt`.

### 3. Create the database and run the API

```bash
cd backend
alembic upgrade head          # creates/updates the schema (SQLite by default)
uvicorn app.main:app --reload
```

For PostgreSQL (what production uses): `docker compose up -d db`, set `DATABASE_URL` in `.env` to
`postgresql+psycopg://autobasket:autobasket@localhost:5433/autobasket`, then run the same two commands.
(Host port 5433 avoids clashing with a locally installed PostgreSQL.)
Schema changes are always made through Alembic (`alembic revision --autogenerate -m "..."`); a test fails if the
models and migrations drift apart.

The API will be available at:

- http://localhost:8000/
- http://localhost:8000/docs for Swagger UI

### 4. Run the frontend

```bash
cd frontend
npm ci
cp .env.example .env.local   # set VITE_API_URL if the API is not on localhost:8000
npm run dev
```

The frontend will be available at http://localhost:5173.

## Logging in and the API

Authentication is email + 6-digit code. With `AUTH_DEV_MODE=1` the code is returned by the API instead of emailed:

```
POST /auth/request-otp  {"email": "you@example.com"}        -> {"dev_code": "123456"}
POST /auth/verify-otp   {"email": "...", "code": "123456"}  -> {"access_token": "..."}
GET  /auth/me                                                (Authorization: Bearer <token>)
```

Every other endpoint requires the bearer token and is scoped to the caller's household:
`/households/me`, `/households/me/slots`, `/inventory`, `/vendors/compare/{product}`, `/vendors/review`,
`/orders`, `/agent/chat`. `POST /seed/dev` loads 20 products, 3 vendors and a dev fridge (dev mode only).
Interactive docs: http://localhost:8000/docs.

## How "runs out on Thursday" is calculated

Every reading becomes an `inventory_event`. `services/consumption.py` learns each household's daily use of each
product from the last 30 days of events (drops are consumption, refills are skipped, jitter is ignored) and blends
it with a household-size guess until about a week of history exists. The UI shows which one it is
("Based on 14 days of use" vs "Estimated from household size"). An item needs reordering when it will not outlast
a delivery plus one day (`predictor.py`).

Predictions refresh on every reading and, for quiet households, from the background worker:

```bash
cd backend
python -m app.worker        # recomputes every 15 minutes
```

To demo learning without waiting a week, let the simulator post two weeks of history first:
`python edge/simulator.py --backfill-days 14`.

## What the camera does

Weights say *how much* is left; the camera says *what* it is. A photo of one shelf goes to an image-capable model
(any OpenAI-compatible endpoint: set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `VISION_MODEL` or `OPENAI_MODEL`)
with the catalog names and a strict "JSON, one entry per slot" prompt. Each answer is matched to the catalog and
stored in `vision_results` (only a hash of the photo is kept). The Shelves and Camera pages then show, per slot:

#### Choosing a vision provider

`.env.example` carries four ready blocks — NVIDIA NIM (demo), Google Gemini and Groq (free tiers for practice) and
OpenRouter. Uncomment exactly one, restart the API. All four use the same prompt and code, so practice results
predict demo results. Check any block with one photo:

```powershell
cd backend
..\.venv\Scripts\python.exe scriptsision_smoke.py path	o\shelf.jpg 4 "milk,eggs,butter,paneer"
```

#### Watching the camera live (developer page)

Set `VISION_DEBUG_DIR=some/folder` in `.env` (ignored in production), restart the API, and open
`http://localhost:8000/vision/debug` — in Antigravity / VS Code use *Simple Browser: Show*. The page shows the latest
photo with free in-browser detector boxes (COCO-SSD), the model's verdict per slot, live grams, and a **Snap now**
button that asks the board for a fresh photo. Photos land only in that folder, never in the database.

![Live camera viewer](docs/screenshots/vision-debug.png)

- **Camera and scale agree**: the model saw what you assigned.
- **Not assigned yet**: an empty slot with a recognised item, one tap assigns it.
- **Different from what's assigned**: someone put curd where milk was; one tap fixes the assignment.

Upload from a phone with `POST /vision/trays/{tray_id}/photo`, or from the fridge device with
`POST /vision/device/trays/{position}/photo` (Phase 8 sends one per shelf whenever a weight changes, and every 30 min). Without a key the
endpoint answers 503 with the variables to set; it never guesses. `docs/screenshots/phase-7-sample-shelf.jpg` is a
labelled test image the model reads correctly; a real fridge photo is the intended input.

## From alert to verified delivery

The background worker checks every household every 15 minutes. For each product that will not outlast a
delivery, it sends one **proposal**: "Milk runs out tomorrow" with the three best offers and Yes / Skip buttons.
The same proposal shows on the dashboard ("Needs your yes") and, when linked, in Telegram; answering on either
side answers both. `POST /notifications/propose` runs the check on demand.

Saying yes creates the order and moves it along this path:

| Seller | After "Yes" | Then |
|---|---|---|
| Kirana | `confirmed` with a payment link | `paid` (Razorpay webhook, or the dev page) → shop taps Accept → `accepted` → Delivered → `delivered` |
| Delivery app | `handoff` with a link into their app search | you finish there |

Both end as **`verified`** the moment the fridge reports that slot refilled (a reading at 60 % or more). After
delivery the household can give a one-tap star rating, which updates the shop's stars and its reliability score
(used by the ranking).

- **Telegram**: set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` and `TELEGRAM_WEBHOOK_SECRET`, point the bot's
  webhook at `https://<api>/telegram/webhook` with that secret, and users connect from Settings → Alerts on your
  phone. Without a token, alerts are in-app only.
- **Payments**: set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (test keys work) and `RAZORPAY_WEBHOOK_SECRET`, and
  point the webhook at `/payments/razorpay/webhook` for the `payment_link.paid` event. Without keys, the payment
  link opens `/pay/<order>` in the web app, a clearly labelled test page that only works in dev mode.
- **Installable**: the web app ships a manifest and a small service worker, so it installs on a phone like an app.
  Push notifications need HTTPS and arrive with deployment.

## How the top 3 are chosen

`GET /recommendations/milk` returns the three best places to buy milk for the signed-in household. The order is
computed, never guessed: each seller gets a score from five parts, all between 0 and 1.

| Part | How it is scored |
|---|---|
| Price | 1 for the cheapest offer, 0 for the dearest |
| Delivery time | Absolute decay: 10 min ≈ 0.6, 30 min ≈ 0.2, 2 hours ≈ 0 |
| Distance | 1 next door, 0 at 10 km or more (0.5 when either side has no GPS) |
| Rating | Stars out of 5 |
| Reliability | The shop's service score (updated by post-delivery ratings) |

The weights come from the household's **priority**, set on the Settings page: *balanced* (price 35 %, time 20 %,
distance/rating/reliability 15 % each), *price* (price 60 %) or *speed* (time 45 %). A kirana outside its own
delivery radius is dropped. Each result carries a one-line reason ("Cheapest, about 25 min"), produced from the
same numbers; the chat agent may reword it but cannot reorder it.

Prices come through `services/scout/`. Kirana prices are whatever the shop set in the portal. Blinkit, Zepto and
Instamart are real adapters with an empty fetch hook, because none of them offers a price API and scraping their
apps breaks constantly and violates their terms; plug in a feed and the rest works unchanged. Until then their
last known price is used and marked "price from earlier today" after 30 minutes. Every price change from any
source is kept in `price_snapshots`.

## Kirana shop portal

Local shops sell through the same app. A shopkeeper signs in with the same email code, opens **I run a shop**
(`/shop`), and fills in the shop's name, pincode, hours, delivery time and radius. Then:

- **Products**: type a price next to anything in the catalog and it is live for nearby homes immediately.
  Untick "In stock" to hide it without deleting the price. A CSV price list (`product,price,in_stock`) can be
  uploaded in one go; unknown product names are reported back, not silently dropped.
- **Orders**: a household's "Yes" lands here. The shop taps Accept, then Delivered (or "Can't do it").
  Order statuses move `proposed → confirmed → accepted → delivered → verified`; the API refuses illegal jumps.

The shop-side API lives under `/vendor/*` (`/vendor/shop`, `/vendor/catalog`, `/vendor/offers`,
`/vendor/offers/csv`, `/vendor/orders/{id}/accept|reject|deliver`) and is scoped to the shop owned by the caller.
The portal uses a turmeric accent so a shopkeeper always knows which side of the app they are on.

## Fridge devices and the simulator

Each fridge has a **device** (an ESP32-CAM plus an Arduino reading the load cells; see `edge/README.md`) that authenticates with its own token and posts load-cell readings:

```
GET  /devices/me                    slot layout (tray/slot positions, product, empty/full grams)
POST /devices/me/readings           {"readings":[{"tray":1,"slot":1,"weight_grams":565}]}
```

The API turns a weight into "milk is 50 % left" only for slots that have a product assigned **and** are
calibrated (Slots page → *Mark empty* / *Mark full*). Every raw reading is kept in `slot_readings`; every
inventory change is kept in `inventory_events`, which the predictor learns from.

Until the hardware arrives, `edge/simulator.py` plays the Pi — see `edge/README.md`. With the API running:

```powershell
$env:AB_DEVICE_TOKEN = "<token from Slots page → Add device, or /seed/dev>"
.venv\Scripts\python.exe edge\simulator.py --interval 3
```

![Dashboard](docs/screenshots/phase-2-dashboard.png)

## Deploying

The whole product runs from one command on a small VPS: Postgres, the API (migrations run on start), the
background worker, and Caddy serving the web app with automatic HTTPS and proxying `/api/*` to the API.

```bash
cp .env.production.example .env.production   # fill in the REQUIRED values
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

With `APP_ENV=production` the API refuses to start until dev mode is off, the JWT secret is random, the database
is PostgreSQL and SMTP is set (sign-in codes go out by email). The full 12-step runbook, including Telegram and
Razorpay webhooks, backups and updates, is in [docs/deploy.md](docs/deploy.md).

## Environment variables

See `.env.example` — every variable is documented there. The important ones:

- `DATABASE_URL` — SQLite by default, PostgreSQL in production
- `JWT_SECRET`, `AUTH_DEV_MODE` — login
- `LLM_PROVIDER`, `OPENAI_*`, `OLLAMA_MODEL` — chat agent; with nothing configured it falls back to keyword routing

## Testing and linting

These are exactly what CI runs (`.github/workflows/ci.yml`):

```bash
ruff check backend edge --config backend/pyproject.toml   # Python lint (auto-fix with --fix)
pytest backend/tests -q                                   # backend tests (SQLite, fast)
cd frontend && npm run lint                               # JavaScript lint
cd frontend && npm run build                              # production bundle
```

To also exercise the real database: `docker compose up -d db`, then
`AB_PG_URL=postgresql+psycopg://autobasket:autobasket@localhost:5433/autobasket pytest backend/tests/test_postgres_smoke.py`.

## Documentation

- `docs/superpowers/specs/` — design documents (start with the smart-fridge roadmap)
- `docs/superpowers/plans/` — per-phase implementation plans
- `docs/hardware/BOM.md` — hardware bill of materials
- `AGENT_SETUP.md` — running the LLM agent locally

## Contributing

Contributions are welcome. Please open an issue or submit a pull request with a clear summary of the change and relevant tests.

## License

This project is licensed under the MIT License.
