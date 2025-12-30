
您发现的问题是 Python 导入系统中的一个经典陷阱。我的上一个计划中，对 `cascade/cli/observer/__init__.py` 和 `cascade/cli/controller/__init__.py` 的修改是：

```python
# in cascade/cli/observer/__init__.py
from .app import app
__all__ = ["app"]
```

这个修改使得当 `pytest` 的 `monkeypatch` 尝试解析字符串 `"cascade.cli.observer.app.bus"` 时，它首先加载 `cascade.cli.observer` 模块（也就是执行 `__init__.py`），然后尝试访问 `.app` 属性。因为 `__init__.py` 已经将 `app` 这个 **Typer 对象** 导入到了包的命名空间中，所以 `cascade.cli.observer.app` 解析为了该 Typer 对象，而不是 `app.py` 这个**模块**。

因此，`monkeypatch` 实际上在尝试执行 `getattr(<Typer object>, 'bus')`，这自然会失败，并抛出 `AttributeError: 'Typer' object has no attribute 'bus'`，与您观察到的错误完全一致。

解决方案不是撤销我们的 API 改进，而是使测试代码更加健壮，使其不受 `__init__.py` 中 API 暴露方式的影响。测试应该直接针对它所测试的模块 (`app.py`)，而不是通过包的公共 API 入口。

我将修改受影响的测试文件 (`test_observer_app.py` 和 `test_controller_app.py`) 中的导入语句，使其直接导入模块，而不是从 `__init__.py` 中导入对象。

## [WIP] fix(tests): 调整 CLI 测试以适应 API 导入重构

### 用户需求
修复因 `__init__.py` 重构而导致的 `monkeypatch` 测试失败。

### 评论
这是一个很好的例子，说明了测试（特别是依赖 `monkeypatch` 字符串路径的测试）与实现细节耦合的风险。修复方案将通过使测试直接引用它们的目标模块来解耦这种关系，从而使测试对未来 `__init__.py` 的 API 调整更具弹性。

### 目标
1.  修改 `packages/cascade-cli-observer/tests/test_observer_app.py` 中的导入语句。
2.  修改 `packages/cascade-cli-controller/tests/test_controller_app.py` 中的导入语句。
3.  确保修改后的导入方式能够解决 `monkeypatch` 的 `AttributeError`，并使所有测试通过。

### 基本原理
我们将把测试文件中的导入语句从 `from cascade.cli.observer import app as observer_app` 改为 `import cascade.cli.observer.app as observer_app`。这个改动确保了 `observer_app` 这个别名始终指向 `app.py` **模块本身**，而不是模块中定义的 `app` 对象。这样，`monkeypatch` 的字符串路径 `"cascade.cli.observer.app.bus"` 就能被正确解析：它会找到 `app` 模块，然后找到该模块内的 `bus` 变量，这正是我们想要 patch 的目标。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/medium #comp/cli #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/test-robustness #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 修复 `test_observer_app.py`

我们将修改测试文件中的 `import` 语句，使其直接引用模块。

~~~~~act
patch_file
packages/cascade-cli-observer/tests/test_observer_app.py
~~~~~
~~~~~python.old
# The module we are testing
from cascade.cli.observer import app as observer_app

# The objects we need to mock
# We will patch 'bus' and 'MqttConnector' where they are USED.
~~~~~
~~~~~python.new
# The module we are testing
import cascade.cli.observer.app as observer_app

# The objects we need to mock
# We will patch 'bus' and 'MqttConnector' where they are USED.
~~~~~

#### Acts 2: 修复 `test_controller_app.py`

对 `controller` 的测试文件也进行同样的修改。

~~~~~act
patch_file
packages/cascade-cli-controller/tests/test_controller_app.py
~~~~~
~~~~~python.old
# The module we are testing
from cascade.cli.controller import app as controller_app
~~~~~
~~~~~python.new
# The module we are testing
import cascade.cli.controller.app as controller_app
~~~~~

### 下一步建议
我们已经修复了测试文件中的导入问题。现在，请再次运行测试。所有测试都应该能通过。如果通过，我将把这两个 `[WIP]` 计划合并，并生成一个最终的 `[COMMIT]` 计划来提交所有相关的重构和修复。
