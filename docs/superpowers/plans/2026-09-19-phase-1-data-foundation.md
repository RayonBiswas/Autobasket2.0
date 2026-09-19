# Phase 1 — Data Foundation + Auth: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five toy tables with the 14-table production schema, add email-OTP login with household scoping, and rewire the existing endpoints and chat agent onto the new schema — with the frontend still working.

**Architecture:** SQLAlchemy 2.0 typed models split by domain under `app/models/`, one `Base` in `app/database.py`, Alembic migrations, pydantic-settings config, JWT auth dependency that yields the caller's `Household`. Routes are thin; logic lives in `app/services/` and `app/agent/tools.py`. Tests use an in-memory SQLite created from the models, plus one test that upgrades a temp DB with Alembic and diffs it against the models.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, pydantic-settings, PyJWT, pytest, React/Vite.

**Spec:** `docs/superpowers/specs/2026-09-19-phase-1-data-foundation-design.md` (schema §3, auth §4, rewiring §5, files §7, done-when §8).

## Global Constraints

- Python 3.12, `.venv\Scripts\python.exe`; run tests as `.venv\Scripts\python.exe -m pytest backend/tests -q` from repo root; lint with `ruff check backend`.
- Every table has `household_id` scoping where the spec says so; every protected route uses `current_household`.
- Timestamps: `DateTime(timezone=True)`, default `utcnow()` from `app.models.base`.
- Enums stored as short strings; Python `StrEnum` classes in `app/models/enums.py`.
- Existing 8 tests must pass at the end of every task that touches their code paths (fixtures may be updated, assertions may not be weakened).
- Ask before deleting anything not listed in this plan. Commits end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: Settings + database core

**Files:**
- Create: `backend/app/core/__init__.py` (empty), `backend/app/core/config.py`
- Modify: `backend/app/database.py`, `backend/requirements.txt`
- Test: `backend/tests/test_database_config.py` (extend)

**Interfaces:**
- Produces: `app.core.config.get_settings() -> Settings` with fields `database_url`, `jwt_secret`, `jwt_expires_hours`, `auth_dev_mode`, `otp_ttl_minutes`; `app.database.Base` (DeclarativeBase), `engine`, `SessionLocal`, `get_db()`, `get_database_url()`.

- [ ] **Step 1: Add deps** to `backend/requirements.txt`:
```
pydantic-settings>=2.4.0
alembic>=1.13.0
psycopg[binary]>=3.2.0
PyJWT>=2.9.0
```
Install: `uv pip install --python .venv\Scripts\python.exe -r backend\requirements-dev.txt`

- [ ] **Step 2: Extend the test** — append to `backend/tests/test_database_config.py`:
```python
def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "abc")
    monkeypatch.setenv("AUTH_DEV_MODE", "0")
    from app.core.config import Settings
    s = Settings()
    assert s.jwt_secret == "abc"
    assert s.auth_dev_mode is False
    assert s.jwt_expires_hours == 24
```
Run: `.venv\Scripts\python.exe -m pytest backend/tests/test_database_config.py -q` → FAIL (`No module named app.core`).

- [ ] **Step 3: Implement** `backend/app/core/config.py`:
```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All runtime configuration. Values come from the environment, then repo-root .env."""

    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./autobasket.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expires_hours: int = 24
    auth_dev_mode: bool = True
    otp_ttl_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
```
Rewrite `backend/app/database.py`:
```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .core.config import Settings


class Base(DeclarativeBase):
    """Single declarative base for every model (see app/models)."""


def get_database_url() -> str:
    """DATABASE_URL from the environment / .env, else the local SQLite file."""
    return Settings().database_url


DATABASE_URL = get_database_url()

# check_same_thread is a SQLite-only flag; other drivers reject it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
Note: `test_default_is_local_sqlite` must also clear any `.env` influence — in that test add `monkeypatch.setattr("app.core.config.Settings.model_config", {**Settings.model_config, "env_file": None})` is overkill; instead the test sets `monkeypatch.setenv("DATABASE_URL", "sqlite:///./autobasket.db")` is a tautology. Keep the original test but make it robust: assert the *default field* — `Settings.model_fields["database_url"].default == "sqlite:///./autobasket.db"`.

- [ ] **Step 4: Run** `pytest backend/tests/test_database_config.py -q` → 3 passed; full suite still 8 passed (models still import old `Base` from `models.py` — that changes in Task 2).
- [ ] **Step 5: Commit** `feat(core): pydantic-settings config and single declarative Base`.

---

### Task 2: Models package + shared test fixtures

**Files:**
- Create: `backend/app/models/__init__.py`, `base.py`, `enums.py`, `auth.py`, `device.py`, `catalog.py`, `inventory.py`, `orders.py`
- Delete: `backend/app/models.py`, `backend/app/schemas.py` (replaced per-router)
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: the 14 ORM classes named exactly as in the spec §3 (`User, OtpCode, Household, HouseholdMember, Device, Tray, Slot, Product, InventoryEvent, InventoryState, Vendor, VendorOffer, Order, OrderItem`), all importable from `app.models`; enums `UserRole, MemberRole, ProductUnit, EventSource, StockStatus, VendorKind, OfferSource, OrderStatus, OrderChannel`; fixture `db_session` (in-memory SQLite, tables created).

- [ ] **Step 1: Write the failing test** `backend/tests/test_models.py`:
```python
from sqlalchemy import inspect

