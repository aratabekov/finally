"""FinAlly market data subsystem.

Selects a price source from the environment (Massive when ``MASSIVE_API_KEY`` is
set, otherwise the built-in GBM simulator), keeps an in-memory price cache
current via a single background feed, and exposes the SSE stream and history
route that the frontend consumes. See ``planning/MARKET_DATA_DESIGN.md``.
"""
