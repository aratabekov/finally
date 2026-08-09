import pytest
from fastapi.testclient import TestClient

from main import app
from market.types import PriceTick

# Fixed prices so trade math is exact: the live simulator never reaches these
# routes in tests because the cache is swapped for a stub after startup.
TICKS = {
    "AAPL": PriceTick("AAPL", 200.0, 199.0, "up", "2026-08-09T00:00:00+00:00"),
    "GOOGL": PriceTick("GOOGL", 100.0, 101.0, "down", "2026-08-09T00:00:00+00:00"),
}


class StubCache:
    """Stands in for PriceCache — routes and the snapshot task only snapshot()."""

    def __init__(self, ticks):
        self._ticks = ticks

    async def snapshot(self):
        return dict(self._ticks)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from db import connection as connection_module
    from snapshots.task import SnapshotTask

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    # Keep the periodic snapshot loop out of the way so snapshot rows only ever
    # come from the trades a test makes.
    monkeypatch.setattr(SnapshotTask, "start", lambda self: None)
    with TestClient(app) as c:
        c.app.state.price_cache = StubCache(TICKS)
        yield c


def _buy(client, ticker, quantity):
    return client.post(
        "/api/portfolio/trade",
        json={"ticker": ticker, "quantity": quantity, "side": "buy"},
    )


def test_portfolio_returns_seed_state(client):
    body = client.get("/api/portfolio").json()
    assert body["cash"] == 10000.0
    assert body["total_value"] == 10000.0
    assert body["positions"] == []


def test_buy_updates_cash_and_positions(client):
    resp = _buy(client, "AAPL", 10)
    assert resp.status_code == 200
    result = resp.json()
    assert result["success"] is True
    assert result["price"] == 200.0
    assert result["cash_balance"] == 8000.0
    assert result["total_value"] == 10000.0

    body = client.get("/api/portfolio").json()
    assert body["cash"] == 8000.0
    (position,) = body["positions"]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == 10
    assert position["avg_cost"] == 200.0
    assert position["market_value"] == 2000.0


def test_sell_closes_position_and_returns_cash(client):
    _buy(client, "AAPL", 5)
    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
    )
    assert resp.status_code == 200
    assert resp.json()["cash_balance"] == 10000.0
    assert client.get("/api/portfolio").json()["positions"] == []


def test_buy_with_insufficient_cash_returns_400(client):
    resp = _buy(client, "AAPL", 1000)
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"].startswith("Insufficient cash")


def test_sell_more_than_held_returns_400(client):
    _buy(client, "AAPL", 2)
    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 3, "side": "sell"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"].startswith("Insufficient shares")


def test_trade_without_price_returns_400(client):
    resp = _buy(client, "ZZZZ", 1)
    assert resp.status_code == 400
    assert resp.json()["error"] == "No price available for ZZZZ"


def test_trade_with_bad_side_returns_400(client):
    resp = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "hodl"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "Side must be 'buy' or 'sell'"


def test_trade_rejects_malformed_body(client):
    resp = client.post("/api/portfolio/trade", json={"ticker": "AAPL"})
    assert resp.status_code == 422


def test_history_records_a_snapshot_per_trade(client):
    assert client.get("/api/portfolio/history").json() == []
    _buy(client, "GOOGL", 1)
    history = client.get("/api/portfolio/history").json()
    assert len(history) == 1
    assert set(history[0]) == {"total_value", "recorded_at"}
    assert history[0]["total_value"] == 10000.0


@pytest.mark.asyncio
async def test_snapshot_task_records_current_value(monkeypatch, tmp_path):
    from db import connection as connection_module
    from db.snapshots import get_snapshots
    from snapshots.task import SnapshotTask

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    await SnapshotTask(StubCache(TICKS)).record_once()

    (snapshot,) = get_snapshots()
    assert snapshot["total_value"] == 10000.0
