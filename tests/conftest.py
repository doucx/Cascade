import pytest
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.fixture
def bus_and_spy():
    """Provides a MessageBus instance and an attached SpySubscriber."""
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy