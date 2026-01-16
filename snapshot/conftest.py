import pytest
from typing import Type
from cascade.vm.reactor import Reactor
from cascade.spec.vm.interfaces import ReactorProtocol

# Imports for new global fixtures
from cascade.runtime import EventBus
from cascade.test_utils.helpers import SpySubscriber

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
) -> Type[ReactorProtocol]:
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
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python'."
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

import os
import asyncio
from typing import Callable, Any, Dict, Optional

# Core Engine & Interfaces
from cascade.runtime.host.instance import Engine
from cascade.spec.runtime import ExecutionStrategy, Solver, Executor
from cascade.runtime import ResourceManager

# Default Components for Graph Strategy
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.execution.graph.logic.processor import NodeProcessor
from cascade.execution.graph.strategy import GraphExecutionStrategy
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer

# Default Components for VM Strategy
from cascade.runtime.strategies.vm import VMExecutionStrategy


@pytest.fixture
def engine_factory() -> Callable[..., Engine]:
    """
    Provides a factory function to create a Cascade Engine instance.

    This factory encapsulates the logic for selecting a default execution strategy
    based on the CASCADE_BACKEND environment variable, decoupling the core Engine
    from specific strategy implementations.
    """

    def _factory(
        *,  # Force keyword arguments for clarity
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[EventBus] = None,
        strategy: Optional[ExecutionStrategy] = None,
        resource_manager: Optional[ResourceManager] = None,
        **kwargs,  # Pass-through for other Engine args like connector, system_resources etc.
    ) -> Engine:
        # 1. Provide sane defaults for core components
        _solver = solver or NativeSolver()
        _executor = executor or LocalExecutor()
        _bus = bus or EventBus()

        # 2. Manage shared ResourceManager dependency
        # If a manager is passed in, use it. Otherwise, create one from system_resources kwarg.
        _resource_manager = resource_manager or ResourceManager(
            capacity=kwargs.get("system_resources")
        )

        # 3. Create strategy if not provided
        if strategy is None:
            backend_choice = os.getenv("CASCADE_BACKEND", "graph").lower()
            if backend_choice == "vm":
                strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
            else:  # Default to 'graph'
                # build graph strategy with shared components
                constraint_manager = ConstraintManager(_resource_manager)
                wakeup_event = asyncio.Event()
                constraint_manager.set_wakeup_callback(wakeup_event.set)
                resource_container = ResourceContainer(_bus)
                node_processor = NodeProcessor(
                    executor=_executor,
                    bus=_bus,
                    resource_manager=_resource_manager,
                    constraint_manager=constraint_manager,
                    solver=_solver,
                )
                strategy = GraphExecutionStrategy(
                    solver=_solver,
                    node_processor=node_processor,
                    resource_container=resource_container,
                    constraint_manager=constraint_manager,
                    bus=_bus,
                    wakeup_event=wakeup_event,
                )

        # 4. Construct Engine with all components
        return Engine(
            solver=_solver,
            executor=_executor,
            bus=_bus,
            strategy=strategy,
            resource_manager=_resource_manager,
            **kwargs,  # Pass through system_resources, connector etc.
        )

    return _factory


@pytest.fixture
def engine(engine_factory: Callable[..., Engine]) -> Engine:
    """Provides a default-configured Cascade Engine instance for simple tests."""
    return engine_factory()
