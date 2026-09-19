"""Learn how fast a household uses a product from its inventory history.

Pure arithmetic, no database: give it (time, remaining fraction) points and get a daily rate back.
Between two consecutive points:
  - a drop is consumption over that interval;
  - a big rise (a refill) means we cannot know what was used in between, so the interval is skipped;
  - a tiny rise is load-cell jitter and counts as zero consumption over the interval.
The learned rate is blended with the household-size prior until about a week of history exists.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

REFILL_RISE = 0.15  # fraction of a pack; a rise this big is "someone shopped"
NOISE_RISE = 0.02  # fraction of a pack; a rise this small is sensor jitter
FULL_CONFIDENCE_DAYS = 7.0
MIN_OBSERVED_DAYS = 0.5


@dataclass(frozen=True)
class RateEstimate:
    daily_rate: float  # pack units per day, what the app should use
    confidence: float  # 0..1
    method: str  # prior | blended | learned
    observed_days: float
    learned_rate: float | None


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def learned_consumption(events: list[tuple[datetime, float]], now: datetime, window_days: int) -> tuple[float, float]:
    """Return (consumed fraction, observed days) over the window using the interval rules above."""
    since = _as_utc(now) - timedelta(days=window_days)
    points = sorted(((_as_utc(t), f) for t, f in events if _as_utc(t) >= since), key=lambda p: p[0])

    consumed = 0.0
    observed_seconds = 0.0
    for (t1, f1), (t2, f2) in zip(points, points[1:], strict=False):
        gap = (t2 - t1).total_seconds()
        if gap <= 0:
            continue
        delta = f2 - f1
        if delta <= 0:
            consumed += -delta
            observed_seconds += gap
        elif delta < NOISE_RISE:
            observed_seconds += gap
        # NOISE_RISE <= delta: a refill (or ambiguous); skip the interval entirely.
    return consumed, observed_seconds / 86400


def estimate_rate(
    events: list[tuple[datetime, float]],
    pack_size: float,
    prior_rate: float,
    now: datetime,
    window_days: int = 30,
) -> RateEstimate:
    consumed_fraction, observed_days = learned_consumption(events, now, window_days)

    if observed_days < MIN_OBSERVED_DAYS:
        return RateEstimate(round(prior_rate, 3), 0.0, "prior", round(observed_days, 2), None)

    learned = consumed_fraction * pack_size / observed_days
    confidence = min(1.0, observed_days / FULL_CONFIDENCE_DAYS)
    blended = confidence * learned + (1 - confidence) * prior_rate
    method = "learned" if confidence >= 1.0 else "blended"
    return RateEstimate(round(blended, 3), round(confidence, 2), method, round(observed_days, 2), round(learned, 3))
