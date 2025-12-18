from typing import TYPE_CHECKING, Dict, Any

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    from .manager import ConstraintManager

def _parse_rate_string(rate_str: str) -> float:
    """Parses '10/m', '5/s', '300/h' into tokens per second."""
    if not isinstance(rate_str, str):
        return float(rate_str)
    
    parts = rate_str.split("/")
    if len(parts) != 2:
        try:
            return float(rate_str)
        except ValueError:
             # Default fallback or error
            return 1.0

    count = float(parts[0])
    unit = parts[1].lower()
    
    divisor = 1.0
    if unit in ("s", "sec", "second"):
        divisor = 1.0
    elif unit in ("m", "min", "minute"):
        divisor = 60.0
    elif unit in ("h", "hr", "hour"):
        divisor = 3600.0
    
    return count / divisor


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


class RateLimitConstraintHandler(ConstraintHandler):
    """
    Handles 'rate_limit' constraints using a Token Bucket algorithm.
    """

    def __init__(self):
        self.limiter = RateLimiter()

    def handles_type(self) -> str:
        return "rate_limit"

    def _get_scope_key(self, constraint: GlobalConstraint) -> str:
        return constraint.scope

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))
        
        # We can optionally allow users to set burst capacity via params
        # For now, default burst = rate (1 second worth)
        capacity = constraint.params.get("capacity") 
        if capacity is not None:
            capacity = float(capacity)
        
        self.limiter.update_bucket(self._get_scope_key(constraint), rate_hertz, capacity)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        # Currently RateLimiter doesn't support deleting buckets, which is fine.
        # It just won't be used.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        # Check scope match
        scope = constraint.scope
        is_match = False

        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                is_match = True
        
        if not is_match:
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))
        
        if wait_time == 0.0:
            return True
        else:
            # We are rate limited. Request a wakeup when tokens should be available.
            manager.request_wakeup(wait_time)
            return False

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        pass