from app import models
from app.database import Base

EXPECTED = {
    "users", "otp_codes", "households", "household_members", "devices", "trays", "slots",
    "products", "inventory_events", "inventory_state", "vendors", "vendor_offers", "orders", "order_items",
}


def test_all_fourteen_tables_exist(db_session):
    names = set(inspect(db_session.get_bind()).get_table_names())
    assert EXPECTED <= names


def test_metadata_has_exactly_expected_tables():
    assert set(Base.metadata.tables) == EXPECTED


def test_household_member_roundtrip(db_session):
    user = models.User(email="a@b.c")
    home = models.Household(name="Home")
    db_session.add_all([user, home])
    db_session.flush()
    db_session.add(models.HouseholdMember(user_id=user.id, household_id=home.id, role=models.MemberRole.OWNER))
    db_session.commit()
    assert db_session.get(models.Household, home.id).members[0].user.email == "a@b.c"
```
And `backend/tests/conftest.py`:
```python
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  (registers tables on Base)


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
```
Run → FAIL (`app.models` has no attribute `MemberRole` / import errors).

- [ ] **Step 2: Implement models.** `base.py`:
```python
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def ts_column(**kw):
    """Timezone-aware timestamp column defaulting to now (UTC)."""
    return mapped_column(DateTime(timezone=True), default=utcnow, **kw)
```
`enums.py`:
```python
from enum import StrEnum


class UserRole(StrEnum):
    HOUSEHOLD = "household"; VENDOR = "vendor"; ADMIN = "admin"

class MemberRole(StrEnum):
    OWNER = "owner"; MEMBER = "member"

class ProductUnit(StrEnum):
    G = "g"; ML = "ml"; PCS = "pcs"

class EventSource(StrEnum):
    WEIGHT = "weight"; VISION = "vision"; MANUAL = "manual"; ORDER = "order"

class StockStatus(StrEnum):
    SAFE = "safe"; WARNING = "warning"; CRITICAL = "critical"; UNKNOWN = "unknown"

class VendorKind(StrEnum):
    KIRANA = "kirana"; PLATFORM = "platform"

class OfferSource(StrEnum):
    PORTAL = "portal"; SCRAPER = "scraper"; SEED = "seed"

class OrderStatus(StrEnum):
    PROPOSED = "proposed"; PENDING_CONFIRMATION = "pending_confirmation"; CONFIRMED = "confirmed"
    PAID = "paid"; ACCEPTED = "accepted"; DELIVERING = "delivering"; DELIVERED = "delivered"
    VERIFIED = "verified"; HANDOFF = "handoff"; CANCELLED = "cancelled"

class OrderChannel(StrEnum):
    KIRANA = "kirana"; HANDOFF = "handoff"
```
(Write one member per line in the real file — ruff E702 forbids `;`.)

`auth.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column
from .enums import MemberRole, UserRole


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.HOUSEHOLD)
    created_at: Mapped[datetime] = ts_column()
    memberships: Mapped[list["HouseholdMember"]] = relationship(back_populates="user")


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = ts_column()


class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    pincode: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    adults: Mapped[int] = mapped_column(default=2)
    children: Mapped[int] = mapped_column(default=1)
    food_habit: Mapped[str] = mapped_column(String(16), default="mixed")
    created_at: Mapped[datetime] = ts_column()
    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household")


class HouseholdMember(Base):
    __tablename__ = "household_members"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default=MemberRole.MEMBER)
    user: Mapped["User"] = relationship(back_populates="memberships")
    household: Mapped["Household"] = relationship(back_populates="members")
