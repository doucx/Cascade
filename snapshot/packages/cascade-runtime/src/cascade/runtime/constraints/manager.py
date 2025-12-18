from typing import Dict, Optional, TYPE_CHECKING
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler

if TYPE_CHECKING:
    from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: Optional["ResourceManager"] = None):
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        self._resource_manager = resource_manager

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint
        self._apply_side_effects(constraint)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            # TODO: Ideally we should revert side effects (e.g. remove resource limit),
            # but setting capacity to infinite/high is complex without explicit removal support in RM.
            # For now, we leave the resource limit as is, or rely on future overwrites.
            # In a robust impl, we would reset the capacity to infinite.
            del self._constraints[cid]

    def _apply_side_effects(self, constraint: GlobalConstraint):
        """Applies side effects for specific constraint types (e.g. concurrency)."""
        if constraint.type == "concurrency" and self._resource_manager:
            limit = constraint.params.get("limit")
            if limit is not None:
                resource_key = f"constraint:concurrency:{constraint.scope}"
                self._resource_manager.update_capacity({resource_key: float(limit)})

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
