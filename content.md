简要回答
我们确立了 TCO 优化的核心在于引入 **"Topology Hash" (拓扑哈希)**，该哈希算法通过**忽略字面量值但保留结构引用**的方式，使得不同输入但结构相同的递归帧能够命中同一个图缓存。这将把图构建的时间复杂度从 O(N) 降低到 O(1)（缓存命中时）。

## [WIP] feat: 设计并实现 LazyResult 拓扑哈希 (Topology Hash)
### 用户需求
实现一种稳定的哈希机制，能够识别出具有相同拓扑结构但不同输入数据的 `LazyResult` 对象，从而允许 Engine 缓存和复用计算图，消除递归 Agent 的图构建开销。

### 评论
当前的 `LazyResult` 使用随机 UUID，导致即使逻辑完全相同的两次调用（如递归的每一步）也被视为全新的图，必须重新构建。拓扑哈希是解决此问题的“指纹”技术。它必须能够区分“结构依赖”和“数据输入”。

### 目标
1.  **定义拓扑哈希算法**: 创建一个递归算法，计算 `LazyResult` 的指纹。规则是：`LazyResult` 参与结构哈希，字面量（int, str 等）仅作为“输入槽位”参与哈希（忽略具体值）。
2.  **增强 LazyResult**: 在 `LazyResult` 类中实现此哈希缓存属性。
3.  **验证**: 通过单元测试证明 `task(1)` 和 `task(2)` 拥有相同的拓扑哈希，而 `task(other_task())` 拥有不同的哈希。

### 基本原理
在 TCO 循环中，`step(state=1)` 和 `step(state=2)` 生成的 `LazyResult` 对象，其内部包含的 `Task` 引用和参数结构是完全一致的。唯一的区别是参数列表中的字面量值。如果我们定义一种哈希算法，将所有字面量视为 `Placeholder(type)`，那么这两个对象的哈希值将相同。Engine 可以利用这个哈希值作为 Key，在 `GraphCache` 中查找已编译好的图，并将新的字面量值（1 或 2）注入到图的输入槽中。

### 标签
#intent/architect #intent/perf #flow/draft #priority/critical
#comp/interfaces #comp/runtime #concept/hashing #concept/tco
#task/domain/core #task/object/topology-hash #task/action/design-and-implement #task/state/continue

---

### Script

#### Acts 1: 创建拓扑哈希设计文档 (RFC)
我们将把设计思路固化为文档，明确哈希计算规则。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/graph/hashing.py
~~~~~
~~~~~python
import hashlib
import json
from typing import Any, Dict, Tuple, List, Union

# We import LazyResult only for type checking to avoid circular imports at runtime if possible,
# but for logic we need isinstance checks.
# Since this module is in runtime, and lazy_types is in interfaces, it is safe to import.
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


def _get_type_name(obj: Any) -> str:
    return type(obj).__name__


def compute_topology_hash(obj: Any) -> str:
    """
    Computes a stable hash representing the topological structure of a LazyResult.
    
    Rules:
    1. LazyResult / MappedLazyResult:
       Hash = Hash(TaskName, Hash(Args), Hash(Kwargs), Hash(Policies))
       This captures the compute graph structure.
       
    2. Router:
       Hash = Hash("Router", Hash(Selector), Hash(Routes))
       
    3. Literals (int, str, float, bool, None):
       Hash = Hash("Literal", TypeName)
       CRITICAL: The *value* is ignored. This allows step(1) and step(2) 
       to share the same topology hash.
       
    4. Collections (list, tuple, dict):
       Recursively hashed. Structure matters.
       
    Returns:
        A hex digest string.
    """
    hasher = hashlib.blake2b(digest_size=16)
    _update_hash(hasher, obj)
    return hasher.hexdigest()


