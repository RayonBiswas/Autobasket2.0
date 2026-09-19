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
