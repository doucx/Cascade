from typing import TYPE_CHECKING

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


if TYPE_CHECKING:
    from .manager import ConstraintManager


class PauseConstraintHandler(ConstraintHandler):
    """
    Handles the 'pause' constraint type.
    It can pause execution globally or for a specific task.
    """

    def handles_type(self) -> str:
        return "pause"

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # Project-specific scope (placeholder for future implementation)
        # if scope.startswith("project:"):
        #     ...

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True