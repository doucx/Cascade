You've hit the next logical error in our refactoring cascade. My apologies for not catching this in the previous step. We removed the `Constant` class from `binding.py` along with `SlotRef`, but a few files still try to import or use it.

This is the final cleanup step. I will generate a plan to remove these last remaining references, which should resolve the `ImportError` and get the test suite running.

## [WIP] fix(core): Remove Constant import and usage to finalize refactoring

### 错误分析
-   **现象**: `pytest` 启动时因 `ImportError: cannot import name 'Constant'` 而崩溃。
-   **根因**: 在上一步中，我们从 `cascade.spec.binding` 模块中彻底移除了 `Constant` 类的定义，但 `resolvers.py` 和一个测试文件 `test_preview.py` 仍然在尝试导入和使用它。
-   **影响**: 重构处于未完成状态，测试套件无法启动。

### 用户需求
修复 `ImportError`, 移除对已废弃的 `Constant` 类的所有引用，使代码库与新的、自包含的 `Node` 模型完全一致。

### 评论
这是完成 `binding.py` 模块简化的最后一步。通过移除这些悬空的引用，我们不仅能修复当前的 `ImportError`，还能确保整个代码库的概念一致性，使 `Node` 的 `input_bindings` 成为一个只包含普通 Python 对象的简单字典。

### 目标
1.  从 `resolvers.py` 中移除对 `Constant` 的导入。
2.  更新 `test_preview.py` 中的测试用例，使其不再使用 `Constant` 包装器，而是直接使用字面量值。
3.  更新 `model.py` 中的一个相关注释，以反映 `input_bindings` 的新设计。

### 基本原理
完成上一步重构的清理工作。通过消除对 `Constant` 类的所有引用，我们确保了代码的内部一致性，并解决了由此引发的 `ImportError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #comp/graph #scope/core #ai/instruct #task/domain/architecture #task/object/node-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `resolvers.py`

移除导致 `ImportError` 的 `Constant` 导入语句。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.binding import Constant
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend
~~~~~
~~~~~python
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend
~~~~~

#### Acts 2: 修复 `test_preview.py`

更新 `test_console_subscriber_renders_correctly` 测试用例，直接在 `input_bindings` 中使用字面量 `42`，而不是 `Constant(42)`。

~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            input_bindings={"param": cs.spec.binding.Constant(42)},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "Bindings: {'param': 'Const(42)'}" in captured.out
~~~~~
~~~~~python
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            input_bindings={"param": 42},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "Bindings: {'param': 42}" in captured.out
~~~~~

#### Acts 3: 更新 `model.py` 中的注释

最后，更新 `Node` 类中的注释，使其准确描述 `input_bindings` 的当前状态。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
    # Structural Bindings
    # Maps argument names to references (Slots or Constants).
    # Actual values are stored in a separate DataTuple at runtime.
    input_bindings: Dict[str, Binding] = field(default_factory=dict)

    def __hash__(self):
~~~~~
~~~~~python
    # Structural Bindings
    # Maps argument names to their literal (JSON-serializable) values.
    # This makes the Node self-contained.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
~~~~~

### 下一步建议
我们已经清除了所有已知的 `SlotRef` 和 `Constant` 残留。请再次运行 `pytest`。如果测试能够成功启动并运行，我们将可以确认重构已稳定，然后继续验证性能基准。
