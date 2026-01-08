简要回答
执行阶段四：将 `model`, `registry`, `exceptions`, `serialize` 迁移至 `cascade-runtime`，迁移 `BlueprintHasher`，并全局更新引用路径。

## [WIP] refactor(graph): 迁移对象模型至 Runtime 并更新全局引用

### 用户需求
执行 "cascade-graph 绞杀计划" 第四阶段：
1.  将 `cascade-graph` 的核心资产 (`model.py`, `registry.py`, `exceptions.py`, `serialize.py`) 搬迁至 `cascade-runtime`。
2.  将 `BlueprintHasher` 从 `cascade-reflection` 迁移至 `cascade-runtime` (解决分层违规问题)。
3.  更新代码库中所有对 `cascade.graph` 的引用为 `cascade.runtime.graph`。

### 评论
这是一个破坏性变更 (Breaking Change)，涉及大量文件的移动和导入路径修改。通过脚本化重构 (`sed`) 可以降低人为错误。`BlueprintHasher` 的迁移顺便解决了 `reflection` 包依赖 `runtime` 模型的潜在循环依赖风险。

### 目标
1.  完成文件物理移动。
2.  在 `cascade-runtime` 中建立完整的图模型能力。
3.  确保所有下游包 (`compiler`, `runtime` 自身) 指向新的图模型位置。
4.  清理 `cascade-reflection` 中不再属于它的 `BlueprintHasher`。

### 基本原理
为了实现 "Runtime 自包含" 的架构目标，运行时对象模型 (`Graph`, `Node`) 必须属于 Runtime 包，而不是一个独立的 `graph` 包。这减少了包的数量，提高了内聚性。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/reflection #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-graph #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 物理移动文件

我们将 `cascade-graph` 中的核心文件移动到 `cascade-runtime` 下的对应目录。

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-runtime/src/cascade/runtime/graph/model.py
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/registry.py
packages/cascade-runtime/src/cascade/runtime/graph/registry.py
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/exceptions.py
packages/cascade-runtime/src/cascade/runtime/graph/exceptions.py
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-runtime/src/cascade/runtime/graph/serialize.py
~~~~~

#### Acts 2: 迁移 BlueprintHasher

`BlueprintHasher` 依赖于 `Graph` 和 `Node` 对象，这些对象现在位于 Runtime 中。为了避免 `cascade-reflection` (底层) 依赖 `cascade-runtime` (上层)，我们必须将 `BlueprintHasher` 提升到 Runtime 层。

首先，在 Runtime 中创建新文件。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/graph/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import List
from cascade.runtime.graph.model import Graph, Node


class BlueprintHasher:
    # Existing logic for Blueprint hashing
    def compute_hash(self, graph: Graph) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['canonical_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")

        # ... Edge logic remains same
        incoming_edges = sorted(
            [
                e
                for e in graph.edges
                if e.target.current_node_instance_hash
                == node.current_node_instance_hash
            ],
            key=lambda e: e.source.current_node_instance_hash,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.current_node_instance_hash}, to={node.current_node_instance_hash}, type={edge.edge_type.name})"
            )
        return components
~~~~~

然后，从 Reflection 中清理它。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
import hashlib
from typing import Any, List, Dict
from cascade.graph.model import Graph, Node
from cascade.spec.ir.graph import TaskDef
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
~~~~~
~~~~~python.new
import hashlib
from typing import Any, List, Dict
from cascade.spec.ir.graph import TaskDef
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components


class BlueprintHasher:
    # Existing logic for Blueprint hashing (can be updated later if needed)
    def compute_hash(self, graph: Graph) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['canonical_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")

        # ... Edge logic remains same
        incoming_edges = sorted(
            [
                e
                for e in graph.edges
                if e.target.current_node_instance_hash
                == node.current_node_instance_hash
            ],
            key=lambda e: e.source.current_node_instance_hash,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.current_node_instance_hash}, to={node.current_node_instance_hash}, type={edge.edge_type.name})"
            )
        return components
~~~~~
~~~~~python.new
        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components
~~~~~

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/__init__.py
~~~~~
~~~~~python.old
from .protocols import TaskAnalyzer
from .analyzer import ReflectionAnalyzer
from .hashing import HashingService, BlueprintHasher
from .naming import PhysicalIdGenerator
from .tasks import _get_param_value, _get_env_var, _internal_gather

__all__ = [
    "TaskAnalyzer",
    "ReflectionAnalyzer",
    "HashingService",
    "BlueprintHasher",
    "PhysicalIdGenerator",
    "_get_param_value",
    "_get_env_var",
    "_internal_gather",
]
~~~~~
~~~~~python.new
from .protocols import TaskAnalyzer
from .analyzer import ReflectionAnalyzer
from .hashing import HashingService
from .naming import PhysicalIdGenerator
from .tasks import _get_param_value, _get_env_var, _internal_gather

__all__ = [
    "TaskAnalyzer",
    "ReflectionAnalyzer",
    "HashingService",
    "PhysicalIdGenerator",
    "_get_param_value",
    "_get_env_var",
    "_internal_gather",
]
~~~~~

#### Acts 3: 全局引用更新

我们将所有 Python 文件中的 `cascade.graph` 替换为 `cascade.runtime.graph`。这会同时修复新移动文件的内部引用和其他包的外部引用。

~~~~~act
run_command
~~~~~
~~~~~bash
grep -r "cascade.graph" packages | grep "\.py" | cut -d ":" -f 1 | sort | uniq | xargs sed -i 's/cascade.graph/cascade.runtime.graph/g'
~~~~~

#### Acts 4: 修复 BlueprintHasher 引用

由于 `BlueprintHasher` 的位置变更（从 reflection 移到了 runtime.graph.hashing），我们需要更新其唯一的消费者：`GraphExecutionStrategy`。
注意：上一步的 sed 替换可能不会影响 `from cascade.reflection import BlueprintHasher`，因为那里没有 `cascade.graph`。我们需要单独处理。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.runtime.graph.model import Graph, Node, EdgeType
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.registry import NodeRegistry
from cascade.reflection import BlueprintHasher
from cascade.spec.runtime.interfaces import Solver, StateBackend
~~~~~
~~~~~python.new
from cascade.runtime.graph.model import Graph, Node, EdgeType
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.registry import NodeRegistry
from cascade.runtime.graph.hashing import BlueprintHasher
from cascade.spec.runtime.interfaces import Solver, StateBackend
~~~~~

#### Acts 5: 导出新模块

最后，更新 `cascade-runtime` 的 graph 模块导出，使其成为一个新的公共 API。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
from .registry import NodeRegistry
from .exceptions import StaticGraphError, CascadeGraphError
from .serialize import to_json, from_json
from .adapter import IRToRuntimeAdapter
from .hashing import BlueprintHasher

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
]
~~~~~

### 下一步建议

1.  **验证**: 运行 `uv run pytest packages/cascade-runtime` 验证所有运行时逻辑是否正常工作。
2.  **清理**: 检查 `packages/cascade-graph` 目录，现在应该只剩下空的目录结构或非核心文件。可以准备删除它。
3.  **依赖更新**: 更新 `cascade-runtime` 的 `pyproject.toml`，移除对 `cascade-graph` 的依赖（现在是自包含的了）。同样更新 `cascade-compiler`。
