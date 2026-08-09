import pytest

from db import connection as connection_module
from db.portfolio import (
    compute_valuation,
    execute_trade,
    get_portfolio,
    get_positions,
    get_profile,
    get_trades,
)
from db.reads import load_active_tickers
from db.snapshots import get_snapshots, record_snapshot

PRICES = {"AAPL": 100.0, "MSFT": 400.0}


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    return tmp_path / "finally.db"


def cash(user_id="default"):
    return get_profile(user_id)["cash_balance"]


def test_buy_updates_cash_position_trade_and_snapshot(temp_db):
    result = execute_trade("default", "AAPL", "buy", 10, PRICES)

    assert result.success
    assert result.price == 100.0
    assert result.cash_balance == pytest.approx(9000.0)
    assert result.total_value == pytest.approx(10000.0)
    assert cash() == pytest.approx(9000.0)

    positions = get_positions()
    assert positions == [
        {
            "ticker": "AAPL",
            "quantity": 10.0,
            "avg_cost": 100.0,
            "updated_at": positions[0]["updated_at"],
        }
    ]

    trades = get_trades()
    assert len(trades) == 1
    assert (trades[0]["ticker"], trades[0]["side"], trades[0]["quantity"]) == ("AAPL", "buy", 10.0)

    snapshots = get_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == pytest.approx(10000.0)


def test_buy_is_case_insensitive_on_ticker(temp_db):
    result = execute_trade("default", " aapl ", "buy", 1, PRICES)
    assert result.success
    assert result.ticker == "AAPL"
    assert get_positions()[0]["ticker"] == "AAPL"


def test_second_buy_recomputes_weighted_average_cost(temp_db):
    execute_trade("default", "AAPL", "buy", 10, {"AAPL": 100.0})
    execute_trade("default", "AAPL", "buy", 30, {"AAPL": 200.0})

    position = get_positions()[0]
    assert position["quantity"] == pytest.approx(40.0)
    # (10 * 100 + 30 * 200) / 40
    assert position["avg_cost"] == pytest.approx(175.0)
    assert cash() == pytest.approx(10000.0 - 1000.0 - 6000.0)


def test_partial_sell_keeps_average_cost(temp_db):
    execute_trade("default", "AAPL", "buy", 10, {"AAPL": 100.0})
    result = execute_trade("default", "AAPL", "sell", 4, {"AAPL": 150.0})

    assert result.success
    position = get_positions()[0]
    assert position["quantity"] == pytest.approx(6.0)
    assert position["avg_cost"] == pytest.approx(100.0)
    assert cash() == pytest.approx(9000.0 + 600.0)


def test_full_sell_deletes_the_position(temp_db):
    execute_trade("default", "AAPL", "buy", 10, {"AAPL": 100.0})
    result = execute_trade("default", "AAPL", "sell", 10, {"AAPL": 120.0})

    assert result.success
    assert get_positions() == []
    assert "AAPL" in load_active_tickers()  # still on the seeded watchlist
    assert cash() == pytest.approx(10200.0)


def test_full_sell_of_unwatched_ticker_drops_out_of_active_tickers(temp_db):
    execute_trade("default", "PYPL", "buy", 2, {"PYPL": 60.0})
    assert "PYPL" in load_active_tickers()

    execute_trade("default", "PYPL", "sell", 2, {"PYPL": 60.0})
    assert "PYPL" not in load_active_tickers()


def test_fractional_shares_are_supported(temp_db):
    result = execute_trade("default", "AAPL", "buy", 0.5, {"AAPL": 100.0})
    assert result.success
    assert get_positions()[0]["quantity"] == pytest.approx(0.5)
    assert cash() == pytest.approx(9950.0)


def test_insufficient_cash_returns_error_and_changes_nothing(temp_db):
    result = execute_trade("default", "MSFT", "buy", 100, PRICES)

    assert not result.success
    assert "Insufficient cash" in result.error
    assert cash() == pytest.approx(10000.0)
    assert get_positions() == []
    assert get_trades() == []
    assert get_snapshots() == []


def test_buy_spending_exactly_all_cash_succeeds(temp_db):
    result = execute_trade("default", "AAPL", "buy", 100, {"AAPL": 100.0})
    assert result.success
    assert cash() == pytest.approx(0.0)


def test_insufficient_shares_returns_error_and_changes_nothing(temp_db):
    execute_trade("default", "AAPL", "buy", 5, PRICES)
    before = cash()

    result = execute_trade("default", "AAPL", "sell", 6, PRICES)

    assert not result.success
    assert "Insufficient shares" in result.error
    assert cash() == pytest.approx(before)
    assert get_positions()[0]["quantity"] == pytest.approx(5.0)
    assert len(get_trades()) == 1


