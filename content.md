好的，我们正处于 RED 状态，目标明确。现在是实施修复，让 `test_task_returning_lazy_result_is_forbidden` 测试通过的时候了。

经过分析，我发现我之前的思考有一个偏差：这个检查**不能**在 `GraphBuilder` 中静态完成，因为它无法预知一个任务在运行时的返回值类型。这个检查**必须**在任务被实际执行后，在运行时进行。

因此，我们的测试用例 `test_task_returning_lazy_result_is_forbidden` 的方向是正确的，但它测试了错误的目标 (`build_graph`)。它应该测试 **执行时** 的行为 (`engine.run`)。

我将生成一个计划来同时完成两件事：
1.  修正测试用例，使其正确地调用 `engine.run` 来触发运行时检查。
2.  在 `LocalExecutor` 中实现这个运行时检查，当检测到返回 `LazyResult` 时抛出 `StaticGraphError`。

## [WIP] feat(engine): 在运行时强制执行静态图完整性

### 错误分析
测试 `test_task_returning_lazy_result_is_forbidden` 失败的直接原因是它错误地期望 `build_graph` 抛出 `StaticGraphError`。然而，图的构建过程无法静态地知道任务的返回值类型。这个“任务返回 `LazyResult`”的反模式只能在任务被**实际执行**时才能被检测到。因此，检查逻辑必须位于执行器（Executor）中，而测试用例必须触发执行器。

### 用户需求
实施新的战略原则，即在运行时检测并禁止任务返回 `LazyResult`，从而使静态图完整性测试通过。

### 评论
这是一个关键的实现步骤，它将我们的战略决议转化为具体的代码护栏。通过在 `LocalExecutor` 中添加这个检查，我们创建了一个强大的安全网，确保旧的、隐式的 TCO 行为被彻底根除，并为用户提供清晰、可操作的错误信息，引导他们使用新的 `cs.Jump` 模式。

### 目标
1.  修改 `test_task_returning_lazy_result_is_forbidden` 测试，使其调用 `engine.run` 而非 `build_graph`，从而正确地测试运行时行为。
2.  修改 `LocalExecutor`，在执行完任务后检查其返回值。如果返回值是 `LazyResult` 或 `MappedLazyResult`，则抛出 `StaticGraphError`。

### 基本原理
我们将把验证逻辑放在它唯一能够生效的地方：`LocalExecutor.execute` 方法中，在任务函数被调用并返回结果之后。同时，我们将修正测试用例，使其从一个错误的“构建时”测试转变为一个正确的“运行时”测试。这两项修改将协同工作，使我们的测试套件能够正确地验证并强制执行新的架构原则。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/engine #comp/tests #concept/graph-integrity #scope/core #ai/instruct #task/domain/engine #task/object/executor #task/action/validation-enforcement #task/state/continue

---

### Script

#### Acts 1: 修正测试用例以测试运行时

我们将重写 `test_static_integrity.py` 中的测试，使其成为一个 `async` 测试，并调用 `engine.run`。

~~~~~act
write_file
tests/engine/graph/test_static_integrity.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.graph import StaticGraphError
from cascade.runtime import Engine, MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_task_returning_lazy_result_is_forbidden_at_runtime():
    """
    Verifies that the Executor rejects the anti-pattern of a task
    returning a LazyResult at runtime. This violates the static, declarative nature
    of Cascade graphs and the new explicit control flow model.
    """

    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        # This is the anti-pattern: a task's logic should not be
        # building new graph components at runtime. It should return data or a Jump.
        return task_b()

    workflow = task_a_violating()

    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )

    # This test will FAIL initially because the LocalExecutor does not yet
    # raise StaticGraphError. It will pass once the validation is implemented.
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' illegally returned a LazyResult",
    ):
        await engine.run(workflow)
~~~~~

#### Acts 2: 在 LocalExecutor 中实现运行时检查

现在，我们在 `LocalExecutor` 中添加检查逻辑，使其在检测到反模式时抛出 `StaticGraphError`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List
from cascade.graph.model import Node


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if inspect.iscoroutinefunction(node.callable_obj):
            return await node.callable_obj(*args, **kwargs)
        else:
            return node.callable_obj(*args, **kwargs)
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """



    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if inspect.iscoroutinefunction(node.callable_obj):
            result = await node.callable_obj(*args, **kwargs)
        else:
            result = node.callable_obj(*args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
            raise StaticGraphError(
                f"Task '{node.name}' illegally returned a LazyResult. "
                "Tasks must return data. For control flow, return a cs.Jump(...) signal instead."
            )

        return result
~~~~~

### 下一步建议
我们已经完成了运行时检查的实现和相应测试的修正。现在，请再次运行测试。我们期望 `test_static_integrity.py` 和 `test_explicit_control_flow.py` 都能通过，将测试套件带回 GREEN 状态。

一旦成功，我们将彻底废弃隐式 TCO，并可以安全地清理 `GraphExecutionStrategy` 中所有相关的旧代码（如 `_cycle_cache`），进一步简化架构。
