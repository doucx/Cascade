## [WIP] feat: 设计并实现 TCO 零开销优化的第一阶段（结构哈希与缓存）

### 简要回答
我已经完成了“结构哈希”的基础设施建设，并率先在 `Engine` 中实现了一个针对**单节点递归**（Agent 常见模式）的**零开销快速路径 (Zero-Overhead Fast Path)**。

### 用户需求
解决 Cascade 在执行高频递归任务（如 Agent 心跳循环）时，因重复构建相同的计算图而导致的严重性能开销。

### 评论
我们采取了分步走的策略。首先解决最痛点——Agent 的单节点自循环。通过在 `Engine` 层面识别“简单任务”并直接复用图对象（仅更新 ID 和输入），我们消除了 `build_graph` 的所有开销。同时，我们引入了 `StructuralHasher`，为未来处理复杂多节点图的缓存复用奠定了理论和代码基础。

### 目标
1.  实现 `StructuralHasher`，用于生成计算图的稳定指纹。
2.  在 `Engine` 的 TCO 循环中实现针对“简单任务”的图复用优化。
3.  确保优化逻辑的安全性（深度检查依赖）。

### 基本原理
*   **结构哈希**: 将 `LazyResult` 的拓扑结构（Task ID + 依赖关系 + 策略）序列化为字符串并 Hash，忽略具体的字面量值。这使得 `step(1)` 和 `step(2)` 被视为同构。
*   **快速路径**: 对于不包含嵌套依赖的 `LazyResult`，其对应的计算图必然只有一个节点。我们在 TCO 循环中缓存这个单节点图，并在下一次迭代时，如果检测到同构（同一个 Task），直接将新的参数注入到缓存的节点中，从而跳过昂贵的图构建和反射过程。

### 标签
#intent/architect #intent/perf #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/brainstorm #task/domain/runtime #task/object/tco-optimization #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建结构哈希模块 `hashing.py`