def test_selling_a_ticker_with_no_position_fails(temp_db):
    result = execute_trade("default", "AAPL", "sell", 1, PRICES)
    assert not result.success
    assert "Insufficient shares" in result.error


@pytest.mark.parametrize("quantity", [0, -5, "abc", None])
def test_non_positive_quantity_is_rejected(temp_db, quantity):
    result = execute_trade("default", "AAPL", "buy", quantity, PRICES)
    assert not result.success
    assert result.error == "Quantity must be greater than zero"


def test_unknown_side_is_rejected(temp_db):
    result = execute_trade("default", "AAPL", "short", 1, PRICES)
    assert not result.success
    assert result.error == "Side must be 'buy' or 'sell'"


def test_missing_price_is_rejected(temp_db):
    result = execute_trade("default", "ZZZZ", "buy", 1, PRICES)
    assert not result.success
    assert result.error == "No price available for ZZZZ"


def test_price_map_accepts_price_tick_objects(temp_db):
    from market.types import PriceTick

    tick = PriceTick(
        ticker="AAPL",
        price=100.0,
        previous_price=99.0,
        direction="up",
        timestamp="2026-08-09T00:00:00+00:00",
    )
    result = execute_trade("default", "AAPL", "buy", 2, {"AAPL": tick})

    assert result.success
    assert result.price == pytest.approx(100.0)


def test_compute_valuation_math():
    positions = [
        {"ticker": "AAPL", "quantity": 10.0, "avg_cost": 100.0},
        {"ticker": "MSFT", "quantity": 2.0, "avg_cost": 500.0},
    ]
    valuation = compute_valuation(positions, {"AAPL": 120.0, "MSFT": 400.0}, cash=1000.0)

    assert valuation["cash"] == pytest.approx(1000.0)
    assert valuation["positions_value"] == pytest.approx(1200.0 + 800.0)
    assert valuation["cost_basis"] == pytest.approx(1000.0 + 1000.0)
    assert valuation["unrealized_pl"] == pytest.approx(0.0)
    assert valuation["total_value"] == pytest.approx(3000.0)

    apple, microsoft = valuation["positions"]
    assert apple["market_value"] == pytest.approx(1200.0)
    assert apple["unrealized_pl"] == pytest.approx(200.0)
    assert apple["pct_change"] == pytest.approx(20.0)
    assert microsoft["unrealized_pl"] == pytest.approx(-200.0)
    assert microsoft["pct_change"] == pytest.approx(-20.0)


def test_compute_valuation_falls_back_to_avg_cost_when_price_missing():
    positions = [{"ticker": "AAPL", "quantity": 3.0, "avg_cost": 50.0}]
    valuation = compute_valuation(positions, {}, cash=0.0)

    assert valuation["positions"][0]["current_price"] == pytest.approx(50.0)
    assert valuation["positions"][0]["unrealized_pl"] == pytest.approx(0.0)
    assert valuation["total_value"] == pytest.approx(150.0)


def test_compute_valuation_with_no_positions():
    valuation = compute_valuation([], {}, cash=10000.0)
    assert valuation["total_value"] == pytest.approx(10000.0)
    assert valuation["positions"] == []


def test_get_portfolio_reads_cash_and_positions(temp_db):
    execute_trade("default", "AAPL", "buy", 10, {"AAPL": 100.0})

    portfolio = get_portfolio({"AAPL": 110.0})

    assert portfolio["cash"] == pytest.approx(9000.0)
    assert portfolio["positions_value"] == pytest.approx(1100.0)
    assert portfolio["total_value"] == pytest.approx(10100.0)
    assert portfolio["unrealized_pl"] == pytest.approx(100.0)


def test_snapshots_are_chronological_and_limitable(temp_db):
    for value in (10000.0, 10100.0, 10200.0):
        record_snapshot("default", value)

    assert [s["total_value"] for s in get_snapshots()] == [10000.0, 10100.0, 10200.0]
    assert [s["total_value"] for s in get_snapshots(limit=2)] == [10100.0, 10200.0]


def test_snapshot_after_trade_uses_post_trade_valuation(temp_db):
    execute_trade("default", "AAPL", "buy", 10, {"AAPL": 100.0})
    # Cash 9000 + 10 shares valued at the same 100.0 fill price.
    assert get_snapshots()[-1]["total_value"] == pytest.approx(10000.0)
