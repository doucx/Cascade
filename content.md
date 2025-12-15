你指出的问题非常深刻。我们引入 `ParamNode` 的重构方向是正确的，但执行过程中触发了一个经典的 Python 问题：循环导入。

## [WIP] fix(core): Resolve circular import by splitting spec types

### 错误分析
测试框架在收集测试文件时就崩溃了，报错 `ImportError: cannot import name 'Param' from partially initialized module 'cascade.spec.task' (most likely due to a circular import)`。

**循环路径**:
1.  `cascade.graph.model` 想要知道 `Node.param_spec` 的类型，于是 `from cascade.spec.task import Param`。
2.  `cascade.spec.task` 想要知道 `LazyResult._cache_policy` 的类型，于是 `from cascade.runtime.protocols import CachePolicy`。
3.  `cascade.runtime.protocols` 想要知道 `Solver` 协议的 `resolve` 方法的返回类型，于是 `from cascade.graph.model import Graph, Node`。
4.  这就形成了一个致命的循环： `graph.model` -> `spec.task` -> `runtime.protocols` -> `graph.model`。

### 技术债务分析
这个循环导入是我们“洋葱架构”实现中的一个裂缝。`spec`（规格）层本应是纯粹的数据结构，不应依赖于 `runtime`（运行时）或 `graph`（图结构）的实现细节。但为了类型提示，我们让 `spec.task` 依赖了 `runtime.protocols`，而 `graph.model` 又依赖了 `spec.task`，最终导致了耦合。

### 解决方案：创建纯粹的类型定义层

我们将创建一个新的、更底层的模块 `cascade.core.types` (或类似名称)，专门用于存放被广泛引用的、纯粹的数据结构定义，如 `Param`。这将打破循环。

**重构步骤**:
1.  **创建 `src/cascade/spec/common.py`**: 将 `Param` 类的定义从 `task.py` 移动到这个新文件中。这个文件将成为我们类型体系的基础，它不应有任何内部的 `cascade` 导入。
2.  **更新导入路径**:
    *   在 `cascade.graph.model` 中，将 `from cascade.spec.task import Param` 改为 `from cascade.spec.common import Param`。
    *   在 `cascade.spec.task` 中，将 `from cascade.spec.task import Param` (自引用，现在非法) 改为 `from .common import Param`。
    *   在 `cascade/__init__.py` 中，从 `common.py` 导出 `Param`。

这个小重构将彻底解耦我们的类型定义，修复循环导入，并使我们的架构更加符合洋葱模型。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #scope/core #ai/instruct #task/domain/core #task/object/circular-import #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 创建 `spec/common.py` 并移动 `Param`

将 `Param` 的定义分离到一个新的、无依赖的文件中。

~~~~~act
write_file
src/cascade/spec/common.py
~~~~~
~~~~~python
from typing import Any
from dataclasses import dataclass

@dataclass
class Param:
    """Represents a runtime parameter."""

    name: str
    default: Any = None
    type: Any = None
    description: str = ""
~~~~~

#### Acts 2: 移除 `task.py` 中的 `Param` 定义

从 `task.py` 中删除 `Param` 类，并导入新的 `Param`。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
@dataclass
class Param:
    """Represents a runtime parameter."""

    name: str
    default: Any = None
    type: Any = None
    description: str = ""


@dataclass
class LazyResult(Generic[T]):
~~~~~
~~~~~python
from .common import Param

@dataclass
class LazyResult(Generic[T]):
~~~~~

#### Acts 3: 修复 `graph/model.py` 的导入

更新 `graph.model` 以从新位置导入 `Param`。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
from cascade.spec.task import Param
~~~~~
~~~~~python
from cascade.spec.common import Param
~~~~~

#### Acts 4: 修复 `graph/build.py` 的导入

更新 `GraphBuilder` 以从新位置导入 `Param`。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.spec.task import LazyResult, Param
~~~~~
~~~~~python
from cascade.spec.task import LazyResult
from cascade.spec.common import Param
~~~~~

#### Acts 5: 修复 `__init__.py` 的导出

确保 `Param` 仍然是公共 API。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
~~~~~
~~~~~python
from .spec.task import task, LazyResult
from .spec.common import Param
~~~~~

### 下一步建议
这次重构应该能解决循环导入问题。请执行此计划，然后我们可以重新运行测试，确认所有模块都能被正确加载，并继续我们对 `ParamNode` 的修复工作。
