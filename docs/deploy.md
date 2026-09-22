# Deploying AutoBasket

One VPS, one command. The stack is four containers: Postgres, the API, the background worker, and Caddy serving the
web app with automatic HTTPS and proxying `/api/*` to the API.

## What you need

- A small Linux VPS (Ubuntu 22.04 or 24.04, 2 GB RAM is plenty). Hetzner CX22 or DigitalOcean's basic droplet
  cost roughly ₹500–1,500 a month.
- A domain (or subdomain) you control, e.g. `fridge.example.com`.
- An SMTP account for sign-in emails (Brevo and Resend have free tiers; a Gmail app password also works).
- Optional: an OpenRouter or OpenAI key (chat agent and camera), a Telegram bot token, Razorpay test keys.

## Steps

1. **Point DNS at the server.** Create an A record for `fridge.example.com` → the VPS IP. Wait until
   `ping fridge.example.com` answers from your laptop.

2. **Install Docker on the VPS.**
   ```bash
   ssh root@<vps-ip>
   curl -fsSL https://get.docker.com | sh
   ```

3. **Get the code.**
   ```bash
   git clone https://github.com/RayonBiswas/Autobasket2.0.git /opt/autobasket
   cd /opt/autobasket
   ```

4. **Write the production settings.**
   ```bash
   cp .env.production.example .env.production
   nano .env.production
   ```
   Fill in every value marked REQUIRED. Generate the JWT secret with
   `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep `APP_ENV=production` and
   `AUTH_DEV_MODE=0`: the API refuses to start otherwise, and tells you exactly what is missing.

5. **Start everything.**
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
   docker compose -f docker-compose.prod.yml logs -f api
   ```
   You should see `applying database migrations` then `Application startup complete`. Caddy fetches the TLS
   certificate on the first request; give it a few seconds.

6. **Check it.**
   ```bash
   curl https://fridge.example.com/health        # "ok" from Caddy
   curl https://fridge.example.com/api/health    # {"status":"ok"} from the API
   ```

7. **First sign-in.** Open `https://fridge.example.com`, enter your email, and use the 6-digit code from the
   email. The first account owns its own household. Add a fridge from Shelves to get a device key.

8. **Telegram alerts (optional).** Create a bot with @BotFather, put the token and username in
   `.env.production`, restart (`up -d`), then register the webhook once:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://fridge.example.com/api/telegram/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
   Users connect from Settings → Alerts on your phone.

9. **Razorpay payments (optional).** In the Razorpay dashboard add a webhook for
   `https://fridge.example.com/api/payments/razorpay/webhook` with the event `payment_link.paid` and the
   secret you put in `RAZORPAY_WEBHOOK_SECRET`. Test keys work end to end.

10. **Backups.** The database lives in the `pgdata` volume. A nightly dump:
    ```bash
    crontab -e
    # 0 3 * * * cd /opt/autobasket && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U autobasket autobasket | gzip > /root/backups/autobasket-$(date +\%F).sql.gz
    ```
    Restore with `gunzip -c file.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U autobasket autobasket`.

11. **Updating.**
    ```bash
    cd /opt/autobasket && git pull && docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
    ```
    Migrations run automatically when the API container starts.

12. **Logs and status.**
    ```bash
    docker compose -f docker-compose.prod.yml ps
    docker compose -f docker-compose.prod.yml logs -f --tail=100 api worker web
    ```

## Testing the exact stack on your own PC

Set `SITE_ADDRESS=:80`, `WEB_URL=http://localhost` and (only locally) `APP_ENV=development`, `AUTH_DEV_MODE=1` in
`.env.production`, then run the same `up -d --build`. Open http://localhost. No TLS, no email needed.

## What the production guard checks

With `APP_ENV=production` the API refuses to start unless: dev mode is off, `JWT_SECRET` is 32+ random
characters, the database is PostgreSQL, and SMTP is configured. The message lists every failing item.

## Fridge devices

Each fridge posts readings with its own device key (created from Shelves → Add a fridge). Point the device's
`AB_API_URL` at `https://fridge.example.com/api`. See `edge/README.md`.
