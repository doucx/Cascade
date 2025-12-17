好的，我们正式开始实施**阶段二：引擎解耦与核心逻辑统一**。

根据路线图，第一步是实现 `Engine` 的依赖注入，并剥离其与具体实现的耦合。这将使 `Engine` 成为一个纯粹的、由协议驱动的编排器。同时，为了保持项目在每个阶段都处于可测试状态，我将同步更新 `cs.run` 门面函数以适应新的 `Engine` 构造器，并创建第一个核心的、隔离的 `Engine` 单元测试。

## [WIP] refactor(runtime): 实现 Engine 依赖注入并创建核心测试

### 用户需求
根据重构路线图第二阶段的要求，将 `cascade.runtime.Engine` 类重构为纯粹的依赖注入模式，并为其核心编排逻辑建立独立的单元测试。

### 评论
这是整个重构中最关键的一步。通过强制依赖注入，我们从根本上解除了 `Engine`（高层策略）与 `NativeSolver` 或 `LocalExecutor`（底层实现）之间的硬编码耦合。这不仅遵循了“依赖倒置原则”，也为未来引入新的执行器（如分布式执行器）或解析器（如资源感知解析器）铺平了道路，而无需修改 `Engine` 的核心代码。

同时，创建 `test_engine_core.py` 是一个重要的里程碑，它标志着我们开始为系统的“大脑”构建一套独立于任何具体实现的、健壮的验证机制。

### 目标
1.  **重构 `Engine`**: 修改 `src/cascade/runtime/engine.py`，移除 `__init__` 方法中对 `NativeSolver`, `LocalExecutor`, 和 `MessageBus` 的硬编码默认实例化，强制调用者提供实现协议的实例。
2.  **更新 `cs.run` 门面**: 修改 `src/cascade/__init__.py` 中的 `run` 函数，由其负责实例化默认的 `NativeSolver` 和 `LocalExecutor`，并将其注入到新的 `Engine` 构造器中，以保持高级 API 的行为不变。
3.  **创建核心测试**: 新建 `tests/runtime/test_engine_core.py` 文件，并添加第一个测试用例 `test_engine_follows_solver_plan`，使用 Mock/Spy 对象验证 `Engine` 严格按照 `Solver` 提供的计划顺序调用 `Executor`。

### 基本原理
本次重构遵循“依赖倒置”原则。`Engine` 作为高层模块，不应依赖于底层模块的具体实现，而应依赖于抽象（即 `Solver` 和 `Executor` 协议）。

我将通过 `patch_file` 原子化地修改 `Engine` 的构造函数和 `cs.run` 的实现。然后，通过 `write_file` 创建新的测试文件。这个新的测试将使用我们自己实现的轻量级测试替身（`MockSolver`, `SpyExecutor`）来隔离 `Engine`，确保我们只测试其“编排”逻辑，而不受具体解析或执行逻辑的影响。这种方法保证了测试的精确性和稳定性。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/engine-decoupling #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `Engine` 以强制依赖注入

首先，我将修改 `engine.py`，移除 `__init__` 中的默认组件实例化逻辑。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.runtime.protocols import Solver, Executor
from cascade.runtime.exceptions import DependencyMissingError
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.runtime.protocols import Solver, Executor
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}
~~~~~

#### Acts 2: 更新 `cs.run` 门面以使用新的 `Engine`

现在，我将更新 `cs.run()`，让它负责创建默认的 `Solver` 和 `Executor` 并注入到 `Engine` 中，以保持 API 的向后兼容性。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
# Runtime
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .runtime.exceptions import DependencyMissingError
~~~~~
~~~~~python
# Runtime
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .runtime.exceptions import DependencyMissingError
from .adapters.solvers.native import NativeSolver
from .adapters.executors.local import LocalExecutor
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    engine = Engine(bus=event_bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 3: 创建 `Engine` 的核心单元测试

最后，我将创建新的测试文件和第一个隔离测试，以验证 `Engine` 的核心编排逻辑。

~~~~~act
write_file
tests/runtime/test_engine_core.py
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

@pytest.mark.asyncio
async def test_engine_follows_solver_plan():
    """
    Tests that Engine correctly iterates over the plan provided by a Solver
    and calls the Executor for each node in the correct order.
    """
    # 1. Define a simple workflow (the graph structure doesn't matter much
    # as the MockSolver will override the plan)
    @cs.task
    def task_a(): pass
    @cs.task
    def task_b(x): pass
    
    workflow = task_b(task_a())
    graph = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == 'task_a')
    node_b = next(n for n in graph.nodes if n.name == 'task_b')

    # 2. Define the execution plan that the MockSolver will return
    # A simple sequential plan: [A], then [B]
    mock_plan: ExecutionPlan = [
        [node_a],
        [node_b]
    ]
    
    # 3. Setup test doubles and Engine
    solver = MockSolver(plan=mock_plan)
    executor = SpyExecutor()
    bus = MessageBus()
    
    engine = Engine(solver=solver, executor=executor, bus=bus)
    
    # 4. Run the engine
    await engine.run(workflow)
    
    # 5. Assert the executor was called in the correct order
    assert len(executor.call_log) == 2
    assert executor.call_log[0].name == "task_a"
    assert executor.call_log[1].name == "task_b"
~~~~~

### 下一步建议
我们已经成功地将 `Engine` 解耦，并为其建立了第一个核心测试。现在，我们应该继续丰富 `test_engine_core.py`，以覆盖 `Engine` 的其他关键职责。

根据路线图，我建议下一步是添加以下测试用例：
1.  `test_engine_publishes_lifecycle_events`: 使用 `SpySubscriber` 验证 `Engine` 在任务开始、成功、失败时发布了正确的事件。
2.  `test_engine_respects_retry_policy`: 给 `SpyExecutor` 编程，让它在前两次调用时抛出异常，验证 `Engine` 是否正确地进行了重试并发布了 `TaskRetrying` 事件。

如果你同意，我将立即开始准备实现这些测试的计划。
