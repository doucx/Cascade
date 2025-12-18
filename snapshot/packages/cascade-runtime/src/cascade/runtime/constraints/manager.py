from typing import Dict, List
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from cascade.runtime.resource_manager import ResourceManager
from .protocols import ConstraintHandler


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        if constraint.type == "concurrency":
            resource_name = f"constraint:concurrency:{constraint.scope}"
            limit = float(constraint.params.get("limit", 1))
            self.resource_manager.set_resource_capacity(resource_name, limit)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        constraints_to_remove = [
            c for c in self._constraints.values() if c.scope == scope
        ]
        for c in constraints_to_remove:
            if c.type == "concurrency":
                resource_name = f"constraint:concurrency:{c.scope}"
                self.resource_manager.remove_resource(resource_name)
            del self._constraints[c.id]
    
    def get_matching_constraints(
        self, task: Node, constraint_type: str
    ) -> List[GlobalConstraint]:
        """Finds all active constraints of a given type that apply to a task."""
        matches = []
        for constraint in self._constraints.values():
            if constraint.type != constraint_type:
                continue

            scope = constraint.scope
            if scope == "global":
                matches.append(constraint)
                continue

            if scope.startswith("task:"):
                target_task_name = scope.split(":", 1)[1]
                if task.name == target_task_name:
                    matches.append(constraint)
                    continue
        return matches

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints against a task. If any handler denies
        permission, the task is deferred.
        """
        # TODO: Implement expiry logic (check constraint.expires_at)

        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted

        # If no handler denied permission, permit execution.
        return True
