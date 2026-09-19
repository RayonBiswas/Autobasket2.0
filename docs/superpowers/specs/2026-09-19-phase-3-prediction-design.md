# Phase 3 — Prediction v2 (learned consumption) + Worker: Design

Date: 2026-09-19
Status: IMPLEMENTED 2026-09-19 (branch phase-3-prediction). Live check: 14-day backfill → milk learned 1.14 l/day (true 1.1), water 8.43 (true 8.0). Screenshot docs/screenshots/phase-3-provenance.png.
Parent: roadmap §3.5, §6 Phase 3

## 1. Goal (plain words)

Today "Milk runs out on Thursday" is a guess from family size. After this phase it comes from *how fast this
household actually uses milk*, learned from the weight history, and it keeps itself up to date in the
background. The UI says where the number came from ("based on 9 days of use" vs "estimated from household
size") so nobody over-trusts a young guess.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Learning signal | `inventory_events` (remaining fraction over time) for the last 30 days | Already collected by every reading; no new sensors. |
| Rate estimate | Piecewise: between consecutive events, a *drop* counts as consumption over that interval; a *big rise* (≥ 15 % of pack) is a refill and the interval is skipped; a tiny rise (< 2 %) is sensor noise and counts as zero consumption. `rate = Σconsumed / Σelapsed_days`. | Simple, explainable, robust to refills and load-cell jitter. |
| Cold start | Blend with the household-size prior by confidence `w = min(1, observed_days / 7)`: `rate = w·learned + (1−w)·prior`. | Day-1 answers still exist; after a week the data dominates. |
| Where it runs | Inside `set_remaining()` on every event (cheap, ≤ 30 days of rows) **and** in a worker every 15 min for households with no fresh readings. | days_left drifts even when nothing is weighed; the worker keeps it honest. |
| Worker | `backend/app/worker.py`, APScheduler `BlockingScheduler`, one job `recompute_all`. Runs as its own process (`python -m app.worker`). | Roadmap choice; no broker to operate. |
| Reorder rule | `needs_reorder = days_left ≤ LEAD_TIME_DAYS (1) + SAFETY_DAYS (1)`; `status`: critical if needs_reorder, warning if ≤ 5 days, else safe. | Same thresholds as today, now with a named reason Phase 6 can notify on. |
| Schema | Migration 0003 adds to `inventory_state`: `rate_confidence float?` (0–1), `rate_method str?` (`learned` \| `blended` \| `prior`), `observed_days float?`. | The UI and future notifications need to show provenance. |
| Simulator | Gains `--backfill-days N`: posts N days of realistic history (past `captured_at`, per-day rates, refills) before going live, so the learner has data in seconds. Live drain unchanged. | Lets you demo learning without waiting a week. |

## 3. API

- `GET /inventory` rows gain `rate_confidence`, `rate_method`, `observed_days`, `needs_reorder`.
- `GET /inventory/reorder` → the items that need reordering, soonest first (Phase 6 notifies from this).
- `POST /inventory/recompute` (household) → recompute all rows now; returns count. Used by the UI "Refresh" and tests.

## 4. Files

```
backend/app/services/consumption.py   estimate_rate(events, pack_size, prior_rate, now) -> RateEstimate
backend/app/services/inventory.py     set_remaining() calls the learner; recompute_state(); recompute_all(); reorder_list()
backend/app/services/predictor.py     predict_state() uses learned rate + confidence; status via needs_reorder
backend/app/worker.py                 APScheduler job every 15 min -> recompute_all
backend/alembic/versions/0003_*.py    three new columns
backend/tests/test_consumption.py     steady use, refill, noise, holiday gap, cold start blend
backend/tests/test_recompute.py       worker function + /inventory/recompute + /inventory/reorder
edge/simulator.py                     --backfill-days
frontend Dashboard tile               provenance line under "runs out"
```

## 5. Done when

1. Unit tests: steady 1 L/day history → rate ≈ 1.0 ± 0.05; a refill in the middle doesn't inflate it; ±1 % jitter doesn't create phantom consumption; 3 days of data → method `blended`, 10 days → `learned`.
2. Simulator `--backfill-days 14` then `/inventory` shows `rate_method: learned` for milk with `observed_days ≥ 10`.
3. `python -m app.worker` logs one recompute pass; `/inventory/recompute` returns the row count.
4. Dashboard tile shows "Based on 14 days of use".
5. Full suite green, ruff/eslint/build clean, Postgres smoke green.

## 6. Not in Phase 3

Notifications (6), seasonality/holiday modelling, per-item lead times from vendor ETA (5/6), retraining any ML model — this is deliberately arithmetic, not ML.
