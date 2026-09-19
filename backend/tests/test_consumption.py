from datetime import UTC, datetime, timedelta

from app.services.consumption import estimate_rate

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)
PRIOR = 1.15  # household-size guess, L/day


def steady_history(days: int, rate_per_day: float, pack: float, samples_per_day: int = 2, refill_below: float = 0.1):
    """Simulate a fridge sampled `samples_per_day` times a day, refilled when nearly empty."""
    points = []
    fraction = 1.0
    step = timedelta(days=1 / samples_per_day)
    t = NOW - timedelta(days=days)
    while t <= NOW:
        points.append((t, round(fraction, 4)))
        fraction -= rate_per_day / pack / samples_per_day
        if fraction < refill_below:
            fraction = 1.0
        t += step
    return points


def test_steady_use_is_learned_accurately():
    # 3 L of milk used at 1 L/day: refills every ~3 days, 14 days of history
    est = estimate_rate(steady_history(14, 1.0, 3.0), pack_size=3.0, prior_rate=PRIOR, now=NOW)
    assert est.method == "learned"
    assert abs(est.daily_rate - 1.0) < 0.05
    assert est.confidence == 1.0
    assert est.observed_days >= 7


def test_refills_do_not_inflate_the_rate():
    # 5 kg rice at 0.75 kg/day refills roughly every 6 days -> two refills in 14 days
    est = estimate_rate(steady_history(14, 0.75, 5.0), pack_size=5.0, prior_rate=0.9, now=NOW)
    assert est.method == "learned"
    assert abs(est.daily_rate - 0.75) < 0.05


def test_jitter_is_not_consumption():
    points = []
    for i in range(10):  # 5 days, twice a day, wobbling around 0.6 by ±1 %
        points.append((NOW - timedelta(days=5) + timedelta(hours=12 * i), 0.6 + (0.01 if i % 2 else -0.01)))
    est = estimate_rate(points, pack_size=1.0, prior_rate=PRIOR, now=NOW)
    assert est.learned_rate is not None
    assert est.learned_rate < 0.05
    assert est.method == "blended"
    assert est.daily_rate < PRIOR


def test_short_history_is_blended_towards_prior():
    est = estimate_rate(steady_history(2, 1.0, 2.0), pack_size=2.0, prior_rate=3.0, now=NOW)
    assert est.method == "blended"
    assert 0.15 < est.confidence < 0.4
    assert 1.0 < est.daily_rate < 3.0


def test_no_history_uses_prior():
    est = estimate_rate([], pack_size=1.0, prior_rate=PRIOR, now=NOW)
    assert est.method == "prior"
    assert est.daily_rate == PRIOR
    assert est.confidence == 0.0


def test_old_events_outside_window_are_ignored():
    old = [(NOW - timedelta(days=60), 1.0), (NOW - timedelta(days=50), 0.0)]  # 10 days of heavy use, long ago
    est = estimate_rate(old, pack_size=1.0, prior_rate=PRIOR, now=NOW)
    assert est.method == "prior"


def test_naive_timestamps_are_treated_as_utc():
    naive = [(t.replace(tzinfo=None), f) for t, f in steady_history(14, 1.0, 3.0)]
    est = estimate_rate(naive, pack_size=3.0, prior_rate=PRIOR, now=NOW)
    assert est.method == "learned"
