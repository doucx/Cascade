你的分析和提醒非常及时。之前的 `patch_file` 确实存在语法不规范和匹配范围模糊的问题。

由于 `sequence` 和 `pipeline` 的错误导入分布在 `_IMPORT_MAP` 和 `TYPE_CHECKING` 两个不同的逻辑块中，我将按照你的要求，使用两个精确匹配的 `patch_file` 指令来分别修正它们，并严格遵守 `.old` 和 `.new` 的后缀规范。

## [WIP] fix(python): 修正 sequence 和 pipeline 的导入映射

### 错误分析
测试失败 `AttributeError: module 'cascade.runtime.flow' has no attribute 'sequence'` 是因为在 `cascade-python` 的统一入口中，将 `sequence` 和 `pipeline` 错误地映射到了 `cascade.runtime.flow` 模块。

实际上：
- `cascade.runtime.flow` 仅包含运行时引擎使用的 `FlowManager`。
- `sequence` 和 `pipeline` 作为用户侧的流程编排工具，定义在 `cascade-library` 包的 `cascade.flow` 模块中。

### 用户需求
修正 `cs.sequence` 和 `cs.pipeline` 的导出路径，使其指向正确的实现位置。

### 评论
这种映射错误会导致 SDK 核心功能失效。通过拆分为两个精确的 patch，我们可以确保修改的原子性和匹配的准确性。

### 目标
1.  修正 `_IMPORT_MAP` 字典中的运行时加载路径。
2.  修正 `TYPE_CHECKING` 块中的静态分析导入路径。

### 基本原理
`cascade-python` 使用 PEP 562 (`__getattr__`) 实现延迟导入。修正 `_IMPORT_MAP` 后，运行时调用 `cs.sequence` 将触发正确的模块加载逻辑。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/core #ai/instruct #task/domain/sdk #task/object/import-map #task/action/correction #task/state/begin

---

### Script

#### Acts 1: 修正 `_IMPORT_MAP` 中的运行时路径

我们将 `sequence` 和 `pipeline` 的来源模块从 `cascade.runtime.flow` 更改为 `cascade.flow`。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
    "sequence": ("cascade.runtime.flow", "sequence"),
    "pipeline": ("cascade.runtime.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.adapters.solvers.native", "NativeSolver"),
~~~~~
~~~~~python.new
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.adapters.solvers.native", "NativeSolver"),
~~~~~

#### Acts 2: 修正 `TYPE_CHECKING` 块中的类型导入

同步更新类型提示的来源，以消除 IDE 和 Pyright 的虚假报错。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    from cascade.runtime.bus import MessageBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
    from cascade.runtime.flow import sequence, pipeline

    from cascade.adapters.solvers.native import NativeSolver
~~~~~
~~~~~python.new
    from cascade.runtime.bus import MessageBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.adapters.solvers.native import NativeSolver
~~~~~

### 下一步建议
执行完成后，请尝试重新运行测试：
`pytest packages/cascade-engine/tests/integration/test_engine_flow_primitives.py`
验证 `AttributeError` 是否消失。如果仍然遇到 `ImportError`，则说明 `cascade-library` 的开发路径未被正确识别，可能需要检查 `sys.path` 或 `pyproject.toml` 的配置。
