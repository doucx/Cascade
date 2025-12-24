好的，我们正式开始 **阶段四：[Optimization] - 建立统一的双层身份体系**。

遵循您指定的严格 TDD 流程，我的第一步是创建一个测试用例来定义我们最终要实现的行为。这个测试将验证引擎对于结构相同但参数不同的工作流，是否能够复用其执行计划，从而只调用一次昂贵的 `Solver.resolve()` 方法。

根据我的分析，由于当前基于 `template_id` 的缓存实现，这个测试在初始状态下会 **通过 (PASS)**。这看起来似乎与 TDD “先红后绿”的原则相悖，但这是一个符合逻辑且必要的步骤：

1.  **定义契约 (当前 Plan)**: 我们首先通过一个会通过的测试，将“计划可复用”这个核心行为固化为一个必须遵守的契约和回归测试。
2.  **进入 RED 状态 (下一 Plan)**: 我的下一个计划将是对 `HashingService` 进行重构，移除 `template_id` 的计算逻辑。这个重构会**破坏**现有的缓存机制，从而使我们刚刚添加的测试转为 **失败 (RED)** 状态。
3.  **进入 GREEN 状态 (后续 Plan)**: 最后，我将实现新的 `BlueprintHasher` 并改造 `Engine` 的缓存逻辑，让测试重新 **通过 (GREEN)**，但这次是基于一个更清晰、更健壮的架构。

这个“绿 -> 红 -> 绿”的序列确保了我们在进行破坏性重构之前，有一个可靠的安全网，完全符合 TDD 的精神。

我将生成创建此测试文件的计划。

## [WIP] test: Add integration test for execution plan caching

### 用户需求
作为启动第四阶段“统一身份体系”的第一步，需要创建一个集成测试，用于验证 Cascade 引擎是否能够对结构相同但字面量参数不同的工作流，正确地复用其编译好的执行计划（Execution Plan）。

### 评论
这个测试是整个重构工作的基石和“北极星”。它将作为一个关键的回归测试，确保在我们将 `HashingService` 的职责拆分并引入新的 `BlueprintHasher` 后，引擎的核心性能承诺——“编译一次，运行多次”——没有被破坏。

### 目标
1.  创建一个新的测试文件 `tests/engine/integration/test_plan_caching.py`。
2.  在该文件中，实现一个测试用例，断言当连续运行两个结构相同（例如 `add(1, 2)` 和 `add(3, 4)`）的工作流时，`Solver.resolve()` 方法只被调用一次。

### 基本原理
我们将采用“测试间谍 (Test Spy)”模式，创建一个 `SpySolver` 来包装一个真实的 `NativeSolver`。这个 Spy 会使用 `unittest.mock.MagicMock` 来记录 `resolve` 方法的调用次数，同时将调用委托给真实的求解器以确保工作流能够正确执行。

通过断言 `mock_resolve.assert_called_once()`，我们可以高保真地验证引擎的 JIT 计划缓存机制是否按预期工作，而无需关心其内部实现（无论是基于旧的 `template_id` 还是新的 `Blueprint Hash`）。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/plan-caching #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 创建计划缓存的集成测试文件

我们将创建新的测试文件，并添加验证执行计划缓存行为的测试用例。

~~~~~act
write_file
tests/engine/integration/test_plan_caching.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock

from cascade import task, Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.bus import MessageBus
from cascade.spec.protocols import Solver
from cascade.graph.model import Graph


# Define a simple task for testing
@task
def add(a: int, b: int) -> int:
    return a + b


class SpySolver(Solver):
    """A solver that spies on calls and delegates to a real solver."""

    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        # Use MagicMock to wrap the real resolve method. This allows us to track
        # calls while still executing the real logic.
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph):
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol.
        pass


@pytest.fixture
def engine_with_spy_solver():
    """Provides an Engine with a solver that spies on `resolve` calls."""
    # The spy wraps a real solver to ensure the test can actually run
    spy_solver = SpySolver(NativeSolver())

    engine = Engine(
        solver=spy_solver,
        executor=LocalExecutor(),
        bus=MessageBus(),  # A silent bus for clean test output
    )
    # Return the engine and the mock object for making assertions
    return engine, spy_solver.resolve


@pytest.mark.asyncio
async def test_engine_reuses_plan_for_structurally_identical_graphs(
    engine_with_spy_solver,
):
    """
    Tests that the Engine's JIT plan cache is effective.

    It runs two workflows that are structurally identical but have different
    literal parameters. The solver should only be called once, for the first
    workflow, and the plan should be reused for the second.
    """
    engine, mock_resolve = engine_with_spy_solver

    # Define two structurally identical workflows with different literals
    workflow_a = add(1, 2)
    workflow_b = add(3, 4)

    # Run both workflows
    result_a = await engine.run(workflow_a)
    assert result_a == 3

    result_b = await engine.run(workflow_b)
    assert result_b == 7

    # Assert that the expensive solver was only called once
    mock_resolve.assert_called_once()
~~~~~

### 下一步建议

我们已经成功创建了定义期望行为的测试。

下一步，我将对 `cascade-graph` 包中的 `HashingService` 进行重构，移除计算 `template_id` 的逻辑，使其只负责计算实例的 `structural_id`。

这个改动将故意**破坏**当前的计划缓存功能，并使我们刚刚添加的测试**失败**，从而正式将我们的 TDD 流程带入 **RED** 状态。如果你同意，我将生成执行此重构的计划。
