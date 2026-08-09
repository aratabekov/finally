from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat import llm as llm_module
from chat.actions import compose_message
from chat.routes import router as chat_router
from chat.schema import AssistantReply, parse_reply
from market.types import PriceTick

# AAPL arrives as a PriceTick (what the real cache holds); the rest as floats,
# since the DB layer accepts either.
PRICES = {
    "AAPL": PriceTick("AAPL", 190.0, 189.0, "up", "2026-08-09T00:00:00+00:00"),
    "MSFT": 400.0,
    "TSLA": 250.0,
}


class _FakeCache:
    async def snapshot(self):
        return dict(PRICES)


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from db import connection as connection_module

    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    monkeypatch.setattr(
        llm_module, "settings", replace(llm_module.settings, llm_mock=True)
    )

    app = FastAPI()
    app.include_router(chat_router)
    app.state.price_cache = _FakeCache()
    with TestClient(app) as c:
        yield c


def _post(client, message: str) -> dict:
    resp = client.post("/api/chat", json={"message": message})
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- mock mode, end to end -------------------------------------------------


def test_plain_question_returns_the_canned_analysis(client):
    body = _post(client, "how am I doing?")
    assert body["message"] == (
        "Mock analysis: total value $10,000.00, cash $10,000.00, "
        "0 open positions, unrealized P&L $0.00."
    )
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert body["errors"] == []


def test_buy_intent_executes_a_trade(client):
    from db.portfolio import get_positions, get_profile

    body = _post(client, "buy 5 AAPL")
    trade = body["trades"][0]
    assert (trade["success"], trade["ticker"], trade["side"]) == (True, "AAPL", "buy")
    assert trade["quantity"] == 5
    assert trade["price"] == 190.0
    assert body["message"] == "Executing buy 5 AAPL at the current market price."

    assert get_profile()["cash_balance"] == pytest.approx(10_000.0 - 5 * 190.0)
    assert get_positions()[0]["ticker"] == "AAPL"


def test_sell_intent_executes_a_trade(client):
    _post(client, "buy 4 MSFT")
    trade = _post(client, "sell 4 shares of MSFT")["trades"][0]
    assert (trade["success"], trade["side"], trade["quantity"]) == (True, "sell", 4)

    from db.portfolio import get_positions

    assert get_positions() == []


def test_failed_trade_surfaces_the_validation_error(client):
    body = _post(client, "buy 1000 AAPL")
    trade = body["trades"][0]
    assert trade["success"] is False
    assert trade["error"].startswith("Insufficient cash")
    # The attempt is still described, not just the error.
    assert (trade["ticker"], trade["side"], trade["quantity"]) == ("AAPL", "buy", 1000)
    assert body["errors"] == [trade["error"]]
    assert "Could not complete: Insufficient cash" in body["message"]


def test_unpriced_ticker_fails_cleanly(client):
    body = _post(client, "buy 1 ZZZZ")
    assert body["errors"] == ["No price available for ZZZZ"]


def test_watchlist_add(client):
    from db.watchlist import list_watchlist

    body = _post(client, "add PYPL to the watchlist")
    assert body["watchlist_changes"] == [
        {
            "ticker": "PYPL",
            "action": "add",
            "success": True,
            "changed": True,
            "error": None,
        }
    ]
    assert body["message"] == "Adding PYPL to the watchlist."
    assert "PYPL" in list_watchlist()


def test_watchlist_remove(client):
    from db.watchlist import list_watchlist

    body = _post(client, "remove AAPL from my watchlist")
    assert body["watchlist_changes"][0]["action"] == "remove"
    assert "AAPL" not in list_watchlist()


def test_watchlist_word_is_required_for_a_watchlist_change(client):
    body = _post(client, "should I add PYPL?")
    assert body["watchlist_changes"] == []


def test_trade_and_watchlist_change_in_one_message(client):
    body = _post(client, "buy 2 TSLA and add PYPL to the watchlist")
    assert body["trades"][0]["ticker"] == "TSLA"
    assert body["watchlist_changes"][0]["ticker"] == "PYPL"


# --- persistence -----------------------------------------------------------


