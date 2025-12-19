好的，我收到了测试失败的反馈。这表明在之前的重构计划中，虽然结构上正确，但可能触发了一个潜在的、与测试环境或 `pytest-mock` 行为相关的脆弱性。

### 错误分析

所有失败都发生在 `tests/connector-mqtt/test_connector.py` 文件中，并且错误是相同的 `TypeError: object.__new__() takes exactly one argument (the type to instantiate)`。

这个错误通常发生在尝试实例化一个不是类的对象时。在我们的测试场景中，我们正在 Mock `aiomqtt.Client` 这个类。错误表明，在测试执行时，被 Mock 的 `aiomqtt.Client` 对象不再是一个可实例化的类（或返回实例的工厂），而可能是一个普通的 Mock 实例。

虽然之前的重构没有直接修改这个文件，但目录结构的改变可能会影响 `pytest` 的测试发现路径和模块加载顺序，从而暴露了 `mocker.patch(..., return_value=...)` 这种快捷方式在特定上下文中的不稳定行为。

**解决方案**:
我们将修改 `test_connector.py` 中的 Mocking 策略，采用一种更明确、更健壮的方式：
1.  创建一个 `MagicMock` 对象，它将作为被 Mock 类的替代品（一个工厂）。
2.  配置这个 `MagicMock` 工厂，使其在被调用时返回我们预先准备好的 `AsyncMock` 实例。
3.  使用 `mocker.patch(..., new=...)` 显式地用我们创建的工厂来替换目标类。

这种方法比使用 `return_value` 快捷方式更底层，也更不容易受环境影响，应该可以解决这个问题。

## [WIP] fix(tests): 修复 MQTT 连接器测试中的 Mocking 策略

### 用户需求
修复在 `tests/connector-mqtt/test_connector.py` 中因 Mocking 策略不稳定而导致的 `TypeError` 测试失败。

### 评论
测试失败是重构过程中的正常现象，它帮助我们识别并加固系统中脆弱的部分。通过采用更明确的 Mocking 模式，我们可以提高测试套件的健壮性，使其更能抵抗未来因环境变化而引入的不确定性。

### 目标
1.  修改 `test_connector.py` 中的 `mock_client` Fixture，使用 `mocker.patch(..., new=...)`。
2.  修改 `test_connector.py` 中的 `test_connect_and_disconnect_lifecycle` 测试，使用相同的 `new=...` 模式进行 Mock。

### 基本原理
我们将 `mocker.patch` 的 `return_value` 参数替换为更明确的 `new` 参数。`new` 参数接受一个对象，该对象将完全替换被 patch 的目标。我们提供一个配置好的 `MagicMock` 作为这个 `new` 对象，它在被调用时（即代码尝试 `aiomqtt.Client(...)` 时）会返回我们想要的 `AsyncMock` 实例。这消除了 `return_value` 快捷方式可能存在的歧义。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/mocking-strategy #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修复 `mock_client` Fixture

我们将更新 Fixture 以使用更明确的 `new=` 参数进行 patching。

~~~~~act
patch_file
tests/connector-mqtt/test_connector.py
~~~~~
~~~~~python
@pytest.fixture
def mock_client(mocker):
    """Provides a mocked aiomqtt.Client instance and patches the class."""
    mock_instance = AsyncMock()
    # Configure the context manager protocol
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None

    mocker.patch(
        "cascade.connectors.mqtt.connector.aiomqtt.Client", return_value=mock_instance
    )
    return mock_instance
~~~~~
~~~~~python
@pytest.fixture
def mock_client(mocker):
    """Provides a mocked aiomqtt.Client instance and patches the class."""
    mock_instance = AsyncMock()
    # Configure the context manager protocol
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None

    mock_class = mocker.MagicMock(return_value=mock_instance)
    mocker.patch(
        "cascade.connectors.mqtt.connector.aiomqtt.Client", new=mock_class
    )
    return mock_instance
~~~~~

#### Acts 2: 修复 `test_connect_and_disconnect_lifecycle` 测试

同样，我们将更新此测试用例内部的 patching 逻辑。

~~~~~act
patch_file
tests/connector-mqtt/test_connector.py
~~~~~
~~~~~python
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    mock_client_class = mocker.patch(
        "cascade.connectors.mqtt.connector.aiomqtt.Client",
        return_value=mock_client_instance,
    )
    mock_will_class = mocker.patch("cascade.connectors.mqtt.connector.aiomqtt.Will")
~~~~~
~~~~~python
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    mock_client_class_factory = mocker.MagicMock(return_value=mock_client_instance)
    mocker.patch(
        "cascade.connectors.mqtt.connector.aiomqtt.Client",
        new=mock_client_class_factory,
    )
    mock_will_class = mocker.patch("cascade.connectors.mqtt.connector.aiomqtt.Will")
~~~~~

### 下一步建议
我们已经应用了针对性的修复。现在请重新运行测试套件。如果所有测试通过，我们可以将这次重构标记为一个完整的提交 (`[COMMIT]`)。
