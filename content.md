分析完全正确。

`cascade` 模块的顶层 `__init__.py` 文件中的 `__getattr__` 实现过于宽泛，它将所有未找到的属性都委托给了 provider registry 进行查找。这是一个反模式，因为像 `NativeSolver`、`Engine` 这样的核心组件并非 provider，而是应该被明确导出的 API。这导致了用户遇到的 `AttributeError`。

我们将遵循测试驱动开发 (TDD) 的流程来解决这个问题：

1.  **Red**: 首先，我会创建一个新的集成测试，该测试会尝试从顶层 `cascade` 包导入这些核心组件。这个测试目前会失败，从而精确地复现你报告的错误。
2.  **Green**: 接着，我会修改 `cascade-sdk` 的 `__init__.py` 文件，移除有问题的 `__getattr__` 逻辑中关于 provider 的部分，并用显式的导入语句替换它，以正确地暴露核心 API。
3.  **Refactor**: 最后，我们将确保代码整洁，并且新加入的测试能够清晰地记录和保护我们所期望的公共 API 接口。

我将生成一个计划来实现这个 TDD 流程。

## [WIP] test(sdk): 为公共 API 导入添加集成测试并修复

### 错误分析
`observatory/experiments/run_fireflies.py` 脚本在执行 `cs.NativeSolver()` 时失败，抛出 `AttributeError`。根本原因在于 `packages/cascade-sdk/src/cascade/__init__.py` 中实现的 `__getattr__` 函数。该函数错误地拦截了所有在 `cascade` 模块上未找到的属性访问，并尝试将它们作为 "provider" 从 `registry` 中加载。

然而，像 `NativeSolver`, `LocalExecutor`, `Engine` 和 `MessageBus` 这样的核心类是引擎的关键组件，而不是通过插件系统加载的 provider。因此，当 `__getattr__` 尝试在 provider 注册表中查找 `NativeSolver` 时，它失败了，并抛出一个误导性的 `AttributeError: Cascade provider 'NativeSolver' not found.`，最终被包装成顶层的 `AttributeError: module 'cascade' has no attribute 'NativeSolver'`。

### 用户需求
用户要求遵循 TDD 流程解决 `cascade` 模块混乱的导入问题，确保核心组件能够作为稳定的公共 API 被正确访问，并增加测试覆盖率以防止未来出现类似问题。

### 评论
这是一个至关重要的修复。一个库的公共 API 应该是明确、稳定且可预测的。当前使用 `__getattr__` 来动态解析核心组件的行为非常脆弱，且违反了“显式优于隐式”的 Python 设计哲学。通过 TDD 流程，我们不仅能修复当前的 bug，还能建立一个回归测试屏障，确保核心 API 的稳定性。

### 目标
1.  在 `packages/cascade-sdk/tests/integration/` 目录下创建一个新的测试文件 `test_public_api_imports.py`。
2.  在该文件中编写一个测试用例，专门用于验证核心引擎组件（`NativeSolver`, `LocalExecutor`, `Engine`, `MessageBus`）是否可以从顶层 `cascade` 包中成功导入。此测试在修改前应该会失败。
3.  修改 `packages/cascade-sdk/src/cascade/__init__.py`，移除 `__getattr__` 的不当使用，并添加显式的导入语句来暴露上述核心组件。
4.  更新 `__init__.py` 中的 `__all__` 列表，以包含这些新暴露的公共 API。
5.  确保新添加的测试在修改后能够通过。

### 基本原理
我们将遵循 TDD 的核心原则。首先编写一个失败的测试来捕获问题，这能确保我们的修复是针对性且有效的。然后，我们将修改 `cascade-sdk` 的入口文件 `__init__.py`。我们将把 `__getattr__` 的功能限制在它设计的初衷——动态加载 providers，而不是拦截所有属性。核心 API 组件将通过标准的 `from ... import ...` 语句进行显式导入和导出。这种方法使 API 更加清晰、易于静态分析工具理解，并从根本上解决了此类 `AttributeError` 问题。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/sdk #comp/engine #comp/tests #concept/api #scope/dx #ai/instruct #task/domain/testing #task/object/api-surface #task/action/stabilization #task/state/begin

---
### Script

#### Acts 1: [RED] 创建一个失败的集成测试

