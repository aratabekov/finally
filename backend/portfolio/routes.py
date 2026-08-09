"""Portfolio endpoints: valuation, trade execution, and the P&L history.

Live prices come from `app.state.price_cache`; every DB call goes through the
`db.portfolio` / `db.snapshots` contract. The DB layer is synchronous sqlite,
so it runs on a worker thread to keep the event loop (and the SSE stream) free.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db.connection import DEFAULT_USER_ID
from db.portfolio import execute_trade, get_portfolio
from db.snapshots import get_snapshots

router = APIRouter(prefix="/api/portfolio")


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


@router.get("")
async def portfolio(request: Request):
    """Cash, positions valued at live prices, total value, unrealized P&L."""
    prices = await request.app.state.price_cache.snapshot()
    return await asyncio.to_thread(get_portfolio, prices, DEFAULT_USER_ID)


@router.post("/trade")
async def trade(body: TradeRequest, request: Request):
    """Execute a market order. Validation failures come back as HTTP 400 with
    the same body shape as a success (`success: false` plus `error`)."""
    prices = await request.app.state.price_cache.snapshot()
    result = await asyncio.to_thread(
        execute_trade,
        DEFAULT_USER_ID,
        body.ticker,
        body.side,
        body.quantity,
        prices,
    )
    if not result.success:
        return JSONResponse(result.as_dict(), status_code=400)
    return result.as_dict()


@router.get("/history")
async def history():
    """Portfolio value snapshots, oldest first — chart-ready."""
    return await asyncio.to_thread(get_snapshots, DEFAULT_USER_ID)
