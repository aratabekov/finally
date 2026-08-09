from __future__ import annotations

import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Current UTC time as an ISO 8601 string — the format every timestamp
    column in the schema uses."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Fresh UUID4 primary key."""
    return str(uuid.uuid4())


def normalize_ticker(ticker: str) -> str:
    """Tickers are stored uppercase and unpadded, everywhere."""
    return ticker.strip().upper()
