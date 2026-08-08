import httpx
from fastapi import FastAPI

from market.cache import PriceCache
from market.routes import _price_events, router
from market.simulator import SimulatedSource
from market.types import PriceTick


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.price_cache = PriceCache()
    app.state.market_source = SimulatedSource(seed=42)
    return app


async def test_history_route_returns_ohlc_shape():
    app = _make_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://test") as client:
        resp = await client.get("/api/history/aapl", params={"days": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "AAPL"            # normalized to upper-case
    assert len(body["bars"]) == 10
    bar = body["bars"][0]
    assert set(bar) == {"t", "o", "h", "l", "c", "v"}   # 'low' mapped back to 'l'


class _FakeRequest:
    """Minimal stand-in for a Starlette Request for the SSE generator."""

    def __init__(self, disconnect_after: int) -> None:
        self._calls = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._calls += 1
        return self._calls > self._disconnect_after


def _tick(ticker: str, price: float, ts: str) -> PriceTick:
    return PriceTick(ticker=ticker, price=price, previous_price=price,
                     direction="up", timestamp=ts)


async def test_sse_emits_initial_snapshot_then_only_changes():
    cache = PriceCache()
    await cache.update(_tick("AAPL", 190.0, "t1"))
    request = _FakeRequest(disconnect_after=2)

    events = []
    async for chunk in _price_events(request, cache):
        events.append(chunk)
        # After the first cache read, change AAPL so the next cycle re-emits it,
        # then add MSFT which should also appear.
        if len(events) == 2:  # 'retry' + first AAPL tick
            await cache.update(_tick("AAPL", 191.0, "t2"))
            await cache.update(_tick("MSFT", 420.0, "t2"))

    joined = "".join(events)
    assert events[0].startswith("retry:")          # reconnection hint first
    assert '"ticker": "AAPL"' in joined
    assert '"ticker": "MSFT"' in joined
    # AAPL emitted twice (t1 then t2), never a duplicate for the same timestamp.
    assert joined.count('"AAPL"') == 2


async def test_sse_stops_on_disconnect():
    cache = PriceCache()
    await cache.update(_tick("AAPL", 190.0, "t1"))
    request = _FakeRequest(disconnect_after=0)   # disconnected immediately

    events = [chunk async for chunk in _price_events(request, cache)]
    # Only the initial retry hint is yielded before the loop notices disconnect.
    assert events == ["retry: 2000\n\n"]
