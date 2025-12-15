简要回答
这是一个经典的 Python `dataclass` 继承陷阱：基类 `Event` 包含了带有默认值的字段 (`run_id=None`)，因此继承它的子类字段**必须**也要有默认值，否则会破坏 `__init__` 方法的参数顺序规则。

我将通过给 `src/cascade/tools/events.py` 中的所有字段添加默认值来修复此 `TypeError`。

## [WIP] fix(tools): resolve dataclass inheritance TypeError in dry_run events

### 摘要头
**fix(tools): resolve dataclass inheritance TypeError in dry_run events**

### 错误分析
`TypeError: non-default argument 'target_node_id' follows default argument 'run_id'`

-   **原因**: 基类 `cascade.runtime.events.Event` 定义了 `run_id: Optional[str] = None`。Python 语法规定，在函数签名（包括 `dataclass` 生成的 `__init__`）中，非默认参数不能出现在默认参数之后。
-   **子类现状**: `PlanAnalysisStarted` 定义了 `target_node_id: str` (无默认值)。
-   **冲突**: 导致 `__init__(self, ..., run_id=None, target_node_id)`，这是非法的。
-   **解决**: 为子类所有字段提供默认值（如 `""`, `0`, `field(default_factory=dict)`）。这在保留类型签名的同时满足了 Python 的语法要求。

### 用户需求
修复测试套件无法收集（Collection Error）的问题，以便验证 `dry_run` 的重构是否成功。

### 评论
这是在使用 `dataclass` 构建层级事件系统时常见的问题。虽然给必填字段加默认值在语义上略显宽松（允许了空构造），但这是为了利用继承带来的代码复用优势所必须做的权衡。

### 目标
修改 `src/cascade/tools/events.py`，为所有 `dataclass` 字段添加默认值。

### 基本原理
通过赋默认值，使得生成的 `__init__` 方法签名变为 `(..., run_id=None, target_node_id="")`，符合 Python 语法。

### 标签
#intent/fix #flow/draft #priority/critical
#comp/cli #comp/tests #scope/core
#ai/instruct
#task/domain/core #task/object/dry-run-tool #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修复 `tools/events.py` 中的 Dataclass 定义

我们将为所有字段添加合理的默认值（空字符串、0 或空字典）。

~~~~~act
write_file
src/cascade/tools/events.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, Dict, List
from ..runtime.events import Event


@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    """Fired when dry_run starts analyzing a target."""
    target_node_id: str = ""
    
    def _get_payload(self) -> Dict[str, Any]:
        return {"target_node_id": self.target_node_id}


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "literal_inputs": self.literal_inputs
        }


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    """Fired when dry_run analysis is complete."""
    total_steps: int = 0

    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}
~~~~~

### 下一步建议
一旦此修复应用，测试收集过程应该能通过。届时我们将运行测试以验证逻辑正确性。
