好的，我们开始实施 **里程碑 3.2: 并发管理**。

你的计划非常合理。我们将首先增强 `ResourceManager` 以支持动态定义的资源，然后逐层向上，将 `ConstraintManager` 与之集成，并通过 `ConstraintResolver` 将这些动态约束应用到具体的任务上。这是一个清晰、低耦合的实现路径。

我将生成一个计划来执行这些修改。

## [WIP] feat: 实现动态并发管理

### 用户需求
根据项目路线图，实现里程碑 3.2：并发管理。系统应能通过外部指令（`concurrency` 类型的 `GlobalConstraint`）动态限制特定任务的并发执行数量，并利用现有的 `ResourceManager` 机制来处理等待和调度。

### 评论
这是将 Cascade 从一个工作流引擎提升为自适应执行环境的关键一步。此功能通过将外部控制信号（约束）转化为内部调度行为（资源限制），建立了核心的反馈回路。

我们采用的策略——复用 `ResourceManager`——非常高效，它避免了重复造轮子，并确保了并发控制逻辑与 `ResourceManager` 中既有的、经过测试的 `asyncio.Condition` 同步机制保持一致。

### 目标
1.  **增强 `ResourceManager`**：使其能够动态地增加、更新和移除资源及其容量。
2.  **集成 `ConstraintManager`**：使其在接收到 `concurrency` 类型的约束时，能够自动在 `ResourceManager` 中创建或更新对应的资源限制。
3.  **扩展 `ConstraintResolver`**：使其在为任务解析资源需求时，能自动识别并应用当前生效的并发约束。
4.  **连接组件**：在 `Engine` 中正确初始化并连接上述修改后的组件。
5.  **添加验证**：编写集成测试，验证整个并发控制流程的正确性。

### 基本原理
1.  **`ResourceManager` 扩展**: 我们将为 `ResourceManager` 添加 `set_resource_capacity` 和 `remove_resource` 两个同步方法。由于它们仅操作内部字典并调用 `notify_all()`（一个同步方法），因此无需将 `ResourceManager` 的核心修改为异步，从而将影响降至最低。
2.  **职责分离**:
    *   **`ConstraintManager`** 负责“翻译”。它接收外部 `GlobalConstraint` 对象，并将其“翻译”为对 `ResourceManager` 的具体操作（例如，`set_resource_capacity("constraint:concurrency:task:api_call", 5)`）。
    *   **`ConstraintResolver`** 负责“应用”。它查询 `ConstraintManager` 以了解当前哪个约束适用于给定的任务，然后将这个约束转化为任务的一个具体资源需求（例如，`{ "constraint:concurrency:task:api_call": 1 }`）。
    *   **`ResourceManager`** 负责“执行”。它接收到任务的资源需求后，并不知道这个需求是静态的还是动态的，它只负责根据现有容量进行标准的 `acquire`/`release` 同步操作。
3.  **动态资源命名**: 我们将使用一个确定的模式，如 `constraint:concurrency:<scope>`，来命名由约束动态创建的资源。这确保了逻辑的清晰和可预测性。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/concurrency-limit #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强 ResourceManager 以支持动态资源

我们将为 `ResourceManager` 添加 `set_resource_capacity` 和 `remove_resource` 方法，使其能够响应 `ConstraintManager` 的动态需求。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        """
        Atomically acquires the requested resources.
        Waits until all resources are available.
~~~~~
~~~~~python
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    def set_resource_capacity(self, name: str, capacity: float):
        """Dynamically sets or updates the capacity for a single resource."""
        with self._condition:
            is_new = name not in self._capacity
            self._capacity[name] = capacity
            if is_new:
                self._usage[name] = 0.0
            # Wake up waiting tasks, as this change might satisfy their needs
            self._condition.notify_all()

    def remove_resource(self, name: str):
        """Dynamically removes a resource."""
        with self._condition:
            if name in self._capacity:
                del self._capacity[name]
            if name in self._usage:
                del self._usage[name]
            # Wake up waiting tasks
            self._condition.notify_all()

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        """
        Atomically acquires the requested resources.
        Waits until all resources are available.
~~~~~

#### Acts 2: 将 ConstraintManager 与 ResourceManager 集成

我们将修改 `ConstraintManager`，使其在处理 `concurrency` 类型的约束时，能够直接操作 `ResourceManager`。同时，添加一个辅助方法，供 `ConstraintResolver` 查询匹配的约束。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self):
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            del self._constraints[cid]
~~~~~
~~~~~python
from typing import Dict, List
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from cascade.runtime.resource_manager import ResourceManager
from .protocols import ConstraintHandler


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        if constraint.type == "concurrency":
            resource_name = f"constraint:concurrency:{constraint.scope}"
            limit = float(constraint.params.get("limit", 1))
            self.resource_manager.set_resource_capacity(resource_name, limit)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        constraints_to_remove = [
            c for c in self._constraints.values() if c.scope == scope
        ]
        for c in constraints_to_remove:
            if c.type == "concurrency":
                resource_name = f"constraint:concurrency:{c.scope}"
                self.resource_manager.remove_resource(resource_name)
            del self._constraints[c.id]
    
    def get_matching_constraints(
        self, task: Node, constraint_type: str
    ) -> List[GlobalConstraint]:
        """Finds all active constraints of a given type that apply to a task."""
        matches = []
        for constraint in self._constraints.values():
            if constraint.type != constraint_type:
                continue

            scope = constraint.scope
            if scope == "global":
                matches.append(constraint)
                continue

            if scope.startswith("task:"):
                target_task_name = scope.split(":", 1)[1]
                if task.name == target_task_name:
                    matches.append(constraint)
                    continue
        return matches
