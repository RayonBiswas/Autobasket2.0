import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_default_is_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app import database
    assert database.get_database_url() == "sqlite:///./autobasket.db"


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/autobasket")
    from app import database
    assert database.get_database_url() == "postgresql+psycopg://u:p@localhost:5432/autobasket"
