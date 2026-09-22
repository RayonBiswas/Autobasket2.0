# Phase 9 — Deployment: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command brings up the whole product on a VPS with HTTPS: API, worker, Postgres and the web app, with real sign-in emails, refusing to start in an unsafe configuration.

**Architecture:** Two images. `backend/Dockerfile` runs the API (after `alembic upgrade head`) or the worker depending on the command. `frontend/Dockerfile` builds the React app and serves it from Caddy, which is also the public edge: it terminates TLS automatically for `SITE_ADDRESS`, serves the static app, and proxies `/api/*` to the API container (so the web app talks to `/api` on the same origin and no CORS is needed). `docker-compose.prod.yml` wires db + api + worker + web. Production safety lives in `core/config.validate_production()`, called at API startup.

**Tech Stack:** Docker, Compose, Caddy 2, Postgres 16, smtplib (STARTTLS), GitHub Actions.

**Spec:** roadmap §3.8, §6 Phase 9.

## Global Constraints
No secrets in images or the repo; `.env.production` is gitignored and documented by `.env.production.example`. Dev-only routes (`/seed/dev`, `/payments/dev/complete`, dev OTP echo) must be off in production. Everything the runbook says must have been run once locally.

---

### Task 1: Production settings + email (TDD)
- [ ] Settings: `app_env` (development|production), `cors_origins` (comma list, default `*`), `smtp_host`, `smtp_port=587`, `smtp_user`, `smtp_password`, `smtp_from`, property `email_enabled`. `validate_production()` raises `RuntimeError` listing every problem when `app_env == "production"` and any of: `auth_dev_mode` on, `jwt_secret` is the default or shorter than 32 chars, `database_url` is SQLite, email not configured. Called from a FastAPI lifespan in `main.py`.
- [ ] `services/email.py`: `send_email(to, subject, body) -> bool` via `smtplib.SMTP` + STARTTLS; fail-soft with a log line. `routes/auth.send_otp` uses it; when not in dev mode and email is off → 503 "Sign-in email is not configured on this server".
- [ ] CORS from `cors_origins`; `allow_credentials` only when it is not `*`.
- [ ] Tests (`test_production.py`): `validate_production` lists all four problems for the defaults; passes for a good config; `send_email` returns False when SMTP is unreachable (monkeypatched); non-dev OTP request without SMTP → 503; with a fake SMTP → 204 and the fake got the code.
- [ ] Commit `feat(config): production guard, SMTP sign-in emails, CORS from settings`.

### Task 2: Images + compose
- [ ] `backend/Dockerfile` (python:3.12-slim, non-root user, `docker/entrypoint.sh`: `api` → `alembic upgrade head` then `uvicorn --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*`; `worker` → `python -m app.worker`). `backend/.dockerignore`.
- [ ] `frontend/Dockerfile` (node:20-alpine build with `VITE_API_URL=/api` → caddy:2-alpine with `frontend/Caddyfile`: `{$SITE_ADDRESS}`, `encode`, `handle_path /api/*` → `reverse_proxy api:8000`, SPA fallback, `/health` for the edge). `frontend/.dockerignore`. `services/api.js` defaults to `/api` in production builds.
- [ ] `docker-compose.prod.yml`: `db` (postgres:16-alpine, named volume, healthcheck), `api` (build backend, `env_file: .env.production`, depends on db healthy, healthcheck on `/health`), `worker` (same image, command worker), `web` (build frontend, ports 80/443, `SITE_ADDRESS`, `caddy_data` volume, depends on api). `.env.production.example` with every variable and a comment. `.gitignore` adds `.env.production`.
- [ ] Verify locally: `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build` with `SITE_ADDRESS=:80`; `curl localhost/health` (Caddy), `curl localhost/api/health` (API through the proxy), sign in through the browser at http://localhost. Commit `feat(deploy): production images, Caddy edge, compose stack`.

### Task 3: CI + runbook
- [ ] CI job `images`: builds both images with `docker compose -f docker-compose.prod.yml build` (no push; pushing needs a registry decision).
- [ ] `docs/deploy.md`: VPS in 12 steps (Ubuntu, Docker, DNS A record, clone, `.env.production`, up, first sign-in, Telegram `setWebhook`, Razorpay webhook URL, backups with `pg_dump` cron, updating with `git pull && up -d --build`, logs). README "Deploying" section pointing at it. Commit `docs: deployment runbook`.

## Self-review
§3.8 Docker Compose on VPS, HTTPS via Caddy, CI builds images → T2/T3; "ready to use" needs real OTP delivery → T1; done-when: stack up locally through Caddy → T2.
