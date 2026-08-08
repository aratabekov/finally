import httpx
import pytest

from market.massive import MassiveSource

SNAPSHOT = {
    "tickers": [
        {"ticker": "AAPL", "lastTrade": {"p": 191.2},
         "day": {"c": 190.0}, "prevDay": {"c": 189.0}},
        {"ticker": "MSFT", "lastTrade": {},          # closed: fall back to day.c
         "day": {"c": 421.5}, "prevDay": {"c": 420.0}},
        {"ticker": "IBM", "lastTrade": {},           # only prevDay available
         "day": {}, "prevDay": {"c": 150.0}},
    ]
}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler),
                             base_url="https://api.massive.com")


async def test_snapshot_parsing_and_fallback():
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(200, json=SNAPSHOT))
    prices = await src.get_prices(["AAPL", "MSFT", "IBM"])
    # last trade, then day.c, then prevDay.c
    assert prices == {"AAPL": 191.2, "MSFT": 421.5, "IBM": 150.0}
    await src.aclose()


async def test_empty_tickers_makes_no_request():
    def handler(req):  # pragma: no cover - should never be called
        raise AssertionError("no HTTP request expected for empty tickers")

    src = MassiveSource("key")
    src._client = _client(handler)
    assert await src.get_prices([]) == {}
    await src.aclose()


async def test_rate_limit_returns_empty_not_raises():
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(429, json={}))
    assert await src.get_prices(["AAPL"]) == {}          # feed keeps cached values
    await src.aclose()


async def test_bad_key_returns_empty_not_raises():
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(401, json={}))
    assert await src.get_prices(["AAPL"]) == {}
    await src.aclose()


async def test_transport_error_returns_empty_not_raises():
    def handler(req):
        raise httpx.ConnectError("boom", request=req)

    src = MassiveSource("key")
    src._client = _client(handler)
    assert await src.get_prices(["AAPL"]) == {}
    await src.aclose()


async def test_snapshot_request_is_a_single_call_for_all_tickers():
    calls: list[httpx.Request] = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=SNAPSHOT)

    src = MassiveSource("key")
    src._client = _client(handler)
    await src.get_prices(["AAPL", "MSFT", "IBM"])
    assert len(calls) == 1
    # Decoded query params, robust to comma percent-encoding.
    assert calls[0].url.params["tickers"] == "AAPL,MSFT,IBM"
    assert calls[0].headers["Authorization"] == "Bearer key"
    await src.aclose()


async def test_history_maps_to_bar_shape():
    aggs = {"results": [{"t": 1_700_000_000_000, "o": 1, "h": 2, "l": 0.5,
                         "c": 1.5, "v": 100}]}
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(200, json=aggs))
    bars = await src.get_history("AAPL", days=1)
    assert bars[0].o == 1 and bars[0].low == 0.5 and bars[0].c == 1.5
    assert bars[0].t == 1_700_000_000_000 and bars[0].v == 100
    await src.aclose()


async def test_history_error_returns_empty_list():
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(500, json={}))
    assert await src.get_history("AAPL", days=5) == []
    await src.aclose()


async def test_history_trims_to_requested_days():
    results = [{"t": 1_700_000_000_000 + i, "o": 1, "h": 2, "l": 0.5,
                "c": 1.5, "v": 10} for i in range(10)]
    src = MassiveSource("key")
    src._client = _client(lambda req: httpx.Response(200, json={"results": results}))
    bars = await src.get_history("AAPL", days=3)
    assert len(bars) == 3
    # keeps the most recent (last) 3 bars, in order
    assert [b.t for b in bars] == [r["t"] for r in results[-3:]]
    await src.aclose()


def test_configurable_poll_interval():
    default = MassiveSource("key")
    fast = MassiveSource("key", poll_interval_seconds=2.0)
    assert default.poll_interval_seconds == 15.0
    assert fast.poll_interval_seconds == 2.0
