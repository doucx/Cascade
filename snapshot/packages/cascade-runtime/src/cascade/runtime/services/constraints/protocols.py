from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint

if TYPE_CHECKING:
    from ..resources.manager import ResourceManager


class HandlerContext(Protocol):
    def request_wakeup(self, delay: float) -> None: ...
    def get_resource_manager(self) -> ResourceManager: ...


class ConstraintHandler(Protocol):
    def handles_type(self) -> str: ...

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: HandlerContext
    ) -> None: ...

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: HandlerContext
    ) -> None: ...

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: HandlerContext
    ) -> bool: ...

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: dict[str, Any],
        context: HandlerContext,
    ) -> None: ...
