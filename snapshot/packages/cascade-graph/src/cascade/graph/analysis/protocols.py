from typing import Protocol, Any
from cascade.spec.ir.models import TaskDef


class TaskAnalyzer(Protocol):
    """
    Protocol for components capable of analyzing a raw target object (e.g. a function)
    and producing a static Task Definition (TaskDef).
    """

    def analyze(self, target: Any) -> TaskDef:
        """
        Analyze the given target and return its static definition.

        Args:
            target: The executable object (function, coroutine function, etc.)

        Returns:
            TaskDef: The static intermediate representation.
        """
        ...