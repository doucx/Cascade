from typing import Dict
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class ConstraintManager:
    """
    Manages a collection of global constraints that affect workflow execution.
    """

    def __init__(self):
        # Stores constraints by their unique ID for easy updates
        self._constraints: Dict[str, GlobalConstraint] = {}

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """
        Adds a new constraint or updates an existing one.
        """
        self._constraints[constraint.id] = constraint

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.
        """
        # TODO: This will be replaced by the dispatcher logic in the next milestone.
        # For now, it permits all execution to allow incremental refactoring.
        return True
