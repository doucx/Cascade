from typing import TYPE_CHECKING, Dict, Any

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

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        pass

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        pass

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

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        pass


class ConcurrencyConstraintHandler(ConstraintHandler):
    """
    Handles the 'concurrency' constraint type.
    Maps concurrency limits to dynamic system resources.
    """

    def handles_type(self) -> str:
        return "concurrency"

    def _get_resource_name(self, constraint: GlobalConstraint) -> str:
        return f"constraint:concurrency:{constraint.scope}"

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        limit = constraint.params.get("limit", 1)
        res_name = self._get_resource_name(constraint)
        manager.resource_manager.update_resource(res_name, limit)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        # We don't necessarily delete the resource, but we could set capacity to infinite?
        # Or just leave it. If the constraint is gone, tasks won't ask for it anymore.
        # So doing nothing is safe and simpler.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        # Concurrency is handled via resource acquisition, not boolean permission checks.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        # Check scope match
        scope = constraint.scope
        is_match = False

        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                is_match = True

        if is_match:
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
