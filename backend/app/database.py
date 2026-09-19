import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./autobasket.db"


def get_database_url() -> str:
    """DATABASE_URL from the environment, else the local SQLite file."""
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


DATABASE_URL = get_database_url()

# check_same_thread is a SQLite-only flag; other drivers reject it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
