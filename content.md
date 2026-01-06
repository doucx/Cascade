好的，我们将进入 **第二阶段：存储适配器实现 (Phase 2: Storage Adapters)**。

我将按照路线图，在 `cascade-runtime` 包中创建新的 `storage` 模块，并实现 `InMemoryObjectStore`。这将是 v3.1 架构中默认的、用于开发和测试的存储后端。

## [WIP] feat(runtime): 实现 InMemoryObjectStore

### 用户需求
在 `cascade-runtime` 中创建存储适配器层，并实现基于内存的 `ObjectStore`，用于支持 v3.1 Ref-Based 架构的本地运行和测试。

### 评论
这是连接物理引用 (`Ref`) 与实际数据 (`Object`) 的第一座桥梁。虽然它很简单，但它完整地展示了“引用-实体分离”的语义。后续的 Redis 或 S3 实现将遵循相同的协议。

### 目标
1.  创建 `cascade.runtime.storage` 包。
2.  实现 `InMemoryObjectStore` 类，符合 `cascade.spec.runtime.storage.ObjectStore` 协议。
3.  实现 URI 生成逻辑 (`mem://<uuid>`)。

### 基本原理
*   **存储结构**: 使用一个简单的 `Dict[str, Tuple[Any, Dict]]` 来存储对象及其元数据。
*   **URI 协议**: 采用 `mem://` 作为协议头，保证 URI 的自描述性。
*   **元数据处理**: `put` 操作会自动提取基本元数据（如 `type`），同时也接受用户自定义元数据。`peek` 操作仅查表返回元数据，不进行深拷贝。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/storage #scope/core #ai/instruct #task/domain/storage #task/object/memory-store #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 创建存储模块目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-runtime/src/cascade/runtime/storage
~~~~~

#### Acts 2: 实现 `InMemoryObjectStore`

创建 `packages/cascade-runtime/src/cascade/runtime/storage/memory.py`。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/storage/memory.py
~~~~~
~~~~~python
import uuid
from typing import Any, Dict, Optional, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.storage import ObjectStore


class InMemoryObjectStore:
    """
    A reference implementation of ObjectStore using an in-memory dictionary.
    Suitable for development, testing, and single-process execution.
    URI Scheme: mem://<uuid>
    """

    def __init__(self):
        # Storage: uri -> (obj, metadata)
        self._store: Dict[str, Tuple[Any, Dict[str, Any]]] = {}

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        """
        Store an object in memory and return a Reference.
        """
        # 1. Generate URI
        uid = str(uuid.uuid4())
        uri = f"mem://{uid}"

        # 2. Prepare Metadata
        meta = metadata.copy() if metadata else {}
        
        # Auto-detect basic metadata if not provided
        if "type" not in meta:
            meta["type"] = type(obj).__name__
        
        # 3. Store
        self._store[uri] = (obj, meta)

        # 4. Return Ref
        return Ref(uri=uri, meta=meta)

    def get(self, ref: Ref) -> Any:
        """
        Dereference a Reference to retrieve the actual object.
        """
        if ref.uri not in self._store:
            raise KeyError(f"Object not found: {ref.uri}")
        
        obj, _ = self._store[ref.uri]
        return obj

    def peek(self, ref: Ref) -> Ref:
        """
        Retrieve the latest metadata for a Reference.
        For InMemoryStore, this is a cheap lookup.
        """
        if ref.uri not in self._store:
            # If the object is missing in the store but we have a Ref, 
            # we consider it "gone" or invalid, but peek typically shouldn't fail hard 
            # if we just want to check existence, or maybe it should?
            # Following the protocol: if we can't find it, we can't refresh metadata.
            # We raise KeyError to be consistent with get().
            raise KeyError(f"Object not found: {ref.uri}")

        _, meta = self._store[ref.uri]
        
        # Return a new Ref with potentially updated metadata from the store
        return Ref(uri=ref.uri, meta=meta)

    def delete(self, ref: Ref) -> None:
        """
        Physically destroy the object.
        """
        if ref.uri in self._store:
            del self._store[ref.uri]
~~~~~

#### Acts 3: 导出存储模块

创建 `packages/cascade-runtime/src/cascade/runtime/storage/__init__.py`。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/storage/__init__.py
~~~~~
~~~~~python
from .memory import InMemoryObjectStore

__all__ = ["InMemoryObjectStore"]
~~~~~

### 下一步建议
我们已经实现了 `ObjectStore` 的内存版本。根据路线图，第三阶段是 **执行层大分裂 (Phase 3: The Great Schism)**，我们将建立 `PhysicsKernel` 和 `LocalComputeDelegate`。

我建议先实现 `LocalComputeDelegate`，因为它将使用我们刚刚创建的 `InMemoryObjectStore` 来模拟数据的存取，这将是一个很好的集成验证点。
