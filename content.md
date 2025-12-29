分析正确。这是一个经典的 Python 包 API 可见性问题。

我在上一步将 `ControllerTestApp` 移动到了 `cascade.testing` 模块中，但是忘记在 `cascade` 包的顶层 `__init__.py` 文件中将其导出。因此，当测试环境尝试从已安装的 `cascade` 包中 `from cascade.testing import ControllerTestApp` 时，该名称是不可见的。

## [WIP] fix(sdk): Expose ControllerTestApp in package public API

### 错误分析
`ImportError` 的根本原因是 `ControllerTestApp` 虽然已经被添加到了 `packages/cascade-sdk/src/cascade/testing.py` 文件中，但并未在 `packages/cascade-sdk/src/cascade/__init__.py` 中被导出。`__init__.py` 文件定义了 `cascade` 包的公共 API。任何未在该文件中导入或在 `__all__` 列表中声明的成员，都无法从包的外部被直接访问，导致测试代码在 `import` 时失败。

### 用户需求
修复 `ImportError`，使得 `ControllerTestApp` 可以作为 `cascade.testing` 模块的一部分被正常导入。

### 评论
这是一个简单的疏忽，修正它可以确保我们对 `cascade.testing` 模块的重构是完整的，并使得测试工具能被项目的其他部分（尤其是 E2E 测试）正确使用。

### 目标
1.  修改 `packages/cascade-sdk/src/cascade/__init__.py`。
2.  从 `.testing` 模块导入 `ControllerTestApp`。
3.  将 `ControllerTestApp`添加到 `__all__` 列表中，正式将其作为公共 API 的一部分。

### 基本原理
遵循 Python 打包的最佳实践，所有希望对外暴露的符号都应该在包的 `__init__.py` 文件中进行管理。

### 标签
#intent/fix #flow/ready #priority/critical #comp/sdk #scope/api #ai/fix #task/domain/testing #task/object/harness #task/action/promote #task/state/continue

---

### Script

#### Acts 1: 在 `cascade/__init__.py` 中导出 `ControllerTestApp`

我们将修改 `__init__.py` 文件以正确导出 `ControllerTestApp`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
# --- Tools ---
from .testing import override_resource
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json
~~~~~
~~~~~python.new
# --- Tools --- 
from .testing import override_resource, ControllerTestApp
from .tools.cli import create_cli
from cascade.graph.serialize import to_json, from_json
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
    # Tools & Utilities
    "to_json",
    "from_json",
    "override_resource",
    "create_cli",
    # Exceptions
    "DependencyMissingError",
    # Context (for advanced usage)
    "get_current_context",
]
~~~~~
~~~~~python.new
    # Tools & Utilities
    "to_json", 
    "from_json", 
    "override_resource", 
    "ControllerTestApp",
    "create_cli", 
    # Exceptions
    "DependencyMissingError", 
    # Context (for advanced usage) 
    "get_current_context", 
]
~~~~~
