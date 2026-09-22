from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All runtime configuration. Values come from the environment, then the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

    # development | production. Production refuses to start with unsafe settings (see validate_production).
    app_env: str = "development"

    database_url: str = "sqlite:///./autobasket.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expires_hours: int = 24
    auth_dev_mode: bool = True
    otp_ttl_minutes: int = 10
    # Comma-separated browser origins allowed to call the API; "*" for local development.
    cors_origins: str = "*"

    # Sign-in emails. Any SMTP provider with STARTTLS on port 587.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

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

    # LLM (chat agent + vision). Any OpenAI-compatible endpoint; OpenRouter works. Ollama is used when no key is set.
    llm_provider: str = "ollama"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_model: str = "llama3.1:8b"
    # Vision model (optional): an image-capable model on the same endpoint; falls back to openai_model.
    vision_model: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key != "your_openai_api_key_here")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


DEFAULT_JWT_SECRET = "dev-secret-change-me"


def validate_production(s: "Settings") -> None:
    """Refuse to run a production deployment that would leak codes, use a guessable secret, or lose data."""
    if not s.is_production:
        return
    problems: list[str] = []
    if s.auth_dev_mode:
        problems.append("AUTH_DEV_MODE must be 0 (dev mode shows sign-in codes in API responses)")
    if s.jwt_secret == DEFAULT_JWT_SECRET or len(s.jwt_secret) < 32:
        problems.append("JWT_SECRET must be a random string of at least 32 characters")
    if s.database_url.startswith("sqlite"):
        problems.append("DATABASE_URL must point at PostgreSQL, not SQLite")
    if not s.email_enabled:
        problems.append("SMTP_HOST (and SMTP_USER/SMTP_PASSWORD) must be set so people can receive sign-in codes")
    if problems:
        raise RuntimeError("Refusing to start in production:\n  - " + "\n  - ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
