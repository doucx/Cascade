from contextvars import ContextVar
from typing import Dict, List, Any, Optional
from cascade.spec.dsl.inputs import InputSpec


class WorkflowContext:
    def __init__(self):
        self.input_specs: Dict[str, InputSpec] = {}
        self.values: Dict[str, Any] = {}

    def register(self, spec: InputSpec):
        if spec.name in self.input_specs:
            # 在未来可以实现更复杂的合并或警告逻辑
            return
        self.input_specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self.input_specs.values())

    def set_value(self, name: str, value: Any) -> None:
        self.values[name] = value

    def get_value(self, name: str) -> Optional[Any]:
        return self.values.get(name)


# 创建一个全局可访问的上下文变量
_current_context = ContextVar("cascade_workflow_context", default=WorkflowContext())


def get_current_context() -> WorkflowContext:
    return _current_context.get()
