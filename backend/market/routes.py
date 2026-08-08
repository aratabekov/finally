from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from config import settings

from .cache import PriceCache
from .types import Bar, PriceTick

router = APIRouter(prefix="/api")


def _tick_json(tick: PriceTick) -> str:
    return json.dumps(asdict(tick))


async def _price_events(request: Request, cache: PriceCache):
    # Tell EventSource to retry after 2s if the connection drops.
    yield "retry: 2000\n\n"

    last_sent: dict[str, str] = {}          # ticker -> last ISO timestamp emitted
    heartbeat_every = max(1, int(5 / settings.sse_push_seconds))
    cycles = 0

    while True:
        if await request.is_disconnected():
            break

        snapshot = await cache.snapshot()
        for ticker, tick in snapshot.items():
            if last_sent.get(ticker) != tick.timestamp:
                last_sent[ticker] = tick.timestamp
                yield f"data: {_tick_json(tick)}\n\n"

        # Drop de-watchlisted tickers so last_sent can't grow without bound on a
        # long-lived connection.
        if len(last_sent) > len(snapshot):
            for stale in last_sent.keys() - snapshot.keys():
                del last_sent[stale]

        cycles += 1
        if cycles % heartbeat_every == 0:
            yield ": keepalive\n\n"       # SSE comment; ignored by EventSource

        await asyncio.sleep(settings.sse_push_seconds)


@router.get("/stream/prices")
async def stream_prices(request: Request):
    cache: PriceCache = request.app.state.price_cache
    return StreamingResponse(
        _price_events(request, cache),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disable proxy buffering (nginx)
        },
    )


MAX_HISTORY_DAYS = 5 * 365   # cap so a huge `days` can't tie up the event loop


@router.get("/history/{ticker}")
async def history(ticker: str, request: Request, days: int = 90):
    days = max(1, min(days, MAX_HISTORY_DAYS))
    source = request.app.state.market_source
    bars: list[Bar] = await source.get_history(ticker.upper(), days=days)
    # Map Bar.low -> "l" so the payload is the {t,o,h,l,c,v} charts expect.
    return {
        "ticker": ticker.upper(),
        "bars": [
            {"t": b.t, "o": b.o, "h": b.h, "l": b.low, "c": b.c, "v": b.v}
            for b in bars
        ],
    }
