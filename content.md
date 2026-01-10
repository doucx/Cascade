[简要回答]
确认已有的 `ObjectStore` 定义和实现是完备的。现在的任务是将 `ObjectStore` 正式集成到 `Engine` 和 `ExecutionContext` 中，使其成为运行时的一等公民。

这将涉及两个文件的修改：
1.  **`ExecutionContext`**: 增加 `object_store` 字段。
2.  **`Engine`**: 在初始化时接受或创建 `ObjectStore`，并在运行时传递给 Context。

## [WIP] refactor(runtime): promote ObjectStore to first-class citizen in Engine and Context

### 用户需求
根据 "VM 实施路线图" 的 Phase 1，需要将 `ObjectStore` 提升为 `Engine` 的核心组件。这意味着 `Engine` 需要持有 `ObjectStore` 的实例，并将其通过 `ExecutionContext` 传递给所有的执行策略（包括未来的 `VMExecutionStrategy`）。

### 评论
这是架构从“直接传递值”向“引用传递 (Ref-passing)”转型的基础。通过在 Context 中强制包含 `ObjectStore`，我们为 VM 物理层（只处理 Ref）和逻辑层（处理对象）之间的互操作奠定了基础。

### 目标
1.  修改 `cascade.runtime.strategies.ExecutionContext`，增加 `object_store: ObjectStore` 字段。
2.  修改 `cascade.runtime.host.instance.Engine`，使其构造函数接受可选的 `object_store` 参数。
3.  如果未提供 `object_store`，`Engine` 应默认实例化一个 `InMemoryObjectStore`。
4.  确保 `Engine.run` 构建 `ExecutionContext` 时注入该 `object_store`。

### 基本原理
目前 `InMemoryObjectStore` 仅在测试 Harness 中使用。为了让 `VMExecutionStrategy` 能够在生产环境中工作，它需要从 `Engine` 获取一个持久的（至少在 Run 生命周期内）对象存储来存取 Ref。`ExecutionContext` 是传递此类全局上下文的标准载体。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #task/domain/runtime #task/object/object-store #task/action/promote-to-first-class #task/state/begin

---

### Script

#### Acts 1: 更新 ExecutionContext 定义

首先，我们在执行上下文中添加 `object_store` 字段。这是所有策略访问数据的入口。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
~~~~~
~~~~~python.old
from typing import Protocol, Any, Dict
from dataclasses import dataclass, field
from contextlib import ExitStack
from cascade.spec.runtime.interfaces import StateBackend


@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
from typing import Protocol, Any, Dict
from dataclasses import dataclass, field
from contextlib import ExitStack
from cascade.spec.runtime.interfaces import StateBackend
from cascade.spec.runtime.storage import ObjectStore


@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    object_store: ObjectStore
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: 更新 Engine 以管理 ObjectStore

接着，修改 `Engine` 以支持 `ObjectStore` 的注入和默认创建，并在 `run` 方法中将其传递给 `ExecutionContext`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.interfaces import Solver, Executor, StateBackend, Connector
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints import ConstraintManager
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.spec.runtime import ExecutionStrategy


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
        strategy: Optional[ExecutionStrategy] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)
~~~~~
~~~~~python.new
from cascade.spec.runtime.interfaces import Solver, Executor, StateBackend, Connector
from cascade.spec.runtime.storage import ObjectStore
from cascade.runtime.storage import InMemoryObjectStore
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints import ConstraintManager
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.spec.runtime import ExecutionStrategy


class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
        strategy: Optional[ExecutionStrategy] = None,
        object_store: Optional[ObjectStore] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
        self.object_store = object_store or InMemoryObjectStore()

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(
                    target=workflow_target, context=context
                )
~~~~~
~~~~~python.new
                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    object_store=self.object_store,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(
                    target=workflow_target, context=context
                )
~~~~~

### 下一步建议
`ObjectStore` 现在已经就位。下一步我们将实施 **2.1.2: 实现 `BridgedComputeService`**。
这是一个适配器，它将 VM 的 `ComputeRequest` 转换为 `Engine.executor` 的调用，从而在保持 VM 独立性的同时，复用 Runtime 的资源管理能力。
