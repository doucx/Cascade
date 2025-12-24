这是一个典型的遗漏导入错误。在上一轮重构 `GraphExecutionStrategy` 时，我引入了对 `EdgeType.ITERATIVE_JUMP` 的引用，但没有在文件顶部添加相应的导入语句。

## [WIP] fix(engine): 修复 GraphExecutionStrategy 中缺失的 EdgeType 导入

### 错误分析
在执行 `test_explicit_jump_loop` 时，引擎在处理 `Jump` 信号时抛出了 `NameError: name 'EdgeType' is not defined`。这是因为 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py` 文件中使用了 `EdgeType` 枚举来识别跳转边，但该枚举并未从 `cascade.graph.model` 导入。

### 用户需求
修复 `GraphExecutionStrategy` 的导入错误，使显式控制流测试能够继续运行。

### 评论
在复杂的架构重构中，跨包引用很容易导致此类遗漏。通过 TDD 的反馈循环，我们能够迅速定位并修复这些细小的集成问题。

### 目标
1.  在 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py` 中导入 `EdgeType`。

### 基本原理
`EdgeType` 是定义在 `cascade-graph` 包中的核心枚举。由于 `cascade-engine` 现在的逻辑需要区分不同类型的图边以识别显式跳转路径，因此必须显式导入它。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/control-flow #scope/core #ai/instruct #task/domain/engine #task/object/graph-strategy #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 GraphExecutionStrategy 的导入

我们将 `EdgeType` 添加到 `cascade.graph.model` 的导入列表中。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from contextlib import ExitStack
from typing import Any, Dict, List, Set

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
~~~~~
~~~~~python
from contextlib import ExitStack
from typing import Any, Dict, List, Set

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
~~~~~

### 下一步建议
修复此导入后，请再次运行测试 `tests/engine/runtime/test_explicit_control_flow.py`。

如果测试通过，意味着我们已经打通了从 **API 声明 -> 图构建 (Binding) -> 运行时识别 (Jump Handling)** 的完整链路。届时，我们将完成阶段一的目标，并可以开始考虑如何为这一新机制引入 **Fast Path (零图构建开销)** 优化。
