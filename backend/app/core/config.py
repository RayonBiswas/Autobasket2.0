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

    # Where the web app lives; used in payment and Telegram links.
    web_url: str = "http://localhost:5173"

    # Telegram bot (optional). Without a token, alerts are in-app only.
    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None
    telegram_webhook_secret: str | None = None

    # Razorpay (optional, test keys are fine). Without keys, a dev payment page stands in.
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # Vision model (optional). Any OpenAI-compatible endpoint with image input; falls back to the chat settings.
    vision_model: str | None = None

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
