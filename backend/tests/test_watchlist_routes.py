import pytest
from fastapi.testclient import TestClient

from db.connection import DEFAULT_WATCHLIST
from main import app
from market.types import PriceTick

# Only AAPL has a cached tick, so the rest of the seed watchlist exercises the
# "on the watchlist but not yet priced" path.
TICKS = {"AAPL": PriceTick("AAPL", 200.0, 199.0, "up", "2026-08-09T00:00:00+00:00")}


class StubCache:
    def __init__(self, ticks):
        self._ticks = ticks

    async def snapshot(self):
        return dict(self._ticks)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from db import connection as connection_module
    from snapshots.task import SnapshotTask

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    monkeypatch.setattr(SnapshotTask, "start", lambda self: None)
    with TestClient(app) as c:
        c.app.state.price_cache = StubCache(TICKS)
        yield c


def test_watchlist_returns_seed_tickers_with_prices(client):
    body = client.get("/api/watchlist").json()
    assert [entry["ticker"] for entry in body] == DEFAULT_WATCHLIST
    assert body[0] == {
        "ticker": "AAPL",
        "price": 200.0,
        "previous_price": 199.0,
        "direction": "up",
        "timestamp": "2026-08-09T00:00:00+00:00",
    }


def test_unpriced_ticker_comes_back_with_nulls(client):
    body = client.get("/api/watchlist").json()
    google = next(entry for entry in body if entry["ticker"] == "GOOGL")
    assert google == {
        "ticker": "GOOGL",
        "price": None,
        "previous_price": None,
        "direction": "flat",
        "timestamp": None,
    }


def test_add_ticker_normalizes_and_appends(client):
    resp = client.post("/api/watchlist", json={"ticker": " pypl "})
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "PYPL", "added": True}

    tickers = [entry["ticker"] for entry in client.get("/api/watchlist").json()]
    assert tickers[-1] == "PYPL"


def test_add_existing_ticker_is_idempotent(client):
    assert client.post("/api/watchlist", json={"ticker": "AAPL"}).json()["added"] is False
    tickers = [entry["ticker"] for entry in client.get("/api/watchlist").json()]
    assert tickers == DEFAULT_WATCHLIST


def test_add_blank_ticker_returns_400(client):
    resp = client.post("/api/watchlist", json={"ticker": "  "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Ticker is required"


def test_remove_ticker(client):
    resp = client.delete("/api/watchlist/tsla")
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "TSLA", "removed": True}

    tickers = [entry["ticker"] for entry in client.get("/api/watchlist").json()]
    assert "TSLA" not in tickers


def test_remove_unknown_ticker_reports_false(client):
    resp = client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 200
    assert resp.json() == {"ticker": "ZZZZ", "removed": False}
