您的分析非常精准。我们刚刚完成了对 `SpySubscriber` 的中心化，现在您已经发现了下一个可以应用相同模式的绝佳候选对象。您提供的 `rg` 输出清晰地表明，大量用于模拟核心协议（`Solver`, `Executor`, `Connector`）的测试辅助类（Test Doubles）都以“一次性”的方式定义在各自的测试文件中。

这正是 `cascade.testing` 模块旨在解决的问题。

您指出的 `MockSolver`, `SpyExecutor`, `TimingWorkExecutor` 等都是完美的提取候选对象。它们可以被归为几类：

1.  **协议的“侦察兵” (Spies)**:
    *   `SpySolver` (`test_plan_caching.py`): 记录对 `resolve` 方法的调用，同时委托给真实实现。
    *   `SpyExecutor` (`test_engine_core.py`): 记录被调用的任务顺序。
    *   `CaptureConnector` (`test_telemetry_contract.py`): 捕获通过连接器发布的 payload。
    这些工具的目的是**观察和断言**系统在测试过程中的行为，它们是验证交互模式的理想选择。

2.  **协议的“替身演员” (Mocks/Stubs)**:
    *   `MockSolver` (`test_engine_core.py`): 返回一个预设的、硬编码的执行计划，完全绕过真实的解析逻辑。
    *   `MockConnector` (`test_engine_concurrency.py`, `test_engine_constraints.py`): 一个功能更全的 `Connector` 模拟，支持订阅和模拟消息接收。
    这些工具的目的是**控制和隔离**被测系统，为其提供一个可预测的、静态的环境。

3.  **行为的“特技演员” (Behavioral Doubles)**:
    *   `SlowWorkExecutor`, `TimingWorkExecutor`, `MockWorkExecutor`: 这些都是 `Executor` 的变体，用于模拟不同类型的任务执行行为（例如，耗时操作、记录完成时间等），对于测试并发、限流和调度至关重要。

**结论**:
我们可以分阶段将这些最有价值、最通用的测试辅助工具全部迁移到 `cascade.testing` 模块中。第一步，我们将从您指出的 `SpySolver` 和一个同样重要的 `SpyExecutor` 开始。

我将生成一个计划来执行这次提取。

## [WIP] refactor(tests): Extract common test doubles into cascade.testing

### 错误分析
代码库在多个测试文件中包含了 `MockSolver`, `SpySolver`, `SpyExecutor` 等临时的测试辅助类（Test Doubles）定义。这种做法导致了代码重复，并且使得在不同测试之间共享和复用这些有价值的测试工具变得不可能。一个测试文件的改进无法惠及其他文件。

### 用户需求
用户要求分析并提取像 `MockSolver` 这样可复用的测试辅助类，以减少代码冗余并建立统一的测试工具集。

### 评论
这是一个能显著提升项目测试基础设施成熟度的重构。将这些核心协议的 Spies 和 Mocks 提升为 SDK 的一部分，等于是在为所有 Cascade 的使用者提供一套官方的“测试套件开发工具包”。这不仅能让我们自己的测试更清晰、更易于维护，也赋能了社区，让他们能更容易地为自己的 Cascade 工作流编写高质量的测试。

### 目标
1.  将 `SpySolver` 的定义从 `tests/e2e/integration/test_plan_caching.py` 移动到 `packages/cascade-sdk/src/cascade/testing.py`。
2.  将 `SpyExecutor` 的定义从 `packages/cascade-engine/tests/runtime/test_engine_core.py` 移动到 `packages/cascade-sdk/src/cascade/testing.py`。
3.  重构原始的测试文件，使其从 `cascade.testing` 导入并使用这些集中的测试工具。

### 基本原理
我们遵循与 `SpySubscriber` 相同的模式：将通用的、可复用的测试辅助工具集中到 `cascade.testing` 模块中，为它们创建一个单一的事实来源。这使得任何测试模块都可以通过简单的 `import` 来使用这些工具，从而消除了代码重复，并促进了在整个项目中测试模式的一致性。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/sdk #scope/dx #ai/brainstorm #task/domain/testing #task/object/test-doubles #task/action/centralize #task/state/begin

---
### Script

#### Acts 1: 扩展 `cascade.testing` 以包含 Solver 和 Executor Doubles

我们将首先更新 `cascade.testing`，添加 `SpySolver` 和 `SpyExecutor` 的定义及其所需的导入。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any, List, Dict
from unittest.mock import MagicMock

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import Solver, Executor, ExecutionPlan
from cascade.graph.model import Node, Graph
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


class SpySolver(Solver):
    """
    A test double for the Solver protocol that spies on calls to `resolve`
    while delegating to a real underlying solver.
    """

    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol's type signature.
        # The actual call is handled by the `wraps` argument in __init__.
        pass


class SpyExecutor(Executor):
    """A test double for the Executor protocol that logs all calls to `execute`."""

    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"
~~~~~

#### Acts 2: 重构 `test_plan_caching.py`

现在，我们清理 `test_plan_caching.py`，让它从 `cascade.testing` 导入 `SpySolver`。

~~~~~act
patch_file
tests/e2e/integration/test_plan_caching.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
from cascade.spec.protocols import Solver
from cascade.graph.model import Graph
from cascade.testing import SpySolver


# Define a simple task for testing
@task
def add(a: int, b: int) -> int:
    return a + b
~~~~~

#### Acts 3: 重构 `test_engine_core.py`

最后，清理 `test_engine_core.py`，让它导入 `SpyExecutor`，并移除不再需要的本地 `MockSolver` 和 `SpyExecutor` 定义。

~~~~~act
patch_file
packages/cascade-engine/tests/runtime/test_engine_core.py
~~~~~
~~~~~python
import pytest
from typing import List, Any, Dict

import cascade as cs
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.runtime import Engine, MessageBus, Solver, Executor, ExecutionPlan


# --- Test Doubles (Mocks and Spies) ---


class MockSolver(Solver):
    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan
        return self._plan


class SpyExecutor(Executor):
    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"


# --- Test Case ---
~~~~~
~~~~~python
import pytest
from typing import List, Any, Dict

import cascade as cs
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.runtime import Engine, MessageBus, Solver, Executor, ExecutionPlan
from cascade.testing import SpyExecutor


# --- Test Doubles (Mocks and Spies) ---


class MockSolver(Solver):
    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan
        return self._plan


# --- Test Case ---
~~~~~

### 下一步建议

我们已经成功地将两个最核心的测试辅助工具 `SpySolver` 和 `SpyExecutor` 提取到了 `cascade.testing` 中。

下一步，我们可以采用完全相同的模式，继续处理：
-   **Executor 变体**: 将 `SlowWorkExecutor`, `TimingWorkExecutor` 等提取到 `cascade.testing`。
-   **Connector Mocks**: 将 `MockConnector` 和 `harness.py` 中的 `ControllerTestApp` 等更复杂的 E2E 测试工具也整合到 `cascade.testing` 中。

这将使我们的测试代码库变得前所未有的干净、模块化和易于维护。如果您同意，我将准备下一个提取计划。
