# Phase 6 — Notifications, "Yes", Payment, Order Lifecycle: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When something is about to run out, the household gets a message with the three best offers and Yes buttons; one tap creates the order, opens a payment link (kirana) or the app (Blinkit etc.), the shop delivers, the next weight reading proves it, and the order ends *verified*.

**Architecture:** A `notifications` table is the single source of truth for what we asked and what the user tapped; channels (in-app, Telegram) only deliver it. The worker turns the reorder list into *proposals* (one open proposal per product). Answering a proposal, from the web or Telegram, goes through the same `services/proposals.accept()`. Payments go through `services/payments.py`: Razorpay payment links when keys are configured, otherwise a clearly-labelled dev payment page so the loop runs locally with zero keys. Delivery verification hooks into `set_remaining()`: a refill after *delivered* or *handoff* flips the order to *verified*.

**Tech Stack:** FastAPI, httpx (Telegram + Razorpay HTTP), APScheduler, React Router, PWA manifest.

**Spec:** roadmap §3.7, §5 (`notifications`), §6 Phase 6.

## Global Constraints
No secrets in the repo; every external call fails soft and is logged; webhooks verify their secret; dev-only routes refuse unless `AUTH_DEV_MODE=1`; plain-language copy; every schema change via Alembic. Web push (VAPID) is out of scope for this phase: the PWA installs and shows in-app alerts; push arrives with deployment (Phase 9) where HTTPS exists.

---

### Task 1: Migration 0006
- [ ] `Notification`: id, household_id FK, product_id FK|None, channel (String 12: inapp|telegram), kind (String 24: reorder_offer|order_update), title (200), body (Text), payload (Text JSON), sent_at, response (String 16|None), responded_at. Index (household_id, responded_at).
- [ ] `Household.telegram_chat_id: str|None (32)`, `Household.telegram_link_code: str|None (12)`.
- [ ] `Order.payment_url (500)|None`, `Order.handoff_url (500)|None`, `Order.delivered_at`, `Order.verified_at`, `Order.rating: int|None`. Autogenerate `0006_order_flow`. Commit `feat(db): notifications, telegram link, order payment/handoff columns`.

### Task 2: Settings + payments + handoff (TDD)
Config: `telegram_bot_token`, `telegram_bot_username`, `telegram_webhook_secret`, `razorpay_key_id`, `razorpay_key_secret`, `razorpay_webhook_secret`, `web_url="http://localhost:5173"`.
```python
# services/payments.py
def create_payment_link(order, household) -> tuple[str, str]   # (url, reference)  razorpay if keys else dev
def verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool  # HMAC-SHA256 hex
# services/handoff.py
def handoff_url(vendor_name: str, product_name: str) -> str | None   # Blinkit/Zepto/Instamart/BigBasket public search URLs
```
- [ ] Tests: dev link is `{web_url}/pay/{id}?ref=dev_...`; signature helper round-trips; handoff url for Blinkit contains the product; unknown vendor → None.
- [ ] Commit `feat(orders): payment links and platform handoff urls`.

### Task 3: Order lifecycle service (TDD)
```python
# services/orders.py (extend)
def confirm(db, order, household) -> Order   # kirana: → confirmed + payment_url ; platform: → handoff + handoff_url
def mark_paid(db, order, reference) -> Order
def verify_refill(db, household, product_id, fraction) -> list[Order]  # delivered/handoff orders containing product → verified when fraction ≥ 0.6
def rate(db, order, stars) -> Order  # order.rating; vendor.rating running avg; vendor.service_score = 0.8*old + 0.2*stars/5
```
`inventory.set_remaining()` calls `verify_refill` after writing the event (import inside the function to avoid a cycle).
- [ ] Tests (`test_order_flow.py`): kirana confirm → status confirmed, payment_url set; platform confirm → handoff with url; paid → accepted → delivered → set_remaining(0.9) → verified with verified_at; set_remaining(0.3) does not verify; rate 5 raises service_score; rating twice → 409.
- [ ] Routes: `POST /orders/{id}/confirm` uses `confirm`; `POST /orders/{id}/rate {stars}`; `POST /payments/razorpay/webhook` (verify header `X-Razorpay-Signature`, event `payment_link.paid`, `reference_id` = order id → mark_paid); `POST /payments/dev/complete {order_id}` (dev mode, household-scoped). `GET /orders` rows include payment_url, handoff_url, rating, delivered_at, verified_at.
- [ ] Commit `feat(orders): confirm → pay → deliver → verified lifecycle, ratings, payment webhooks`.

