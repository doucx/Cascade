Excellent. This is a critical strategic decision that will simplify the architecture and make the programming model much more robust. By completely abandoning the old, implicit TCO model, we eliminate ambiguity and make the entire system more predictable.

We will now proceed with TDD to enforce this new, stricter model. Our first step is to create a test that fails because the `GraphBuilder` *doesn't yet* reject the anti-pattern (a task returning a `LazyResult`).

## [WIP] test: 添加静态图完整性校验的失败测试

### 用户需求
根据新的战略决议，我们必须禁止任务返回 `LazyResult`。为了驱动这一变更，需要创建一个新的测试用例。该测试用例应尝试构建一个包含此反模式的图，并断言 `GraphBuilder` 会抛出一个新的、特定的 `StaticGraphError`。

### 评论
这是一个决定性的步骤，它将 Cascade 的编程模型从“灵活但模糊”转变为“严格但清晰”。通过在 `GraphBuilder` 层面设立一个“看门人”，我们从根本上杜绝了运行时可能出现的歧义和上下文丢失问题。这个测试将成为新架构原则的第一个守护者。

### 目标
1.  在 `cascade-graph` 中创建一个新的异常类型 `StaticGraphError`。
2.  创建一个新的测试文件 `tests/engine/graph/test_static_integrity.py`。
3.  在新测试文件中，编写一个名为 `test_task_returning_lazy_result_is_forbidden` 的测试。
4.  此测试将定义一个返回 `LazyResult` 的任务，并调用 `build_graph`。
5.  测试将使用 `pytest.raises(StaticGraphError)` 来断言 `build_graph` 的行为。
6.  **预期结果**: 此测试将**失败**，因为 `build_graph` 目前会成功构建图，而不会抛出我们期望的 `StaticGraphError`。

### 基本原理
我们正在将一个曾经导致**运行时错误**（`RuntimeError`）的问题，转变为一个**构建时错误**（`StaticGraphError`）。这是“快速失败”原则的体现。此测试的目的是验证 `GraphBuilder` 的验证逻辑。在当前代码下，由于验证逻辑尚不存在，`pytest.raises` 将捕获不到任何异常，从而导致测试失败，使我们进入一个清晰的 RED 状态。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/graph #comp/tests #concept/graph-integrity #scope/api #scope/dx #ai/instruct #task/domain/engine #task/object/graph-builder #task/action/validation-enforcement #task/state/continue

---

### Script

#### Acts 1: 定义新的异常类型

我们首先在 `cascade-graph` 包中创建新的异常文件和类型。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/exceptions.py
~~~~~
~~~~~python
class CascadeGraphError(Exception):
    """Base class for errors in the cascade-graph package."""

    pass


class StaticGraphError(CascadeGraphError):
    """
    Raised when an anti-pattern that violates static graph principles
    is detected during the build process.
    """

    pass
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "analyze_task_source",
    "assign_tco_cycle_ids",
]
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids
from .exceptions import StaticGraphError

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "analyze_task_source",
    "assign_tco_cycle_ids",
    "StaticGraphError",
]
~~~~~

#### Acts 2: 创建新的失败测试文件

现在，我们创建 `test_static_integrity.py` 文件，其中包含我们的 RED 测试。

~~~~~act
write_file
tests/engine/graph/test_static_integrity.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.graph import build_graph, StaticGraphError


def test_task_returning_lazy_result_is_forbidden():
    """
    Verifies that the GraphBuilder rejects the anti-pattern of a task
    returning a LazyResult. This violates the static, declarative nature
    of Cascade graphs.
    """

    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        # This is the anti-pattern: a task's logic should not be
        # building new graph components at runtime.
        return task_b()

    workflow = task_a_violating()

    # This test will FAIL initially, because build_graph does not yet
    # raise StaticGraphError. It will pass once the validation is implemented.
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' returns a LazyResult",
    ):
        build_graph(workflow)
~~~~~

#### Acts 3: 删除旧的、有缺陷的测试

既然我们已经有了新的、更根本的测试，`test_explicit_jump_from_downstream_task` 就变得多余且具有误导性了。我们将其删除。

~~~~~act
patch_file
tests/engine/runtime/test_explicit_control_flow.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_explicit_jump_from_downstream_task():
    """
    Tests that the engine can correctly handle a Jump signal that originates
    from a downstream task, not the root of the execution graph for that step.
    """

    @cs.task
    def decider(n: int):
        if n <= 0:
            return cs.Jump(target_key="exit", data=n)
        else:
            return cs.Jump(target_key="continue", data=n - 1)

    @cs.task
    def main_task(n: int):
        # This task delegates the jump decision to a downstream task
        return decider(n)

    # The jump selector's target must be the task that receives the new data.
    # Here, 'decider' is the task that gets re-invoked with new data.
    loop_node = decider(cs.Param("next_n"))

    jump_selector = cs.select_jump(
        {
            "continue": loop_node,
            "exit": None,
        }
    )

    # CRITICAL: The binding is correctly placed on the task that returns the
    # Jump signal (`decider`), which is instantiated here as `loop_node`.
    cs.bind(loop_node, jump_selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We run the main_task. The engine must be smart enough to identify that
    # the Jump signal came from `decider` and find the binding there.
    final_result = await engine.run(main_task(3))

    assert final_result == 0
~~~~~
~~~~~python
# The test `test_explicit_jump_from_downstream_task` has been removed.
# It was based on a flawed premise that tasks should be able to return
# LazyResults. The new strategic direction is to forbid this pattern at the
# graph build stage, making the runtime test obsolete.
~~~~~

### 下一步建议
我们已经成功地将测试套件置于一个真正的 RED 状态。新的测试 `test_task_returning_lazy_result_is_forbidden` 现在会失败，因为它期望一个 `StaticGraphError`，但 `GraphBuilder` 尚未实现此检查。

下一步，我们将进入 GREEN 阶段。我将生成一个新计划，修改 `GraphBuilder` 和 `NodeProcessor` 以检测并拒绝这种反模式，从而使我们的新测试通过。
