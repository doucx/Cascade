根据你的指示，我已定位到与 `BluePrint` 相关的死代码。

**分析结果：**
1.  **定义**: `BlueprintHasher` 定义在 `packages/cascade-runtime/src/cascade/runtime/graph/hashing.py` 中。该文件仅包含此逻辑，因此可以删除整个文件。
2.  **导出**: 需要从 `packages/cascade-runtime/src/cascade/runtime/graph/__init__.py` 中移除导出。
3.  **使用**: `BlueprintHasher` 仅被 `packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py` 中的 `GraphExecutionStrategy` 使用，用于通过 `_template_plan_cache` 缓存执行计划。
4.  **策略**: 既然 `BluePrint` 是旧 VM 的产物，我们可以安全地从 `GraphExecutionStrategy`（Legacy 策略）中移除基于 Blueprint 的缓存优化逻辑，使其在剩余的生命周期中每次都重新解析图（反正它已经是 Legacy 了）。

以下是清理计划。

## [WIP] refactor(runtime): 移除过时的 BlueprintHasher 及相关缓存逻辑

### 用户需求
移除与旧 VM 相关的 `BluePrint` 代码，包括 `BlueprintHasher` 及其在 `GraphExecutionStrategy` 中的使用。

### 评论
`BlueprintHasher` 用于对图结构进行哈希以缓存执行计划。由于新架构采用了不同的哈希机制（`cascade-reflection` 中的 `HashingService`），且旧的 VM 策略正在逐步淘汰，移除这个复杂的缓存层可以简化代码库。

### 目标
1.  删除 `packages/cascade-runtime/src/cascade/runtime/graph/hashing.py`。
2.  更新 `packages/cascade-runtime/src/cascade/runtime/graph/__init__.py` 移除导出。
3.  重构 `packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py`，移除对 `BlueprintHasher` 的依赖以及相关的 `_template_plan_cache` 逻辑。

### 基本原理
根据用户指示，`BluePrint` 相关逻辑是死代码。虽然 `GraphExecutionStrategy` 仍被 `Engine` 引用作为默认策略（在切换到新 VM 前），但我们可以移除其内部的“缓存优化”部分，使其回退到每次通过 Solver 解析图的简单模式。这既删除了死代码，又保持了 Legacy 策略的基本功能不崩溃。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/runtime #scope/core
#ai/instruct
#task/domain/cleanup #task/object/blueprint #task/action/delete
#task/state/begin

---

### Script

#### Acts 1: 删除定义文件

首先删除定义了 `BlueprintHasher` 的文件。

~~~~~act
delete_file
packages/cascade-runtime/src/cascade/runtime/graph/hashing.py
~~~~~

#### Acts 2: 移除导出

从包的 `__init__.py` 中移除对 `BlueprintHasher` 的引用。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/__init__.py
~~~~~
~~~~~python.old
from .serialize import to_json, from_json
from .adapter import IRToRuntimeAdapter
from .hashing import BlueprintHasher
from .build import build_graph

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "TaskNode",
    "MapNode",
    "ParamNode",
    "NodeRegistry",
    "StaticGraphError",
    "CascadeGraphError",
    "to_json",
    "from_json",
    "IRToRuntimeAdapter",
    "BlueprintHasher",
    "build_graph",
]
~~~~~
~~~~~python.new
from .serialize import to_json, from_json
from .adapter import IRToRuntimeAdapter
from .build import build_graph

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "TaskNode",
    "MapNode",
    "ParamNode",
    "NodeRegistry",
    "StaticGraphError",
    "CascadeGraphError",
    "to_json",
    "from_json",
    "IRToRuntimeAdapter",
    "build_graph",
]
~~~~~

#### Acts 3: 重构 Legacy Strategy

修改 `GraphExecutionStrategy`，移除缓存逻辑、辅助方法 (`_index_plan`, `_rehydrate_plan`) 和 import。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.runtime.graph.model import Graph, Node, EdgeType
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.registry import NodeRegistry
from cascade.runtime.graph.hashing import BlueprintHasher
from cascade.spec.runtime.interfaces import Solver, StateBackend
from cascade.spec.dsl.jump import Jump
~~~~~
~~~~~python.new
from cascade.runtime.graph.model import Graph, Node, EdgeType
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.registry import NodeRegistry
from cascade.spec.runtime.interfaces import Solver, StateBackend
from cascade.spec.dsl.jump import Jump
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event
        self.blueprint_hasher = BlueprintHasher()

        self._template_plan_cache: Dict[str, List[List[int]]] = {}
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        id_to_idx = {
            node.current_node_instance_hash: i for i, node in enumerate(graph.nodes)
        }
        indexed_plan = []
        for stage in plan:
            indexed_stage = [
                id_to_idx[node.current_node_instance_hash] for node in stage
            ]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        plan = []
        for stage_indices in indexed_plan:
            stage_nodes = [graph.nodes[idx] for idx in stage_indices]
            plan.append(stage_nodes)
        return plan

    async def execute(
        self,
        target: Any,
~~~~~
~~~~~python.new
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event

        self._node_registry = NodeRegistry()

    async def execute(
        self,
        target: Any,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    current_graph_structure_hash = self.blueprint_hasher.compute_hash(
                        graph
                    )
                    if current_graph_structure_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[
                            current_graph_structure_hash
                        ]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[current_graph_structure_hash] = (
                            indexed_plan
                        )

                    local_context_cache[current_target._uuid] = (
                        graph,
                        instance_map,
~~~~~
~~~~~python.new
                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    # Legacy cache logic removed. Always resolve the plan.
                    plan = self.solver.resolve(graph)

                    local_context_cache[current_target._uuid] = (
                        graph,
                        instance_map,
~~~~~

### 下一步建议

由于我们修改了 `GraphExecutionStrategy` 的内部逻辑，虽然理论上只是移除了缓存优化，但仍建议运行现有的测试集以确保没有破坏基本的执行流程。

建议运行：
`pytest packages/cascade-runtime/tests` (如果有的话，或相关的集成测试)
