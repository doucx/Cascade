Excellent. The test failed exactly as predicted.

The `AssertionError: Expected 'mock' to have been called once. Called 2 times` confirms that our previous refactoring was successful in its objective: by removing the `template_id` and simplifying `HashingService`, the two workflow instances (`add(1, 2)` and `add(3, 4)`) now produce different `structural_id`s. Consequently, the engine's caching mechanism sees them as two unrelated workflows and correctly calls the expensive `Solver.resolve()` for each one.

We are now officially in the **RED** state of our TDD cycle. It's time to fix this by introducing a superior mechanism and turning the test back to **GREEN**.

My plan is to create a new, dedicated `BlueprintHasher` service. Its sole responsibility will be to compute a hash based on a graph's *topology* (its structure), while completely ignoring the literal values of its inputs. The engine will then use this "blueprint hash" as the key for its execution plan cache.

This re-establishes our desired caching behavior on a much cleaner and more explicit architectural foundation.

## [WIP] feat: Implement BlueprintHasher for plan caching

### 用户需求
为了修复因 `HashingService` 重构而导致的计划缓存失效问题，需要实现一个新的 `BlueprintHasher` 服务。该服务将为工作流图计算一个“蓝图哈希”，该哈希只反映图的拓扑结构，忽略所有字面量参数，并将其集成到引擎的执行策略中以恢复 JIT 计划缓存功能。

### 评论
这是“双层身份体系”架构的核心实现。我们正在将两种截然不同的身份概念进行物理分离：
1.  **实例身份 (`structural_id`)**: 由 `HashingService` 计算，用于**结果缓存**。
2.  **结构身份 (Blueprint Hash)**: 由新的 `BlueprintHasher` 计算，用于**执行计划缓存**。

这种分离极大地提升了系统的概念完整性和可维护性，是本次重构的最终目标。

### 目标
1.  在 `cascade.graph.hashing` 模块中创建一个新的 `BlueprintHasher` 类。
2.  实现 `BlueprintHasher.compute_hash(graph)` 方法，使其能够遍历一个 `Graph` 对象并生成一个忽略字面量参数的、稳定的拓扑哈希。
3.  修改 `cascade.runtime.strategies.graph.GraphExecutionStrategy`，在 `__init__` 中实例化 `BlueprintHasher`。
4.  更新 `GraphExecutionStrategy.execute` 方法，使用 `BlueprintHasher` 计算出的哈希作为 `_template_plan_cache` 的键，从而修复测试并恢复缓存功能。

### 基本原理
新的 `BlueprintHasher` 将通过确定性地遍历图中的节点和边来工作。对于每个节点，它会提取其任务名称、策略和**依赖项的结构**，但会将节点自身的 `input_bindings`（即字面量参数）替换为一个固定的占位符。通过将这些规范化的组件组合成一个 Merkle 哈希，我们就能得到一个代表工作流“蓝图”的、与具体输入数据无关的唯一标识符。

### 标签
#intent/build #flow/ready #priority/critical #comp/graph #comp/engine #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/plan-caching #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 实现 `BlueprintHasher` 服务

我们将 `BlueprintHasher` 添加到 `hashing.py` 中。它的逻辑将类似于旧 `HashingService` 的 `template=True` 模式，但操作对象是更稳定、更清晰的 `Graph` 和 `Node` 对象，而不是 `LazyResult`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict, Tuple
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict, Tuple
from cascade.graph.model import Graph, Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components
~~~~~
~~~~~python
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components


class BlueprintHasher:
    """
    Computes a hash for a Graph's topology, ignoring literal input values.
    This hash is used to cache compiled execution plans.
    """

    def compute_hash(self, graph: Graph) -> str:
        """Computes the blueprint hash for the entire graph."""
        all_components = []
        # Sort nodes by structural_id to ensure deterministic traversal
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.structural_id)

        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))

        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        """Gets the hash components for a single node, normalizing literals."""
        components = [f"Node({node.name}, type={node.node_type})"]

        # Policies are part of the structure
        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if node.cache_policy:
            components.append(f"Cache({type(node.cache_policy).__name__})")

        # IMPORTANT: Normalize literal bindings
        if node.input_bindings:
            components.append("Bindings:?")

        # Dependencies are structural
        # Sort edges to ensure determinism
        incoming_edges = sorted(
            [e for e in graph.edges if e.target.structural_id == node.structural_id],
            key=lambda e: e.source.structural_id,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.structural_id}, to={node.structural_id}, type={edge.edge_type.name})"
            )

        return components
~~~~~

#### Acts 2: 将 `BlueprintHasher` 集成到执行策略中

现在，我们将新的 `BlueprintHasher` 引入到 `GraphExecutionStrategy` 中，并用它来驱动计划缓存。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List
from dataclasses import dataclass

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List
from dataclasses import dataclass

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.graph.hashing import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry for node interning
        self._node_registry = NodeRegistry()
~~~~~
~~~~~python
        self.wakeup_event = wakeup_event
        self.blueprint_hasher = BlueprintHasher()

        # JIT Compilation Cache
        # Maps a graph's blueprint hash to an IndexedExecutionPlan (List[List[int]])
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry for node interning
        self._node_registry = NodeRegistry()
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )

                target_node = instance_map[current_target._uuid]
                cache_key = target_node.structural_id

                # 2. Resolve Plan (with caching)
                if cache_key in self._template_plan_cache:
                    indexed_plan = self._template_plan_cache[cache_key]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    plan = self.solver.resolve(graph)
                    indexed_plan = self._index_plan(graph, plan)
                    self._template_plan_cache[cache_key] = indexed_plan
~~~~~
~~~~~python
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )

                target_node = instance_map[current_target._uuid]

                # 2. Resolve Plan (with caching based on blueprint hash)
                blueprint_hash = self.blueprint_hasher.compute_hash(graph)
                if blueprint_hash in self._template_plan_cache:
                    indexed_plan = self._template_plan_cache[blueprint_hash]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    plan = self.solver.resolve(graph)
                    indexed_plan = self._index_plan(graph, plan)
                    self._template_plan_cache[blueprint_hash] = indexed_plan
~~~~~

### 下一步建议

我们已经成功地引入了 `BlueprintHasher` 并将其集成到了执行引擎中。这应该能修复之前失败的测试，使我们的 TDD 流程重新回到 **GREEN** 状态。

在运行测试确认一切正常后，我们就完成了一个逻辑上完整的工作单元。因此，下一步最合适的操作是创建一个 `[COMMIT]` 计划，将阶段四的所有这些改动（测试的创建、破坏性的重构、以及最终的修复）作为一个原子性的提交保存到版本历史中。

如果你同意，我将在你确认测试通过后，生成这个提交计划。
