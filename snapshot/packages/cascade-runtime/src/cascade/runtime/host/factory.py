from __future__ import annotations

import asyncio
import os

from cascade.bus.core import EventBus

# Dynamic imports for strategies
from cascade.execution.graph.solvers.native import NativeSolver
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.services.constraints.handlers import (
    ConcurrencyConstraintHandler,
    PauseConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.spec.runtime import ExecutionStrategy, Executor, Solver

from .instance import Engine


def create_engine(
    *,
    use_vm: bool = False,
    solver: Solver | None = None,
    executor: Executor | None = None,
    bus: EventBus | None = None,
    strategy: ExecutionStrategy | None = None,
    resource_manager: ResourceManager | None = None,
    constraint_manager: ConstraintManager | None = None,
    **kwargs,  # Pass-through for other Engine args like connector, system_resources etc.
) -> Engine:
    # 1. Provide sane defaults for core components
    _solver = solver or NativeSolver()
    _executor = executor or LocalExecutor()
    _bus = bus or EventBus()

    # 2. Create and configure shared services
    _resource_manager = resource_manager or ResourceManager(
        capacity=kwargs.get("system_resources")
    )
    _constraint_manager = constraint_manager or ConstraintManager(_resource_manager)
    _wakeup_event = asyncio.Event()

    # Register default handlers if the manager is newly created
    if not constraint_manager:
        _constraint_manager.register_handler(PauseConstraintHandler())
        _constraint_manager.register_handler(ConcurrencyConstraintHandler())
        _constraint_manager.register_handler(RateLimitConstraintHandler())

    _constraint_manager.set_wakeup_callback(_wakeup_event.set)

    # 3. Create strategy if not provided
    _resource_container = ResourceContainer(_bus)

    # 3. Create strategy if not provided
    if strategy is None:
        backend_choice = (
            "vm" if use_vm else os.getenv("CASCADE_BACKEND", "graph").lower()
        )

        if backend_choice == "vm":
            from cascade.runtime.strategies.vm import VMExecutionStrategy

            strategy = VMExecutionStrategy(executor=_executor, bus=_bus)
        else:  # Default to 'graph'
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            node_processor = NodeProcessor(
                executor=_executor,
                bus=_bus,
                resource_manager=_resource_manager,
                constraint_manager=_constraint_manager,
                solver=_solver,
            )
            strategy = GraphExecutionStrategy(
                solver=_solver,
                node_processor=node_processor,
                resource_container=_resource_container,
                constraint_manager=_constraint_manager,
                bus=_bus,
                wakeup_event=_wakeup_event,
            )

    # 4. Construct Engine with all assembled components
    return Engine(
        solver=_solver,
        executor=_executor,
        bus=_bus,
        strategy=strategy,
        resource_manager=_resource_manager,
        constraint_manager=_constraint_manager,
        resource_container=_resource_container,
        wakeup_event=_wakeup_event,
        **kwargs,
    )
