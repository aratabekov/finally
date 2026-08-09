import pytest

from market.cache import PriceCache
from market.feed import MarketFeed
from market.simulator import SimulatedSource
from market.source import MarketDataSource
from market.types import Bar


@pytest.mark.asyncio
async def test_feed_populates_cache_and_computes_direction():
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=5), cache,
                      get_active_tickers=lambda: ["AAPL"])
    await feed.prime()          # first fill: previous == price, direction flat
    first = await cache.get("AAPL")
    assert first is not None and first.direction == "flat"

    await feed._tick_once()     # second step: direction reflects the move
    second = await cache.get("AAPL")
    assert second.previous_price == first.price
    assert second.direction in ("up", "down", "flat")


@pytest.mark.asyncio
async def test_feed_noop_when_no_active_tickers():
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=5), cache, get_active_tickers=lambda: [])
    await feed.prime()
    assert await cache.snapshot() == {}


@pytest.mark.asyncio
async def test_feed_evicts_tickers_that_leave_the_active_set():
    # Active set = watchlist union open positions. A ticker that drops out of
    # it must stop being priced, or it stays tradeable at a frozen price.
    active = ["AAPL", "ZZZZ"]
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=5), cache,
                      get_active_tickers=lambda: active)
    await feed.prime()
    assert set(await cache.snapshot()) == {"AAPL", "ZZZZ"}

    active.remove("ZZZZ")       # de-watchlisted, no open position
    await feed._tick_once()
    snapshot = await cache.snapshot()
    assert "ZZZZ" not in snapshot
    assert "AAPL" in snapshot   # still active, so it keeps its live price


@pytest.mark.asyncio
async def test_feed_keeps_pricing_a_held_ticker_after_it_leaves_the_watchlist(
    tmp_path, monkeypatch
):
    # load_active_tickers keeps tickers with an open position, so the position
    # never loses its price even once it is off the watchlist.
    from db import connection as connection_module
    from db.reads import load_active_tickers

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=5), cache,
                      get_active_tickers=load_active_tickers)
    conn = connection_module.get_connection()
    try:
        conn.execute("DELETE FROM watchlist")
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES ('p1', 'default', 'AAPL', 5, 100.0, '2026-08-09T00:00:00+00:00')"
        )
        conn.commit()
    finally:
        conn.close()

    await feed.prime()
    assert set(await cache.snapshot()) == {"AAPL"}


class _FlakySource(MarketDataSource):
    poll_interval_seconds = 0.01

    async def get_prices(self, tickers: list[str]) -> dict[str, float]:
        raise RuntimeError("boom")

    async def get_history(self, ticker: str, days: int = 90) -> list[Bar]:
        return []


@pytest.mark.asyncio
async def test_feed_survives_source_exception():
    cache = PriceCache()
    feed = MarketFeed(_FlakySource(), cache, get_active_tickers=lambda: ["AAPL"])
    await feed.prime()          # should not raise
    assert await cache.get("AAPL") is None


@pytest.mark.asyncio
async def test_feed_start_and_stop_cleans_up_task():
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=1), cache, get_active_tickers=lambda: ["AAPL"])
    feed.start()
    await feed.stop()
    assert feed._task.cancelled() or feed._task.done()
