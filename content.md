好的，我来分析并修复这个错误。

### 错误分析

你的分析非常准确。在我执行上一个计划进行重构时，引入了一个 Python 命名空间包（namespace package）的冲突。

1.  **冲突源头**:
    *   `cascade-engine` 包提供了一个模块 `cascade.connectors.local` (通过文件 `local.py`)，其中定义了 `LocalBusConnector`。
    *   我将 `cascade-connector-sqlite` 重命名并重构为 `cascade-connector-local`，这创建了一个**包** `cascade.connectors.local` (通过目录 `local/`)，其中定义了 `LocalConnector`。

2.  **冲突后果**:
    *   当 Python 的导入系统尝试解析 `from cascade.connectors.local import ...` 时，它会优先找到 `cascade-connector-local` 提供的 `local/` **目录**。一旦找到，它就不会再寻找 `cascade-engine` 提供的 `local.py` **文件**。
    *   因此，当测试代码尝试 `from cascade.connectors.local import LocalBusConnector` 时，Python 只在 `local/` 目录中查找，但 `LocalBusConnector` 并不在那里（它在另一个包的 `local.py` 文件中），从而导致 `ImportError`。

### 解决方案

解决方案是解决这个命名空间冲突，同时进行一次有益的架构整理。我将把 `LocalBusConnector` (内存总线连接器) 从 `cascade-engine` 移动到 `cascade-connector-local` 包中。

这在概念上是正确的：`cascade-connector-local` 包将成为所有“本地”（非网络、单机）连接器的统一归宿，包括基于内存的 (`LocalBusConnector`) 和基于文件系统的 (`LocalConnector`)。

我将生成一个新的计划来执行这个修复。

## [WIP] fix: 通过合并本地连接器解决命名空间冲突

### 错误分析
上一步的重构意外地在两个不同的包中创建了同名的 `cascade.connectors.local` 命名空间，一个是 `cascade-engine` 中的模块 (`local.py`)，另一个是 `cascade-connector-local` 中的包 (`local/`)。这导致 Python 无法找到 `LocalBusConnector`，因为包的优先级高于模块，从而引发了 `ImportError`。

### 用户需求
修复在运行测试时遇到的 `ImportError: cannot import name 'LocalBusConnector' from 'cascade.connectors.local'` 错误。

### 评论
这是一个典型的命名空间冲突问题，修复它同时也是一次很好的架构改进。将所有功能相似的“本地”连接器（无论是内存中的还是基于文件的）整合到一个包中，可以使项目结构更清晰，依赖关系更明确。

### 目标
1.  将 `LocalBusConnector` 的实现文件从 `cascade-engine` 包移动到 `cascade-connector-local` 包。
2.  更新 `cascade-connector-local` 包的 `__init__.py`，以同时导出 `LocalConnector` 和 `LocalBusConnector`。
3.  确保此更改后，所有测试都能正确找到并导入 `LocalBusConnector`。

### 基本原理
通过将 `cascade-engine/src/cascade/connectors/local.py` 移动到 `cascade-connector-local` 包内，我们消除了命名空间冲突。现在，`cascade.connectors.local` 这个命名空间将由 `cascade-connector-local` 这一个包唯一提供，其中包含了所有相关的类，从而解决了导入错误。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/config #scope/dx #ai/instruct #task/domain/storage #task/object/local-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 移动 `LocalBusConnector` 的实现

我们将 `LocalBusConnector` 的源文件从 `cascade-engine` 移动到 `cascade-connector-local` 包中，并将其重命名为 `bus.py` 以避免与目录名混淆。

~~~~~act
move_file
packages/cascade-engine/src/cascade/connectors/local.py
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~

#### Acts 2: 统一导出连接器类

现在，更新 `cascade-connector-local` 包的 `__init__.py` 文件，使其同时导出 `LocalConnector` 和新移入的 `LocalBusConnector`。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import LocalConnector

__all__ = ["LocalConnector"]
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import LocalConnector
from .bus import LocalBusConnector

__all__ = ["LocalConnector", "LocalBusConnector"]
~~~~~

### 下一步建议
这次修复解决了由之前重构引起的严重导入错误，并优化了项目结构。现在 `cascade.connectors.local` 命名空间是干净且唯一的。

在执行此计划后，所有的测试应该都能成功通过。之后，我们可以安全地继续执行路线图的 **步骤 2: [核心机制] 实现基于 UDS 的 Telemetry 事件服务器**。
