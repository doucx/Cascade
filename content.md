按照路线图，我将执行 **Phase 1: Ontology & Protocols**。这将建立 v3.1 Ref-Based 架构的核心类型定义。

## [WIP] feat(spec): 定义 v3.1 Ref-Based 架构核心本体与协议

### 用户需求
实现 Cascade v3.1 "Ref-Based Architecture" 的第一阶段：本体定义与协议。
具体包括：
1.  定义物理引用 `Ref`，作为物理图流转的基本粒子。
2.  定义存储协议 `ObjectStore`，规范数据层的交互。
3.  定义计算委托协议 `ComputeDelegate`，用于异步计算任务的提交。

### 评论
这是 v3.1 架构的地基。通过引入 `Ref`，我们正式将控制流（物理层）与数据流（逻辑层）解耦。这些协议定义纯粹位于 `cascade-spec` 包中，不涉及具体实现，确保了接口的纯粹性。

### 目标
1.  创建 `cascade.spec.physical.object` 模块，定义 `Ref`。
2.  创建 `cascade.spec.runtime.storage` 模块，定义 `ObjectStore`。
3.  创建 `cascade.spec.runtime.compute` 模块，定义 `ComputeDelegate`。
4.  更新相关的 `__init__.py` 文件以导出新符号。

### 基本原理
*   **`Ref`**: 必须是轻量级、不可变的数据结构 (`frozen dataclass`)，包含 `uri` 和 `meta`。它是物理图上唯一流动的实体。
*   **`ObjectStore`**: 定义了 `put`/`get`/`peek`/`delete` 操作，确保存储后端的可插拔性。`peek` 方法对于实现无需下载 payload 即可进行路由决策至关重要。
*   **`ComputeDelegate`**: 取代旧的 `Executor` 概念，强调其“委托”性质。它接收 `Ref`，返回 `Ref`，完全在引用层面操作。

### 标签
#intent/architect #flow/ready #priority/critical #comp/interfaces #scope/core #ai/instruct #task/domain/spec #task/object/ref-architecture #task/action/define-protocols #task/state/begin

---

### Script

#### Acts 1: 定义物理引用对象 (`Ref`)

创建 `cascade/spec/physical/object.py` 并定义 `Ref` 数据结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physical/object.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class Ref:
    """
    A physical reference to a data object stored in an external ObjectStore.
    This is the fundamental particle of the v3.1 Physics Layer.

    The Physics Layer (Reactor) only operates on Ref objects, never on the actual
    heavyweight payloads.
    """

    uri: str
    """The Uniform Resource Identifier for the data (e.g., mem://uuid, redis://key)."""

    meta: Dict[str, Any] = field(default_factory=dict)
    """
    Lightweight metadata hoisted from the payload to allow routing decisions
    without I/O (e.g., {'type': 'Tensor', 'size': 1024, 'is_error': False}).
    """
~~~~~

#### Acts 2: 导出 `Ref`

更新 `packages/cascade-spec/src/cascade/spec/__init__.py`。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from cascade.spec.ir.fingerprint import Fingerprint, InvalidFingerprintKeyError
from cascade.spec.physical.nodes import (
    Token,
    PhysicsNode,
~~~~~
~~~~~python.new
from cascade.spec.ir.fingerprint import Fingerprint, InvalidFingerprintKeyError
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import (
    Token,
    PhysicsNode,
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
~~~~~
~~~~~python.new
__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Ref",
    "Token",
    "PhysicsNode",
~~~~~

#### Acts 3: 定义存储协议 (`ObjectStore`)

创建 `cascade/spec/runtime/storage.py`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/runtime/storage.py
~~~~~
~~~~~python
from typing import Protocol, Any, Dict, Optional
from cascade.spec.physical.object import Ref


class ObjectStore(Protocol):
    """
    Protocol defining the interface for the Data Plane storage layer.
    """

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        """
        Store an object and return a physical Reference.
        """
        ...

    def get(self, ref: Ref) -> Any:
        """
        Dereference a Reference to retrieve the actual object.
        This is typically an I/O intensive operation.
        """
        ...

    def peek(self, ref: Ref) -> Ref:
        """
        Retrieve the latest metadata for a Reference without loading the object.
        Useful for control flow decisions based on metadata (e.g. is_error, type checks).
        Returns a new Ref instance with potentially updated metadata.
        """
        ...

    def delete(self, ref: Ref) -> None:
        """
        Physically destroy the object associated with the Reference.
        """
        ...
~~~~~

#### Acts 4: 定义计算委托协议 (`ComputeDelegate`)

创建 `cascade/spec/runtime/compute.py`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/runtime/compute.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Awaitable, Any
from cascade.spec.physical.object import Ref


class ComputeDelegate(Protocol):
    """
    Protocol for offloading computation to the Data Plane (User Executors).
    This interface deals exclusively with References, never with raw objects.
    """

    def submit(
        self, code_hash: str, input_refs: Dict[str, Ref], config: Dict[str, Any]
    ) -> Awaitable[Ref]:
        """
        Submit a computation task asynchronously.

        Args:
            code_hash: The canonical hash of the code to execute.
            input_refs: A dictionary mapping argument names to input References.
            config: Execution configuration (e.g., resources, timeouts).

        Returns:
            An Awaitable that resolves to a Ref pointing to the result.
            The Reactor should NOT await this directly in its main loop;
            instead, it should treat this as a signal that the task has been dispatched.
        """
        ...
~~~~~

#### Acts 5: 导出运行时协议

更新 `packages/cascade-spec/src/cascade/spec/runtime/__init__.py`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/runtime/__init__.py
~~~~~
~~~~~python
from .interfaces import (
    Solver,
    Executor,
    CacheBackend,
    CachePolicy,
    StateBackend,
    SubscriptionHandle,
    LazyFactory,
    Provider,
    Connector,
)
from .storage import ObjectStore
from .compute import ComputeDelegate

__all__ = [
    "Solver",
    "Executor",
    "CacheBackend",
    "CachePolicy",
    "StateBackend",
    "SubscriptionHandle",
    "LazyFactory",
    "Provider",
    "Connector",
    "ObjectStore",
    "ComputeDelegate",
]
~~~~~

### 下一步建议
我们已经完成了 Phase 1 的所有定义。
下一步应进入 **第二阶段：存储适配器实现 (Phase 2: Storage Adapters)**。建议优先实现 `InMemoryObjectStore`，这是后续开发和测试的基础。
