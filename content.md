You are absolutely right to point this out. My apologies, I made a mistake in the last plan. Your traceback clearly shows my error.

The `graph` module is now a direct submodule of `cascade` (i.e., `cascade.graph`), not nested under `cascade.runtime`. My previous fix in `cascade-py`'s `__init__.py` used the wrong path.

Let's correct this immediately.

## [WIP] fix: Correct graph module import path after refactoring

### 错误分析
`pytest` 失败的根本原因是 `packages/cascade-py/src/cascade/__init__.py` 中的一个导入路径错误。
-   **错误路径**: `from cascade.runtime.graph.serialize import to_json, from_json`
-   **正确路径**: `from cascade.graph.serialize import to_json, from_json`

在我们将项目重构为多包结构后，`graph` 目录 (`build.py`, `serialize.py`) 与 `runtime` 目录位于同一层级，它们都是 `cascade` 命名空间下的直接子模块。因此，正确的导入路径不应包含 `runtime`。

### 用户需求
修复 `ModuleNotFoundError`，使 `pytest` 能够成功加载模块并运行测试。

### 评论
这是一个简单的路径引用错误，但它阻断了整个测试流程。修复它将使我们能够真正验证重构的成果。

### 目标
1.  修正 `packages/cascade-py/src/cascade/__init__.py` 中对 `serialize` 模块的导入语句。

### 基本原理
将错误的导入路径 `cascade.runtime.graph.serialize` 更改为正确的 `cascade.graph.serialize`，以匹配重构后的文件系统结构。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/build #concept/refactoring #scope/core
#ai/instruct
#task/domain/runtime #task/object/monorepo #task/action/fix_imports #task/state/continue

---

### Script

#### Acts 1: 修正 `cascade-py` 的入口文件

这是导致当前错误的唯一原因。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# Core Runtime from cascade-runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.graph.serialize import to_json, from_json
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~
~~~~~python
# Core Runtime from cascade-runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.graph.serialize import to_json, from_json
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
~~~~~

### 下一步建议
这次修复非常精确，直接针对了 `pytest` 报告的错误。请再次运行 `pytest`。我们现在应该已经解决了所有的启动时导入错误。
