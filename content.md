我明白了。删除 `hashing.py` 文件后，我没有清理所有对它的引用，导致了连锁的 `ModuleNotFoundError`。这是一个典型的重构疏忽。

感谢您提供详细的错误追踪信息。`conftest.py` 的加载失败路径清楚地表明，`cascade.graph.__init__.py` 仍然在尝试导入一个不存在的模块。`strategies.py` 也存在同样的问题。

我将立即修复这些导入错误。

## [WIP] fix(graph): Remove dangling imports after deleting hashing.py

### 用户需求
在删除了 `packages/cascade-graph/src/cascade/graph/hashing.py` 文件后，多个模块的 `__init__.py` 和其他文件中仍然存在对该文件的无效导入语句，导致 `pytest` 无法启动。需要清理这些悬空的导入引用。

### 评论
这是一个直接的修复，旨在解决上一个重构步骤中遗留的导入问题。通过清理这些引用，我们将使测试套件能够再次正常运行，从而验证我们对 `GraphBuilder` 的核心修改是否成功。

### 目标
1.  修改 `packages/cascade-graph/src/cascade/graph/__init__.py`，移除对 `ShallowHasher` 的导入和导出。
2.  修改 `packages/cascade-engine/src/cascade/runtime/strategies.py`，移除对 `StructuralHasher` 的导入，因为它不再被该模块使用。
3.  确保项目的所有导入路径都与新的文件结构保持一致。

### 基本原理
删除文件后，必须更新所有引用该文件的 `import` 语句，否则 Python 的模块加载机制会失败，导致 `ModuleNotFoundError`。这是一个标准的重构清理步骤。

### 标签
#intent/fix #flow/ready #priority/high
#comp/graph #comp/engine #scope/core
#ai/instruct
#task/domain/graph #task/object/hashing-model #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Clean up imports in `cascade.graph`

我们将首先修复 `cascade-graph` 包自身的 `__init__.py` 文件。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .hashing import StructuralHasher, ShallowHasher
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "StructuralHasher",
    "ShallowHasher",
    "analyze_task_source",
    "assign_tco_cycle_ids",
]
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from .build import build_graph
from .registry import NodeRegistry
from .ast_analyzer import analyze_task_source, assign_tco_cycle_ids

__all__ = [
    "Graph",
    "Node",
    "Edge",
    "EdgeType",
    "build_graph",
    "NodeRegistry",
    "analyze_task_source",
    "assign_tco_cycle_ids",
]
~~~~~

#### Acts 2: Clean up imports in `cascade.runtime.strategies`

接着，我们修复 `cascade-engine` 中 `strategies.py` 的悬空导入。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
from cascade.graph.model import Graph
from cascade.graph.build import build_graph
from cascade.graph.hashing import StructuralHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.graph.model import Graph
from cascade.graph.build import build_graph
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

#### Acts 3: Fix Import in `test_hashing.py` (Again)

我们还需要从 `test_hashing.py` 中移除对 `StructuralHasher` 的导入，因为它也不再需要了。

~~~~~act
patch_file
tests/engine/graph/test_hashing.py
~~~~~
~~~~~python
from cascade import task
from cascade.graph.hashing import StructuralHasher
from cascade.graph.build import build_graph
~~~~~
~~~~~python
from cascade import task
from cascade.graph.build import build_graph
~~~~~

### 下一步建议
导入清理工作已经完成。现在，`ModuleNotFoundError` 应该已经解决。

请再次运行**完整的测试套件** (`pytest`)。

我们期待的结果是：
1.  `test_hashing_distinguishes_nested_lazy_results` **通过**。
2.  其他所有测试也**通过**。
3.  没有 `ImportError`。

如果一切顺利，我们就可以继续验证性能测试了。
