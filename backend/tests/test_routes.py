import json

import pytest
from fastapi.testclient import TestClient

from main import app

from market.routes import MAX_HISTORY_DAYS


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from db import connection as connection_module

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_history_returns_bar_shape(client):
    resp = client.get("/api/history/AAPL", params={"days": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "AAPL"
    assert len(body["bars"]) == 5
    bar = body["bars"][0]
    assert set(bar) == {"t", "o", "h", "l", "c", "v"}


def test_history_uppercases_ticker(client):
    resp = client.get("/api/history/aapl", params={"days": 3})
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "AAPL"


def test_history_clamps_excessive_days(client):
    resp = client.get("/api/history/AAPL", params={"days": 1_000_000})
    assert resp.status_code == 200
    assert len(resp.json()["bars"]) == MAX_HISTORY_DAYS


def test_history_clamps_non_positive_days_to_one(client):
    resp = client.get("/api/history/AAPL", params={"days": 0})
    assert resp.status_code == 200
    assert len(resp.json()["bars"]) == 1


class _NeverDisconnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_sse_generator_emits_price_tick_frames():
    # Exercise the SSE generator directly rather than through TestClient: the
    # endpoint is an infinite stream, and closing it over the test transport
    # would block. anext + aclose gives a clean, fast smoke test of the frames.
    from market.cache import PriceCache
    from market.routes import _price_events
    from market.types import PriceTick

    cache = PriceCache()
    await cache.update(PriceTick("AAPL", 190.0, 189.0, "up",
                                 "2026-08-08T00:00:00+00:00"))

    gen = _price_events(_NeverDisconnectedRequest(), cache)
    try:
        frames = [await anext(gen) for _ in range(2)]  # retry line, then data
    finally:
        await gen.aclose()

    assert frames[0].startswith("retry:")
    assert frames[1].startswith("data: ")
    payload = json.loads(frames[1][len("data: "):].strip())
    assert payload["ticker"] == "AAPL"
    assert set(payload) == {
        "ticker", "price", "previous_price", "direction", "timestamp",
    }
