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

- Backend: FastAPI, SQLAlchemy, Pydantic, LangGraph-style agent orchestration
- Frontend: React, Vite, Axios
- Data: SQLite by default for local development
- AI: Ollama or OpenAI-compatible chat endpoints with a heuristic fallback

## Project structure

- backend/app: FastAPI application, database models, routes, and agent logic
- backend/tests: smoke and guardrail tests for the agent workflow
- frontend/src: React pages and UI components

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

## Fridge devices and the simulator

Each fridge has a **device** (a Raspberry Pi) that authenticates with its own token and posts load-cell readings:

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
