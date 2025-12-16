好的，审查完成。

根据 `rg assert` 的输出，我识别出以下几个可以应用我们新测试模式的关键文件：
1.  `tests/integration/test_end_to_end.py`: 这个文件定义了它自己的 `SpySubscriber` 类，这是典型的重复代码，可以被我们的 centralized fixture 替代。
2.  `tests/tools/test_preview.py`: `test_dry_run_emits_correct_events_linear` 使用了 `unittest.mock.MagicMock` 来模拟 bus，这可以被 `bus_and_spy` fixture 替代，使其测试模式更统一。此外，`test_console_subscriber_renders_correctly` 仍然在断言完整的 UI 字符串，可以使其更加健壮。

其他文件中的 `assert` 主要用于验证数据、类型或逻辑流程，并未违反“验证意图”的原则，因此暂不作修改。

我将生成一个计划来重构这两个文件。

## [WIP] test: 推广事件驱动的测试模式到集成和工具测试中

### 用户需求
继续审查测试套件，识别并重构那些可以从新的 `bus_and_spy` fixture 中受益的测试用例，以提高整个测试套件的一致性、健壮性和可维护性。

### 评论
这次重构是上一个计划的自然延续，它将我们建立的最佳实践推广到更高层次的测试（集成测试和工具测试）中。通过移除本地的 `SpySubscriber` 实现并替换 `MagicMock` 的使用，我们不仅减少了代码重复，还统一了整个项目的异步和事件驱动测试方法，这是一个巨大的开发者体验 (DX) 胜利。

### 目标
1.  **重构 `tests/integration/test_end_to_end.py`**:
    *   移除本地定义的 `SpySubscriber` 类。
    *   将所有测试用例修改为使用 `bus_and_spy` fixture。
    *   保持原有的事件断言逻辑不变。
2.  **重构 `tests/tools/test_preview.py`**:
    *   修改 `test_dry_run_emits_correct_events_linear`，用 `bus_and_spy` fixture 替换 `MagicMock`，并更新断言以检查 `spy.events`。
    *   修改 `test_console_subscriber_renders_correctly`，使其断言更关注语义标记而非精确的字符串匹配，以增强健壮性。

### 基本原理
我们正在系统性地偿还测试技术债务。
*   **消除重复 (DRY)**: `test_end_to_end.py` 中的 `SpySubscriber` 是一个教科书式的重复代码示例。将其替换为 `conftest.py` 中的共享 fixture 是标准实践。
*   **统一模式**: 在 `test_preview.py` 中用真实的 `MessageBus` 和 `SpySubscriber` 替换 `MagicMock`，使测试更接近真实世界的场景，并与其他事件驱动的测试保持一致。
*   **增强韧性**: 对 `test_console_subscriber_renders_correctly` 的断言进行“软化”，使其在保留测试核心目的（验证输出格式）的同时，不易因微小的文本调整而失败。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `test_end_to_end.py` 以使用共享 fixture

我们将完全重写此文件，移除本地的 `SpySubscriber` 并将所有测试函数注入 `bus_and_spy` fixture。

~~~~~act
write_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.events import (
    TaskExecutionFinished,
    RunFinished,
)


