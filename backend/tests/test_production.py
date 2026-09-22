"""Production safety: the API refuses unsafe settings, and sign-in codes go out by email when dev mode is off."""

import pytest

from app.core.config import Settings, get_settings, validate_production
from app.services import email as email_service


def test_validate_production_lists_every_problem():
    bad = Settings(app_env="production", auth_dev_mode=True, jwt_secret="dev-secret-change-me", database_url="sqlite:///x.db")
    with pytest.raises(RuntimeError) as exc:
        validate_production(bad)
    text = str(exc.value)
    for needle in ("AUTH_DEV_MODE", "JWT_SECRET", "DATABASE_URL", "SMTP_HOST"):
        assert needle in text


def test_validate_production_accepts_good_config():
    good = Settings(
        app_env="production", auth_dev_mode=False, jwt_secret="x" * 48,
        database_url="postgresql+psycopg://u:p@db/autobasket", smtp_host="smtp.example.com", smtp_user="u", smtp_password="p",
    )
    validate_production(good)  # no exception


def test_validate_production_is_noop_in_development():
    validate_production(Settings(app_env="development"))


def test_send_email_fails_soft(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    get_settings.cache_clear()

    class Boom:
        def __init__(self, *a, **k):
            raise OSError("no network")

    monkeypatch.setattr(email_service.smtplib, "SMTP", Boom)
    assert email_service.send_email("a@b.c", "s", "b") is False
    get_settings.cache_clear()


def test_otp_without_email_in_non_dev_is_503(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("AUTH_DEV_MODE", "0")
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    r = client.post("/auth/request-otp", json={"email": "p@x.y"})
    assert r.status_code == 503
    get_settings.cache_clear()


def test_otp_goes_by_email_in_non_dev(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("AUTH_DEV_MODE", "0")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    get_settings.cache_clear()
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.routes.auth.send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)

    r = client.post("/auth/request-otp", json={"email": "p@x.y"})
    assert r.status_code == 204 and r.content == b""
    assert sent and sent[0][0] == "p@x.y"
    code = "".join(ch for ch in sent[0][2] if ch.isdigit())[:6]
    assert len(code) == 6
    assert client.post("/auth/verify-otp", json={"email": "p@x.y", "code": code}).status_code == 200
    get_settings.cache_clear()
