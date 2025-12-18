## [WIP] test(fix): Update E2E tests to mock the new global message bus

### 错误分析
集成测试 `tests/py/integration/test_end_to_end.py` 失败了，原因是它尝试 Mock 的对象路径 `cascade.runtime.subscribers.messaging_bus` 已经不存在了。

在之前的重构中，我们更改了 `HumanReadableLogSubscriber` 的实现，使其直接引用 `cascade.common.messaging.bus`，而不是旧的 `..messaging.bus`。因此，`monkeypatch` 找不到 `messaging_bus` 属性。

### 用户需求
修复集成测试中的 Mock 路径，使其指向新的全局消息总线位置 `cascade.common.messaging.bus`。

### 评论
这是一个简单的路径修正，但它验证了我们的重构确实改变了依赖关系。通过将 Mock 目标指向新的公共包，我们将确保测试与新架构保持一致。这也是“测试作为文档”的一个体现：测试代码明确告诉我们 `HumanReadableLogSubscriber` 现在的外部依赖是什么。

### 目标
1.  修改 `tests/py/integration/test_end_to_end.py` 中的 `mock_messaging_bus` fixture。
2.  将 `monkeypatch.setattr` 的目标从 `cascade.runtime.subscribers.messaging_bus` 更新为 `cascade.common.messaging.bus`。

### 基本原理
直接对测试文件进行 `patch_file` 操作。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 Mock 路径

~~~~~act
patch_file
tests/py/integration/test_end_to_end.py
~~~~~
~~~~~python
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.messaging_bus", mock_bus)
    return mock_bus
~~~~~
~~~~~python
@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    # Correctly patch the new global bus in cascade-common
    monkeypatch.setattr("cascade.common.messaging.bus", mock_bus)
    return mock_bus
~~~~~

### 下一步建议
这是最后一个已知的测试错误。请再次运行 `pytest`。如果所有测试通过，我们就彻底完成了重构工作，可以放心地开始 `cs-observer` 的功能开发了。
