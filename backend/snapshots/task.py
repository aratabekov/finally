"""Periodic portfolio value snapshots — the series behind the P&L chart.

`execute_trade` already records a snapshot inside its own transaction, so this
task only has to cover the quiet stretches between trades.
"""

from __future__ import annotations

import asyncio
import logging

from db.connection import DEFAULT_USER_ID
from db.portfolio import get_portfolio
from db.snapshots import record_snapshot
from market.cache import PriceCache

log = logging.getLogger("finally.snapshots")

SNAPSHOT_INTERVAL_SECONDS = 30.0


def _record(prices: dict, user_id: str) -> None:
    """Value the portfolio and store the total. Sync — runs on a worker thread."""
    portfolio = get_portfolio(prices, user_id)
    record_snapshot(user_id, portfolio["total_value"])


class SnapshotTask:
    """Records one snapshot on start, then one every `interval_seconds`."""

    def __init__(
        self,
        cache: PriceCache,
        interval_seconds: float = SNAPSHOT_INTERVAL_SECONDS,
        user_id: str = DEFAULT_USER_ID,
    ) -> None:
        self._cache = cache
        self._interval = interval_seconds
        self._user_id = user_id
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def record_once(self) -> None:
        prices = await self._cache.snapshot()
        await asyncio.to_thread(_record, prices, self._user_id)

    async def _run(self) -> None:
        while True:
            try:
                await self.record_once()
            except Exception:
                # A bad snapshot must not kill the loop for the whole session.
                log.exception("snapshot failed; retrying next interval")
            await asyncio.sleep(self._interval)
