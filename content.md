好的，收到了测试错误报告。

这是一个典型的 Python 导入错误，我的上一个计划中存在疏忽。

## [WIP] fix: 修复 SqliteConnector 的包导出问题

### 错误分析
测试套件在收集测试用例时失败，抛出了 `ImportError: cannot import name 'SqliteConnector' from 'cascade.connectors.sqlite'`。

根本原因在于 `packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/__init__.py` 文件是空的。根据 Python 的包管理机制，为了能从一个包（`cascade.connectors.sqlite`）直接导入一个在子模块（`connector.py`）中定义的类（`SqliteConnector`），该包的 `__init__.py` 文件必须显式地将这个类导入到自己的命名空间中。

由于 `__init__.py` 文件为空，`cascade.connectors.sqlite` 命名空间下没有任何对象，导致 `from cascade.connectors.sqlite import SqliteConnector` 语句失败。

### 用户需求
修复 `ImportError`，使测试套件能够正常运行。

### 评论
这是一个常见的打包错误，修复起来很简单，但它完全阻断了我们的测试流程，因此修复优先级很高。这也凸显了在创建新模块时，确保 `__init__.py` 文件正确配置的重要性。

### 目标
修改 `packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/__init__.py` 文件，使其正确地导出 `SqliteConnector` 类。

### 基本原理
为了解决这个问题并遵循项目中其他连接器包（如 `cascade-connector-mqtt`）的结构，我将使用 `write_file` 来更新 `__init__.py`。新的内容将包含：
1.  一个标准的命名空间包声明，以确保在可编辑模式下安装的兼容性。
2.  从同级目录的 `connector.py` 模块中导入 `SqliteConnector` 类。
3.  将 `SqliteConnector` 添加到 `__all__` 列表中，以明确包的公共 API。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/state #scope/dx #ai/instruct #task/domain/cli #task/object/sqlite-connector #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 更新 `__init__.py` 以导出 `SqliteConnector`

我们将覆写这个 `__init__.py` 文件，添加必要的导入语句。

~~~~~act
write_file
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import SqliteConnector

__all__ = ["SqliteConnector"]
~~~~~

### 下一步建议
这个修复应该能解决测试收集阶段的 `ImportError`。请重新运行测试。如果测试通过，我们就可以继续执行原计划的 **步骤 4**，即为新的 CLI 功能编写全面的端到端测试。