```
`device.py`:
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = ts_column()
    trays: Mapped[list["Tray"]] = relationship(back_populates="device", order_by="Tray.position")


class Tray(Base):
    __tablename__ = "trays"
    __table_args__ = (UniqueConstraint("device_id", "position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    position: Mapped[int]
    label: Mapped[str | None] = mapped_column(String(60))
    device: Mapped["Device"] = relationship(back_populates="trays")
    slots: Mapped[list["Slot"]] = relationship(back_populates="tray", order_by="Slot.position")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("tray_id", "position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tray_id: Mapped[int] = mapped_column(ForeignKey("trays.id"), index=True)
    position: Mapped[int]
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    tare_grams: Mapped[float | None]
    full_grams: Mapped[float | None]
    tray: Mapped["Tray"] = relationship(back_populates="slots")
```
`catalog.py`:
```python
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column
from .enums import OfferSource, VendorKind


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("name", "brand", "pack_size"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    brand: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    unit: Mapped[str] = mapped_column(String(8))
    pack_size: Mapped[float]
    typical_full_grams: Mapped[float | None]
    created_at: Mapped[datetime] = ts_column()


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=VendorKind.KIRANA)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pincode: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    rating: Mapped[float] = mapped_column(default=4.0)
    review_count: Mapped[int] = mapped_column(default=0)
    service_score: Mapped[float] = mapped_column(default=0.5)
    eta_minutes: Mapped[int | None]
    delivery_radius_km: Mapped[float | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = ts_column()
    offers: Mapped[list["VendorOffer"]] = relationship(back_populates="vendor")


class VendorOffer(Base):
    __tablename__ = "vendor_offers"
    __table_args__ = (UniqueConstraint("vendor_id", "product_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[float]
    in_stock: Mapped[bool] = mapped_column(default=True)
    eta_minutes: Mapped[int | None]
    source: Mapped[str] = mapped_column(String(16), default=OfferSource.PORTAL)
    fetched_at: Mapped[datetime] = ts_column()
    vendor: Mapped["Vendor"] = relationship(back_populates="offers")
    product: Mapped["Product"] = relationship()
```
`inventory.py`:
```python
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column, utcnow
from .enums import EventSource, StockStatus


class InventoryEvent(Base):
    __tablename__ = "inventory_events"
    __table_args__ = (Index("ix_inventory_events_hh_prod_time", "household_id", "product_id", "recorded_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"))
    source: Mapped[str] = mapped_column(String(16), default=EventSource.MANUAL)
    weight_grams: Mapped[float | None]
    remaining_fraction: Mapped[float]
    recorded_at: Mapped[datetime] = ts_column()


class InventoryState(Base):
    __tablename__ = "inventory_state"
    __table_args__ = (UniqueConstraint("household_id", "product_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    remaining_fraction: Mapped[float] = mapped_column(default=1.0)
    daily_rate: Mapped[float | None]
    days_left: Mapped[float | None]
    status: Mapped[str] = mapped_column(String(16), default=StockStatus.UNKNOWN)
    updated_at: Mapped[datetime] = ts_column(onupdate=utcnow)
    product: Mapped["Product"] = relationship()
```
`orders.py`:
```python
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column, utcnow
from .enums import OrderChannel, OrderStatus


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    status: Mapped[str] = mapped_column(String(24), default=OrderStatus.PROPOSED)
    channel: Mapped[str] = mapped_column(String(16), default=OrderChannel.KIRANA)
    total_amount: Mapped[float] = mapped_column(default=0.0)
    payment_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = ts_column()
    updated_at: Mapped[datetime] = ts_column(onupdate=utcnow)
    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[float] = mapped_column(default=1.0)
    unit_price: Mapped[float]
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
```
`__init__.py` re-exports every class and enum (`from .auth import ...` etc., plus `__all__`).

- [ ] **Step 3: Delete** `backend/app/models.py` and `backend/app/schemas.py` (`git rm`). The old routes/tools now fail to import — expected until Tasks 5–8. Temporarily the full suite is red; `test_models.py` and `test_database_config.py` must be green: run `pytest backend/tests/test_models.py backend/tests/test_database_config.py -q` → 6 passed.
- [ ] **Step 4: Commit** `feat(models): 14-table schema as typed SQLAlchemy 2.0 models`.

---

### Task 3: Alembic + migration-vs-models test

**Files:**
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_migrations.py`

- [ ] **Step 1: Failing test**:
```python
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.database import Base

BACKEND = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url)
    assert "inventory_state" in inspect(engine).get_table_names()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"
```
Run → FAIL (no alembic.ini).

- [ ] **Step 2: Init Alembic.** Run from `backend/`: `..\.venv\Scripts\python.exe -m alembic init alembic`. Then replace `alembic/env.py` with:
```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  registers all tables
from app.database import Base, get_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# CLI usage reads DATABASE_URL; tests override sqlalchemy.url explicitly.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```
In `alembic.ini` set `sqlalchemy.url =` (empty) and `prepend_sys_path = .`.

- [ ] **Step 3: Generate the initial migration** from `backend/`: `..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial schema" --rev-id 0001`. Open `alembic/versions/0001_initial_schema.py`, confirm 14 `create_table` calls, no `drop_table`.
- [ ] **Step 4: Run** `pytest backend/tests/test_migrations.py -q` → 1 passed. Add `backend/alembic/versions/*.db` nothing; ensure `*.db` already ignored.
- [ ] **Step 5: Commit** `feat(db): alembic migrations with initial schema and drift test`.

---

### Task 4: Security helpers + auth routes + deps

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/api/__init__.py`, `backend/app/api/deps.py`, `backend/app/routes/auth.py`
- Test: `backend/tests/test_auth.py`; extend `conftest.py` with `app_client`

**Interfaces:**
- Produces: `security.hash_otp(email, code) -> str`, `security.create_access_token(user_id, household_id) -> str`, `security.decode_access_token(token) -> dict`; deps `get_db`, `current_user(...) -> User`, `current_household(...) -> Household`, `current_device(...) -> Device`; router `auth.router` with `/request-otp`, `/verify-otp`, `/me`.
- conftest fixture `app_client(monkeypatch, session_factory)` → `(TestClient, session_factory)` with the **full** `app.main:app` and `get_db` overridden; helper `login(client, email) -> token` that calls request-otp (dev mode) and verify-otp.

- [ ] **Step 1: Failing tests** `backend/tests/test_auth.py`:
```python
def test_request_otp_returns_dev_code(app_client):
    client, _ = app_client
    r = client.post("/auth/request-otp", json={"email": "a@b.c"})
    assert r.status_code == 200
    assert len(r.json()["dev_code"]) == 6


