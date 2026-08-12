from typing import Any, Protocol

from cascade.spec.ir.graph import TaskDef


class TaskAnalyzer(Protocol):
    def analyze(self, target: Any) -> TaskDef: ...
