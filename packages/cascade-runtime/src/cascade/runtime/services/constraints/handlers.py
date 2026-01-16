from typing import TYPE_CHECKING, Dict, Any, Optional
import fnmatch
from cascade.bus.feedback import bus

from .protocols import ConstraintHandler, HandlerContext
from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    pass


def _matches(scope: str, task_name: str) -> bool:
    if scope == "global":
        return True

    if scope.startswith("task:"):
        pattern = scope.split(":", 1)[1]
        return fnmatch.fnmatch(task_name, pattern)

    return False


def _parse_rate_string(rate_str: str) -> float:
    try:
        if not isinstance(rate_str, str):
            return float(rate_str)

        parts = rate_str.split("/")
        if len(parts) != 2:
            return float(rate_str)

        count = float(parts[0])
        unit = parts[1].lower()

        divisor = 1.0
        if unit in ("s", "sec", "second"):
            divisor = 1.0
        elif unit in ("m", "min", "minute"):
            divisor = 60.0
        elif unit in ("h", "hr", "hour"):
            divisor = 3600.0
        else:
            # Invalid unit, treat as malformed
            raise ValueError(f"Unknown rate limit unit: '{unit}'")

        return count / divisor
    except (ValueError, TypeError) as e:
        bus.error(
            "constraint.parse.error",
            constraint_type="rate_limit",
            raw_value=rate_str,
            error=str(e),
        )
        # Return a safe default (e.g., 1 token per second) to prevent crashes
        return 1.0


class PauseConstraintHandler(ConstraintHandler):
    def handles_type(self) -> str:
        return "pause"

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        pass

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:
        if _matches(constraint.scope, task.name):
            return False
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:  # pragma: no cover
        pass


class ConcurrencyConstraintHandler(ConstraintHandler):
    def handles_type(self) -> str:
        return "concurrency"

    def _get_resource_name(self, constraint: GlobalConstraint) -> str:
        return f"constraint:concurrency:{constraint.scope}"

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:
        limit = constraint.params.get("limit", 1)
        res_name = self._get_resource_name(constraint)
        context.get_resource_manager().update_resource(res_name, limit)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        # We don't necessarily delete the resource, but we could set capacity to infinite?
        # Or just leave it. If the constraint is gone, tasks won't ask for it anymore.
        # So doing nothing is safe and simpler.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:  # pragma: no cover
        # Concurrency is handled via resource acquisition, not boolean permission checks.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:
        if _matches(constraint.scope, task.name):
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1


class RateLimitConstraintHandler(ConstraintHandler):
    def __init__(self):
        self.limiter = RateLimiter()

    def handles_type(self) -> str:
        return "rate_limit"

    def _get_scope_key(self, constraint: GlobalConstraint) -> str:
        return constraint.scope

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))

        # We can optionally allow users to set burst capacity via params
        # For now, default burst = rate (1 second worth)
        capacity_val: Optional[float] = None
        raw_capacity = constraint.params.get("capacity")
        if raw_capacity is not None:
            capacity_val = float(raw_capacity)

        self.limiter.update_bucket(
            self._get_scope_key(constraint), rate_hertz, capacity_val
        )

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        # Currently RateLimiter doesn't support deleting buckets, which is fine.
        # It just won't be used.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:
        if not _matches(constraint.scope, task.name):
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))

        if wait_time == 0.0:
            return True
        else:
            # We are rate limited. Request a wakeup when tokens should be available.
            context.request_wakeup(wait_time)
            return False

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:  # pragma: no cover
        pass
