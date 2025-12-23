遵循 `d2-skill-generate-quipu-plan` 流程生成计划：

简要回答：
好的，这是实现“通用结构缓存”的关键一步。

正如路线图所规划的，我们将通过在 `GraphExecutionStrategy` 中引入 `_plan_cache` 和持久化的 `NodeRegistry` 来激活 JIT 缓存。这将使得结构相同的计算图（由规范化的 `Node.id` 标识）能够复用已解析的 `ExecutionPlan`，从而在 TCO 循环中跳过昂贵的求解过程。

我们将执行以下操作：
1.  在策略初始化时创建 `_plan_cache` 和 `_node_registry`。
2.  将 `_node_registry` 传递给 `build_graph` 以实现跨迭代的节点对象复用（Hash-Consing）。
3.  利用 `target_node.id`（结构哈希）作为键来实现计划的查找和缓存。

这将是 Cascade 性能飞跃的基石。

## [WIP] feat(runtime): 在 GraphExecutionStrategy 中实现结构化计划缓存

### 用户需求
在 `GraphExecutionStrategy` 中实现基于 `Node.id`（结构哈希）的通用计划缓存 (JIT Cache)，以消除重复图结构的求解开销，并优化 TCO 循环性能。

### 评论
这是架构路线图 v3.2 第二阶段的核心任务。通过将“构建”和“求解”的结果缓存起来，我们将 O(N) 的图处理开销降低为 O(1)（对于缓存命中的情况）。引入 `NodeRegistry` 的复用也进一步减少了内存分配 churn。

### 目标
1.  在 `GraphExecutionStrategy` 中引入 `_plan_cache` 和 `_node_registry`。
2.  修改执行循环，使其在构建图时使用持久化的 registry。
3.  实现“查缓存 -> 命中复用 / 未命中求解并存入”的逻辑。

### 基本原理
-   **结构稳定性**: `Node.id` 现在是基于 Merkle Hash 的纯结构标识符，与运行时实例解耦。这意味着如果两个 `current_target` 对应同一个 `Node.id`，它们的执行计划必然是相同的。
-   **Registry 复用**: 通过在策略生命周期内保持一个 `NodeRegistry`，我们确保了相同结构的 Node 在内存中只有一份副本，这不仅节省内存，也保证了 `plan` 中缓存的 Node 对象与新 `build_graph` 返回的 Node 对象是完全一致的实例。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/performance #task/object/jit-cache #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `GraphExecutionStrategy` 以启用缓存

我们将修改 `graph.py`，导入必要的类，并在 `execute` 方法中植入缓存逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.spec.protocols import Solver, StateBackend, ExecutionPlan
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Caching removed for Correctness Phase (1.3)

    async def execute(
        self,
        target: Any,
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        
        # JIT Compilation Cache
        # Maps structural hash (root_node_id) to a compiled ExecutionPlan
        self._plan_cache: Dict[str, ExecutionPlan] = {}
        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()

    async def execute(
        self,
        target: Any,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (No Caching)
                # This constructs the structural graph and the instance map.
                graph, data_tuple, instance_map = build_graph(current_target)
                
                # 2. Resolve Plan
                # We resolve the plan every time.
                plan = self.solver.resolve(graph)

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
~~~~~
~~~~~python
        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, data_tuple, instance_map = build_graph(current_target, registry=self._node_registry)
                
                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(f"Critical: Target instance {current_target._uuid} not found in InstanceMap.")
                target_node = instance_map[current_target._uuid]
                root_node_id = target_node.id

                # 2. Resolve Plan (With JIT Caching)
                if root_node_id in self._plan_cache:
                    # Hit: Reuse the existing plan directly.
                    # Since we use a persistent NodeRegistry, the Nodes in this plan are valid for the current graph.
                    plan = self._plan_cache[root_node_id]
                else:
                    # Miss: Ask solver to resolve and then cache it.
                    plan = self.solver.resolve(graph)
                    self._plan_cache[root_node_id] = plan

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
~~~~~

### 下一步建议
实现缓存后，虽然理论上逻辑是健壮的，但我们应该验证其性能收益以及是否引入了任何回归。
建议运行现有的测试套件，特别是那些涉及 TCO 循环的测试，以确保一切正常。
接下来可以着手实现“2.2 验证”，即运行 `tco_performance.py` 基准测试（如果有权限访问的话）。
