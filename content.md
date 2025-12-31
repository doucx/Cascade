好的，我们来修复测试。失败的原因很明确：

1.  `test_compile_conditional_task` 失败是因为 `Frontend` 还没有实现对 `LazyResult._condition` 的识别，因此没有生成预期的 `EdgeKind.CONTROL` 边。
2.  `test_compile_map_node` 失败是因为 `Frontend._visit` 方法只接受 `LazyResult`，需要扩展以支持 `MappedLazyResult`。同时，`NodeIR` 也缺少 `meta` 字段来标记这是一个 map 操作。

我们将分两步解决：首先，扩充 Spec (`NodeIR`)；然后，重构 `Frontend` 以支持新类型和新逻辑。

## [WIP] feat(compiler): Implement frontend support for map and control flow

### 错误分析
1.  **Control Flow**: `Frontend` 在访问 `LazyResult` 时，没有检查 `._condition` 属性，因此无法生成 `EdgeKind.CONTROL` 类型的边。
2.  **Map Operations**: `Frontend` 的主访问方法 `_visit` 不支持 `MappedLazyResult` 类型，导致 `TypeError`。此外，`NodeIR` 数据结构缺少一个字段（如 `meta`）来携带“这是一个 Map 操作”的语义信息。

### 用户需求
修复 `test_frontend.py` 中的失败测试，使 `Frontend` 能够正确编译 `run_if` 和 `task.map()` 构造。

### 评论
这是将 `Frontend` 从一个简单的 `LazyResult` 遍历器升级为能够理解 Cascade 核心编程模型的编译器的关键一步。通过在 IR 中显式表达控制流 (`EdgeKind`) 和操作模式 (`meta` 字段)，我们为下游的 `Backend` 和 `VM` 提供了生成高效、正确代码所需的所有信息。

### 目标
1.  在 `cascade.spec.ir.models.NodeIR` 中添加 `meta: Dict[str, Any]` 字段。
2.  重构 `frontend.py` 中的 `_GraphBuilder._visit` 方法，使其能够分派 `LazyResult` 和 `MappedLazyResult` 到各自的处理函数。
3.  在 `LazyResult` 的处理逻辑中，增加对 `._condition` 的检查，并创建 `EdgeKind.CONTROL` 边。
4.  实现对 `MappedLazyResult` 的处理逻辑，并正确填充 `NodeIR.meta` 字段。

### 基本原理
我们采用访问者模式（Visitor Pattern）的变体。`_visit` 方法作为主分派器，根据输入的类型（`LazyResult` 或 `MappedLazyResult`）调用不同的、专门的构建方法。这种方式使代码结构更清晰，易于未来扩展以支持更多类型的 `LazyResult`。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #concept/ir #concept/parser #task/domain/core #task/object/frontend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `NodeIR` Spec 以支持 `meta`

我们在 `NodeIR` 中添加 `meta` 字段，用于携带额外的编译时元信息，例如标记一个节点是 Map 操作。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
~~~~~
~~~~~python.new
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
~~~~~

#### Acts 2: 重构 Frontend 以支持 Map 和 Control Flow

这是一个结构性变更，我们将使用 `write_file` 来完整地更新 `frontend.py`。
- 新增 `MappedLazyResult` 和 `EdgeKind` 的导入。
- 将 `_visit` 重构为分派器。
- 将原 `_visit` 的逻辑移入新的 `_visit_lazy_result` 方法，并添加对 `_condition` 的处理。
- 新增 `_visit_mapped_result` 方法来处理 `task.map()`，并设置 `meta` 字段。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python
from typing import Any, Dict, List, cast
from dataclasses import dataclass

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.graph.analysis.reflection import ReflectionAnalyzer
from cascade.graph.hashing import HashingService


@dataclass
class NodeIDShim:
    """Helper to satisfy HashingService's expectation of objects with structural_id."""

    structural_id: str


class Frontend:
    """
    Compiler Frontend: Transforms user-facing LazyResults into Intermediate Representation (GraphIR).
    """

    @staticmethod
    def compile(target: Any) -> GraphIR:
        builder = _GraphBuilder()
        return builder.build(target)


class _GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, NodeIR] = {}  # Map structural_id -> NodeIR
        self.edges: List[EdgeIR] = []
        self._visited_lazy_uuids: Dict[str, str] = {}  # Map LazyResult.uuid -> structural_id

        # Services from cascade-graph (reused for stability)
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> GraphIR:
        self._visit(target)
        return GraphIR(nodes=list(self.nodes.values()), edges=self.edges)

    def _visit(self, obj: Any) -> str:
        """
        Visits a LazyResult type, creating NodeIRs and EdgeIRs.
        Returns the structural_id of the visited object.
        """
        if isinstance(obj, MappedLazyResult):
            return self._visit_mapped_result(obj)
        elif isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
        else:
            raise TypeError(f"Frontend currently only supports LazyResult types, got {type(obj)}")

    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(arg)
                dep_shims[arg._uuid] = NodeIDShim(structural_id=dep_id)

        for val in obj.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(structural_id=dep_id)
        
        if obj._condition:
            if isinstance(obj._condition, LazyResult):
                dep_id = self._visit(obj._condition)
                dep_shims[obj._condition._uuid] = NodeIDShim(structural_id=dep_id)

        task_def = self.analyzer.analyze(obj.task)
        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_inputs = {
                str(i): arg for i, arg in enumerate(obj.args) if not isinstance(arg, (LazyResult, MappedLazyResult))
            }
            literal_inputs.update(
                {k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))}
            )

            node = NodeIR(id=node_id, definition=task_def, inputs=literal_inputs)
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[arg._uuid].structural_id,
                    target_id=node_id,
                    target_arg=str(i)
                ))

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))
        
        if obj._condition:
            self.edges.append(EdgeIR(
                source_id=dep_shims[obj._condition._uuid].structural_id,
                target_id=node_id,
                target_arg="_condition",
                kind=EdgeKind.CONTROL
            ))

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id

    def _visit_mapped_result(self, obj: MappedLazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}
        for val in obj.mapping_kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(structural_id=dep_id)

        task_def = self.analyzer.analyze(obj.factory)
        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_inputs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                inputs=literal_inputs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id
~~~~~

### 下一步建议
测试现在应该全部通过（GREEN）。我们已经完成了 `Frontend` 的核心功能对齐。下一步是让 `Backend` 和 `VM` 能够理解并执行 `Map` 节点。

建议的步骤：
1.  在 `test_backend.py` 中添加新的测试，验证 `Backend` 看到 `NodeIR.meta.is_map` 时，能生成特殊的 `MapCall` 指令（这需要再次扩展 Spec）。
2.  在 `test_vm_*.py` 中添加测试，验证 VM 看到 `MapCall` 指令时，能正确地迭代输入、并行调用子任务。
