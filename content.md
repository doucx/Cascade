好的，收到了测试收集阶段的 `ImportError`。

错误分析

这是一个典型的 Python 包结构问题。

1.  **错误**: `ImportError: cannot import name 'NativeSolver' from 'cascade.adapters.solvers'`.
2.  **原因**: 我们在测试文件 `test_static_analysis.py` 中尝试从 `cascade.adapters.solvers` 这个包直接导入 `NativeSolver`。
3.  **代码结构**: 文件浏览器显示，`NativeSolver` 类实际上定义在 `cascade.adapters.solvers.native` 这个模块中。
4.  **根本问题**: `cascade.adapters.solvers/__init__.py` 文件是空的。它没有从 `native.py` 模块中导入 `NativeSolver` 类，因此 `NativeSolver` 没有被“提升”或暴露在包的顶层命名空间中。

同样的结构性问题也存在于 `cascade.adapters.executors` 包中，它的 `__init__.py` 也是空的，而 `LocalExecutor` 定义在 `local.py` 模块里。

解决方案

我们将修复这两个包的 `__init__.py` 文件，将它们的核心类导入到包的命名空间中。这是一种标准的 Python 实践，可以为库的使用者提供更简洁、更稳定的 API。

## [WIP] fix(engine): 在 adapter 包中暴露核心类以修复导入错误

### 错误分析
测试收集失败，因为 `test_static_analysis.py` 无法从 `cascade.adapters.solvers` 导入 `NativeSolver`。根本原因是 `cascade.adapters.solvers/__init__.py` 是空的，没有将其模块内的 `NativeSolver` 类暴露到包级别。`cascade.adapters.executors` 包也存在同样的问题。

### 用户需求
修复 `ImportError`，使 `pytest` 能够成功收集并运行测试。

### 评论
这是一个简单的包结构维护任务，但对开发者体验（DX）至关重要。通过在 `__init__.py` 中定义包的公共 API，我们可以提供更清晰、更易于使用的导入路径，并避免此类导入错误的发生。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/adapters/solvers/__init__.py`，使其导入并暴露 `NativeSolver` 和 `CSPSolver`。
2.  修改 `packages/cascade-engine/src/cascade/adapters/executors/__init__.py`，使其导入并暴露 `LocalExecutor`。

### 基本原理
在包的 `__init__.py` 文件中使用 `from .module import Class` 语句，可以将模块内部的类提升到包的顶层命名空间。这样做之后，`from package import Class` 这样的导入语句就能成功解析。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/dx #ai/instruct #task/domain/runtime #task/object/package-api #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `adapters` 的 `__init__.py` 文件

我们将使用 `write_file` 来更新 `solvers` 和 `executors` 包的 `__init__.py` 文件，使其正确地暴露其核心组件。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/solvers/__init__.py
~~~~~
~~~~~python
from .native import NativeSolver
from .csp import CSPSolver

__all__ = ["NativeSolver", "CSPSolver"]
~~~~~

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/executors/__init__.py
~~~~~
~~~~~python
from .local import LocalExecutor

__all__ = ["LocalExecutor"]
~~~~~

### 下一步建议
我们已经修复了导致测试收集失败的导入错误。现在，所有测试都应该能够被 `pytest` 正常发现和执行。

我建议你重新运行测试。我们应该会看到 `test_static_analysis.py` 中的测试用例实际执行的结果。
