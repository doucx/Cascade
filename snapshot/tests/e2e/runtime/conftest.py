import pytest

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local.bus import LocalBusConnector
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


from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber


@pytest.fixture
def bus_and_spy():
    """Provides a MessageBus instance and an attached SpySubscriber."""
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
