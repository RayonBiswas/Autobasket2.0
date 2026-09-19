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

### 3. Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

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

## Environment variables

A sample file is provided in .env.example. The most relevant settings are:

- LLM_PROVIDER=ollama or openai
- OPENAI_API_KEY=your_key_here
- OPENAI_MODEL=gpt-4o-mini
- OPENAI_BASE_URL=https://api.openai.com/v1
- OLLAMA_MODEL=lfm2.5:8b-toolfix
- DATABASE_URL=sqlite:///./autobasket.db (default; PostgreSQL URL in production)

If no remote model is configured, the agent falls back to local heuristic routing for demos and testing.

## Testing and linting

These are exactly what CI runs (`.github/workflows/ci.yml`):

```bash
ruff check backend            # Python lint (auto-fix with --fix)
pytest backend/tests -q       # backend tests
cd frontend && npm run lint   # JavaScript lint
cd frontend && npm run build  # production bundle
```

## Documentation

- `docs/superpowers/specs/` — design documents (start with the smart-fridge roadmap)
- `docs/superpowers/plans/` — per-phase implementation plans
- `docs/hardware/BOM.md` — hardware bill of materials
- `AGENT_SETUP.md` — running the LLM agent locally

## Contributing

Contributions are welcome. Please open an issue or submit a pull request with a clear summary of the change and relevant tests.

## License

This project is licensed under the MIT License.
