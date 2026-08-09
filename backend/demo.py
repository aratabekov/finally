#!/usr/bin/env python
"""Rich terminal dashboard for the market data simulator.

Drives the real ``SimulatedSource`` (the same code path the FastAPI feed uses)
and renders a live, colour-coded terminal dashboard — no server, no browser, no
API key required. Handy for eyeballing the GBM simulator: correlated sector
moves, the occasional ``⚡`` shock event, per-ticker sparklines, and session P&L.

    cd backend
    uv run python demo.py                 # all 10 default tickers, Ctrl+C to quit
    uv run python demo.py --seed 42       # deterministic run (mirrors SIM_SEED)
    uv run python demo.py --steps 40 --interval 0.1
    uv run python demo.py --tickers AAPL,NVDA,TSLA
    uv run python demo.py --plain         # no alt-screen; append frames (pipe/CI)

It writes only to the terminal and never touches the database or the network.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field

from market.feed import _direction  # reuse the feed's exact up/down/flat rule
from market.seeds import SEEDS
from market.simulator import SimulatedSource
from market.types import Direction

# --- terminal / colour --------------------------------------------------------

BLOCKS = "▁▂▃▄▅▆▇█"           # sparkline ramp, low → high
ARROWS: dict[Direction, str] = {"up": "▲", "down": "▼", "flat": "─"}

CSI = "\x1b["
RESET = f"{CSI}0m"
ALT_SCREEN_ON = f"{CSI}?1049h"
ALT_SCREEN_OFF = f"{CSI}?1049l"
HIDE_CURSOR = f"{CSI}?25l"
SHOW_CURSOR = f"{CSI}?25h"
HOME = f"{CSI}H"
CLEAR_BELOW = f"{CSI}0J"
CLEAR_LINE = f"{CSI}0K"


class Palette:
    """ANSI SGR codes, collapsed to no-ops when colour is disabled."""

    def __init__(self, enabled: bool) -> None:
        self._on = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"{CSI}{code}m{text}{RESET}" if self._on else text

    def green(self, s: str) -> str:  return self._wrap("32", s)
    def red(self, s: str) -> str:    return self._wrap("31", s)
    def yellow(self, s: str) -> str: return self._wrap("33", s)
    def blue(self, s: str) -> str:   return self._wrap("36", s)
    def dim(self, s: str) -> str:    return self._wrap("2", s)
    def bold(self, s: str) -> str:   return self._wrap("1", s)

    def for_direction(self, direction: Direction, s: str) -> str:
        if direction == "up":
            return self.green(s)
        if direction == "down":
            return self.red(s)
        return self.dim(s)


# --- pure, testable helpers ---------------------------------------------------

def sparkline(values: list[float], width: int) -> str:
    """Render the last ``width`` values as Unicode block glyphs, scaled to the
    window's own min/max. Empty for <2 points; a flat line maps to the low block."""
    window = values[-width:]
    if len(window) < 2:
        return ""
    lo, hi = min(window), max(window)
    if hi == lo:
        return BLOCKS[0] * len(window)
    span = hi - lo
    return "".join(BLOCKS[round((v - lo) / span * (len(BLOCKS) - 1))] for v in window)


def fmt_price(x: float) -> str:
    return f"{x:,.2f}"


def fmt_signed(x: float) -> str:
    return f"{x:+,.2f}"


def fmt_pct(x: float) -> str:
    return f"{x:+.2f}%"


@dataclass
class TickerState:
    """Per-ticker running state accumulated across simulator steps."""

    ticker: str
    sector: str
    start: float = 0.0
    prev: float = 0.0
    price: float = 0.0
    history: list[float] = field(default_factory=list)
    ticks: int = 0
    shocks: int = 0        # steps whose move was large enough to look like an event

    #: single-step moves at/above this magnitude are flagged as a shock event
    SHOCK_THRESHOLD = 0.015

    def update(self, price: float) -> None:
        first = self.ticks == 0
        self.prev = price if first else self.price
        if first:
            self.start = price
        self.price = price
        self.history.append(price)
        self.ticks += 1
        if not first and abs(self.step_change_pct) >= self.SHOCK_THRESHOLD * 100:
            self.shocks += 1

    @property
    def direction(self) -> Direction:
        return _direction(self.price, self.prev)

    @property
    def session_change(self) -> float:
        return self.price - self.start

    @property
    def session_change_pct(self) -> float:
        return (self.session_change / self.start * 100) if self.start else 0.0

    @property
    def step_change_pct(self) -> float:
        return ((self.price - self.prev) / self.prev * 100) if self.prev else 0.0

    @property
    def is_shock(self) -> bool:
        return abs(self.step_change_pct) >= self.SHOCK_THRESHOLD * 100


