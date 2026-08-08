"""The factory selects a source purely from configuration."""
import config
import market.factory as factory
from market.factory import make_source
from market.massive import MassiveSource
from market.simulator import SimulatedSource
from market.source import MarketDataSource


def _with_settings(monkeypatch, **overrides):
    base = dict(
        massive_api_key="",
        massive_poll_seconds=15.0,
        sim_seed=None,
        sse_push_seconds=0.5,
        openrouter_api_key="",
        llm_mock=False,
    )
    base.update(overrides)
    # factory.py does ``from config import settings``, binding the name in its
    # own namespace, so patch the reference the factory actually reads.
    monkeypatch.setattr(factory, "settings", config.Settings(**base))


def test_simulator_selected_when_no_key(monkeypatch):
    _with_settings(monkeypatch, massive_api_key="")
    src = make_source()
    assert isinstance(src, SimulatedSource)
    assert isinstance(src, MarketDataSource)


async def test_massive_selected_when_key_present(monkeypatch):
    _with_settings(monkeypatch, massive_api_key="secret", massive_poll_seconds=3.0)
    src = make_source()
    assert isinstance(src, MassiveSource)
    assert src.poll_interval_seconds == 3.0
    await src.aclose()


async def test_both_sources_satisfy_the_interface(monkeypatch):
    """Both implementations expose get_prices and get_history."""
    sim = SimulatedSource(seed=1)
    assert await sim.get_prices(["AAPL"])
    assert await sim.get_history("AAPL", days=5)

    massive = MassiveSource("key")
    assert hasattr(massive, "get_prices") and hasattr(massive, "get_history")
    await massive.aclose()
