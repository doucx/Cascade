from contextvars import ContextVar
from typing import Dict, List
from cascade.interfaces.spec.input import InputSpec

class WorkflowContext:
    def __init__(self):
        self.input_specs: Dict[str, InputSpec] = {}

    def register(self, spec: InputSpec):
        if spec.name in self.input_specs:
            # 在未来可以实现更复杂的合并或警告逻辑
            return
        self.input_specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self.input_specs.values())

# 创建一个全局可访问的上下文变量
_current_context = ContextVar("cascade_workflow_context", default=WorkflowContext())

def get_current_context() -> WorkflowContext:
    """获取当前的 WorkflowContext。"""
    return _current_context.get()