from __future__ import annotations

import asyncio
from collections.abc import Iterable

from .types import PriceTick


class PriceCache:
    def __init__(self) -> None:
        self._ticks: dict[str, PriceTick] = {}
        self._lock = asyncio.Lock()

    async def update(self, tick: PriceTick) -> None:
        async with self._lock:
            self._ticks[tick.ticker] = tick

    async def get(self, ticker: str) -> PriceTick | None:
        async with self._lock:
            return self._ticks.get(ticker)

    async def snapshot(self) -> dict[str, PriceTick]:
        async with self._lock:
            return dict(self._ticks)  # shallow copy: consistent view, no tearing

    async def retain(self, tickers: Iterable[str]) -> None:
        """Drop every cached tick outside `tickers`. Feed-only, like update():
        without it a de-watchlisted ticker would keep a frozen price that stays
        tradeable for the life of the process."""
        keep = set(tickers)
        async with self._lock:
            for stale in self._ticks.keys() - keep:
                del self._ticks[stale]
