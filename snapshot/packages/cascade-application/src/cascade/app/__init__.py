import asyncio
from typing import Any, Dict, List, Tuple, Union, Optional, Callable

from cascade.spec.lazy_types import LazyResult
from cascade.spec.task import task
from cascade.spec.protocols import Connector, StateBackend

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers (Duplicated from sdk to avoid circular dependency) ---

@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """An internal pure task used to gather results from a list."""
    return list(args)


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
) -> Optional[Callable[[str], StateBackend]]:
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )

            # Create a shared client pool
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


# --- CascadeApp ---

class CascadeApp:
    """
    The central manager for a workflow's lifecycle, encapsulating all
    infrastructure, configuration, and top-level operations.
    """

    def __init__(
        self,
        target: Union[LazyResult, List[Any], Tuple[Any, ...]],
        params: Optional[Dict[str, Any]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
        log_format: str = "human",
        connector: Optional[Connector] = None,
        state_backend: Union[str, Callable[[str], StateBackend], None] = None,
    ):
        """
        Initializes the application context.

        Args:
            target: The workflow target (LazyResult, list, or tuple).
            params: Parameters to pass to the workflow.
            system_resources: System-wide resources capacity (e.g. {"gpu": 1}).
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
            log_format: Logging format ("human" or "json").
            connector: Optional external connector (e.g. MQTT).
            state_backend: State persistence backend URI or factory.
        """
        self.raw_target = target
        self.params = params
        self.system_resources = system_resources
        self.connector = connector

        # 1. Handle Auto-Gathering
        if isinstance(target, (list, tuple)):
            if not target:
                self.workflow_target = _internal_gather()  # Empty gather
            else:
                self.workflow_target = _internal_gather(*target)
        else:
            self.workflow_target = target

        # 2. Setup Messaging & Rendering
        if log_format == "json":
            self.renderer = JsonRenderer(min_level=log_level)
        else:
            self.renderer = CliRenderer(store=bus.store, min_level=log_level)
        
        # Inject renderer into the GLOBAL bus (as per current architecture)
        # TODO: In future, we might want scoped buses per App instance.
        bus.set_renderer(self.renderer)

        # 3. Setup Event System
        self.event_bus = MessageBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
        
        self.telemetry_subscriber = None
        if self.connector:
            self.telemetry_subscriber = TelemetrySubscriber(self.event_bus, self.connector)

        # 4. Setup Engine Components
        self.solver = NativeSolver()
        self.executor = LocalExecutor()
        self.sb_factory = _create_state_backend_factory(state_backend)

        # 5. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
        )

        # Register managed subscribers for graceful shutdown
        # (Engine handles this via add_subscriber, but currently Engine implementation 
        #  of add_subscriber expects objects with 'shutdown' method. 
        #  TelemetrySubscriber has it. HumanReadableLogSubscriber does not.)
        if self.telemetry_subscriber:
            self.engine.add_subscriber(self.telemetry_subscriber)

    def run(self) -> Any:
        """
        Executes the workflow and returns the final result.
        """
        return asyncio.run(
            self.engine.run(self.workflow_target, params=self.params)
        )

    def visualize(self) -> str:
        """Generates and returns a Graphviz DOT string of the workflow."""
        # TODO: Implement in Stage 3
        raise NotImplementedError("visualize() is not yet implemented in CascadeApp")

    def dry_run(self) -> None:
        """Builds and prints the execution plan without running any tasks."""
        # TODO: Implement in Stage 3
        raise NotImplementedError("dry_run() is not yet implemented in CascadeApp")