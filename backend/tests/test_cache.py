from market.cache import PriceCache
from market.types import PriceTick


def _tick(ticker: str, price: float) -> PriceTick:
    return PriceTick(ticker=ticker, price=price, previous_price=price,
                     direction="flat", timestamp="2026-08-08T00:00:00+00:00")


async def test_update_and_get():
    cache = PriceCache()
    assert await cache.get("AAPL") is None
    await cache.update(_tick("AAPL", 190.0))
    got = await cache.get("AAPL")
    assert got is not None and got.price == 190.0


async def test_update_overwrites_same_ticker():
    cache = PriceCache()
    await cache.update(_tick("AAPL", 190.0))
    await cache.update(_tick("AAPL", 191.0))
    got = await cache.get("AAPL")
    assert got.price == 191.0


async def test_snapshot_returns_independent_copy():
    cache = PriceCache()
    await cache.update(_tick("AAPL", 190.0))
    snap = await cache.snapshot()
    assert snap == {"AAPL": await cache.get("AAPL")}
    # Mutating the returned dict must not affect the cache.
    snap["MSFT"] = _tick("MSFT", 420.0)
    assert await cache.get("MSFT") is None
