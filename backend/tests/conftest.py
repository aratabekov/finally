"""Make the backend package root importable as ``market`` / ``config`` when
running ``pytest`` from anywhere (e.g. ``uv run pytest`` at the repo root)."""
from __future__ import annotations

import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