def test_e2e_linear_workflow(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    import asyncio
    engine = Engine(bus=bus)
    result = asyncio.run(engine.run(final_greeting))

    assert result == "Hello, {name}!".format(name="Cascade")

    event_names = [type(e).__name__ for e in spy.events]
    assert event_names == [
        "RunStarted",
        "TaskExecutionStarted",
        "TaskExecutionFinished",
        "TaskExecutionStarted",
        "TaskExecutionFinished",
        "RunFinished",
    ]

    # Assert specific event details
    assert spy.events[1].task_name == "get_name"
    assert spy.events[2].status == "Succeeded"
    assert spy.events[2].result_preview == "'Cascade'"
    assert spy.events[4].status == "Succeeded"
    assert spy.events[5].status == "Succeeded"


def test_e2e_diamond_workflow_and_result(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def t_a():
        return 5

    @cs.task
    def t_b(x):
        return x * 2  # 10

    @cs.task
    def t_c(x):
        return x + 3  # 8

    @cs.task
    def t_d(y, z):
        return y + z  # 18

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    import asyncio
    engine = Engine(bus=bus)
    result = asyncio.run(engine.run(r_d))
    assert result == 18


def test_e2e_failure_propagation(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def ok_task():
        return True

    @cs.task
    def failing_task(x):
        raise ValueError("Something went wrong")

    @cs.task
    def unreachable_task(y):
        return False

    r1 = ok_task()
    r2 = failing_task(r1)
    r3 = unreachable_task(r2)

    import asyncio
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        asyncio.run(engine.run(r3))

    event_names = [type(e).__name__ for e in spy.events]
    assert event_names == [
        "RunStarted",
        "TaskExecutionStarted",  # ok_task started
        "TaskExecutionFinished",  # ok_task finished
        "TaskExecutionStarted",  # failing_task started
        "TaskExecutionFinished",  # failing_task finished
        "RunFinished",
    ]

    # Assert success of the first task
    task_ok_finished = spy.events[2]
    assert isinstance(task_ok_finished, TaskExecutionFinished)
    assert task_ok_finished.task_name == "ok_task"
    assert task_ok_finished.status == "Succeeded"

    # Assert failure of the second task
    task_fail_finished = spy.events[4]
    assert isinstance(task_fail_finished, TaskExecutionFinished)
    assert task_fail_finished.task_name == "failing_task"
    assert task_fail_finished.status == "Failed"
    assert "ValueError: Something went wrong" in task_fail_finished.error

    # Assert failure of the entire run
    run_finished = spy.events[5]
    assert isinstance(run_finished, RunFinished)
    assert run_finished.status == "Failed"
~~~~~

#### Acts 2: 重构 `test_preview.py` 以统一测试模式

我们将修改此文件，用 `bus_and_spy` fixture 替换 `MagicMock`，并使 UI 断言更加健壮。

~~~~~act
write_file
tests/tools/test_preview.py
~~~~~
~~~~~python
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a(), y=10)
    _analyze_plan(result, bus)

    # Assert basic sequence
    assert len(spy.events) == 4  # Start + NodeA + NodeB + Finish
    assert isinstance(spy.events_of_type(PlanAnalysisStarted)[0], PlanAnalysisStarted)
    assert isinstance(spy.events_of_type(PlanAnalysisFinished)[0], PlanAnalysisFinished)

    node_events = spy.events_of_type(PlanNodeInspected)
    assert len(node_events) == 2

    # Check Step A
    node_a_event = node_events[0]
    assert node_a_event.index == 1
    assert node_a_event.node_name == "step_a"
    assert node_a_event.literal_inputs == {}

    # Check Step B
    node_b_event = node_events[1]
    assert node_b_event.index == 2
    assert node_b_event.node_name == "step_b"
    assert node_b_event.literal_inputs == {"y": 10}


def test_dry_run_emits_correct_events_diamond(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_d = t_d(t_b(r_a), z=t_c(r_a))

    _analyze_plan(r_d, bus)

    node_events = spy.events_of_type(PlanNodeInspected)
    assert len(node_events) == 4

    names = [e.node_name for e in node_events]

    # Assert topological order
    assert names[0] == "t_a"
    assert names[-1] == "t_d"
    assert "t_b" in names[1:3]
    assert "t_c" in names[1:3]


def test_console_subscriber_renders_correctly(capsys):
    """
    Tests the View layer independently for correct formatting.
    """
    bus = MessageBus()
    DryRunConsoleSubscriber(bus)

    # 1. Publish Start Event
    bus.publish(PlanAnalysisStarted(target_node_id="root"))
    captured = capsys.readouterr()
    assert "---" in captured.out
    assert "Execution Plan" in captured.out

    # 2. Publish Node Event
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            literal_inputs={"param": 42},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "'param': 42" in captured.out

    # 3. Publish Finish Event
    bus.publish(PlanAnalysisFinished(total_steps=2))
    captured = capsys.readouterr()
    assert "---" in captured.out
~~~~~

### 下一步建议
我们已经成功地将核心测试套件统一到了一个更健壮、更一致的事件驱动测试模式上。测试技术债务的主要部分已经偿还。

下一步，我们可以将注意力转向代码库的其他方面。一个有价值的方向是：
*   **优化 Fixture 作用域**: 审查测试套件，识别那些创建成本高且只读的 fixture，并根据 `d3-principle-pytest-fixture-scoping` 原则提升其作用域（例如，从 `function` 到 `module`），以提高测试执行速度。
*   **文档生成**: 探索如何利用 Cascade 自身的能力来自动化其文档的某些部分，真正实现“吃自己的狗粮”。
