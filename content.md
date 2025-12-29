我的分析有误。这是一个更深层次的包结构和导入路径问题，而不是简单的忘记导出。我把注意力集中在了 *哪里* 导出，而忽略了 *如何* 导入。

## [WIP] fix(tests): Correct import path for ControllerTestApp in E2E harness

### 错误分析
我的上一个修复是朝着正确的方向，但只完成了一半。

1.  **我做了什么**：我修改了 `packages/cascade-sdk/src/cascade/__init__.py`，将 `ControllerTestApp` 从 `cascade.testing` 模块提升到了顶层的 `cascade` 包的命名空间中。这意味着，`ControllerTestApp` 现在可以通过 `from cascade import ControllerTestApp` 来访问。

2.  **我没做什么**：我没有更新消费这个 API 的地方（即 `tests/e2e/runtime/harness.py`）来使用这个新的、正确的导入路径。它仍然在尝试 `from cascade.testing import ControllerTestApp`。

3.  **根本原因**: `cascade.testing` 不是一个公共的子包。根据 `cascade` 包的 `__init__.py` 文件，它是一个内部模块，其部分内容（如 `override_resource` 和现在我添加的 `ControllerTestApp`）被提升到了顶层的 `cascade` 命名空间。因此，任何外部代码都应该直接从 `cascade` 导入这些工具，而不是试图深入到其内部的 `testing` 模块。

### 用户需求
修复 E2E 测试中的 `ImportError`，确保测试工具可以被正确地导入和使用。

### 评论
这次修复纠正了API消费者（测试代码）与API提供者（SDK包）之间的不匹配。这是一个常见的包维护错误，通过统一导入路径，我们可以使代码更加清晰和健壮。

### 目标
1.  修改 `tests/e2e/runtime/harness.py`。
2.  将其中的 `from cascade.testing import ControllerTestApp` 修改为 `from cascade import ControllerTestApp`。

### 基本原理
API 的使用者必须遵循该 API 的公共接口定义。`cascade/__init__.py` 将 `ControllerTestApp` 定义为 `cascade` 包的一部分，因此导入路径必须是 `from cascade import ...`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/sdk #comp/tests #scope/api #ai/fix #task/domain/testing #task/object/harness #task/action/promote #task/state/continue

---

### Script

#### Acts 1: 修正 `harness.py` 中的导入路径

我们将修改 `harness.py` 文件，使其从正确的顶层包路径导入 `ControllerTestApp`。

~~~~~act
patch_file
tests/e2e/runtime/harness.py
~~~~~
~~~~~python.old
from cascade.connectors.local import LocalBusConnector

# Re-export ControllerTestApp from the official SDK testing module
from cascade.testing import ControllerTestApp

# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally.
InProcessConnector = LocalBusConnector

# ControllerTestApp is now imported from cascade.testing
__all__ = ["InProcessConnector", "ControllerTestApp"]
~~~~~
~~~~~python.new
from cascade.connectors.local import LocalBusConnector
# Import ControllerTestApp from the top-level package where it's exposed
from cascade import ControllerTestApp

# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally. 
InProcessConnector = LocalBusConnector

# ControllerTestApp is now imported from cascade
__all__ = ["InProcessConnector", "ControllerTestApp"]
~~~~~

### 下一步建议
所有测试现在应该可以通过了。由于我们识别出 `InProcessConnector` 的潜在不稳定性，下一步应该系统性地审查所有其他使用 `.harness` 的 E2E 测试，并将它们迁移到使用确定性的 `cascade.testing.MockConnector`。
