# Phase 3 — Prediction v2 + Worker: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learn each household's consumption rate from inventory_events, blend it with the prior by confidence, keep days_left fresh via a worker, and show provenance in the UI.

**Architecture:** Pure function `estimate_rate()` in `services/consumption.py` (no DB) tested with synthetic histories; `services/inventory.py` wires it into `set_remaining()` and exposes `recompute_state/recompute_all/reorder_list`; `app/worker.py` schedules `recompute_all`. Migration 0003 adds provenance columns.

**Tech Stack:** SQLAlchemy 2, Alembic, APScheduler 3, pytest, React.

**Spec:** `docs/superpowers/specs/2026-09-19-phase-3-prediction-design.md`

## Global Constraints
Same as Phases 1–2. Rates are in *pack units per day* (the unit shown to users). Timestamps UTC-aware.

---

### Task 1: Migration 0003 (provenance columns)
- [ ] Add to `InventoryState`: `rate_confidence: Mapped[float | None]`, `rate_method: Mapped[str | None] = mapped_column(String(12))`, `observed_days: Mapped[float | None]`. Autogenerate `0003_rate_provenance`. `test_migrations` green. Commit `feat(db): rate provenance columns`.

### Task 2: `estimate_rate()` (TDD)
**Interface:**
```python
@dataclass
class RateEstimate:
    daily_rate: float; confidence: float; method: str; observed_days: float; learned_rate: float | None
def estimate_rate(events: list[tuple[datetime, float]], pack_size: float, prior_rate: float, now: datetime,
                  window_days: int = 30) -> RateEstimate
```
`events` = (recorded_at, remaining_fraction) any order. Rules from spec §2 (drop = consumption; rise ≥ 0.15 = refill, skip interval; rise < 0.02 = noise, zero consumption, interval counts; rise in between = ambiguous, skip). `observed_days` = Σ counted intervals. `w = min(1, observed_days/7)`; method `prior` if `observed_days < 0.5`, `learned` if `w ≥ 1`, else `blended`. Guard: if learned rate is 0 and observed_days ≥ 2, still return it (a genuinely unused item).
- [ ] Tests (`test_consumption.py`): steady 1 L/day over 10 days sampled twice a day → `daily_rate ≈ 1.0 (±0.05)`, `method == "learned"`; same with a refill on day 5 → still ≈ 1.0; flat readings with ±1 % jitter over 5 days → learned 0, method blended, rate < prior; 2 days of data → `blended` and prior-heavy; no events → `prior`, confidence 0; events older than the window ignored.
- [ ] Implement; commit `feat(prediction): consumption rate learned from inventory history`.

### Task 3: Wire into inventory + predictor + API
- [ ] `predictor.predict_state(state, product, household)` → uses `state.daily_rate` (now always set) and adds `needs_reorder = days_left <= 2`; status critical iff needs_reorder. `state_row()` adds `rate_confidence, rate_method, observed_days, needs_reorder`.
- [ ] `inventory.recompute_state(db, state, product, household, now=None)` loads the last 30 days of events for the pair, calls `estimate_rate` with `prior=estimate_daily_usage(...)`, writes `daily_rate/rate_confidence/rate_method/observed_days/days_left/status`. `set_remaining()` calls it after adding the event. `recompute_all(db) -> int` iterates every state. `reorder_list(db, household)` = rows with needs_reorder sorted by days_left.
- [ ] Routes: `GET /inventory/reorder`, `POST /inventory/recompute`. Agent `build_shopping_list` uses `reorder_list` + warnings.
- [ ] Tests (`test_recompute.py`): seed → post 10 days of backdated readings via `/devices/me/readings` with `captured_at` → `/inventory` milk `rate_method == "learned"`; `/inventory/recompute` returns ≥ 3; `/inventory/reorder` lists milk when nearly empty and not when full.
- [ ] Commit `feat(inventory): learned rates in state, reorder list, recompute endpoint`.

### Task 4: Worker
- [ ] `backend/app/worker.py`: `run_once()` opens a session, calls `recompute_all`, logs `recomputed N rows`; `main()` runs it immediately then every 15 min with `BlockingScheduler`. `python -m app.worker`. Add `apscheduler>=3.10` to requirements. Test: `run_once()` returns the count with the in-memory DB (monkeypatch `SessionLocal`).
- [ ] README: "Background worker" section. Commit `feat(worker): scheduled recompute of predictions`.

### Task 5: Simulator backfill
- [ ] `--backfill-days N` (env `AB_BACKFILL_DAYS`): for each calibrated slot, walk day by day from `now − N days` to now with a per-product daily rate (milk 1.1 L, rice 0.75 kg, water 8 L, else 20 % of pack/day), two readings per day at 08:00 and 20:00 with `captured_at`, refill to full when < 10 %. Post in batches of one day. Then continue live. Test: `backfill_events(...)` pure function yields N×2 readings per slot with strictly increasing timestamps and at least one refill for milk over 14 days.
- [ ] Commit `feat(edge): simulator history backfill`.

### Task 6: Dashboard provenance + verification
- [ ] Tile line under "Runs out …": `Based on 14 days of use` / `Estimated from household size` / `Learning — 3 days so far`. Lint/build.
- [ ] Live: API + worker + simulator `--backfill-days 14`; `/inventory` shows learned; screenshot `docs/screenshots/phase-3-provenance.png`. Full checks incl. Postgres smoke. Update spec status, README, memory. Commit, push, ff-merge.

## Self-review
Spec §2 rules → T2; §3 API → T3; worker → T4; simulator → T5; UI + done-when → T6. Names consistent: `estimate_rate`, `RateEstimate`, `recompute_state`, `recompute_all`, `reorder_list`, `needs_reorder`.
