from typing import Protocol, TYPE_CHECKING, Dict, Any

from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint

if TYPE_CHECKING:
    from .manager import ConstraintManager


class ConstraintHandler(Protocol):
    def handles_type(self) -> str: ...

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None: ...

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None: ...

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool: ...

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None: ...
