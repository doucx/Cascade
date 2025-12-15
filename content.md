## [WIP] fix: 修复运行时事件类的 Dataclass 继承顺序问题

### 错误分析

**错误信息**: `TypeError: non-default argument 'target_tasks' follows default argument 'run_id'`

**原因**: 在 Python 的 `dataclass` 继承机制中，如果父类 (`Event`) 定义了带有默认值的字段（如 `event_id`, `run_id`），那么子类 (`RunStarted`) 中定义的字段也**必须**拥有默认值。否则，生成的 `__init__` 方法会将没有默认值的参数放在有默认值的参数之后，这在 Python 语法中是非法的。

**解决方案**: 为所有继承自 `Event` 的子类字段添加默认值（使用 `field(default_factory=...)` 或 `None`）。虽然这在语义上使字段变为“可选”，但在 `Engine` 内部构造这些事件时，我们会显式传递这些参数，因此不会影响系统的正确性，同时保持了对 Python 3.8+ 的兼容性。

### 计划标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/observability

---

### Script

#### Acts 1: 修正事件定义 (Events)

修改 `src/cascade/runtime/events.py`，为所有子类字段添加默认值。

~~~~~act
write_file
src/cascade/runtime/events.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time

@dataclass(frozen=True)
class Event:
    """Base class for all runtime events."""
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None

@dataclass(frozen=True)
class RunStarted(Event):
    """Fired when the engine starts a new run."""
    # Must provide defaults because base class has defaults
    target_tasks: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RunFinished(Event):
    """Fired when the engine finishes a run."""
    status: str = "Unknown" # "Succeeded", "Failed"
    duration: float = 0.0
    error: Optional[str] = None

@dataclass(frozen=True)
class TaskEvent(Event):
    """Base for events related to a specific task instance."""
    task_id: str = ""
    task_name: str = ""

@dataclass(frozen=True)
class TaskExecutionStarted(TaskEvent):
    """Fired just before a task's function is executed."""
    pass

@dataclass(frozen=True)
class TaskExecutionFinished(TaskEvent):
    """Fired after a task's function finishes, successfully or not."""
    status: str = "Unknown" # "Succeeded", "Failed"
    duration: float = 0.0
    result_preview: Optional[str] = None
    error: Optional[str] = None

@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""
    reason: str = "Unknown" # "CacheHit", "ConditionFalse"
~~~~~

### 下一步建议
如果测试通过，我们可以继续按照原计划执行 **第 5 步：实现核心协议与默认适配器**。
