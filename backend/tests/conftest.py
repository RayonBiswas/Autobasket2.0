import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401  (registers every table on Base)
from app.database import Base  # noqa: E402


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app_client(monkeypatch, session_factory):
    """The full FastAPI app with the database swapped for the in-memory one, in dev auth mode."""
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    from app.core.config import get_settings

    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), session_factory
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def login():
    """login(client, email) -> JWT, using the dev-mode code echo."""

    def _login(client, email: str) -> str:
        code = client.post("/auth/request-otp", json={"email": email}).json()["dev_code"]
        return client.post("/auth/verify-otp", json={"email": email, "code": code}).json()["access_token"]

    return _login
