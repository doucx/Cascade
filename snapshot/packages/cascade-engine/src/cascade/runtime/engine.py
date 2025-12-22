import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.spec.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy, VMExecutionStrategy


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self.resource_container = ResourceContainer(self.bus)

        # Delegate node execution logic to NodeProcessor
        self.node_processor = NodeProcessor(
            executor=self.executor,
            bus=self.bus,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            solver=self.solver,
        )

        # Initialize Strategies
        self.graph_strategy = GraphExecutionStrategy(
            solver=self.solver,
            node_processor=self.node_processor,
            resource_container=self.resource_container,
            constraint_manager=self.constraint_manager,
            bus=self.bus,
            wakeup_event=self._wakeup_event,
        )

        self.vm_strategy = VMExecutionStrategy(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
        )

        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
        """
        Adds a subscriber whose lifecycle (e.g., shutdown) the engine should manage.
        """
        self._managed_subscribers.append(subscriber)

    def register(self, resource_def: ResourceDefinition):
        self.resource_container.register(resource_def)

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False

        for v in lr.kwargs.values():
            if _has_lazy(v):
                return False

        return True

    def get_resource_provider(self, name: str) -> Callable:
        return self.resource_container.get_provider(name)

    def override_resource_provider(self, name: str, new_provider: Any):
        self.resource_container.override_provider(name, new_provider)

    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine initial target name for logging
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        # Initialize State Backend using the factory
        state_backend = self.state_backend_factory(run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # 3. Select Strategy
            strategy = self.vm_strategy if use_vm else self.graph_strategy

            # 4. Execute
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.resource import resource

                    @resource(name="_internal_connector", scope="run")
                    def _connector_provider():
                        yield self.connector

                    self.register(_connector_provider)

                active_resources: Dict[str, Any] = {}

                final_result = await strategy.execute(
                    target=target,
                    run_id=run_id,
                    params=params or {},
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            # Gracefully shut down any managed subscribers BEFORE disconnecting the connector
            for sub in self._managed_subscribers:
                if hasattr(sub, "shutdown"):
                    await sub.shutdown()

            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        try:
            # An empty payload, which becomes {}, signifies a cleared retained message (a resume command)
            if payload == {}:
                # Reconstruct scope from topic, e.g., cascade/constraints/task/api_call -> task:api_call
                scope_parts = topic.split("/")[2:]
                scope = ":".join(scope_parts)
                if scope:
                    self.constraint_manager.remove_constraints_by_scope(scope)
            else:
                # Basic validation, could be improved with a schema library
                constraint = GlobalConstraint(
                    id=payload["id"],
                    scope=payload["scope"],
                    type=payload["type"],
                    params=payload["params"],
                    expires_at=payload.get("expires_at"),
                )
                self.constraint_manager.update_constraint(constraint)
        except Exception as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint update on topic '{topic}': {e}",
                file=sys.stderr,
            )
        finally:
            # After any change (add, remove, or error), wake up the engine loop
            # if it's waiting.
            self._wakeup_event.set()
