我们现在开始执行 **Operation Graph-Strangler** 的 **阶段四：同化与重组 (Assimilation & Restructuring)**。

在本阶段，我们将把 `cascade-graph` 中定义的对象模型、注册表和异常处理逻辑物理迁移到 `cascade-runtime` 包中，并更新全系统的引用路径。这标志着 `cascade-graph` 作为独立包的生命周期进入尾声，其灵魂将被并入运行时内核。

## [WIP] refactor: assimilate cascade-graph into cascade-runtime (Phase 4)

### 用户需求
根据“绞杀计划”路线图，将 `cascade-graph` 的核心资产（模型、注册表、异常）搬迁至 `cascade-runtime`，并完成全系统的命名空间更新（`cascade.graph` -> `cascade.runtime.graph`）。

### 评论
这是架构收敛的关键一步。通过将逻辑图模型（Runtime Model）直接置于 `cascade-runtime` 下，我们消除了不必要的跨包依赖，并建立了一个更清晰的层次结构：DSL -> Compiler -> Runtime。

### 目标
1.  将 `model.py`、`registry.py` 和 `exceptions.py` 从 `cascade-graph` 迁移到 `cascade-runtime/graph/`。
2.  更新迁移后文件的内部导入。
3.  在 `cascade-runtime/graph/__init__.py` 中暴露核心对象。
4.  执行全系统的 `sed` 替换，将 `cascade.graph` 映射到 `cascade.runtime.graph`。

### 基本原理
我们将采用“先搬迁再更新”的策略。通过物理移动文件并立即更新其包路径，我们可以利用全局搜索替换（`sed`）来一次性解决所有引用冲突。为了保证稳定性，迁移后的 `__init__.py` 将作为新的导出点，保持与旧版 API 的兼容性（除了 `build_graph`，它已被编译器前端取代）。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/graph #concept/state #scope/core #ai/delegate #task/domain/architecture #task/object/graph-strangler #task/action/restructuring #task/state/continue

---

### Script

#### Acts 1: 物理搬迁核心逻辑文件

我们将 `cascade-graph` 中的三个核心文件移动到 `cascade-runtime` 的对应位置。

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

#### Acts 2: 更新迁移后的注册表与导出

我们需要更新 `registry.py` 的内部导入，并在 `cascade-runtime/graph/__init__.py` 中建立新的导出规范。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/registry.py
~~~~~
~~~~~python.old
from typing import Dict, Callable
from cascade.graph.model import Node
~~~~~
~~~~~python.new
from typing import Dict, Callable
from .model import Node
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/graph/__init__.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
from .registry import NodeRegistry
from .exceptions import StaticGraphError

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
]
~~~~~

#### Acts 3: 全局命名空间重命名 (The Great Rename)

我们将使用 `sed` 在 `packages` 目录下执行全量替换。这一步会处理 `compiler`、`reflection`、`runtime` 以及旧有的 `graph` 包中所有 Python 文件的引用。

~~~~~act
run_command
~~~~~
~~~~~
find packages -name "*.py" -exec sed -i 's/cascade\.graph/cascade\.runtime\.graph/g' {} +
~~~~~

#### Acts 4: 修复 `cascade-compiler` 的辅助文件路径

编译器中的 `.stitcher.yaml` 文件包含了对旧路径的描述，虽然不直接影响运行，但为了文档一致性需要更新。

~~~~~act
run_command
~~~~~
~~~~~
find packages/cascade-compiler -name "*.stitcher.yaml" -exec sed -i 's/cascade\.graph/cascade\.runtime\.graph/g' {} +
find packages/cascade-reflection -name "*.stitcher.yaml" -exec sed -i 's/cascade\.graph/cascade\.runtime\.graph/g' {} +
find packages/cascade-runtime -name "*.stitcher.yaml" -exec sed -i 's/cascade\.graph/cascade\.runtime\.graph/g' {} +
~~~~~

### 下一步建议

我们已经完成了资产的“同化”。现在的系统状态是：
1.  `cascade-graph` 包依然存在，但其内部的 `model.py` 等核心文件已被移走。
2.  所有包现在都通过 `cascade.runtime.graph` 引用对象模型。

**下一步建议进入 阶段五：终结 (Termination)**：
1.  清理 `cascade-runtime` 的 `pyproject.toml`，移除对 `cascade-graph` 的依赖（因为代码已经内化）。
2.  物理删除 `packages/cascade-graph` 目录。
3.  从根目录的 `pyproject.toml` 中移除 `cascade-graph`。

如果你准备好了，我将生成终结阶段的计划。