~~~~~

#### Acts 3: 扩展 ConstraintResolver 以应用并发约束

现在，我们将让 `ConstraintResolver` 查询 `ConstraintManager`，并将匹配的并发约束动态地添加到任务的资源需求中。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend


class ArgumentResolver:
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend
from cascade.runtime.constraints import ConstraintManager


class ArgumentResolver:
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
~~~~~
~~~~~python
class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def __init__(self, constraint_manager: ConstraintManager):
        self.constraint_manager = constraint_manager

    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        # Start with static constraints defined on the task
        resolved = (
            node.constraints.requirements.copy()
            if node.constraints and not node.constraints.is_empty()
            else {}
        )

        # Add dynamic requirements from global concurrency constraints
        concurrency_constraints = self.constraint_manager.get_matching_constraints(
            node, "concurrency"
        )
        for c in concurrency_constraints:
            resource_name = f"constraint:concurrency:{c.scope}"
            resolved[resource_name] = 1  # Each task acquires 1 unit of the limit

        if not resolved:
            return {}
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        constraint_edges = [
            e
            for e in graph.edges
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
~~~~~
~~~~~python
        constraint_edges = [
            e
            for e in graph.edges
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        # Note: We iterate over the 'resolved' dict which now contains both static
        # and concurrency constraints. The logic for resolving LazyResult amounts
        # only applies to static constraints.
        for res, amount in resolved.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
~~~~~

#### Acts 4: 在 Engine 中连接所有组件

最后，我们在 `Engine` 的构造函数中，将 `ResourceManager` 实例注入 `ConstraintManager`，并将 `ConstraintManager` 实例注入 `ConstraintResolver`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager()
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~python
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(resource_manager=self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver(
            constraint_manager=self.constraint_manager
        )
        self.flow_manager: Optional[FlowManager] = None
~~~~~

#### Acts 5: 编写集成测试

为了验证我们的实现，我们将创建一个新的测试文件，模拟接收并发约束并断言任务执行是否受到了相应的限制。

~~~~~act
write_file
tests/py/runtime/test_engine_concurrency.py
~~~~~
~~~~~python
import asyncio
import time
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from tests.py.runtime.test_engine_constraints import MockConnector, wait_for_task_finish


@pytest.mark.asyncio
async def test_engine_respects_concurrency_constraint(bus_and_spy):
    """
    Tests that tasks matching a concurrency constraint are executed with limited parallelism.
    """
    bus, spy = bus_and_spy
    mock_connector = MockConnector()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=mock_connector,
    )

    # 1. Define tasks. 'api_call' will be the constrained task.
    @cs.task
    async def api_call(i: int):
        await asyncio.sleep(0.1)  # Simulate network latency
        return i

    @cs.task
    def combine(results: list):
        return sorted(results)

    # 2. Define a workflow with 3 parallel api_calls
    # Without constraints, this would take ~0.1s
    calls = [api_call(i) for i in range(3)]
    workflow = combine(calls)

    # 3. Start the engine in a background task
    run_task = asyncio.create_task(engine.run(workflow))

    # 4. Wait for the engine to connect and subscribe
    await asyncio.sleep(0.02)

    # 5. Inject a concurrency limit of 1 for 'api_call' tasks
    concurrency_scope = "task:api_call"
    concurrency_payload = {
        "id": "limit-api",
        "scope": concurrency_scope,
        "type": "concurrency",
        "params": {"limit": 1},
    }
    await mock_connector._trigger_message(
        f"cascade/constraints/{concurrency_scope.replace(':', '/')}",
        concurrency_payload,
    )

    # 6. Measure execution time
    start_time = time.time()
    final_result = await run_task
    duration = time.time() - start_time

    # 7. Assertions
    assert final_result == [0, 1, 2]

    # With a limit of 1, the 3 tasks (0.1s each) must run sequentially.
    # Total time should be > 0.3s. We allow for a small margin.
    assert duration > 0.28, "Tasks did not run sequentially under concurrency limit"
    assert duration < 0.5, "Tasks took unexpectedly long"
~~~~~

### 下一步建议
我们已经完成了 `Engine` 内部并发管理能力的实现。下一步，我们将进入**里程碑 3.3: 速率限制 (Rate Limiting)**，为 `Engine` 增加更精细的、基于时间窗口的流量控制能力。