# --- rendering ----------------------------------------------------------------

def render(states: dict[str, TickerState], *, tick: int, seed: int | None,
           pal: Palette, spark_width: int) -> str:
    up = sum(1 for s in states.values() if s.session_change > 0)
    down = sum(1 for s in states.values() if s.session_change < 0)
    seed_label = str(seed) if seed is not None else "random"

    lines: list[str] = []
    lines.append(pal.bold(pal.yellow("  FinAlly · Market Data Simulator")))
    lines.append(pal.dim(
        f"  source=SimulatedSource  seed={seed_label}  tick={tick}  "
        f"tickers={len(states)}  ") + pal.green(f"▲{up}") + "  " + pal.red(f"▼{down}"))
    lines.append("")

    header = (f"  {'TICKER':<7}{'PRICE':>12}{'Δ SESSION':>13}{'%':>10}   "
              f"{'DIR':<4}{'TREND':<{spark_width + 2}}{'EVT':>4}")
    lines.append(pal.dim(header))
    lines.append(pal.dim("  " + "─" * (len(header) - 2)))

    for sector in sorted({s.sector for s in states.values()}):
        lines.append(pal.blue(f"  {sector.upper()}"))
        members = sorted(
            (s for s in states.values() if s.sector == sector),
            key=lambda s: s.session_change_pct, reverse=True,
        )
        for s in members:
            d = s.direction
            # Pad to width on the plain text FIRST, then colour — so the
            # invisible ANSI bytes never throw the column alignment off.
            price_cell = pal.for_direction(d, f"{fmt_price(s.price):>12}")
            delta_cell = pal.for_direction(d, f"{fmt_signed(s.session_change):>13}")
            pct_cell = pal.for_direction(d, f"{fmt_pct(s.session_change_pct):>10}")
            arrow_cell = pal.for_direction(d, ARROWS[d])
            spark = pal.for_direction(
                "up" if s.session_change >= 0 else "down",
                f"{sparkline(s.history, spark_width):<{spark_width}}",
            )
            evt = pal.yellow("⚡") if s.is_shock else " "
            lines.append(
                f"  {s.ticker:<7}{price_cell}{delta_cell}{pct_cell}"
                f"   {arrow_cell}   {spark}  {evt}"
            )
        lines.append("")

    lines.append(pal.dim("  Ctrl+C to quit"))
    return "\n".join(lines)


# --- driver -------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    source = SimulatedSource(seed=args.seed)
    states = {
        t: TickerState(ticker=t, sector=SEEDS[t].sector if t in SEEDS else "other")
        for t in tickers
    }
    pal = Palette(enabled=args.color)

    out = sys.stdout
    use_alt = not args.plain and out.isatty()
    if use_alt:
        out.write(ALT_SCREEN_ON + HIDE_CURSOR)
        out.flush()

    tick = 0
    try:
        while args.steps is None or tick < args.steps:
            prices = await source.get_prices(tickers)
            for t, price in prices.items():
                states[t].update(price)
            frame = render(states, tick=tick, seed=args.seed,
                           pal=pal, spark_width=args.spark_width)
            if use_alt:
                out.write(HOME + frame.replace("\n", CLEAR_LINE + "\n") + CLEAR_BELOW)
            else:
                out.write(frame + "\n")
            out.flush()
            tick += 1
            if args.steps is not None and tick >= args.steps:
                break
            await asyncio.sleep(args.interval)
    finally:
        await source.aclose()
        if use_alt:
            out.write(SHOW_CURSOR + ALT_SCREEN_OFF)
            out.flush()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_tickers = ",".join(SEEDS.keys())
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tickers", default=default_tickers,
                   help="comma-separated symbols (default: the 10 seeded tickers)")
    p.add_argument("--seed", type=int, default=None,
                   help="deterministic simulator seed (mirrors SIM_SEED)")
    p.add_argument("--interval", type=float, default=0.5,
                   help="seconds between simulator steps (default: 0.5)")
    p.add_argument("--steps", type=int, default=None,
                   help="stop after N steps (default: run until Ctrl+C)")
    p.add_argument("--spark-width", type=int, default=24,
                   help="sparkline width in glyphs (default: 24)")
    p.add_argument("--plain", action="store_true",
                   help="append frames instead of a live in-place redraw (pipe/CI)")
    p.add_argument("--no-color", dest="color", action="store_false",
                   help="disable ANSI colour")
    p.set_defaults(color=sys.stdout.isatty())
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
