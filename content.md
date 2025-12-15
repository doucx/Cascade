好的，测试通过，所有异步改造任务已完成。

现在我们进入阶段二的第三项核心任务：**缓存与重试机制**。

我们将首先进行**协议定义与规格扩展**，确保系统能够理解和传递用户的缓存与重试意图。

## [WIP] feat(spec): 定义缓存协议与扩展任务规格

### 用户需求
1.  定义 `CachePolicy` 协议，规定缓存策略必须实现的方法。
2.  扩展 `LazyResult` 对象，允许用户通过 `.with_cache()` 和 `.with_retry()` 链式方法配置策略。
3.  更新核心图模型 (`Node`) 和构建器 (`GraphBuilder`)，确保这些策略能从用户 API 正确传递到底层计算图。

### 评论
这是实现健壮性功能的“地基”。我们不立即修改 `Engine` 去执行这些策略，而是先打通数据流：从用户在 API 层的声明（`spec`），到图模型的存储（`graph`）。这样，当我们在下一步修改 `Engine` 时，它就已经能从 `Node` 上获取到所需的策略配置了。

### 目标
1.  更新 `src/cascade/runtime/protocols.py`：添加 `CachePolicy` Protocol。
2.  更新 `src/cascade/spec/task.py`：定义 `RetryPolicy` 数据类，并在 `LazyResult` 中实现配置方法。
3.  更新 `src/cascade/graph/model.py`：在 `Node` 类中添加 `retry_policy` 和 `cache_policy` 字段。
4.  更新 `src/cascade/graph/build.py`：在构建图时，将策略从 `LazyResult` 复制到 `Node`。

### 基本原理
-   **声明式 API**: 用户不应该关心重试循环怎么写，只需声明“我要重试 3 次”。`.with_retry()` 这种 Fluent API 是最佳实践。
-   **数据流透传**: 策略是任务的元数据。它必须跟随任务从定义阶段（`LazyResult`）一直流转到执行阶段（`Node`）。

### 标签
#intent/architect #flow/ready #priority/high
#comp/spec #comp/graph #comp/runtime #concept/caching #concept/resilience
#task/domain/core #task/object/resilience-support #task/action/architect
#task/state/begin #task/status/active

---

### Script

#### Acts 1: Define CachePolicy Protocol

定义缓存策略的接口。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
    async def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any: ...
~~~~~
~~~~~python
    async def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any: ...


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
~~~~~

#### Acts 2: Update Spec with Policies

在 `task.py` 中定义 `RetryPolicy` 并更新 `LazyResult`。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

T = TypeVar("T")


@dataclass
class Param:
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional, Union
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class Param:
~~~~~

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
    task: "Task[T]"
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python
    task: "Task[T]"
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[CachePolicy] = None

    def __hash__(self):
        return hash(self._uuid)

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "LazyResult[T]":
        """Configures retry logic for this task."""
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self
~~~~~

#### Acts 3: Update Graph Node Model

更新 `Node` 模型以存储策略。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable


@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    callable_obj: Callable
    # We might store additional metadata here later

    def __hash__(self):
        return hash(self.id)
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any


@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    callable_obj: Callable
    
    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None

    def __hash__(self):
        return hash(self.id)
~~~~~

#### Acts 4: Update Graph Builder

更新构建器，将策略从 `LazyResult` 复制到 `Node`。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
        # Create a new Node for this task execution
        node = Node(
            id=result._uuid, name=result.task.name, callable_obj=result.task.func
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~
~~~~~python
        # Create a new Node for this task execution
        node = Node(
            id=result._uuid,
            name=result.task.name,
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node
~~~~~

### 下一步建议
执行 **子任务 2: 引擎重试逻辑实现**。
有了数据结构的支持，我们现在可以修改 `Engine`，在执行任务时检查 `node.retry_policy`，并实现重试循环。这将立即赋予 Cascade 声明式的重试能力。