def test_verify_creates_user_and_household(app_client, login):
    client, factory = app_client
    token = login(client, "new@user.io")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["user"]["email"] == "new@user.io"
    assert me["household"]["name"].startswith("new@user.io")
    assert me["memberships"][0]["role"] == "owner"


def test_wrong_code_rejected(app_client):
    client, _ = app_client
    client.post("/auth/request-otp", json={"email": "x@y.z"})
    r = client.post("/auth/verify-otp", json={"email": "x@y.z", "code": "000000"})
    assert r.status_code == 401


def test_protected_route_requires_token(app_client):
    client, _ = app_client
    assert client.get("/auth/me").status_code == 401


def test_sixth_otp_request_in_window_is_throttled(app_client):
    client, _ = app_client
    for _ in range(5):
        assert client.post("/auth/request-otp", json={"email": "t@t.t"}).status_code == 200
    assert client.post("/auth/request-otp", json={"email": "t@t.t"}).status_code == 429
```
conftest additions:
```python
@pytest.fixture()
def app_client(monkeypatch, session_factory):
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    from app.core.config import get_settings
    get_settings.cache_clear()
    from fastapi.testclient import TestClient
    from app.api.deps import get_db
    from app.main import app

    def override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), session_factory
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def login():
    def _login(client, email: str) -> str:
        code = client.post("/auth/request-otp", json={"email": email}).json()["dev_code"]
        return client.post("/auth/verify-otp", json={"email": email, "code": code}).json()["access_token"]
    return _login
```
(`app.main` must import cleanly by the end of this task: temporarily stub the old routers out of `main.py` — Task 8 restores the full list. Do it now: `main.py` includes only `auth` and `vision`.)

- [ ] **Step 2: Implement** `core/security.py`:
```python
import hashlib
from datetime import UTC, datetime, timedelta

import jwt

from .config import get_settings


def hash_otp(email: str, code: str) -> str:
    secret = get_settings().jwt_secret
    return hashlib.sha256(f"{email.lower()}:{code}:{secret}".encode()).hexdigest()


