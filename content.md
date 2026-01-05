这两处报错也是典型的“路径残留”，属于 E2E（端到端）测试在重构后没有及时同步内部私有路径导致的。由于我们的 `cascade-runtime` 内部结构变得更加模块化和深层，原本扁平的路径（如 `cascade.runtime.subscribers`）已经不存在了。

我将生成一个计划来修正这些 E2E 测试中的 `monkeypatch` 路径。

## [WIP] fix: 修正 E2E 测试中的内部模块引用路径

### 错误分析

在执行 E2E 测试时，遇到了以下 `ImportError`，这些错误都发生在 `pytest` 的 `monkeypatch.setattr` 过程中：

1.  **`test_end_to_end.py`**: 报错 `No module named 'cascade.runtime.subscribers'`。
    *   **原因**: 在重构后，订阅者逻辑被移动到了 `cascade.runtime.services.observability.subscribers`。
2.  **`test_e2e_robustness.py`**: 报错 `No module named 'cascade.runtime.constraints'`。
    *   **原因**: 约束处理器逻辑被移动到了 `cascade.runtime.services.constraints.handlers`。

`monkeypatch` 需要导入字符串指定的完整模块路径才能进行属性替换。如果路径在物理磁盘上不存在，就会抛出 `ImportError`。

### 用户需求

修正 `tests/e2e/integration/test_end_to_end.py` 和 `tests/e2e/runtime/test_e2e_robustness.py` 中的 `monkeypatch` 目标路径，使其指向重构后的正确物理位置。

### 评论

E2E 测试通常会触及系统的内部深层逻辑，因此对架构重组最为敏感。保持这些测试的路径同步是维护测试套件健康度的必要工作。

### 目标

1.  在 `test_end_to_end.py` 中，将 `monkeypatch.setattr` 的目标从 `"cascade.runtime.subscribers.bus"` 更改为 `"cascade.runtime.services.observability.subscribers.bus"`。
2.  在 `test_e2e_robustness.py` 中，将 `monkeypatch.setattr` 的目标从 `"cascade.runtime.constraints.handlers.bus"` 更改为 `"cascade.runtime.services.constraints.handlers.bus"`。

### 基本原理

通过精确替换 `monkeypatch` 使用的字符串路径，我们可以让 `pytest` 正确找到并 Mock 掉底层的消息总线（Feedback Bus）。这既保证了测试的隔离性（不产生真实的 UI 输出），也解决了因模块路径不存在而导致的导入失败。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/e2e-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `test_end_to_end.py` 中的 Mock 路径

我们将更新集成测试，使其指向正确的观测服务路径。

~~~~~act
patch_file
tests/e2e/integration/test_end_to_end.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    # Patch the bus WHERE IT IS USED, not where it is defined.
    # subscribers.py does: from cascade.common.messaging import bus
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)
    return mock_bus
~~~~~
~~~~~python.new
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    # Patch the bus WHERE IT IS USED, not where it is defined.
    # subscribers.py does: from cascade.common.messaging import bus
    monkeypatch.setattr("cascade.runtime.services.observability.subscribers.bus", mock_bus)
    return mock_bus
~~~~~

#### Acts 2: 修正 `test_e2e_robustness.py` 中的 Mock 路径

接着更新鲁棒性测试，指向正确的约束服务路径。

~~~~~act
patch_file
tests/e2e/runtime/test_e2e_robustness.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_ui_bus(monkeypatch):
    """Mocks the UI bus where it's used for constraint error logging."""
    mock_bus = MagicMock()
    # This must target where 'bus' is imported and used, which is now handlers.py
    monkeypatch.setattr("cascade.runtime.constraints.handlers.bus", mock_bus)
    return mock_bus
~~~~~
~~~~~python.new
@pytest.fixture
def mock_ui_bus(monkeypatch):
    """Mocks the UI bus where it's used for constraint error logging."""
    mock_bus = MagicMock()
    # This must target where 'bus' is imported and used, which is now handlers.py
    monkeypatch.setattr("cascade.runtime.services.constraints.handlers.bus", mock_bus)
    return mock_bus
~~~~~

### 下一步建议

现在所有已知的路径错误和导入错误应该都已清理干净。

我建议你再次运行完整的测试套件。如果这次测试全部通过（或者只有与本次重构无关的错误），我们就可以生成最终的 `[COMMIT]` 计划了。

