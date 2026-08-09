"""Watchlist endpoints — the stored tickers joined with their latest prices.

A ticker that was just added has no cached tick yet (the feed picks it up on its
next poll), so its price fields come back null rather than being omitted.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db.connection import DEFAULT_USER_ID
from db.util import normalize_ticker
from db.watchlist import add_watchlist, list_watchlist, remove_watchlist
from market.types import PriceTick

router = APIRouter(prefix="/api/watchlist")


class WatchlistRequest(BaseModel):
    ticker: str


def _entry(ticker: str, tick: PriceTick | None) -> dict:
    if tick is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "direction": "flat",
            "timestamp": None,
        }
    return {
        "ticker": ticker,
        "price": tick.price,
        "previous_price": tick.previous_price,
        "direction": tick.direction,
        "timestamp": tick.timestamp,
    }


@router.get("")
async def watchlist(request: Request):
    """Watchlist tickers, in the order they were added, with latest prices."""
    prices = await request.app.state.price_cache.snapshot()
    tickers = await asyncio.to_thread(list_watchlist, DEFAULT_USER_ID)
    return [_entry(ticker, prices.get(ticker)) for ticker in tickers]


@router.post("")
async def add(body: WatchlistRequest):
    """Add a ticker. Idempotent: `added` is false if it was already there."""
    ticker = normalize_ticker(body.ticker)
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    added = await asyncio.to_thread(add_watchlist, DEFAULT_USER_ID, ticker)
    return {"ticker": ticker, "added": added}


@router.delete("/{ticker}")
async def remove(ticker: str):
    """Remove a ticker. `removed` is false if it was not on the watchlist."""
    removed = await asyncio.to_thread(remove_watchlist, DEFAULT_USER_ID, ticker)
    return {"ticker": normalize_ticker(ticker), "removed": removed}
