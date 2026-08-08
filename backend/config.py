from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("finally.config")


def _clean(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float_env(name: str, default: float) -> float:
    """Parse a float env var, falling back to `default` (with a warning) rather
    than crashing the whole app at import time on a malformed value."""
    raw = _clean(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("%s=%r is not a number; using default %s", name, raw, default)
        return default


def _int_env(name: str, default: int | None) -> int | None:
    raw = _clean(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("%s=%r is not an integer; using default %s", name, raw, default)
        return default


@dataclass(frozen=True)
class Settings:
    # Market data
    massive_api_key: str
    massive_poll_seconds: float   # override poll cadence (paid tiers can go faster)
    sim_seed: int | None          # deterministic simulator for tests
    sse_push_seconds: float       # how often SSE flushes the cache to clients

    # LLM (documented here for completeness; owned by the chat agent)
    openrouter_api_key: str
    llm_mock: bool

    @property
    def use_massive(self) -> bool:
        return bool(self.massive_api_key)


def load_settings() -> Settings:
    return Settings(
        massive_api_key=_clean("MASSIVE_API_KEY"),
        massive_poll_seconds=_float_env("MASSIVE_POLL_SECONDS", 15.0),
        sim_seed=_int_env("SIM_SEED", None),
        sse_push_seconds=_float_env("SSE_PUSH_SECONDS", 0.5),
        openrouter_api_key=_clean("OPENROUTER_API_KEY"),
        llm_mock=_clean("LLM_MOCK", "false").lower() == "true",
    )


settings = load_settings()
