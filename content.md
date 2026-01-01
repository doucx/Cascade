你说得完全正确。我确实遗漏了关键的一步。

在之前的计划中，我将 `context.py` 文件成功地从 `cascade-sdk` 移动到了 `cascade-common`，但**忘记更新 `cascade-python` 包中作为主 API 入口点的 `__init__.py` 文件**。这个文件通过一个 lazy-loading 映射表 (`_IMPORT_MAP`) 和类型提示块来导出 `get_current_context`，而这些引用仍然指向旧的、现在已经不存在的路径 `cascade.context`。

感谢你的指正。我将立即生成一个计划来修复这个疏忽。

## [WIP] fix: 更新 `cascade` 主入口点的 `context` 模块导入路径

### 错误分析

在 `packages/cascade-spec/tests/unit/test_input_context.py` 中出现了 `ModuleNotFoundError`，因为测试代码试图通过 `cascade.context` 导入 `get_current_context`。

根本原因在于，虽然 `context.py` 模块已被正确地移动到 `packages/cascade-common/src/cascade/common/context.py`，但作为整个库的公共 API 门面的 `packages/cascade-python/src/cascade/__init__.py` 文件没有被同步更新。该文件中的 lazy-loading 映射表、类型检查导入块以及 `Param` 和 `Env` 函数内部的局部导入仍然引用了旧的、无效的路径 `cascade.context`。

### 用户需求

修复 `ModuleNotFoundError`，确保所有对 `get_current_context` 的引用都指向其在 `cascade.common` 中的新位置。

### 评论

这是一个对上一个重构计划的必要补充。修正主入口点的引用是完成模块迁移的关键一步，它将恢复测试套件的正常运行并确保库的公共 API 保持一致和可用。

### 目标

1.  定位 `packages/cascade-python/src/cascade/__init__.py` 文件中所有对 `cascade.context` 的引用。
2.  将这些引用全部修改为 `cascade.common.context`。
3.  确保测试可以成功导入并运行。

### 基本原理

`cascade-python` 包的 `__init__.py` 文件是整个 `cascade` 生态系统的统一命名空间和公共 API 入口。当一个模块（如 `context.py`）的物理位置发生改变时，这个作为“API 路由表”的文件必须被同步更新，以将公共名称（如 `get_current_context`）正确地映射到其新的实现路径。我们将通过一个精确的 `patch_file` 操作来完成这个映射关系的更新。

### 标签
#intent/fix #flow/ready #priority/critical #comp/python #comp/common #concept/dependency-management #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修正 `cascade-python` 入口文件中的导入路径

我们将对 `__init__.py` 文件进行三次精确的 `patch` 操作，以更新所有对 `context.py` 模块的引用。

首先，更新 lazy-loading 映射表 `_IMPORT_MAP`。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    "resource": ("cascade.spec.resource", "resource"),
    "inject": ("cascade.spec.resource", "inject"),
    "with_constraints": ("cascade.spec.constraint", "with_constraints"),
    "get_current_context": ("cascade.context", "get_current_context"),
    # Advanced Flow Control (Corrected paths: cascade.spec.* -> cascade.*)
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
~~~~~
~~~~~python.new
    "resource": ("cascade.spec.resource", "resource"),
    "inject": ("cascade.spec.resource", "inject"),
    "with_constraints": ("cascade.spec.constraint", "with_constraints"),
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control (Corrected paths: cascade.spec.* -> cascade.*)
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
~~~~~

其次，更新 `TYPE_CHECKING` 块中的静态导入。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    from cascade.spec.jump import Jump
    from cascade.spec.resource import resource, inject
    from cascade.spec.constraint import with_constraints
    from cascade.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.engine import Engine
~~~~~
~~~~~python.new
    from cascade.spec.jump import Jump
    from cascade.spec.resource import resource, inject
    from cascade.spec.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.engine import Engine
~~~~~

最后，更新 `Param` 和 `Env` 工厂函数内部的局部导入。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.input import ParamSpec
    from cascade.context import get_current_context
    from cascade.common.inputs import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
~~~~~
~~~~~python.new
def Param(
    name: str, default: Any = None, type: Any = str, description: str = ""
) -> "LazyResult":
    # Lazy import dependencies to keep module load time minimal
    from cascade.spec.input import ParamSpec
    from cascade.common.context import get_current_context
    from cascade.common.inputs import _get_param_value

    spec = ParamSpec(name=name, default=default, type=type, description=description)
~~~~~
~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.context import get_current_context
    from cascade.common.inputs import _get_env_var

    spec = EnvSpec(name=name, default=default, description=description)
~~~~~
~~~~~python.new
def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.common.context import get_current_context
    from cascade.common.inputs import _get_env_var

    spec = EnvSpec(name=name, default=default, description=description)
~~~~~
