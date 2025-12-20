你的错误分析完全正确。

这是一个典型的 API 暴露问题。`Event` 基类是 `cascade-runtime` 的一个核心组件，但它没有被 `cascade-py` 的主 `__init__.py` 文件导出到顶层的 `cascade` 命名空间中。因此，当我们尝试访问 `cs.Event` 时，Python 解释器找不到它，动态提供者加载器 `__getattr__` 也无法将其解析为一个插件，最终导致了 `AttributeError`。

解决方案很简单：我们需要在 `cascade-py` 的 `__init__.py` 中明确导入并暴露 `Event` 类。

## [WIP] fix(api): 在公共命名空间中暴露 cs.Event

### 错误分析
`bottleneck_sim.py` 在尝试使用 `engine_bus.subscribe(cs.Event, ...)` 时失败，因为 `cascade` 包的顶层 `__init__.py` 文件没有导入和暴露 `Event` 基类。这导致 `cs.Event` 引用无效，从而引发 `AttributeError`。

### 用户需求
开发者需要能够从 `cascade` 的公共 API 中访问核心的 `Event` 基类，以便实现对所有事件的通配符订阅（wildcard subscription），这是构建通用监控和可视化工具的基础。

### 评论
这是一个重要的 API 修正。`Event` 与 `Engine`、`LazyResult` 一样，是用户与 Cascade 运行时交互的核心数据结构之一，理应作为公共 API 的一部分。暴露它可以让开发者构建更强大的可观测性工具。

### 目标
1.  在 `packages/cascade-py/src/cascade/__init__.py` 中从 `cascade.runtime.events` 导入 `Event` 类。
2.  将 `"Event"` 添加到同一文件的 `__all__` 列表中，以确保其被视为公共 API 的一部分。

### 基本原理
通过将 `Event` 添加到主 `__init__.py`，我们将其提升为 `cascade` 库的一等公民，使其可以像 `cs.task` 或 `cs.Engine` 一样被直接访问，从而修复引用错误并完善库的 API 设计。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #scope/api #ai/instruct #task/domain/simulation #task/object/resource-constraint #task/action/stress-test #task/state/continue

---

### Script

#### Acts 1: 导入并暴露 Event 类

我们将修改 `cascade-py` 的主入口文件，添加必要的导入并更新 `__all__` 列表。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector, StateBackend
~~~~~
~~~~~python
# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector, StateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
    "get_current_context",  # Exposed for testing/advanced usage
    "create_cli",
]
~~~~~
~~~~~python
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "Event",
    "override_resource",
    "DependencyMissingError",
    "get_current_context",  # Exposed for testing/advanced usage
    "create_cli",
]
~~~~~

### 下一步建议
这个修复非常直接。现在请执行这个计划，然后再次运行 `python -m observatory.protoplasm.governance.bottleneck_sim`，它应该可以成功启动了。