### Task 4: Notifications, proposals, Telegram (TDD)
```python
# services/notify/__init__.py
def send(db, household, kind, title, body, payload: dict, buttons: list[tuple[str, str]], product_id=None) -> Notification
# creates the row (channel inapp), then if telegram configured + chat linked: TelegramBot.send_message(...) and a second row channel telegram
# services/notify/telegram.py
class TelegramBot: __init__(token, http=None); send_message(chat_id, text, buttons) -> bool; answer_callback(id, text) -> bool
def parse_update(update: dict) -> tuple[str, str, str, str | None]   # ("start", chat_id, code, None) | ("callback", chat_id, data, callback_id) | ("other", ...)
# services/proposals.py
def propose_reorders(db, household, now=None) -> list[Notification]   # one open proposal per product; skip products with an open order or an unanswered proposal < 24 h old
def respond(db, household, notification, choice: str) -> Order | None  # "1".."3" → create order from payload offer + confirm(); "skip" → response=skip
```
- [ ] Tests: propose creates one row with 3 offers for milk and none on a second call; respond "1" creates a confirmed kirana order with payment_url and marks the notification; respond "skip"; Telegram `parse_update` for a `/start CODE` message and a callback; webhook link flow: `POST /telegram/link` → code; fake update `/start CODE` → household.telegram_chat_id set; fake callback `p:<id>:1` → order created; wrong secret header → 403. Fake bot injected by monkeypatching `TelegramBot.send_message`.
- [ ] Routes: `GET /notifications?unanswered=1`, `POST /notifications/{id}/respond {choice}`, `POST /telegram/link` → `{code, url}` (`https://t.me/<bot>?start=<code>`), `POST /telegram/webhook`, `DELETE /telegram/link`.
- [ ] Worker: `propose_reorders_once()` every 15 min after recompute. Agent: "what's running out" → reorder list; "order milk" → top recommendation → order + confirm (₹50 guardrail kept).
- [ ] Commit `feat(notify): proposals with Yes buttons, in-app and Telegram channels, worker job`.

### Task 5: UI
- [ ] Dashboard: "Needs your yes" section above the shelves listing unanswered proposals: product, three offers as compact rows with a "Yes" button each, and "Skip". After Yes: kirana → toast + "Pay ₹58" link; platform → opens handoff URL in a new tab.
- [ ] New `/orders` page: every order as a card with a plain-words timeline (Sent → Paid → Packing → Delivered → Back on the shelf), the right next action (Pay now / Open in app / Rate: five stars / Cancel), and cancelled/verified states.
- [ ] `/pay/:orderId` dev payment page (only shown when the URL has `ref=dev_`): amount, "Pay (test)" → `/payments/dev/complete` → back to Orders.
- [ ] Settings: "Alerts on Telegram" card: Connect → shows the t.me link and code; Connected → Disconnect.
- [ ] PWA: `public/manifest.webmanifest`, `public/icons/icon.svg`, `public/sw.js` (cache shell, network-first API), registered in `main.jsx`. Nav: add Orders.
- [ ] Lint/build, live run of the whole loop with the simulator, screenshots `phase-6-proposal.png`, `phase-6-orders.png`. README "From alert to verified delivery". Commit, merge, push.

## Self-review
Telegram link + buttons → T4; web push → deferred, stated; kirana Yes → payment → paid → inbox → delivered → verified → T3/T4/T5; platform handoff → T2/T3; rating → T3; agent tools → T4; done-when → T5.
