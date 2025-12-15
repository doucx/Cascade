Of course. Your analysis is spot on, and embracing this architectural refinement is a significant step towards a more robust and maintainable system. We will proceed with the event-driven refactoring of the `dry_run` tool.

This plan outlines the necessary steps to decouple the tool's core logic from its presentation layer, thereby aligning it with the project's core architectural principles and vastly improving the quality of its tests.

## [WIP] refactor(tools): Re-implement dry_run using an event-driven architecture

### 用户需求
1.  **彻底解耦测试与 UI**: 消除 `test_tools.py` 中对 `dry_run` 输出字符串的硬编码断言。
2.  **事件驱动**: 将 `dry_run` 的核心分析逻辑重构为基于 `MessageBus` 的事件发布机制。
3.  **架构一致性**: 确保 `tools` 模块遵循与 `runtime` 相同的可观测性设计模式。

### 评论
这是一个具有深远价值的重构。它不仅极大地提高了测试的健壮性，还为 `dry_run` 工具未来支持多种输出格式（如 JSON, YAML）打开了大门，而无需修改其核心分析逻辑。这是软件工程中“关注点分离”原则的典范应用。

### 目标
1.  在 `src/cascade/tools/events.py` 中定义 `PlanAnalysisStarted`, `PlanNodeInspected`, 和 `PlanAnalysisFinished` 事件。
2.  在 `src/cascade/tools/preview.py` 中重构 `dry_run`，将其拆分为核心分析函数（发布事件）和默认的控制台订阅者（消费事件并打印）。
3.  重写 `tests/test_tools.py`，使用 Mock `MessageBus` 来验证事件序列的正确性，替代 `capsys` 对 `stdout` 的捕获。

### 基本原理
通过将“计算图分析”与“结果展示”这两个关注点分离，我们可以对前者进行精确的逻辑测试，验证其是否为正确的依赖图生成了正确的节点序列和元数据。测试将验证业务逻辑的“意图”（即正确的数据流向了 Bus），而无需关心“实现”（即最终打印出来的字符格式）。这完全符合 `d3-principle-python-testing-mock-intent` 的精神。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/tools #comp/tests #scope/dx #scope/core
#ai/brainstorm
#task/domain/testing #task/object/dry-run-tool #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 定义工具层事件

我们首先在 `tools` 模块下创建一个新文件来定义描述 `dry_run` 过程的事件结构。

~~~~~act
write_file
src/cascade/tools/events.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any, Dict
from ..runtime.events import Event


@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    """Fired when dry_run starts analyzing a target."""
    target_node_id: str


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""
    index: int
    total_nodes: int
    node_id: str
    node_name: str
    literal_inputs: Dict[str, Any]


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    """Fired when dry_run analysis is complete."""
    total_steps: int
~~~~~

#### Acts 2: 更新 `__init__.py`

在 `tools/__init__.py` 中导出新事件，使其易于访问。

~~~~~act
write_file
src/cascade/tools/__init__.py
~~~~~
~~~~~python
from .preview import dry_run
from .events import (
    ToolEvent,
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)

__all__ = [
    "dry_run",
    "ToolEvent",
    "PlanAnalysisStarted",
    "PlanNodeInspected",
    "PlanAnalysisFinished",
]
~~~~~

#### Acts 3: 重构 `dry_run` 实现

我们将 `dry_run` 拆分为 `_analyze_plan` (核心逻辑) 和 `DryRunConsoleSubscriber` (视图逻辑)。

~~~~~act
write_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..runtime.engine import Engine
from ..runtime.bus import MessageBus
from .events import PlanAnalysisStarted, PlanNodeInspected, PlanAnalysisFinished


def dry_run(target: LazyResult[Any]) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    bus = MessageBus()
    # Attach the console view
    DryRunConsoleSubscriber(bus)
    
    # Run the analysis logic
    _analyze_plan(target, bus)


def _analyze_plan(target: LazyResult[Any], bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine()
    
    # 1. Build the graph statically
    graph = build_graph(target)
    
    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    total_steps = len(plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    for i, node in enumerate(plan, 1):
        bus.publish(
            PlanNodeInspected(
                run_id=target._uuid,
                index=i,
                total_nodes=total_steps,
                node_id=node.id,
                node_name=node.name,
                literal_inputs=node.literal_inputs
            )
        )

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))