我们将首先创建一个新的测试文件，用于验证从 `cascade` 顶层包导入核心类的行为。这个测试现在会失败，因为它暴露了当前的 `AttributeError` 问题。

~~~~~act
write_file
packages/cascade-sdk/tests/integration/test_public_api_imports.py
~~~~~
~~~~~python
"""
Tests that core components are correctly exposed through the top-level `cascade` package.
This is a regression test for issues related to the package's __init__.py structure.
"""

import pytest


def test_core_components_are_accessible_from_top_level():
    """
    Verifies that essential classes from cascade-engine and other core packages
    are importable from the `cascade` namespace directly.
    """
    try:
        from cascade import (
            Engine,
            MessageBus,
            NativeSolver,
            LocalExecutor,
            DependencyMissingError,
        )
    except ImportError as e:
        pytest.fail(f"Failed to import core components from top-level 'cascade': {e}")

    # Dummy assertion to ensure the test runs if imports succeed
    assert Engine is not None
    assert MessageBus is not None
    assert NativeSolver is not None
    assert LocalExecutor is not None
    assert DependencyMissingError is not None


def test_accessing_non_existent_attribute_raises_attribute_error():
    """
    Ensures that accessing a truly non-existent attribute on the cascade module
    raises a standard AttributeError, not an error from the provider system.
    """
    import cascade as cs

    with pytest.raises(AttributeError, match="module 'cascade' has no attribute 'ThisClassShouldNotExist'"):
        _ = cs.ThisClassShouldNotExist
~~~~~

#### Acts 2: [GREEN] 修复 `cascade` SDK 的 `__init__.py`

现在，我们将修改 `packages/cascade-sdk/src/cascade/__init__.py`。我们会显式导入核心组件，并调整 `__getattr__` 的逻辑，使其不再错误地拦截对这些核心组件的访问。我们还会更新 `__all__` 列表。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
# --- Runtime (for type hints and exceptions) ---
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.flow import sequence, pipeline
~~~~~
~~~~~python.new
# --- Runtime (for type hints and exceptions) ---
# Core components explicitly exposed in the public API
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.flow import sequence, pipeline
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
def __getattr__(name: str) -> Any:
    from .providers.registry import registry

    try:
        return registry.get(name)
    except AttributeError:
        # This is the original error that was being hit incorrectly.
        # It's correct for its intended purpose (provider loading).
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
~~~~~
~~~~~python.new
def __getattr__(name: str) -> Any:
    """
    Dynamically loads providers from the registry when they are accessed as attributes
    on the `cascade` module (e.g., `cs.read.text`).
    """
    from .providers.registry import registry

    # This will raise an AttributeError for names that are not registered providers,
    # which is the correct behavior. We no longer need a try/except block that
    # could mask other import-related issues.
    return registry.get(name)
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    # Core API
    "task",
    "Param",
    "Env",
    "run",
    "dry_run",
    "visualize",
    # Advanced Flow Control
    "sequence",
    "pipeline",
    "Router",
    "Jump",
    "select_jump",
    "bind",
    # Policies & Resources
    "with_constraints",
    "resource",
    "inject",
    # Types & Classes
    "LazyResult",
    "Engine",
    "Event",
    "MessageBus",  # Added MessageBus
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
~~~~~python.new
__all__ = [
    # Core API
    "task",
    "Param",
    "Env",
    "run",
    "dry_run",
    "visualize",
    # Advanced Flow Control
    "sequence",
    "pipeline",
    "Router",
    "Jump",
    "select_jump",
    "bind",
    # Policies & Resources
    "with_constraints",
    "resource",
    "inject",
    # Types & Classes
    "LazyResult",
    "Engine",
    "Event",
    "MessageBus",
    "NativeSolver",
    "LocalExecutor",
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

### 下一步建议
1.  **运行测试**: 执行 `pytest packages/cascade-sdk/` 来验证我们新添加的测试 `test_public_api_imports.py` 现在是否通过，并确保没有引入任何回归错误。
2.  **提交变更**: 在测试通过后，将这些修改作为一个逻辑单元进行提交。
3.  **代码审查**: 可以在 `cascade` 包的其他 `__init__.py` 文件中进行类似的审查，以确保导入和 API 暴露的一致性。
