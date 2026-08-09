import pytest

from db import connection as connection_module
from db.chat import add_chat_message, get_recent_chat
from db.watchlist import add_watchlist, list_watchlist, remove_watchlist


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection_module, "DB_PATH", tmp_path / "finally.db")
    return tmp_path / "finally.db"


def test_watchlist_starts_with_the_default_tickers(temp_db):
    assert list_watchlist() == connection_module.DEFAULT_WATCHLIST


def test_add_watchlist_appends_and_is_idempotent(temp_db):
    assert add_watchlist("default", "PYPL") is True
    assert list_watchlist()[-1] == "PYPL"

    assert add_watchlist("default", "PYPL") is False
    assert list_watchlist().count("PYPL") == 1


def test_add_watchlist_normalizes_the_ticker(temp_db):
    assert add_watchlist("default", " pypl ") is True
    assert "PYPL" in list_watchlist()
    assert add_watchlist("default", "PYPL") is False


def test_remove_watchlist(temp_db):
    assert remove_watchlist("default", "aapl") is True
    assert "AAPL" not in list_watchlist()


def test_remove_watchlist_missing_ticker_returns_false(temp_db):
    assert remove_watchlist("default", "ZZZZ") is False
    assert list_watchlist() == connection_module.DEFAULT_WATCHLIST


def test_chat_history_is_chronological(temp_db):
    add_chat_message("default", "user", "how am I doing?")
    add_chat_message("default", "assistant", "up 2 percent")

    history = get_recent_chat()
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "how am I doing?"),
        ("assistant", "up 2 percent"),
    ]
    assert history[0]["actions"] is None


def test_chat_actions_round_trip_as_json(temp_db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 3}]}
    add_chat_message("default", "assistant", "bought 3 AAPL", actions=actions)

    assert get_recent_chat()[0]["actions"] == actions


def test_get_recent_chat_returns_the_newest_messages_in_order(temp_db):
    for i in range(5):
        add_chat_message("default", "user", f"message {i}")

    history = get_recent_chat(limit=2)
    assert [m["content"] for m in history] == ["message 3", "message 4"]


def test_add_chat_message_returns_an_id(temp_db):
    message_id = add_chat_message("default", "user", "hello")
    assert isinstance(message_id, str) and message_id