class DryRunConsoleSubscriber:
    """
    Listens to plan analysis events and prints a human-readable report.
    """
    def __init__(self, bus: MessageBus):
        bus.subscribe(PlanAnalysisStarted, self.on_start)
        bus.subscribe(PlanNodeInspected, self.on_node)
        bus.subscribe(PlanAnalysisFinished, self.on_finish)

    def on_start(self, event: PlanAnalysisStarted):
        print("--- Cascade Execution Plan (Dry Run) ---")

    def on_node(self, event: PlanNodeInspected):
        # Format literal inputs for readability
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in event.literal_inputs.items()
        }
        print(f"[{event.index}/{event.total_nodes}] {event.node_name} (Literals: {literals_repr})")

    def on_finish(self, event: PlanAnalysisFinished):
        print("----------------------------------------")
~~~~~

#### Acts 4: 重写测试用例

我们完全重写测试，使用 Mock `MessageBus` 来验证发布的事件，而不是捕获 `stdout`。

~~~~~act
write_file
tests/test_tools.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
import cascade as cs
from cascade.tools.preview import _analyze_plan
from cascade.tools.events import PlanNodeInspected, PlanAnalysisFinished, PlanAnalysisStarted


def test_dry_run_emits_correct_events_linear():
    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    # Define the workflow
    result = step_b(step_a(), y=10)
    
    # Create a mock bus
    mock_bus = MagicMock()
    
    # Run the core analysis logic
    _analyze_plan(result, mock_bus)

    # Collect all published events
    # mock_bus.publish.call_args_list is a list of calls, each call is (args, kwargs)
    # We want the first arg of each call, which is the event object
    events = [call.args[0] for call in mock_bus.publish.call_args_list]

    # Assert basic sequence
    assert len(events) == 4 # Start + NodeA + NodeB + Finish
    
    assert isinstance(events[0], PlanAnalysisStarted)
    
    # Check Step A
    node_a_event = events[1]
    assert isinstance(node_a_event, PlanNodeInspected)
    assert node_a_event.index == 1
    assert node_a_event.node_name == "step_a"
    assert node_a_event.literal_inputs == {}

    # Check Step B
    node_b_event = events[2]
    assert isinstance(node_b_event, PlanNodeInspected)
    assert node_b_event.index == 2
    assert node_b_event.node_name == "step_b"
    # This assertion replaces the brittle string check "Literals: {'y': 10}"
    assert node_b_event.literal_inputs == {'y': 10}

    assert isinstance(events[3], PlanAnalysisFinished)


def test_dry_run_emits_correct_events_diamond():
    @cs.task
    def t_a(): return 1
    @cs.task
    def t_b(x): return x + 1
    @cs.task
    def t_c(x): return x * 2
    @cs.task
    def t_d(y, z): return y + z

    r_d = t_d(t_b(t_a()), z=t_c(t_a()))

    mock_bus = MagicMock()
    _analyze_plan(r_d, mock_bus)
    
    events = [call.args[0] for call in mock_bus.publish.call_args_list]
    
    # Filter only node events
    node_events = [e for e in events if isinstance(e, PlanNodeInspected)]
    assert len(node_events) == 4
    
    names = [e.node_name for e in node_events]
    
    # Assert topological order
    assert names[0] == "t_a"
    assert names[-1] == "t_d"
    assert "t_b" in names[1:3]
    assert "t_c" in names[1:3]
~~~~~

### 下一步建议

我们已经成功地将 `dry_run` 工具重构为一个事件驱动的组件，并为其配备了健壮的、不依赖 UI 的测试。

下一步，我建议：
1.  **运行测试**: 执行 `pytest` 来验证我们新重构的实现和测试用例是否按预期工作。
2.  **提交变更**: 在测试通过后，创建一个 `[COMMIT]` 计划来将这些逻辑上相关的变更作为一个原子单元提交到版本控制中。
