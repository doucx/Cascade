from typing import Protocol, TYPE_CHECKING, Dict, Any

from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint

if TYPE_CHECKING:
    from .manager import ConstraintManager


class ConstraintHandler(Protocol):
    """
    Protocol for a pluggable handler that implements the logic for a specific
    type of global constraint (e.g., "pause", "rate_limit").
    """

    def handles_type(self) -> str:
        """Returns the constraint type this handler is responsible for."""
        ...

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        """Called when a new constraint of this type is added or updated."""
        ...

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        """Called when a constraint is removed."""
        ...

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Evaluates the constraint against the given task.
        Returns: True if permitted, False if deferred.
        """
        ...

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        """
        Allows the handler to inject dynamic resource requirements for the task.
        Modifies the 'requirements' dictionary in-place.
        """
        ...
