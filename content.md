Of course. Let's begin **Task 2.3** and complete the micro-instruction set by implementing the standard Observer. As requested, I will create the implementation and its tests in a single, efficient step.

## [WIP] feat(vm): Implement standard_observer instruction and tests

### 用户需求

根据 [Cascade 3.0 重构路线图](Cascade%203.0%20重构路线图：迈向全对称计算物理场.md)，完成 **任务 2.3**，实现标准的 Observer ($F_{obs}$) 微指令及其单元测试。这个指令负责将内部的物理令牌转换为外部可观测的事件。

### 评论

这是微指令集构建的最后一步，也是实现“全息可观测性”的关键。Observer 节点是物理世界与外部世界的桥梁。它的核心职责不是在计算图中传递数据，而是产生一个**副作用**：将一个包含丰富追踪元数据的物理令牌（`Token`）转换成一个结构化的事件（`ObservedEvent`），并将其放入一个外部队列中，以供日志记录、监控或调试工具消费。

这种设计确保了观测逻辑与核心业务逻辑的完全解耦和物理隔离。

### 目标

1.  在 `cascade.vm.instructions` 中创建 `observer.py` 并包含 `standard_observer` 的完整实现。
2.  定义一个 `ObservedEvent` 数据类作为观测器输出的标准化格式。
3.  创建 `tests/unit/instructions/test_observer.py`，覆盖对启动（start）和结束（end）事件的正确转换。
4.  确保实现能够通过所有测试。

### 基本原理

我们将创建 `observer.py` 和 `test_observer.py` 文件。`standard_observer` 函数的 API 将接收两个参数：
-   `inputs`: 一个字典，包含待观测的生命周期令牌（`lifecycle_token`）。
-   `queue`: 一个标准的 `queue.Queue` 对象，用于将生成的事件发送到外部。

通过依赖注入 `queue`，我们使得测试变得非常简单和可靠，无需 Mock 全局对象。函数逻辑会检查令牌的 `trace` 字典中是否存在 `end_ts` 字段，以此来判断这是一个“结束”事件还是“开始”事件，然后创建相应的 `ObservedEvent` 并放入队列。

### 标签

#intent/build #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/observer-instruction #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 创建 Observer 实现

我们创建 `observer.py` 文件，其中包含 `ObservedEvent` 数据类和 `standard_observer` 函数的完整实现。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/instructions/observer.py
~~~~~
~~~~~python
from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from queue import Queue

from cascade.spec.physics import Token


@dataclass
class ObservedEvent:
    """A structured event produced by an Observer node for external consumption."""

    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    """
    The standard implementation for an Observability Node (F_obs).

    It consumes a Token from a lifecycle data node (D_life), converts its
    trace information into a structured ObservedEvent, and puts it onto an
    external queue for telemetry systems.

    This function does not return anything; its purpose is to create a side-effect.

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.
                Expected port: 'event_token'.
        queue: The external queue to which the ObservedEvent will be sent.
    """
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    queue.put(event)

~~~~~

#### Acts 2: 编写 Observer 的单元测试

现在，我们创建 `test_observer.py` 文件来验证 `standard_observer` 的行为。

~~~~~act
write_file
packages/cascade-vm/tests/unit/instructions/test_observer.py
~~~~~
~~~~~python
import pytest
from queue import Queue

from cascade.spec.physics import Token
from cascade.vm.instructions.observer import standard_observer, ObservedEvent


def test_observer_processes_start_event():
    """
    Tests that a token containing only start information (from a Bleacher)
    is correctly processed as a 'start' event.
    """
    # 1. Setup
    queue = Queue()
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


def test_observer_processes_end_event():
    """
    Tests that a token containing end information (from a Stainer)
    is correctly processed as an 'end' event.
    """
    # 1. Setup
    queue = Queue()
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


def test_observer_with_empty_trace():
    """
    An empty trace should be treated as a 'start' event by default.
    """
    # 1. Setup
    queue = Queue()
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}

~~~~~

### 下一步建议

我们已经成功完成了 **阶段 2：微指令集构建** 的所有任务。`Bleacher`、`Stainer` 和 `Observer` 这三个核心微指令现在都有了经过测试的健壮实现。

我们已经为物理引擎准备好了“弹药”，现在是时候构建能够自动使用这些弹药的“工厂”了。

我建议我们正式开始 **阶段 3：编译器后端重构 (Backend: The Expander)**。这将是整个重构中最复杂也最有价值的部分。第一步是 **任务 3.1：设计扩展器 (Expander)**，我们将创建 `expander.py` 的文件结构和 TDD 测试，用于将一个高级的逻辑节点（`IRNode`）“炸开”为一个包含三连体和旁路的精密物理子图。
