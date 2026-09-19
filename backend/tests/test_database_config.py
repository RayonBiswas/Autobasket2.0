import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_default_is_local_sqlite():
    from app.core.config import Settings
    assert Settings.model_fields["database_url"].default == "sqlite:///./autobasket.db"


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/autobasket")
    from app import database
    assert database.get_database_url() == "postgresql+psycopg://u:p@localhost:5432/autobasket"


def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "abc")
    monkeypatch.setenv("AUTH_DEV_MODE", "0")
    from app.core.config import Settings
    s = Settings()
    assert s.jwt_secret == "abc"
    assert s.auth_dev_mode is False
    assert s.jwt_expires_hours == 24
