import asyncio

from market.cache import PriceCache
from market.feed import MarketFeed, _direction
from market.simulator import SimulatedSource
from market.source import MarketDataSource
from market.types import Bar


def test_direction_helper():
    assert _direction(2.0, 1.0) == "up"
    assert _direction(1.0, 2.0) == "down"
    assert _direction(1.0, 1.0) == "flat"


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


async def test_feed_empty_watchlist_is_noop():
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=1), cache,
                      get_active_tickers=lambda: [])
    await feed.prime()
    assert await cache.snapshot() == {}


async def test_feed_reads_tickers_fresh_each_cycle():
    """Watchlist edits take effect on the next cycle with no restart."""
    cache = PriceCache()
    active = ["AAPL"]
    feed = MarketFeed(SimulatedSource(seed=2), cache,
                      get_active_tickers=lambda: list(active))
    await feed.prime()
    assert set((await cache.snapshot()).keys()) == {"AAPL"}
    active.append("MSFT")
    await feed._tick_once()
    assert set((await cache.snapshot()).keys()) == {"AAPL", "MSFT"}


class _BoomSource(MarketDataSource):
    poll_interval_seconds = 0.01

    async def get_prices(self, tickers):
        raise RuntimeError("source blew up")

    async def get_history(self, ticker, days=90) -> list[Bar]:
        return []


async def test_feed_survives_source_exception():
    cache = PriceCache()
    feed = MarketFeed(_BoomSource(), cache, get_active_tickers=lambda: ["AAPL"])
    await feed.prime()          # must not raise; cache simply stays empty
    assert await cache.get("AAPL") is None


async def test_start_and_stop_lifecycle():
    cache = PriceCache()
    feed = MarketFeed(SimulatedSource(seed=8), cache,
                      get_active_tickers=lambda: ["AAPL"])
    feed.start()
    await asyncio.sleep(0.05)    # let the loop run a couple of cycles
    await feed.stop()           # cancels the task cleanly, no leaked task
    assert feed._task.cancelled() or feed._task.done()
    assert await cache.get("AAPL") is not None
