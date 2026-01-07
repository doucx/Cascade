import pytest
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySubscriber


@pytest.fixture
def bus_and_spy():
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy
