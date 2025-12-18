from typing import Protocol, TYPE_CHECKING

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

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Evaluates the constraint against the given task.

        Args:
            task: The task node being considered for execution.
            constraint: The specific constraint instance to evaluate.
            manager: A reference to the parent ConstraintManager, providing access
                     to the overall state if needed.

        Returns:
            True if the task is permitted to run, False if it should be deferred.
        """
        ...