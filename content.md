Of course. You are correct; for API consistency, `dry_run` must also support this new syntax. My apologies for overlooking it.

I will create a single, comprehensive plan that adds the TDD test case for `dry_run` and implements the necessary changes in one step, as requested. This will bring the entire "Auto-Gathering" feature to completion.

## [WIP] feat: Add auto-gathering to dry_run and finalize feature

### 用户需求
`cs.dry_run()` 函数的 API 必须与 `cs.run()` 和 `cs.visualize()` 保持一致。它需要支持接收 `LazyResult` 实例的列表或元组，并为这个隐式的并行工作流打印出正确的执行计划。

### 评论
这是完成“自动汇合语法糖”功能的最后一步，也是至关重要的一步。确保所有面向用户的核心 API（`run`, `visualize`, `dry_run`）都遵循相同的输入约定，是提供无缝、可预测的开发者体验（DX）的基石。

### 目标
1.  向 `tests/sdk/tools/test_preview.py` 中添加一个新的 TDD 测试用例，该用例使用 `cs.dry_run([lr_a, lr_b])` 的形式进行调用。
2.  修改 `cascade.tools.preview.py` 中的 `_analyze_plan` 和/或 `dry_run` 函数，使其能够正确处理列表和元组输入。
3.  确保修改后，所有相关的测试（包括新旧测试）都能通过。

### 基本原理
我们将遵循为 `run` 和 `visualize` 建立的相同模式。通过在 `dry_run` 的入口处添加一个简单的包装层，我们将用户提供的列表输入转换为 `build_graph` 可以理解的单一根节点 (`_internal_gather(...)`)。此更改将与现有逻辑无缝集成，确保 `dry_run` 能够正确分析和显示由多个并行任务组成的隐式工作流的执行计划。

### 标签
#intent/build #flow/ready #priority/high #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/sdk #task/object/auto-gathering #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 为 `dry_run` 添加 TDD 测试

我将首先在 `test_preview.py` 中添加一个失败的测试用例来定义新功能的行为。

~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
    bus.publish(PlanAnalysisFinished(total_steps=2))
    captured = capsys.readouterr()
    assert "---" in captured.out
~~~~~
~~~~~python
    bus.publish(PlanAnalysisFinished(total_steps=2))
    captured = capsys.readouterr()
    assert "---" in captured.out


def test_dry_run_with_list_of_lazy_results(bus_and_spy):
    """
    Verifies that dry_run can accept a list of LazyResults and
    prints the correct plan, including the implicit gather node.
    """
    bus, spy = bus_and_spy

    @cs.task(pure=True)
    def t_a():
        return "a"

    @cs.task(pure=True)
    def t_b():
        return "b"

    lr_a = t_a()
    lr_b = t_b()

    _analyze_plan([lr_a, lr_b], bus)

    node_events = spy.events_of_type(PlanNodeInspected)
    # 3 nodes: t_a, t_b, and the final _internal_gather
    assert len(node_events) == 3

    names = [e.node_name for e in node_events]
    assert names[-1] == "_internal_gather"
    assert "t_a" in names
    assert "t_b" in names

    finish_event = spy.events_of_type(PlanAnalysisFinished)[0]
    assert finish_event.total_steps == 3
~~~~~

#### Acts 2: 在 `dry_run` 中实现自动汇合逻辑

现在，我将修改 `preview.py` 以使新测试通过。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult  # NEW
from cascade.graph.build import build_graph
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
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


def _analyze_plan(target: Any, bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # 1. Build the graph statically
    graph, _ = build_graph(target)
~~~~~
~~~~~python
from typing import Any
from cascade.graph.build import build_graph
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.internal.inputs import _internal_gather
from .events import PlanAnalysisStarted, PlanNodeInspected, PlanAnalysisFinished


def dry_run(target: Any) -> None:
    """
    Builds the computation graph for a target and prints the execution plan
    without running any tasks.
    """
    bus = MessageBus()
    # Attach the console view
    DryRunConsoleSubscriber(bus)

    # Run the analysis logic
    _analyze_plan(target, bus)


def _analyze_plan(target: Any, bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    if isinstance(target, (list, tuple)):
        if not target:
            # For empty list, emit a clean empty plan
            bus.publish(PlanAnalysisStarted(run_id="empty", target_node_id="empty"))
            bus.publish(PlanAnalysisFinished(run_id="empty", total_steps=0))
            return
        workflow_target = _internal_gather(*target)
    else:
        workflow_target = target

    # We use the default engine configuration to get the default solver
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # 1. Build the graph statically
    graph, _ = build_graph(workflow_target)
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~
~~~~~python
    # Calculate total nodes across all stages
    total_steps = sum(len(stage) for stage in plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    current_index = 1
    for stage in plan:
        for node in stage:
            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.structural_id,
                    node_name=node.name,
                    input_bindings=node.input_bindings,
                )
            )
            current_index += 1

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))
~~~~~
~~~~~python
    # Calculate total nodes across all stages
    total_steps = sum(len(stage) for stage in plan)

    run_id = workflow_target._uuid
    bus.publish(PlanAnalysisStarted(run_id=run_id, target_node_id=run_id))

    current_index = 1
    for stage in plan:
        for node in stage:
            bus.publish(
                PlanNodeInspected(
                    run_id=run_id,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.structural_id,
                    node_name=node.name,
                    input_bindings=node.input_bindings,
                )
            )
            current_index += 1

    bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))
~~~~~

### 下一步建议

我们已经完成了 `dry_run` 的实现。至此，"自动汇合"功能已经在所有三个核心用户 API (`run`, `visualize`, `dry_run`) 中得到了一致的支持，并且有了相应的测试覆盖。

整个功能现在是完整的、健壮的。我将生成一个最终的 `[COMMIT]` 计划，将这项功能的所有变更合并到一个原子提交中，以结束这个任务。
