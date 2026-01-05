import pytest
from cascade.runtime import EventBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy
