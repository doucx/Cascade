好的，我们正式启动 v2.0 架构的演进。

这是第一份计划，目标是为 `Engine` 的状态解耦打下坚实的地基。我们将引入 `StateBackend` 协议，创建其内存实现，并改造 `Engine` 的构造函数来为后续的状态剥离做准备。

## [WIP] refactor(engine): 引入 StateBackend 协议以解耦运行时状态

### 用户需求
根据架构审查的结果，开始实施 `Cascade 架构演进技术路线图 (v2.0)` 的第一阶段，首先从引入 `StateBackend` 协议和重构 `Engine` 入手。

### 评论
这是迈向 v2.0 架构最关键、最核心的一步。通过将 `Engine` 的运行时状态（任务结果、跳过状态）抽象为一个独立的 `StateBackend` 协议，我们正在进行一次根本性的“控制与状态分离”手术。

这个重构一旦完成，`Engine` 将从一个具体的执行器演变为一个纯粹的编排器。这将为未来支持 Redis 等分布式状态后端、实现工作流持久化与恢复、以及增强整体系统的可测试性铺平道路。

### 目标
1.  在 `src/cascade/runtime/protocols.py` 中定义全新的 `StateBackend` 协议，明确状态管理的接口契约。
2.  创建一个新的模块 `src/cascade/adapters/state/in_memory.py`，并在其中实现一个默认的、基于内存字典的 `InMemoryStateBackend`。
3.  修改 `src/cascade/runtime/engine.py` 中 `Engine` 类的构造函数（`__init__`），使其能够接收一个 `StateBackend` 的**类型**，为下一步的完整重构做好准备。

### 基本原理
我们将遵循路线图的指导，采用“协议驱动设计”的原则。
1.  **协议先行**: 首先在 `protocols.py` 中定义接口。这个接口将包含 `put_result`, `get_result`, `mark_skipped` 等核心方法。
2.  **默认实现**: 接着在 `adapters` 目录下提供一个 `InMemoryStateBackend`，确保 `cs.run()` 的默认行为和性能不受影响，维持其零依赖的特性。
3.  **依赖注入**: 最后，我们将 `Engine` 的构造函数从依赖具体实现，改为依赖 `StateBackend` 的类型。`Engine` 在每次 `run` 的时候，将使用这个类型来实例化一个与当次运行绑定的状态后端。这是一种清晰的依赖倒置模式。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #comp/interfaces #concept/state #scope/core
#ai/brainstorm
#task/domain/architecture #task/object/state-backend #task/action/implementation #task/state/begin #task/status/active

---

### Script

#### Acts 1: 创建 StateBackend 模块结构

首先，我们创建 `StateBackend` 相关实现所需的目录结构和 `__init__.py` 文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade/adapters/state
~~~~~

~~~~~act
write_file
src/cascade/adapters/state/__init__.py
~~~~~
~~~~~
from .in_memory import InMemoryStateBackend

__all__ = ["InMemoryStateBackend"]
~~~~~

#### Acts 2: 定义 StateBackend 协议

现在，我们在核心协议文件中添加 `StateBackend` 的定义。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...


class LazyFactory(Protocol):
~~~~~
~~~~~python
class CachePolicy(Protocol):
    """
    Protocol for a caching strategy.
    """

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        """
        Checks if a result is cached.
        Returns None if not found, or the cached value if found.
        """
        ...

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        """
        Saves a result to the cache.
        """
        ...


class StateBackend(Protocol):
    """
    Protocol for a backend that stores the transient state of a single workflow run.
    This includes task results and skip statuses.
    """

    def put_result(self, node_id: str, result: Any) -> None:
        """Stores the result of a completed task."""
        ...

    def get_result(self, node_id: str) -> Optional[Any]:
        """Retrieves the result of a task. Returns None if not found."""
        ...

    def has_result(self, node_id: str) -> bool:
        """Checks if a result for a given task ID exists."""
        ...

    def mark_skipped(self, node_id: str, reason: str) -> None:
        """Marks a task as skipped."""
        ...

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        """Retrieves the reason a task was skipped. Returns None if not skipped."""
        ...


class LazyFactory(Protocol):
~~~~~

#### Acts 3: 实现 InMemoryStateBackend

接下来，我们在新创建的模块中编写默认的内存状态后端。

~~~~~act
write_file
src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~
from typing import Any, Dict, Optional


class InMemoryStateBackend:
    """
    An in-memory implementation of the StateBackend protocol using Python dictionaries.
    This is the default backend for local, single-process runs.
    """

    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    def put_result(self, node_id: str, result: Any) -> None:
        self._results[node_id] = result

    def get_result(self, node_id: str) -> Optional[Any]:
        return self._results.get(node_id)

    def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    def mark_skipped(self, node_id: str, reason: str) -> None:
        self._skipped[node_id] = reason

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)
~~~~~

#### Acts 4: 改造 Engine 构造函数

最后，我们更新 `Engine` 的 `__init__` 方法，为其注入 `StateBackend` 的能力。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.protocols import Solver, Executor
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

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

        # Internal resolvers
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Type
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
from cascade.runtime.protocols import Solver, Executor, StateBackend
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}

        # Internal resolvers
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~

### 下一步建议
我们已经成功地为状态解耦铺平了道路。接下来的计划将是这次重构的“心脏手术”：
- **修改 `Engine.run`**: 在 `run` 方法的开头，使用 `self.state_backend_cls` 来实例化一个与本次运行绑定的 `state_backend` 对象。
- **重构 `_execute_graph`**: 移除本地的 `results` 字典，并修改所有相关的读写操作（结果存储、上游结果查询），使其全部通过 `state_backend` 实例进行。
- **重构 `FlowManager`**: 调整 `FlowManager`，使其状态（如 `_skipped_nodes`）也由 `StateBackend` 管理，或者从 `StateBackend` 查询信息。

这将是一次更具侵入性的修改，但完成后，我们的 `Engine` 将变得前所未有的干净和强大。
