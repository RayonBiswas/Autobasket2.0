from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All runtime configuration. Values come from the environment, then the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./autobasket.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expires_hours: int = 24
    auth_dev_mode: bool = True
    otp_ttl_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
