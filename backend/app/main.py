import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from . import models
from .routes import items, vendors, intelligence, vision, orders, household, seed, agent


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

# Create tables
models.Base.metadata.create_all(bind=engine)

# Create app FIRST
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers AFTER app exists
app.include_router(items.router, prefix="/items", tags=["Items"])
app.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
app.include_router(intelligence.router, prefix="/intelligence", tags=["AI"])
app.include_router(vision.router, prefix="/vision", tags=["Vision"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(household.router, prefix="/household", tags=["Household"])
app.include_router(seed.router, prefix="/seed", tags=["Seed"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])

@app.get("/")
def root():
    return {"message": "AutoBasket 2.0 Running"}