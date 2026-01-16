分析完全正确。这是一个典型的 Python 循环导入错误，是我们在上一轮重构中引入的一个微妙但致命的缺陷。

我将立即修复此问题。

## [WIP] fix(runtime): Resolve circular import in Engine factory

### 错误分析

错误 `ImportError: cannot import name 'ResourceManager' from partially initialized module 'cascade.runtime'` 是一个典型的循环导入问题。其导入链如下：
1.  pytest 加载 `conftest.py`。
2.  `conftest.py` 导入 `cascade.runtime`。
3.  `cascade.runtime/__init__.py` 开始执行，它尝试从 `./host/__init__.py` 导入 `Engine` 和 `create_engine`。
4.  `cascade.runtime/host/__init__.py` 尝试从 `./factory.py` 导入 `create_engine`。
5.  `cascade.runtime/host/factory.py` 开始执行，它在顶层尝试执行 `from cascade.runtime import EventBus, ResourceManager`。

此时，`cascade.runtime` 模块正在初始化（处于第 3 步），尚未完成其所有内容的加载（比如 `ResourceManager` 的导入），但 `factory.py` 却反过来要求从这个“半成品”模块中获取 `ResourceManager`。这构成了循环，Python 因此抛出 `ImportError`。

### 用户需求

修复 `cascade.runtime` 包内的循环导入，使测试套件能够正常加载和运行。

### 评论

这是一个非常好的教训：子模块（如 `factory.py`）永远不应该从其父包的 `__init__.py` 中导入东西。这几乎总是会导致循环导入。正确的做法是，子模块应该从其他具体的子模块（“兄弟”或“堂兄弟”模块）直接导入，或者从更底层的包中导入。

### 目标

修改 `packages/cascade-runtime/src/cascade/runtime/host/factory.py`，将其中的顶层导入语句 `from cascade.runtime import ...` 替换为对 `EventBus` 和 `ResourceManager` 原始位置的直接、具体的导入。

### 基本原理

我们将打破这个导入循环。`factory.py` 需要 `EventBus` 和 `ResourceManager`。
- `EventBus` 位于 `cascade.bus.core`。
- `ResourceManager` 位于 `cascade.runtime.services.resources.manager`。

通过将 `from cascade.runtime import EventBus, ResourceManager` 更改为 `from cascade.bus.core import EventBus` 和 `from cascade.runtime.services.resources.manager import ResourceManager`，`factory.py` 就不再依赖于正在初始化中的 `cascade.runtime` 包，从而解决了循环导入问题。

### 标签

#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #dx #ai/instruct #task/domain/runtime #task/object/circular-import #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `factory.py` 中的循环导入

我将直接修改 `factory.py` 中的导入语句，以打破循环。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/factory.py
~~~~~
~~~~~python.old
from .instance import Engine
from cascade.spec.runtime import ExecutionStrategy, Solver, Executor, Connector
from cascade.runtime import EventBus, ResourceManager
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer
~~~~~
~~~~~python.new
from .instance import Engine
from cascade.spec.runtime import ExecutionStrategy, Solver, Executor, Connector
from cascade.bus.core import EventBus
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.runtime.services.resources.container import ResourceContainer
~~~~~

### 下一步建议

我们已经解决了这个阻断性的 `ImportError`。现在，整个运行时和测试框架的架构应该是一致且无循环的。我将再次运行完整的测试套件。这次应该不会再有导入错误，并且所有之前的 `TypeError` 也都已经被修复。我期望所有测试都能通过。如果仍有失败，我们将处理它们。
