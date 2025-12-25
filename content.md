好的，看来我们遇到了“似曾相识”的问题。

错误分析

当我们将测试文件从 `packages/cascade-engine/tests/e2e/` 移动到 `tests/e2e/runtime/` 时，我们实际上将它们移出了 `cascade-engine` 包的上下文。

1.  **Fixture 丢失 (`bus_and_spy`)**:
    *   `bus_and_spy` 是在 `packages/cascade-engine/tests/conftest.py` 中定义的。
    *   被移动后的测试现在位于 `tests/e2e/runtime/`。根据 Pytest 的发现规则，它们**无法再看到**位于 `packages/...` 内部的 `conftest.py`。
    *   因此，所有依赖 `bus_and_spy` 的测试都报错了。

2.  **`conftest.py` 的尴尬位置**:
    *   我们之前在 `packages/cascade-engine/tests/e2e/conftest.py` 中定义了 `cleanup_local_bus`。这个文件也被移动到了 `tests/e2e/runtime/conftest.py`。
    *   日志显示 `cleanup_local_bus` 是可用的（在 `available fixtures` 列表中）。这意味着这个移动后的 `conftest.py` 被正确加载了。

**结论**: 问题在于 `bus_and_spy` 这个 Fixture 被留在了 `packages/cascade-engine` 内部，但现在位于外部的 E2E 测试也需要使用它。

我们需要将 `bus_and_spy` 提升为一个共享的、或者在 E2E 环境中重新定义的 Fixture。考虑到 E2E 测试是针对 Engine 的，它们实际上需要的是一套能观察 Engine 行为的工具。

我将生成一个计划来修复这个问题。

## [WIP] fix(tests): Restore fixtures for relocated E2E tests

### 错误分析
E2E 测试被移动到 `tests/e2e/runtime` 后，失去了对定义在 `packages/cascade-engine/tests/conftest.py` 中的 `bus_and_spy` Fixture 的访问权限。这是因为 Pytest 只在测试目录及其父目录中查找 `conftest.py`，而 `packages/cascade-engine` 不再是这些测试的父目录。

这些 E2E 测试严重依赖 `bus_and_spy` 来监控系统行为。

### 用户需求
用户要求修复因 `bus_and_spy` Fixture 丢失而导致的大量 E2E 测试错误。

### 评论
这验证了之前的架构决策：`bus_and_spy` 是一个通用的测试工具，不应仅局限于单元测试。既然 E2E 测试也需要它，我们需要将其定义复制到 E2E 测试的上下文中，或者将其提升到更全局的位置。考虑到 E2E 测试环境的独立性，最好的做法是在 `tests/e2e/conftest.py` 中提供这个 Fixture，使其对所有 E2E 测试可用。

### 目标
1.  修改 `tests/e2e/runtime/conftest.py`（这是随测试一起移动过来的），添加 `SpySubscriber` 类和 `bus_and_spy` Fixture 的定义。

### 基本原理
通过在 E2E 测试的直接上下文中提供所需的 Fixture，我们切断了对具体包内部测试设施的隐式依赖。这使得 E2E 测试成为真正独立的实体，能够在任何环境中运行，只要安装了 `cascade-engine` 包即可。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/fixtures #task/action/restoration #task/state/continue

---
### Script

#### Acts 1: 在 E2E conftest 中恢复 `bus_and_spy`

我们将把 `SpySubscriber` 和 `bus_and_spy` 的代码添加到 `tests/e2e/runtime/conftest.py` 中。

~~~~~act
patch_file
tests/e2e/runtime/conftest.py
~~~~~
~~~~~python
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
~~~~~
~~~~~python
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()
    yield
    if LocalBusConnector:
        LocalBusConnector._reset_broker_state()


from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.fixture
def bus_and_spy():
    """Provides a MessageBus instance and an attached SpySubscriber."""
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~

### 下一步建议

Fixture 已恢复。现在请再次运行 E2E 测试：
`pytest tests/e2e/runtime`

这应该能解决所有的 "fixture not found" 错误。