def _update_hash(hasher, obj: Any):
    # 1. LazyResult
    if isinstance(obj, LazyResult):
        hasher.update(b"LazyResult")
        # Task identity
        hasher.update(obj.task.name.encode("utf-8"))
        
        # Recursively hash args structure
        hasher.update(b"Args")
        for arg in obj.args:
            _update_hash(hasher, arg)
            
        # Recursively hash kwargs structure (sorted keys)
        hasher.update(b"Kwargs")
        for k, v in sorted(obj.kwargs.items()):
            hasher.update(k.encode("utf-8"))
            _update_hash(hasher, v)
            
        # Hash Policies (Retry, Condition, etc.)
        if obj._retry_policy:
            hasher.update(b"Retry")
            # For retry, max_attempts implies structure (execution limit), 
            # but delay is runtime param. Let's include max_attempts in topology.
            hasher.update(str(obj._retry_policy.max_attempts).encode("utf-8"))
            
        if obj._condition:
            hasher.update(b"Condition")
            _update_hash(hasher, obj._condition)

    # 2. MappedLazyResult
    elif isinstance(obj, MappedLazyResult):
        hasher.update(b"MappedLazyResult")
        factory_name = getattr(obj.factory, "name", str(obj.factory))
        hasher.update(factory_name.encode("utf-8"))
        
        hasher.update(b"Kwargs")
        for k, v in sorted(obj.mapping_kwargs.items()):
            hasher.update(k.encode("utf-8"))
            _update_hash(hasher, v)

    # 3. Router
    elif isinstance(obj, Router):
        hasher.update(b"Router")
        _update_hash(hasher, obj.selector)
        for k, v in sorted(obj.routes.items()):
            # Route keys (e.g., "prod", "dev") are structural part of the router
            hasher.update(str(k).encode("utf-8"))
            _update_hash(hasher, v)

    # 4. Collections
    elif isinstance(obj, (list, tuple)):
        hasher.update(b"List")
        for item in obj:
            _update_hash(hasher, item)
            
    elif isinstance(obj, dict):
        hasher.update(b"Dict")
        for k, v in sorted(obj.items()):
            hasher.update(str(k).encode("utf-8"))
            _update_hash(hasher, v)

    # 5. Literals (The TCO Key)
    else:
        # We treat any other type as a "Literal Input Slot".
        # We assume that changing the *value* of a literal does not change the graph topology,
        # it only changes the data flowing through it.
        hasher.update(b"Literal")
        hasher.update(_get_type_name(obj).encode("utf-8"))

~~~~~

#### Acts 2: 验证拓扑哈希行为的测试用例
在集成到核心代码之前，我们必须验证这个哈希算法是否符合预期：忽略字面量值差异，捕捉结构差异。

~~~~~act
write_file
tests/runtime/graph/test_hashing.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.runtime.graph.hashing import compute_topology_hash

@task
def add(a, b):
    return a + b

@task
def sub(a, b):
    return a - b

def test_topology_hash_ignores_literal_values():
    """
    Verify that task(1, 2) and task(3, 4) have the SAME topology hash.
    This is the key requirement for TCO graph reuse.
    """
    workflow_a = add(1, 2)
    workflow_b = add(3, 4)
    
    hash_a = compute_topology_hash(workflow_a)
    hash_b = compute_topology_hash(workflow_b)
    
    assert hash_a == hash_b, "Topology hash should be invariant to literal values"

def test_topology_hash_respects_structure():
    """
    Verify that changing the task or nesting structure changes the hash.
    """
    # Same args, different task
    hash_add = compute_topology_hash(add(1, 2))
    hash_sub = compute_topology_hash(sub(1, 2))
    assert hash_add != hash_sub
    
    # Same task, different dependency structure
    # Case 1: Flat
    flat = add(1, 2)
    # Case 2: Nested
    nested = add(add(1, 2), 3)
    
    assert compute_topology_hash(flat) != compute_topology_hash(nested)

def test_topology_hash_respects_kwargs_structure():
    """
    Verify that changing keys in kwargs changes the hash.
    """
    t1 = add(a=1, b=2)
    t2 = add(a=1, c=2) # Different arg name
    
    assert compute_topology_hash(t1) != compute_topology_hash(t2)

def test_topology_hash_literal_types_matter():
    """
    Verify that changing the TYPE of a literal changes the hash.
    Graph inputs are often typed, so int vs string might imply different validation logic.
    """
    t_int = add(1, 2)
    t_str = add("1", "2")
    
    assert compute_topology_hash(t_int) != compute_topology_hash(t_str)
~~~~~

### 下一步建议
运行测试 `pytest tests/runtime/graph/test_hashing.py`。
如果测试通过，说明我们的哈希算法能够正确识别“同构”的计算图。接下来的步骤是将此逻辑集成到 `LazyResult` 中（可能作为缓存属性），并在 `GraphBuilder` 中实现基于此哈希的图缓存查找。
