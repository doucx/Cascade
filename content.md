好的，我们现在从 RED 阶段进入 GREEN 阶段。我将使用 `collections.deque` 来实现 `VolatileMemory` 的功能，以通过我们刚才创建的所有单元测试。

## [WIP] feat(vm): 实现 VolatileMemory 以管理令牌状态

### 用户需求
使用 `collections.deque` 实现 `VolatileMemory` 类的逻辑，使其能够通过 `test_memory.py` 中定义的所有单元测试，从 TDD 的 RED 阶段转换到 GREEN 阶段。

### 评论
这是为物理引擎注入“生命”的第一步。通过 `collections.deque` 实现一个高效、健壮的内存模型，我们为后续 Reactor 的核心循环提供了稳定可靠的状态管理基础。这个实现是后续所有物理模拟正确性的保障。

### 目标
1.  在 `VolatileMemory` 中使用 `dict` 存储每个数据节点的 `deque` 队列和容量。
2.  实现 `put` 方法，包括容量检查逻辑。
3.  实现 `take` 方法，确保 FIFO 行为和空队列处理。
4.  实现 `get_count` 和 `is_excited` 以提供状态查询能力。
5.  确保所有逻辑都已实现，以便测试能够通过。

### 基本原理
我们将使用 `collections.defaultdict(deque)` 作为令牌的主要存储结构，这可以优雅地处理新节点的初始化。另一个字典将用于存储每个节点的容量，该容量在第一次 `put` 操作时从 `PhysicsDataNode` 中获取并缓存。这种设计将状态 (`_buffers`) 与物理约束 (`_capacities`) 分离，保持了实现的清晰性。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/volatile-memory #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 VolatileMemory 逻辑

我们现在用完整的、基于 `deque` 的实现来替换 `memory.py` 中的桩代码。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/memory.py
~~~~~
~~~~~python.old
from typing import Dict, List, Any
from cascade.spec.physics import Token, PhysicsDataNode

class MemoryError(Exception):
    """Base class for memory-related errors."""
    pass

class MemoryFullError(MemoryError):
    """Raised when a DataNode exceeds its capacity."""
    pass

class MemoryEmptyError(MemoryError):
    """Raised when attempting to take from an empty DataNode."""
    pass

class VolatileMemory:
    """
    In-memory state manager for PhysicsDataNodes.
    Implements FIFO queues and capacity enforcement.
    """

    def __init__(self):
        pass

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        """Adds a token to the specified data node."""
        raise NotImplementedError

    def take(self, node_id: str) -> Token:
        """Consumes and returns the oldest token from the node."""
        raise NotImplementedError

    def get_count(self, node_id: str) -> int:
        """Returns the current token count in the node."""
        return 0

    def is_excited(self, node_id: str, threshold: int = 1) -> bool:
        """Returns True if the token count meets or exceeds the threshold."""
        return False
~~~~~
~~~~~python.new
from typing import Dict
from collections import deque
from cascade.spec.physics import Token, PhysicsDataNode


class MemoryError(Exception):
    """Base class for memory-related errors."""

    pass


class MemoryFullError(MemoryError):
    """Raised when a DataNode exceeds its capacity."""

    pass


class MemoryEmptyError(MemoryError):
    """Raised when attempting to take from an empty DataNode."""

    pass


class VolatileMemory:
    """
    In-memory state manager for PhysicsDataNodes.
    Implements FIFO queues and capacity enforcement.
    """

    def __init__(self):
        # Maps node_id -> deque of Tokens
        self._buffers: Dict[str, deque[Token]] = {}
        # Maps node_id -> capacity
        self._capacities: Dict[str, int] = {}

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        """Adds a token to the specified data node."""
        node_id = node.id
        if node_id not in self._buffers:
            self._buffers[node_id] = deque()
            self._capacities[node_id] = node.capacity

        buffer = self._buffers[node_id]
        capacity = self._capacities[node_id]

        if len(buffer) >= capacity:
            raise MemoryFullError(
                f"Node '{node.name}' ({node_id}) with capacity {capacity} is full."
            )

        buffer.append(token)

    def take(self, node_id: str) -> Token:
        """Consumes and returns the oldest token from the node."""
        if node_id not in self._buffers or not self._buffers[node_id]:
            raise MemoryEmptyError(f"Node '{node_id}' is empty.")

        return self._buffers[node_id].popleft()

    def get_count(self, node_id: str) -> int:
        """Returns the current token count in the node."""
        return len(self._buffers.get(node_id, []))

    def is_excited(self, node_id: str, threshold: int = 1) -> bool:
        """Returns True if the token count meets or exceeds the threshold."""
        return self.get_count(node_id) >= threshold
~~~~~

### 下一步建议

我们已经完成了 `VolatileMemory` 的实现。请运行 `pytest packages/cascade-vm/tests/unit/test_memory.py` 来确认所有测试都已通过，我们已成功进入 GREEN 状态。

确认无误后，我们就可以继续路线图的下一个任务：**任务 1.2：反应堆核心循环 (The Step)**。这将是构建 `Reactor` 类的第一步，它会使用我们刚刚创建的 `VolatileMemory` 来检查节点是否准备好被激发。
