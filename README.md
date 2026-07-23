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

- Python 3.10+
- Node.js 18+
- Optional: Ollama for local LLM-backed agent mode

### 1. Clone and enter the repository

```bash
git clone https://github.com/RayonBiswas/Autobasket2.0.git
cd Autobasket2.0
```

### 2. Backend setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cp .env.example .env
```

Then update the environment values in .env as needed.

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
npm install
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

If no remote model is configured, the agent falls back to local heuristic routing for demos and testing.

## Testing

Run the backend test suite:

```bash
pytest backend/tests -q
```

Run the frontend build:

```bash
cd frontend && npm run build
```

## Contributing

Contributions are welcome. Please open an issue or submit a pull request with a clear summary of the change and relevant tests.

## License

This project is licensed under the MIT License.
