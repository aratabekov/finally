import pytest

from market.gbm import EVENT_PROBABILITY, SimEngine


def test_determinism():
    a = SimEngine(seed=42).step(["AAPL", "MSFT"])
    b = SimEngine(seed=42).step(["AAPL", "MSFT"])
    assert a == b


def test_state_persists_across_steps():
    eng = SimEngine(seed=11)
    p1 = eng.step(["AAPL"])["AAPL"]
    assert eng._prices["AAPL"] == p1        # step stores what it returns
    p2 = eng.step(["AAPL"])["AAPL"]
    assert eng._prices["AAPL"] == p2
    # The walk continues from p1 (a small move), not a reset to the seed price.
    assert abs(p2 / p1 - 1.0) < 0.06


def test_prices_stay_positive_over_many_steps():
    eng = SimEngine(seed=1)
    for _ in range(10_000):
        for price in eng.step(["TSLA", "NVDA"]).values():
            assert price > 0


def test_lazy_seeding_of_unknown_ticker():
    eng = SimEngine(seed=7)
    p1 = eng.step(["FOO"])["FOO"]
    p2 = eng.step(["FOO"])["FOO"]
    assert p1 > 0 and p2 > 0            # priced, and continues from p1


def test_typical_step_move_is_small():
    """Excluding events, per-step returns should be well under 1%."""
    eng = SimEngine(seed=123)
    prev = eng.step(["AAPL"])["AAPL"]
    big_moves = 0
    steps = 2000
    for _ in range(steps):
        nxt = eng.step(["AAPL"])["AAPL"]
        if abs(nxt / prev - 1.0) > 0.01:
            big_moves += 1
        prev = nxt
    # Only rare shock events should exceed 1%; keep well below 5% of steps.
    assert big_moves < steps * 0.05


def test_event_frequency_in_expected_range():
    """Roughly EVENT_PROBABILITY of steps should show a >2% jump."""
    eng = SimEngine(seed=2024)
    prev = eng.step(["AAPL"])["AAPL"]
    shocks = 0
    steps = 20000
    for _ in range(steps):
        nxt = eng.step(["AAPL"])["AAPL"]
        if abs(nxt / prev - 1.0) >= 0.02:
            shocks += 1
        prev = nxt
    rate = shocks / steps
    # Generous bounds around the ~0.5% target to avoid flakiness.
    assert 0.2 * EVENT_PROBABILITY < rate < 3 * EVENT_PROBABILITY


def test_history_last_close_matches_live_price():
    eng = SimEngine(seed=3)
    eng.step(["AAPL"])                   # establish a live price
    bars = eng.history("AAPL", days=30, end_ms=1_700_000_000_000)
    assert len(bars) == 30
    assert bars[-1].c == pytest.approx(eng._prices["AAPL"], rel=1e-9)
    assert all(b.h >= b.o and b.h >= b.c for b in bars)   # OHLC sanity
    assert all(b.low <= b.o and b.low <= b.c for b in bars)


def test_history_is_deterministic_per_ticker():
    eng = SimEngine(seed=3)
    eng.step(["AAPL"])
    a = eng.history("AAPL", days=20, end_ms=1_700_000_000_000)
    b = eng.history("AAPL", days=20, end_ms=1_700_000_000_000)
    assert a == b


def test_history_bars_are_time_ordered():
    eng = SimEngine(seed=5)
    eng.step(["MSFT"])
    bars = eng.history("MSFT", days=15, end_ms=1_700_000_000_000)
    times = [b.t for b in bars]
    assert times == sorted(times)       # oldest first, strictly increasing


def test_same_sector_moves_correlate():
    eng = SimEngine(seed=99)
    same = cross = 0
    prev = eng.step(["AAPL", "MSFT", "JPM"])
    for _ in range(500):
        nxt = eng.step(["AAPL", "MSFT", "JPM"])
        d = {k: nxt[k] - prev[k] for k in nxt}
        same += (d["AAPL"] > 0) == (d["MSFT"] > 0)       # both tech
        cross += (d["AAPL"] > 0) == (d["JPM"] > 0)        # tech vs financial
        prev = nxt
    assert same > cross                                   # tech co-moves more
