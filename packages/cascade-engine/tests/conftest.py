import pytest
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    """Provides a MessageBus instance and an attached SpySubscriber."""
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
