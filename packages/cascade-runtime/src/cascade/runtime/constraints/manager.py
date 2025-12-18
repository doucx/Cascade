from typing import Dict, Any
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler
from cascade.runtime.resource_manager import ResourceManager


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

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            constraint = self._constraints[cid]
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.on_constraint_remove(constraint, self)
            del self._constraints[cid]

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

    def get_extra_requirements(self, task: Node) -> Dict[str, Any]:
        """
        Collects dynamic resource requirements from all applicable constraints.
        """
        requirements: Dict[str, Any] = {}
        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.append_requirements(task, constraint, requirements, self)
        return requirements
