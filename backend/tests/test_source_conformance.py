"""Both concrete sources must fully satisfy the MarketDataSource contract, so
downstream code (feed, routes) can treat them interchangeably."""
from market.massive import MassiveSource
from market.simulator import SimulatedSource
from market.source import MarketDataSource

SOURCES = (SimulatedSource, MassiveSource)


def test_sources_are_registered_subclasses():
    assert all(issubclass(s, MarketDataSource) for s in SOURCES)


def test_sources_leave_no_abstract_methods():
    # If a source forgot to implement get_prices/get_history, ABCMeta records it
    # here (and instantiation would raise TypeError).
    assert all(s.__abstractmethods__ == frozenset() for s in SOURCES)