我们首先实现核心的哈希逻辑，它能遍历 `LazyResult` 树，提取结构指纹和字面量。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/graph/hashing.py
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List, Union
import hashlib
import json
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    """

    def __init__(self):
        # Flattened map of {canonical_node_path: {arg_name: value}}
        # path examples: "root", "root.args.0", "root.kwargs.data.selector"
        self.literals: Dict[str, Any] = {}
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> Tuple[str, Dict[str, Any]]:
        self._visit(target, path="root")
        
        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        
        return hash_val, self.literals

    def _visit(self, obj: Any, path: str):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj, path)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj, path)
        elif isinstance(obj, Router):
            self._visit_router(obj, path)
        elif isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item, f"{path}[{i}]")
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k], f"{path}.{k}")
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We record a placeholder in the hash, and save the value.
            self._hash_components.append("LIT")
            self.literals[path] = obj

    def _visit_lazy(self, lr: LazyResult, path: str):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")
        
        # Policies (part of structure)
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")
        
        # Args
        self._hash_components.append("Args:")
        for i, arg in enumerate(lr.args):
            self._visit(arg, f"{path}.args.{i}")
            
        # Kwargs
        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(lr.kwargs[k], f"{path}.kwargs.{k}")

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")
        
        # Kwargs (Mapped inputs)
        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(mlr.mapping_kwargs[k], f"{path}.kwargs.{k}")
            
        if mlr._condition:
             self._hash_components.append("Condition:")
             self._visit(mlr._condition, f"{path}.condition")

    def _visit_router(self, router: Router, path: str):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector, f"{path}.selector")
        
        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            # Note: Route keys (k) are structural! (e.g. "prod", "dev")
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k], f"{path}.routes.{k}")
~~~~~

#### Acts 2: 验证结构哈希

编写单元测试以验证哈希逻辑的正确性，特别是它能否区分值变化和结构变化。

~~~~~act
write_file
tests/cascade-runtime/graph/test_hashing.py
~~~~~
~~~~~python
import pytest
from cascade import task
from cascade.graph.hashing import StructuralHasher

@task
def add(a, b):
    return a + b

@task
def sub(a, b):
    return a - b

def test_hashing_simple_structure():
    # Case 1: Same structure, different values
    t1 = add(1, 2)
    t2 = add(3, 4)
    
    h1, l1 = StructuralHasher().hash(t1)
    h2, l2 = StructuralHasher().hash(t2)
    
    assert h1 == h2, "Same task structure should have same hash"
    assert l1 != l2
    assert l1["root.args.0"] == 1
    assert l2["root.args.0"] == 3

    # Case 2: Different structure (different task)
    t3 = sub(1, 2)
    h3, _ = StructuralHasher().hash(t3)
    assert h1 != h3

def test_hashing_nested_structure():
    # Structure: add(1, sub(2, 3))
    t1 = add(1, sub(2, 3))
    t2 = add(10, sub(20, 30))
    
    h1, l1 = StructuralHasher().hash(t1)
    h2, l2 = StructuralHasher().hash(t2)
    
    assert h1 == h2
    assert l1["root.args.1.args.0"] == 2
    assert l2["root.args.1.args.0"] == 20

def test_hashing_list_structure():
    # Structure: add([1, 2], 3)
    t1 = add([1, 2], 3)
    t2 = add([10, 20], 30)
    t3 = add([1, 2, 3], 4) # Different list length -> Different structure
    
    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)
    
    assert h1 == h2
    assert h1 != h3

def test_hashing_kwargs():
    t1 = add(a=1, b=2)
    t2 = add(a=3, b=4)
    t3 = add(b=2, a=1) # Order shouldn't matter for structure
    
    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)
    
    assert h1 == h2
    assert h1 == h3
~~~~~

#### Acts 3: 补全 `engine.py` 的优化逻辑

我们将分三步对 `engine.py` 进行精确修改。

**1.1 注入 `_is_simple_task` 判定工具**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def get_resource_provider(self, name: str) -> Callable:
~~~~~
~~~~~python
    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False
        
        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False
        
        for v in lr.kwargs.values():
            if _has_lazy(v):
                return False
        
        return True

    def get_resource_provider(self, name: str) -> Callable:
~~~~~

**1.2 在 `run` 方法中初始化 TCO 缓存变量**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # Optimization: Reusable graph container for simple recursion (Zero-Overhead TCO)
            # We keep the last simple graph to avoid rebuilding if the structure matches.
            _tco_cached_graph: Optional[Graph] = None
            _tco_cached_task_name: Optional[str] = None

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
~~~~~

**1.3 实现循环内的快速路径 (Fast Path) 调度**

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = build_graph(current_target)

                        # 2. Setup Resources (mixed scope)
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = None
                        
                        # TCO Optimization: Fast path for simple recursion
                        if self._is_simple_task(current_target):
                            task_name = current_target.task.name
                            if _tco_cached_graph and _tco_cached_task_name == task_name:
                                # HIT: Reuse the graph, just update inputs
                                node = _tco_cached_graph.nodes[0]
                                # Re-construct literal inputs from current args/kwargs
                                node.literal_inputs = {str(i): v for i, v in enumerate(current_target.args)}
                                node.literal_inputs.update(current_target.kwargs)
                                # Update UUID to match current target (important for state backend)
                                node.id = current_target._uuid
                                graph = _tco_cached_graph
                            else:
                                # MISS: Build and cache
                                graph = build_graph(current_target)
                                if len(graph.nodes) == 1:
                                    _tco_cached_graph = graph
                                    _tco_cached_task_name = task_name
                                else:
                                    _tco_cached_graph = None
                        else:
                            # Complex task, standard build
                            graph = build_graph(current_target)
                            _tco_cached_graph = None

                        # 2. Setup Resources (mixed scope)
~~~~~

### 下一步建议
如果测试通过，我们将进行压力测试。你可以运行 `observatory/protoplasm/physics/recursion_test.py` 来直观感受优化前后的 TPS 差异。
