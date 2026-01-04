简要回答
好的，我们将对 `cascade-compiler` 进行核心重构。引入 `CompilationArtifact` 作为编译产物，它将作为“链接器”携带源代码映射（SourceMap）和可执行文件注册表（Registry），从而填补逻辑层与物理层之间的信息鸿沟。

## [WIP] refactor(compiler): 引入 CompilationArtifact 以实现全息编译输出

### 用户需求
当前的编译器只输出 `GraphIR`（物理图结构），丢失了 `LazyResult` UUID 与物理节点 ID 的映射关系，以及物理节点 ID 与 Python Callable 的对应关系。这导致 Runtime (VM) 无法将用户意图与物理执行关联起来。用户需要一个包含完整上下文的编译产物。

### 评论
这是一个架构级的修正。通过标准化编译产物，我们不仅解决了 VM 集成的问题，也为未来的调试工具（Debugger）、可视化工具（Visualizer）和热重载（Hot Reload）打下了基础。编译器不再是一个“有损压缩”过程，而是一个“全息投影”过程。

### 目标
1.  定义 `CompilationArtifact` 数据结构。
2.  改造 `IRGenerator`，使其在遍历图的过程中收集 `source_map` 和 `registry`。
3.  更新 `IRGenerator.generate` 方法的签名和返回值。

### 基本原理
我们将编译过程看作是生成三个平行的数据流：
1.  **IR Stream**: 节点的拓扑结构和元数据（用于构建物理图）。
2.  **Source Map**: 逻辑 UUID -> 物理 Hash 的映射（用于调试和结果回溯）。
3.  **Linker Table**: 物理 Hash -> 内存中 Callable 对象的引用（用于 VM 也就是 CPU 的指令执行）。

### 标签
#intent/refactor #flow/ready #priority/high #comp/compiler #concept/ir #scope/core #ai/architect #task/domain/compiler #task/object/artifact #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 定义 CompilationArtifact

我们在前端模块中定义这个核心数据载体。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/frontend/artifact.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Callable
from cascade.spec.ir.models import GraphIR


@dataclass
class CompilationArtifact:
    """
    The holistic output of the compilation process.
    It contains not just the structural IR, but also the semantic links
    required to execute and debug the graph.
    """

    # The structural blueprint of the computation
    graph_ir: GraphIR

    # The Linker Table: Canonical Node Hash -> Python Executable (Function)
    # Used by the VM to initialize the instruction pointer for each node.
    registry: Dict[str, Callable] = field(default_factory=dict)

    # The Source Map: LazyResult UUID -> Canonical Node Hash
    # Used by the Runtime to bridge user-facing objects (LazyResult) to physical nodes.
    source_map: Dict[str, str] = field(default_factory=dict)
~~~~~

#### Acts 2: 导出 Artifact

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/__init__.py
~~~~~
~~~~~python.old
from .generator import IRGenerator

__all__ = ["IRGenerator"]
~~~~~
~~~~~python.new
from .generator import IRGenerator
from .artifact import CompilationArtifact

__all__ = ["IRGenerator", "CompilationArtifact"]
~~~~~

#### Acts 3: 改造 IRGenerator

这是核心逻辑变更。我们需要在 `_visit_lazy_result` 中收集额外信息，并最终打包返回。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
from typing import Any, Dict

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.ir.models import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService


class IRGenerator:
    def __init__(self):
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        # id -> NodeIR
        self.nodes: Dict[str, NodeIR] = {}
        # Tracks visited LazyResult UUIDs to their generated Node IDs to handle DAGs
        self._visited: Dict[str, str] = {}

    def generate(self, target: Any) -> GraphIR:
        self._visit(target)
        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(nodes=list(self.nodes.values()))

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
~~~~~
~~~~~python.new
from typing import Any, Dict, Callable

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.ir.models import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService
from .artifact import CompilationArtifact


class IRGenerator:
    def __init__(self):
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        # id -> NodeIR
        self.nodes: Dict[str, NodeIR] = {}
        # Tracks visited LazyResult UUIDs to their generated Node IDs to handle DAGs
        self._visited: Dict[str, str] = {}
        # id -> Callable
        self.registry: Dict[str, Callable] = {}

    def generate(self, target: Any) -> CompilationArtifact:
        self._visit(target)
        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        graph_ir = GraphIR(nodes=list(self.nodes.values()))

        # The _visited map IS the source map (UUID -> NodeID)
        return CompilationArtifact(
            graph_ir=graph_ir,
            registry=self.registry,
            source_map=self._visited.copy(),
        )

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        # 5. Register
        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        return node_id
~~~~~
~~~~~python.new
        # 5. Register
        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        # Register Executable
        # We store the underlying function, not the Task wrapper,
        # because the VM expects a raw callable with specific signature or behavior.
        # But wait, Task wrapper holds metadata like 'mode'.
        # For now, we store the `func` because that's what physically executes logic.
        if hasattr(lr.task, "func"):
            self.registry[node_id] = lr.task.func
        else:
            self.registry[node_id] = lr.task

        return node_id
~~~~~

### 下一步建议
Compiler 已经完成重构，能够输出全息的 `CompilationArtifact`。现在可以进入下一步：**Refactor VM Strategy**，利用这个新的接口来彻底移除 `vm.py` 中的 Hack 代码，实现稳健的集成。
