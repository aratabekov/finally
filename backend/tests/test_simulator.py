import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from market.gbm import SimEngine


def test_determinism():
    a = SimEngine(seed=42).step(["AAPL", "MSFT"])
    b = SimEngine(seed=42).step(["AAPL", "MSFT"])
    assert a == b


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


def test_history_last_close_matches_live_price():
    eng = SimEngine(seed=3)
    eng.step(["AAPL"])                   # establish a live price
    bars = eng.history("AAPL", days=30, end_ms=1_700_000_000_000)
    assert len(bars) == 30
    assert bars[-1].c == pytest.approx(eng._prices["AAPL"], rel=1e-9)
    assert all(b.h >= b.o and b.h >= b.c for b in bars)   # OHLC sanity
    assert all(b.low <= b.o and b.low <= b.c for b in bars)


def test_history_bar_timestamps_are_business_days_and_ordered():
    eng = SimEngine(seed=11)
    eng.step(["AAPL"])
    bars = eng.history("AAPL", days=10, end_ms=1_700_000_000_000)
    assert bars[-1].t == 1_700_000_000_000            # last bar anchored at "now"

    ts = [b.t for b in bars]
    assert ts == sorted(ts) and len(set(ts)) == len(ts)  # strictly ascending
    # Every gap is a whole number of calendar days, and no bar lands on a weekend.
    diffs = [b - a for a, b in zip(ts, ts[1:])]
    assert all(d % 86_400_000 == 0 and d >= 86_400_000 for d in diffs)
    for t in ts:
        weekday = datetime.fromtimestamp(t / 1000, tz=timezone.utc).weekday()
        assert weekday < 5                                # Mon-Fri only


def test_history_deterministic_per_ticker():
    eng = SimEngine(seed=3)
    eng.step(["AAPL"])
    a = eng.history("AAPL", days=15, end_ms=1_700_000_000_000)
    b = eng.history("AAPL", days=15, end_ms=1_700_000_000_000)
    assert a == b


# Reproduced in two subprocesses with different PYTHONHASHSEED values. Because
# the old implementation seeded history off Python's salted hash(), it produced
# a different past on every process; the crc32-based seeding must not.
_HISTORY_SCRIPT = (
    "from market.gbm import SimEngine\n"
    "eng = SimEngine(seed=42)\n"
    "eng.step(['AAPL'])\n"
    "print([b.c for b in eng.history('AAPL', days=20, end_ms=1_700_000_000_000)])\n"
)


def _run_history(hashseed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hashseed}
    out = subprocess.run(
        [sys.executable, "-c", _HISTORY_SCRIPT],
        cwd=Path(__file__).resolve().parent.parent,   # backend/, so `market` imports
        env=env, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_history_is_deterministic_across_processes():
    assert _run_history("1") == _run_history("2")


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


def test_history_non_positive_days_returns_empty():
    eng = SimEngine(seed=1)
    eng.step(["AAPL"])
    assert eng.history("AAPL", days=0, end_ms=1_700_000_000_000) == []
    assert eng.history("AAPL", days=-5, end_ms=1_700_000_000_000) == []


def test_history_volume_is_float():
    eng = SimEngine(seed=1)
    eng.step(["AAPL"])
    bars = eng.history("AAPL", days=5, end_ms=1_700_000_000_000)
    assert all(isinstance(b.v, float) for b in bars)


def test_price_state_persists_across_steps():
    eng = SimEngine(seed=21)
    eng.step(["AAPL"])
    second = eng.step(["AAPL"])["AAPL"]
    assert eng._prices["AAPL"] == second
