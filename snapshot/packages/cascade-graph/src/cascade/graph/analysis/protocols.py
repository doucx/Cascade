from typing import Protocol, Any
from cascade.spec.ir.models import TaskDef


class TaskAnalyzer(Protocol):
    def analyze(self, target: Any) -> TaskDef: ...
