import pytest
import asyncio
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local import LocalBusConnector
except ImportError:
    LocalBusConnector = None


@pytest.fixture(autouse=True)
def cleanup_local_bus():
    """
    Ensures that the memory broker state is completely cleared between tests.
    This prevents state leakage (retained messages/subscriptions) which
    causes unpredictable failures in E2E tests.
    """
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()


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
