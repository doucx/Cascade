import pytest
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