def test_both_sides_of_the_turn_are_persisted_with_actions(client):
    from db.chat import get_recent_chat

    _post(client, "buy 5 AAPL")
    history = get_recent_chat()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "buy 5 AAPL"
    assert history[0]["actions"] is None
    assert history[1]["actions"]["trades"][0]["ticker"] == "AAPL"


def test_history_endpoint_returns_the_conversation(client):
    _post(client, "how am I doing?")
    messages = client.get("/api/chat/history").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_empty_message_is_rejected(client):
    assert client.post("/api/chat", json={"message": "   "}).status_code == 400


def test_content_key_is_accepted(client):
    resp = client.post("/api/chat", json={"content": "how am I doing?"})
    assert resp.status_code == 200
    assert resp.json()["message"].startswith("Mock analysis:")


# --- structured output parsing --------------------------------------------


def test_parse_reply_accepts_the_full_schema():
    reply = parse_reply(
        '{"message": "done", '
        '"trades": [{"ticker": "aapl", "side": "buy", "quantity": 3}], '
        '"watchlist_changes": [{"ticker": "pypl", "action": "add"}]}'
    )
    assert reply.message == "done"
    assert reply.trades[0].ticker == "AAPL"          # normalized
    assert reply.watchlist_changes[0].ticker == "PYPL"


def test_parse_reply_accepts_a_message_only_payload():
    reply = parse_reply('{"message": "just talking"}')
    assert (reply.trades, reply.watchlist_changes) == ([], [])


def test_parse_reply_salvages_the_message_when_actions_are_malformed():
    reply = parse_reply('{"message": "hi", "trades": "not an array"}')
    assert reply.message == "hi"
    assert reply.trades == []      # dropped rather than half-executed


def test_parse_reply_handles_non_json():
    assert parse_reply("sorry, plain text").message == "sorry, plain text"


def test_parse_reply_handles_empty_and_wrong_shapes():
    assert parse_reply("").message.startswith("I could not read")
    assert parse_reply(None).message.startswith("I could not read")
    assert parse_reply("[1, 2, 3]").message.startswith("I could not read")


def test_compose_message_appends_each_error():
    assert compose_message("ok", ["boom", "bang"]) == (
        "ok\n\nCould not complete: boom\n\nCould not complete: bang"
    )


# --- the real LLM path (no network: the completion call is stubbed) --------


async def test_live_path_calls_cerebras_with_structured_output(monkeypatch):
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"message": "hi"}'))]
        )

    monkeypatch.setattr(llm_module, "_completion", fake_completion)
    monkeypatch.setattr(
        llm_module, "settings", replace(llm_module.settings, llm_mock=False)
    )

    context = {
        "cash": 10_000.0,
        "positions_value": 0.0,
        "total_value": 10_000.0,
        "unrealized_pl": 0.0,
        "positions": [],
        "watchlist": [{"ticker": "AAPL", "price": 190.0}],
    }
    reply = await llm_module.generate_reply("hello", context, [])

    assert reply.message == "hi"
    assert captured["model"] == "openrouter/openai/gpt-oss-120b"
    assert captured["extra_body"] == {"provider": {"order": ["cerebras"]}}
    assert captured["response_format"] is AssistantReply
    roles = [m["role"] for m in captured["messages"]]
    assert roles == ["system", "system", "user"]
    assert "FinAlly" in captured["messages"][0]["content"]
    assert "$10,000.00" in captured["messages"][1]["content"]


async def test_mock_mode_never_calls_the_model(monkeypatch):
    async def explode(**kwargs):
        raise AssertionError("mock mode must not reach the network")

    monkeypatch.setattr(llm_module, "_completion", explode)
    monkeypatch.setattr(
        llm_module, "settings", replace(llm_module.settings, llm_mock=True)
    )

    context = {
        "cash": 1.0,
        "positions_value": 0.0,
        "total_value": 1.0,
        "unrealized_pl": 0.0,
        "positions": [],
        "watchlist": [],
    }
    assert (await llm_module.generate_reply("hi", context, [])).message.startswith(
        "Mock analysis:"
    )
