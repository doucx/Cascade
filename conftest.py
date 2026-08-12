from __future__ import annotations

from typing import Callable

import pytest

# Imports for new global fixtures
from cascade.runtime import EventBus
from cascade.runtime.host.instance import Engine
from cascade.spec.vm.interfaces import ReactorProtocol
from cascade.test_utils.helpers import SpySubscriber
from cascade.vm.reactor import Reactor

# Attempt to import LocalBusConnector for global cleanup
try:
    from cascade.connectors.local.bus import LocalBusConnector
except ImportError:
    LocalBusConnector = None


def pytest_addoption(parser):
    """Adds a command-line option to select the reactor backend."""
    parser.addoption(
        "--reactor-backend",
        action="store",
        default="python",
        help="Select reactor backend to test: python or rust",
    )


@pytest.fixture(scope="session")
def reactor_backend_factory(
    request,
) -> type[ReactorProtocol]:
    """
    A session-scoped fixture that provides the Reactor class
    based on the --reactor-backend command-line option.
    """
    backend = request.config.getoption("--reactor-backend")

    if backend == "python":
        # Return the Python implementation
        return Reactor
    # elif backend == "rust":
    #     # Import the high-performance Rust implementation
    #     # from cascade_vm_js import JSReactor

    #     # return RustReactor
    #     return Reactor
    # elif backend == "js":
    #     # from cascade_vm_rs import RustReactor

    #     # return RustReactor
    #     return Reactor
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. Choose from 'python'."
        )


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


@pytest.fixture
def bus_and_spy():
    """Provides a runtime EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
    spy = SpySubscriber(bus)
    return bus, spy


# --- Engine Fixtures for Decoupled Testing ---


@pytest.fixture
def engine_factory() -> Callable[..., Engine]:
    """
    Provides a factory function to create a Cascade Engine instance for tests.
    This is a thin wrapper around the production `create_engine` factory,
    allowing tests to easily override components.
    """
    from cascade.runtime.host import create_engine

    def _factory(**kwargs) -> Engine:
        # The create_engine function already handles default component creation.
        # This fixture simply acts as a convenient entry point for pytest.
        return create_engine(**kwargs)

    return _factory


@pytest.fixture
def engine(engine_factory: Callable[..., Engine]) -> Engine:
    """Provides a default-configured Cascade Engine instance for simple tests."""
    return engine_factory()