def create_access_token(user_id: int, household_id: int) -> str:
    s = get_settings()
    payload = {"sub": str(user_id), "hid": household_id, "exp": datetime.now(UTC) + timedelta(hours=s.jwt_expires_hours)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
```
`api/deps.py`:
```python
import hashlib

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..core.security import decode_access_token
from ..database import get_db

bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> models.User:
    if creds is None:
        raise _unauthorized()
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc
    user = db.get(models.User, int(payload["sub"]))
    if user is None:
        raise _unauthorized("Unknown user")
    return user


def current_household(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> models.Household:
    user = current_user(creds, db)
    payload = decode_access_token(creds.credentials)
    membership = db.get(models.HouseholdMember, (user.id, payload["hid"]))
    if membership is None:
        raise _unauthorized("Not a member of this household")
    return membership.household


def current_device(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> models.Device:
    if creds is None:
        raise _unauthorized()
    token_hash = hashlib.sha256(creds.credentials.encode()).hexdigest()
    device = db.query(models.Device).filter(models.Device.token_hash == token_hash).first()
    if device is None:
        raise _unauthorized("Unknown device")
    return device


__all__ = ["get_db", "current_user", "current_household", "current_device"]
```
`routes/auth.py`:
```python
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, current_user, get_db
from ..core.config import get_settings
from ..core.security import create_access_token, hash_otp

router = APIRouter()
OTP_WINDOW = timedelta(minutes=10)
OTP_MAX_PER_WINDOW = 5


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    code: str


def send_otp(email: str, code: str) -> None:
    """Delivery hook. Dev mode logs it; Phase 6 wires email/SMS here."""
    print(f"[auth] OTP for {email}: {code}")


@router.post("/request-otp")
def request_otp(body: OtpRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    email = body.email.lower()
    now = datetime.now(UTC)
    recent = db.query(models.OtpCode).filter(models.OtpCode.email == email, models.OtpCode.created_at >= now - OTP_WINDOW).count()
    if recent >= OTP_MAX_PER_WINDOW:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested; try again later")
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(models.OtpCode(email=email, code_hash=hash_otp(email, code), expires_at=now + timedelta(minutes=settings.otp_ttl_minutes)))
    db.commit()
    send_otp(email, code)
    if settings.auth_dev_mode:
        return {"dev_code": code}
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify-otp")
def verify_otp(body: OtpVerify, db: Session = Depends(get_db)):
    email = body.email.lower()
    now = datetime.now(UTC)
    candidate = (db.query(models.OtpCode)
                 .filter(models.OtpCode.email == email, models.OtpCode.consumed_at.is_(None))
                 .order_by(models.OtpCode.id.desc()).first())
    if candidate is None or candidate.expires_at.replace(tzinfo=UTC) < now or candidate.code_hash != hash_otp(email, body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
    candidate.consumed_at = now

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(email=email)
        household = models.Household(name=f"{email}'s home")
        db.add_all([user, household])
        db.flush()
        db.add(models.HouseholdMember(user_id=user.id, household_id=household.id, role=models.MemberRole.OWNER))
    else:
        household = user.memberships[0].household
    db.commit()
    return {
        "access_token": create_access_token(user.id, household.id),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "household": {"id": household.id, "name": household.name},
    }


@router.get("/me")
def me(user: models.User = Depends(current_user), household: models.Household = Depends(current_household)):
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "household": {"id": household.id, "name": household.name, "adults": household.adults, "children": household.children, "food_habit": household.food_habit, "pincode": household.pincode},
        "memberships": [{"household_id": m.household_id, "role": m.role} for m in user.memberships],
    }
```
Add `email-validator>=2.0.0` to requirements (needed by `EmailStr`). Note on SQLite: `expires_at` comes back naive → the `.replace(tzinfo=UTC)` above; on Postgres it is already aware and `replace` is a no-op in value.

- [ ] **Step 3: Run** `pytest backend/tests/test_auth.py -q` → 5 passed.
- [ ] **Step 4: Commit** `feat(auth): email OTP login, JWT, household-scoped dependencies`.

---

### Task 5: Households, inventory, seed routes

**Files:**
- Create: `backend/app/routes/households.py`, `backend/app/routes/inventory.py`; rewrite `backend/app/routes/seed.py`; modify `backend/app/services/predictor.py`
- Delete: `backend/app/routes/items.py`, `intelligence.py`, `household.py`; empty `routes/__init__.py`
- Test: `backend/tests/test_inventory.py`

**Interfaces:**
- Produces: `GET/PATCH /households/me`, `GET /households/me/slots`; `GET /inventory`, `PUT /inventory/{product_id}` body `{remaining_fraction}`; `POST /seed/dev` (dev mode only, authed) returning `{products, vendors, device_token}`; `predictor.predict_state(state: InventoryState, product: Product, household: Household) -> {"days_left","status","estimated_daily_usage"}`; `services.inventory.set_remaining(db, household_id, product_id, fraction, source, slot_id=None) -> InventoryState` (creates state + event).

- [ ] **Step 1: Failing tests**:
```python
def test_seed_then_inventory_and_slots(app_client, login):
    client, _ = app_client
    h = {"Authorization": f"Bearer {login(client, 'seed@x.y')}"}
    seeded = client.post("/seed/dev", headers=h).json()
    assert seeded["products"] >= 20 and seeded["vendors"] == 3 and len(seeded["device_token"]) > 20

    inv = client.get("/inventory", headers=h).json()["inventory"]
    assert {row["name"] for row in inv} >= {"milk", "rice", "water"}
    assert all(row["status"] in {"safe", "warning", "critical", "unknown"} for row in inv)

    slots = client.get("/households/me/slots", headers=h).json()["trays"]
    assert len(slots) == 2 and all(len(t["slots"]) == 4 for t in slots)


def test_manual_update_creates_event(app_client, login):
    client, factory = app_client
    h = {"Authorization": f"Bearer {login(client, 'm@x.y')}"}
    client.post("/seed/dev", headers=h)
    milk = next(r for r in client.get("/inventory", headers=h).json()["inventory"] if r["name"] == "milk")
    r = client.put(f"/inventory/{milk['product_id']}", json={"remaining_fraction": 0.1}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "critical"
    from app import models
    with factory() as s:
        assert s.query(models.InventoryEvent).filter_by(product_id=milk["product_id"]).count() >= 1


def test_household_settings_patch(app_client, login):
    client, _ = app_client
    h = {"Authorization": f"Bearer {login(client, 'p@x.y')}"}
    r = client.patch("/households/me", json={"adults": 3, "children": 0, "food_habit": "veg", "pincode": "560001"}, headers=h)
    assert r.json()["adults"] == 3 and r.json()["pincode"] == "560001"
```
- [ ] **Step 2: Implement.** `services/inventory.py`:
```python
from sqlalchemy.orm import Session

from .. import models
from .predictor import predict_state


def get_or_create_state(db: Session, household_id: int, product_id: int) -> models.InventoryState:
    state = db.query(models.InventoryState).filter_by(household_id=household_id, product_id=product_id).first()
    if state is None:
        state = models.InventoryState(household_id=household_id, product_id=product_id, remaining_fraction=1.0)
        db.add(state)
        db.flush()
    return state


def set_remaining(db: Session, household: models.Household, product_id: int, fraction: float,
                  source: str = models.EventSource.MANUAL, slot_id: int | None = None) -> models.InventoryState:
    fraction = max(0.0, min(1.0, fraction))
    state = get_or_create_state(db, household.id, product_id)
    state.remaining_fraction = fraction
    db.add(models.InventoryEvent(household_id=household.id, product_id=product_id, slot_id=slot_id,
                                 source=source, remaining_fraction=fraction))
    product = db.get(models.Product, product_id)
    pred = predict_state(state, product, household)
    state.days_left, state.status, state.daily_rate = pred["days_left"], pred["status"], pred["estimated_daily_usage"]
    db.commit()
    db.refresh(state)
    return state


def state_row(state: models.InventoryState, product: models.Product, household: models.Household) -> dict:
    pred = predict_state(state, product, household)
    return {
        "product_id": product.id, "name": product.name, "brand": product.brand, "unit": product.unit,
        "pack_size": product.pack_size, "remaining_fraction": state.remaining_fraction,
        "remaining_qty": round(state.remaining_fraction * product.pack_size, 2),
        "days_left": pred["days_left"], "status": pred["status"], "estimated_daily_usage": pred["estimated_daily_usage"],
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }
```
`predictor.py` — keep `estimate_daily_usage(item_name, household)` as-is (units per day in the product's `unit`, e.g. litres → we treat pack units); replace `predict_status` with:
```python
def predict_state(state, product, household) -> dict:
    """Phase-1 predictor: household prior only. Phase 3 replaces with learned rates."""
    daily = state.daily_rate or estimate_daily_usage(product.name, household)
    remaining = state.remaining_fraction * product.pack_size
    days_left = remaining / daily if daily > 0 else 999
    if days_left > 5:
        status = "safe"
    elif days_left > 2:
        status = "warning"
    else:
        status = "critical"
    return {"days_left": round(days_left, 2), "status": status, "estimated_daily_usage": round(daily, 2)}
```
(`estimate_daily_usage` table is keyed by bare names — `milk`, `rice`, `water`, `wheat`, `dal`; pack_size for seed uses the same unit, e.g. milk pack_size 1.0 L → 1 unit.) Change the "water" base to litres consistently: keep as is.

`routes/households.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db

router = APIRouter()


class HouseholdPatch(BaseModel):
    name: str | None = None
    pincode: str | None = None
    adults: int | None = None
    children: int | None = None
    food_habit: str | None = None


def _dump(h: models.Household) -> dict:
    return {"id": h.id, "name": h.name, "pincode": h.pincode, "adults": h.adults, "children": h.children, "food_habit": h.food_habit}


@router.get("/me")
def get_me(household: models.Household = Depends(current_household)):
    return _dump(household)


@router.patch("/me")
def patch_me(body: HouseholdPatch, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(household, field, value)
    db.commit()
    return _dump(household)


@router.get("/me/slots")
def slots(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    devices = db.query(models.Device).filter_by(household_id=household.id).all()
    trays = []
    for d in devices:
        for t in d.trays:
            trays.append({"device": d.name, "tray_id": t.id, "position": t.position, "label": t.label,
                          "slots": [{"slot_id": s.id, "position": s.position, "product_id": s.product_id,
                                     "tare_grams": s.tare_grams, "full_grams": s.full_grams} for s in t.slots]})
    return {"trays": trays}
```
`routes/inventory.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services.inventory import set_remaining, state_row

router = APIRouter()


class RemainingUpdate(BaseModel):
    remaining_fraction: float = Field(ge=0, le=1)


@router.get("")
def list_inventory(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    rows = (db.query(models.InventoryState, models.Product)
              .join(models.Product, models.Product.id == models.InventoryState.product_id)
              .filter(models.InventoryState.household_id == household.id).all())
    return {"inventory": [state_row(s, p, household) for s, p in rows]}


@router.put("/{product_id}")
def update_inventory(product_id: int, body: RemainingUpdate, household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    state = set_remaining(db, household, product_id, body.remaining_fraction)
    return state_row(state, product, household)
```
`routes/seed.py` (dev only): creates 20 products (milk 1 L, curd 400 g, paneer 200 g, eggs 12 pcs, butter 100 g, cheese 200 g, rice 5 kg→pack 5 unit kg, wheat 5, dal 1, water 20 L, tomato 1 kg, onion 1, potato 1, coriander 100 g, apple 1, banana 12 pcs, bread 400 g, juice 1 L, ketchup 500 g, cola 1.25 L), 3 vendors (Local Kirana kirana rating 4.2 eta 25; Blinkit platform 4.8 eta 12; BigBasket platform 4.5 eta 120), offers for every product with prices from a small table, a device "Dev Fridge" (random token, hash stored) with 2 trays × 4 slots, and inventory state for milk/rice/water at 0.5/0.25/0.9. Returns counts + the raw device token. 403 unless `auth_dev_mode`. Idempotent: skips products/vendors that already exist by name.

- [ ] **Step 3: Delete** `items.py`, `intelligence.py`, `household.py` (`git rm`); make `routes/__init__.py` empty. Mount `auth, households, inventory, seed, vision` in `main.py` (vendors/orders/agent come in Tasks 6–7).
- [ ] **Step 4: Run** `pytest backend/tests/test_inventory.py -q` → 3 passed. **Commit** `feat(api): households, inventory, dev seed on the new schema`.

---

### Task 6: Vendors compare/review + ranking service

**Files:**
- Create: `backend/app/services/ranking.py`; rewrite `backend/app/routes/vendors.py`
- Delete: `backend/app/services/vendor_engine.py`
- Test: `backend/tests/test_vendors.py`

**Interfaces:**
- Produces: `ranking.rank_offers(pairs: list[tuple[Vendor, VendorOffer]]) -> list[dict]` (fields `vendor_id, vendor_name, vendor_kind, rating, price, eta_minutes, price_score, rating_score, final_score, recommendation`); `GET /vendors/compare/{product_name}`, `POST /vendors/review?vendor_id&new_rating`.

- [ ] **Step 1: Tests**:
```python
def test_rank_offers_prefers_cheap_and_well_rated():
    from app import models
    from app.services.ranking import rank_offers
    a = models.Vendor(id=1, name="A", rating=4.0); b = models.Vendor(id=2, name="B", rating=5.0)
    pairs = [(a, models.VendorOffer(vendor_id=1, product_id=1, price=30)), (b, models.VendorOffer(vendor_id=2, product_id=1, price=30))]
    ranked = rank_offers(pairs)
    assert [r["vendor_name"] for r in ranked] == ["B", "A"]
    assert ranked[0]["final_score"] > ranked[1]["final_score"]


def test_compare_endpoint_shape(app_client, login):
    client, _ = app_client
    h = {"Authorization": f"Bearer {login(client, 'v@x.y')}"}
    client.post("/seed/dev", headers=h)
    rows = client.get("/vendors/compare/milk", headers=h).json()
    assert len(rows) == 3
    assert {"vendor_id", "vendor_name", "rating", "price", "final_score"} <= set(rows[0])
    assert rows == sorted(rows, key=lambda r: r["final_score"], reverse=True)


def test_review_updates_running_average(app_client, login):
    client, _ = app_client
    h = {"Authorization": f"Bearer {login(client, 'r@x.y')}"}
    client.post("/seed/dev", headers=h)
    vid = client.get("/vendors/compare/milk", headers=h).json()[0]["vendor_id"]
    r = client.post("/vendors/review", params={"vendor_id": vid, "new_rating": 1}, headers=h).json()
    assert r["new_rating"] < r["old_rating"] and r["total_reviews"] >= 1
```
- [ ] **Step 2: Implement** `ranking.py` (same 0.4 price / 0.6 rating formula as today, single place) and `vendors.py` (looks up product by `ilike(name)`, joins active vendors' in-stock offers, calls `rank_offers`; review does the running average and bumps `review_count`). Both require `current_household`.
- [ ] **Step 3: Run** → 3 passed. **Commit** `feat(vendors): compare and review on vendor_offers with shared ranking service`.

---

### Task 7: Orders route + agent tools on the new schema

**Files:**
- Rewrite: `backend/app/routes/orders.py`, `backend/app/agent/tools.py`, `backend/app/routes/agent.py`; modify `backend/app/agent/orchestrator.py` (thread `household` through), `backend/app/agent/prompts.py` (say "database", not "SQLite")
- Update tests: `test_agent_guardrail.py`, `test_agent_smoke.py`, `test_shopping_list.py`
- Test: `backend/tests/test_orders.py`

**Interfaces:**
- Produces: `GET /orders`, `POST /orders` body `{vendor_id, items:[{product_id, qty}]}` → order `proposed` with prices from offers; tools signatures become `fn(..., db, household)`; `run_agent_chat(user_message, session_id, db, household) -> str`; `POST /agent/chat` requires JWT and namespaces memory as `f"{household.id}:{session_id}"`.

- [ ] **Step 1: Tests.** `test_orders.py`: create via API after seed → status `proposed`, total = sum(qty × offer price); list returns it with item names. Update the three existing agent tests to build data with the new models (Product `rice` pack_size 20, InventoryState remaining 0.25, Vendor `FreshMart` kirana, VendorOffer price 80) and to pass a `Household` to tools; smoke test overrides `current_household` with a fixture household and mounts `agent.router` on a bare app as before.
- [ ] **Step 2: Implement** tools: `get_pantry_status(db, household)` (join state+product, `state_row`), `get_vendors(db)`, `compare_prices(name, db, household)` (reuse `rank_offers`), `place_pantry_order(name, vendor_name, db, household)` (offer price; `> 50 → pending_confirmation`; on confirmed → `set_remaining(..., 1.0, source=ORDER)`; `channel` from vendor kind), `confirm_pending_order(order_id, db, household)`, `update_item_qty(name, remaining_qty, db, household)` (fraction = qty / pack_size), `get_household_settings(db, household)`, `set_household_settings(adults, children, habit, db, household)`, `get_recent_orders(db, household)`, `build_shopping_list(db, household)`, `explain_inventory(name, db, household)`. Orchestrator: `build_graph(db, household)`; `_execute_tool(..., db, household)`; `run_heuristic_agent(msg, db, household, session_id)`.
- [ ] **Step 3: Run full suite** → all green (8 old + new). **Commit** `feat(agent,orders): household-scoped tools and order creation on the new schema`.

---

### Task 8: Wire `main.py`, remove leftovers, manual run

**Files:** `backend/app/main.py`; delete `backend/app/services/vendor_engine.py` if not already; update `AGENT_SETUP.md` curl example (needs token).

- [ ] **Step 1:** `main.py` — drop `load_env_file()` (settings handles `.env`), drop `create_all` (Alembic owns schema; keep a guarded `if get_settings().auth_dev_mode and DATABASE_URL.startswith("sqlite"): Base.metadata.create_all(engine)` so local dev without running Alembic still works — comment says so), mount `auth, households, inventory, vendors, orders, seed, agent, vision`, add `GET /health` → `{"status":"ok"}`.
- [ ] **Step 2:** `ruff check backend` clean; full `pytest` green; start uvicorn; run the §8 done-when sequence with PowerShell `Invoke-RestMethod`: request-otp → verify → `/auth/me` → `/seed/dev` → `/vendors/compare/milk` → `/agent/chat "show pantry status"`. Paste outputs.
- [ ] **Step 3: Commit** `feat(api): mount new routers, health endpoint, alembic-owned schema`.

---

### Task 9: PostgreSQL via Docker Compose (verify if Docker present)

**Files:** create `docker-compose.yml`; modify `.env.example`, `README.md` (Database section).

- [ ] **Step 1:** `docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: autobasket
      POSTGRES_PASSWORD: autobasket
      POSTGRES_DB: autobasket
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U autobasket"]
      interval: 5s
      timeout: 3s
      retries: 10
volumes:
  pgdata:
```
`.env.example`: add `JWT_SECRET=change-me`, `AUTH_DEV_MODE=1`, and the Postgres URL `postgresql+psycopg://autobasket:autobasket@localhost:5432/autobasket` (commented, with the SQLite default active).
- [ ] **Step 2:** If `docker` is on PATH: `docker compose up -d db`, then from `backend/`: `DATABASE_URL=postgresql+psycopg://... alembic upgrade head`, then run the suite with that `DATABASE_URL` for the migration test. Else: note "Postgres verification pending Docker install" in the commit message and README.
- [ ] **Step 3: Commit** `chore(db): docker compose postgres and env docs`.

---

### Task 10: Frontend — login gate, auth header, Slots page

**Files:** create `frontend/src/pages/Login.jsx`, `frontend/src/pages/Slots.jsx`, `frontend/src/services/auth.js`; modify `frontend/src/services/api.js`, `frontend/src/App.jsx`.

- [ ] **Step 1:** `auth.js`: `getToken/setToken/clearToken` on `localStorage` key `ab_token` (try/catch), `requestOtp(email)`, `verifyOtp(email, code)`. `api.js`: request interceptor adds `Authorization`; response interceptor on 401 clears token and dispatches `window.dispatchEvent(new Event("ab:logout"))`.
- [ ] **Step 2:** `Login.jsx`: two-step form (email → code), dark theme matching `App.jsx` tokens, shows the dev code hint when the API returns `dev_code`. `Slots.jsx`: fetches `/households/me/slots`, renders trays as rows of 4 slot cards ("Empty" or product id), and a "Seed dev data" button (calls `/seed/dev`) when there are no trays.
- [ ] **Step 3:** `App.jsx`: if no token → `<Login onLogin=…/>`; add `{ id: "slots", label: "Fridge Slots", icon: "▦", description: "Trays & slots" }` to `pages`; listen for `ab:logout`; add a "Sign out" button in the sidebar footer.
- [ ] **Step 4:** `npm run lint && npm run build` clean; run dev server and log in manually; describe what the user should see. **Commit** `feat(web): email-code login, auth header, fridge slots page`.

---

### Task 11: Finish

- [ ] Full suite + ruff + eslint + build green; update `README.md` API section (auth flow, new endpoints) and the roadmap's Phase 1 status; push branch; invoke finishing-a-development-branch (ff-merge to `main`, push, delete branch).

---

## Self-review
- **Spec coverage:** §3 tables → Task 2/3; §4 auth → Task 4; §5 rewiring → Tasks 5–8 (compare/review shape preserved; seed dev-only; dead `routes/__init__` router removed in Task 5; vision untouched); §6 frontend → Task 10; §7 files → all created; §8 done-when → Task 8 step 2 + Task 10 step 4; docker-compose → Task 9.
- **Placeholders:** Task 5 seed and Task 6/7 implementations are described by exact behaviour and signatures rather than full code — acceptable because the interfaces and tests are fully specified; the executor is this session.
- **Type consistency:** `set_remaining(db, household, product_id, fraction, source, slot_id)` used in Tasks 5 and 7 identically; `rank_offers(pairs)` in 6 and 7; `current_household` everywhere; `predict_state(state, product, household)` in 5 and 7.
