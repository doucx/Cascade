好的，我们将开始 **阶段 1：反应堆点火 (Reactor Ignition)** 的第一个任务。根据 TDD 流程，我们首先进入 **RED** 状态。

我将为 `VolatileMemory` 设计一套符合计算物理场哲学的 API。它将负责管理数据节点（DataNode）中的令牌（Token）流转。

## [WIP] test: 为 VolatileMemory 实现 TDD 单元测试

### 用户需求
为 `cascade-vm` 中的 `VolatileMemory` 创建单元测试，定义其作为内存模型的核心 API，并确保测试处于失败状态（RED）。

### 评论
`VolatileMemory` 是物理引擎的“寄存器”。它不仅需要存储令牌，更重要的是它必须严格遵守物理定律：FIFO（先进先出）和 Capacity（容量限制）。通过 TDD，我们可以确保这些基础行为在任何复杂的拓扑结构下都是稳固的。

### 目标
1.  在 `cascade-vm` 中建立测试目录结构。
2.  创建 `test_memory.py`，涵盖以下场景：
    *   基本的令牌存取（`put`/`take`）。
    *   FIFO 顺序验证。
    *   容量限制抛出异常。
    *   激发态（Excitement）检查逻辑。
3.  创建一个空的 `VolatileMemory` 类，使得测试因未实现逻辑而失败。

### 基本原理
我们采用“外部视角”设计 API。`VolatileMemory` 不应持有图的拓扑，它只持有状态。因此，我们在存取时需要传入节点定义（`PhysicsDataNode`）来告知内存相关的物理约束（如容量）。

### 标签
#intent/tooling #flow/ready #priority/high #comp/vm #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/volatile-memory #task/action/tdd #task/state/begin

---

### Script

#### Acts 1: 准备测试目录

创建单元测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/tests/unit
touch packages/cascade-vm/tests/unit/__init__.py
~~~~~

#### Acts 2: 编写 VolatileMemory 单元测试

这些测试定义了 `VolatileMemory` 的 API 契约。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_memory.py
~~~~~
~~~~~python
import pytest
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.memory import VolatileMemory, MemoryFullError, MemoryEmptyError

def test_basic_put_and_take():
    """Test standard token storage and retrieval."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="InputSlot", capacity=1)
    token = Token(payload="hello")
    
    mem.put(node, token)
    assert mem.get_count(node.id) == 1
    
    retrieved = mem.take(node.id)
    assert retrieved.payload == "hello"
    assert mem.get_count(node.id) == 0

def test_fifo_behavior():
    """Tokens must be retrieved in the order they were put (FIFO)."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="Buffer", capacity=10)
    
    mem.put(node, Token(payload="first"))
    mem.put(node, Token(payload="second"))
    
    assert mem.take(node.id).payload == "first"
    assert mem.take(node.id).payload == "second"

def test_capacity_overflow():
    """Putting more tokens than capacity must raise MemoryFullError."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="SmallSlot", capacity=1)
    
    mem.put(node, Token(payload="one"))
    with pytest.raises(MemoryFullError):
        mem.put(node, Token(payload="two"))

def test_empty_take():
    """Taking from an empty node must raise MemoryEmptyError."""
    mem = VolatileMemory()
    with pytest.raises(MemoryEmptyError):
        mem.take("non-existent")

def test_excitement_check():
    """
    A node is 'excited' if it has at least one token (or a specific threshold).
    This is the core signal for the Reactor.
    """
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="Trigger", capacity=5)
    
    assert not mem.is_excited(node.id)
    
    mem.put(node, Token(payload="pulse"))
    assert mem.is_excited(node.id)
    assert mem.is_excited(node.id, threshold=1)
    assert not mem.is_excited(node.id, threshold=2)
~~~~~

#### Acts 3: 创建 API 桩文件 (Entering RED)

创建 `memory.py`，仅包含 API 签名但不实现逻辑，确保测试失败。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/memory.py
~~~~~
~~~~~python
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

### 下一步建议

现在测试已经就绪，运行 `pytest packages/cascade-vm/tests/unit/test_memory.py` 应该会产生一堆 `NotImplementedError`。

接下来我们将进入 **GREEN** 阶段：
1.  实现 `VolatileMemory` 的内部存储（推荐使用 `collections.deque`）。
2.  实现 `put` 和 `take` 的逻辑。
3.  确保所有单元测试通过。
