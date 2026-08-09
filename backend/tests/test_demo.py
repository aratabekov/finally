from __future__ import annotations

import demo


def test_sparkline_empty_for_too_few_points():
    assert demo.sparkline([], 10) == ""
    assert demo.sparkline([1.0], 10) == ""


def test_sparkline_flat_series_uses_low_block():
    assert demo.sparkline([5.0, 5.0, 5.0], 10) == demo.BLOCKS[0] * 3


def test_sparkline_maps_extremes_and_respects_width():
    out = demo.sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], width=4)
    assert len(out) == 4                 # only the last `width` points
    assert out[0] == demo.BLOCKS[0]      # window min → lowest block
    assert out[-1] == demo.BLOCKS[-1]    # window max → highest block


def test_formatters():
    assert demo.fmt_price(1234.5) == "1,234.50"
    assert demo.fmt_signed(12.0) == "+12.00"
    assert demo.fmt_signed(-12.0) == "-12.00"
    assert demo.fmt_pct(1.5) == "+1.50%"
    assert demo.fmt_pct(-1.5) == "-1.50%"


def test_ticker_state_first_update_is_flat_baseline():
    s = demo.TickerState(ticker="AAPL", sector="tech")
    s.update(190.0)
    assert s.start == 190.0
    assert s.prev == 190.0
    assert s.direction == "flat"
    assert s.session_change == 0.0
    assert s.session_change_pct == 0.0
    assert s.ticks == 1


def test_ticker_state_tracks_direction_and_session_change():
    s = demo.TickerState(ticker="AAPL", sector="tech")
    s.update(100.0)
    s.update(110.0)
    assert s.direction == "up"
    assert s.session_change == 10.0
    assert s.session_change_pct == 10.0
    s.update(105.0)
    assert s.direction == "down"
    assert s.session_change == 5.0


def test_ticker_state_flags_shock_on_large_step():
    s = demo.TickerState(ticker="TSLA", sector="tech")
    s.update(100.0)
    s.update(100.5)          # +0.5%, below the 1.5% threshold
    assert not s.is_shock
    assert s.shocks == 0
    s.update(104.0)          # ~+3.5% step → shock
    assert s.is_shock
    assert s.shocks == 1


def test_render_smoke_no_color():
    states = {"AAPL": demo.TickerState(ticker="AAPL", sector="tech")}
    states["AAPL"].update(190.0)
    states["AAPL"].update(191.0)
    pal = demo.Palette(enabled=False)
    frame = demo.render(states, tick=1, seed=42, pal=pal, spark_width=12)
    assert "AAPL" in frame
    assert "SimulatedSource" in frame
    assert "TECH" in frame
    assert "\x1b[" not in frame          # colour disabled → no ANSI escapes
