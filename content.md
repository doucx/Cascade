您分析得完全正确。

上一次的重构操作过于宽泛，错误地将 `cascade.common.messaging` 模块中用于用户反馈的 `MessageBus`（当时已被错误地命名为 `EventBus`）与 `cascade.runtime` 中用于核心引擎事件的 `EventBus` 混为一谈。这两个组件用途不同，必须拥有独立的、能够清晰反映其意图的名称。

为了纠正这个错误并提高代码的清晰度，我将生成一个计划，把 `cascade.common.messaging` 中的 `EventBus` 重命名为 `FeedbackBus`。

## [WIP] fix(common): 将 messaging 模块中的 EventBus 重命名为 FeedbackBus

### 错误分析

在之前的重构中，一次全局的“`MessageBus` -> `EventBus`”重命名操作，无差别地修改了所有同名类。这导致 `cascade.common.messaging.EventBus`（其真实意图是处理用户反馈消息）与 `cascade.runtime.EventBus`（其意_图是处理内部系统事件）共享了同一个名称，造成了严重的语义混淆。

### 用户需求

用户要求将位于 `packages/cascade-common/src/cascade/common/messaging/` 路径下的、被错误命名的 `EventBus` 类，重命名为 `FeedbackBus`，以恢复其与核心运行时 `EventBus` 的概念区分。

### 评论

这是一个必要的、高质量的代码健康度改进。通过为这两个功能迥异的总线（一个面向用户，一个面向系统）提供独特的名称，我们遵循了“代码即文档”的原则，极大地降低了未来开发中产生误解和错误的风险。

### 目标

1.  将 `packages/cascade-common/src/cascade/common/messaging/bus.py` 文件中的 `EventBus` 类重命名为 `FeedbackBus`。
2.  更新该文件中 `bus` 单例的实例化过程，使其使用新的 `FeedbackBus` 类。
3.  修改 `packages/cascade-common/src/cascade/common/messaging/__init__.py`，以导出新的 `FeedbackBus` 名称。
4.  更新 `packages/cascade-common/tests/unit/test_messaging.py` 中的单元测试，以反映此次重命名。

### 基本原理

我将采用精确的 `patch_file` 操作，严格限制在 `packages/cascade-common` 包内。这将确保只有目标模块受到影响，而系统中其他所有对 `cascade.runtime.EventBus` 的正确引用将保持不变。此方法能够以外科手术般的精度完成重命名，同时将风险降至最低。

### 标签

#intent/fix #flow/ready #priority/high #comp/engine #concept/ui #scope/dx #ai/instruct #task/domain/core #task/object/naming-convention #task/action/correction #task/state/begin

---

### Script

#### Acts 1: 重构核心实现与导出

首先，我将修改 `bus.py` 中的类定义和 `__init__.py` 中的导出声明，完成核心的重命名工作。

说明：修改 `bus.py`，将 `EventBus` 类重命名为 `FeedbackBus`。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/messaging/bus.py
~~~~~
~~~~~python.old
class EventBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
_default_store = MessageStore(locale="en")
bus = EventBus(store=_default_store)
~~~~~
~~~~~python.new
class FeedbackBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
_default_store = MessageStore(locale="en")
bus = FeedbackBus(store=_default_store)
~~~~~

说明：修改 `__init__.py`，导出新的 `FeedbackBus` 名称。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/messaging/__init__.py
~~~~~
~~~~~python.old
from .bus import bus, EventBus, MessageStore
from . import protocols

__all__ = ["bus", "EventBus", "MessageStore", "protocols"]
~~~~~
~~~~~python.new
from .bus import bus, FeedbackBus, MessageStore
from . import protocols

__all__ = ["bus", "FeedbackBus", "MessageStore", "protocols"]
~~~~~

#### Acts 2: 更新单元测试

接下来，我将更新相关的单元测试，确保其与新的类名保持一致。

说明：修改 `test_messaging.py`，使用新的 `FeedbackBus` 类。

~~~~~act
patch_file
packages/cascade-common/tests/unit/test_messaging.py
~~~~~
~~~~~python.old
from cascade.common.messaging import MessageStore, EventBus


def test_message_store_loads_defaults():
    store = MessageStore(locale="en")
    # We expect some basic keys to be present from runtime_events.json
    # We don't check exact values to avoid brittleness, just key existence/format
    msg = store.get("run.started", target_tasks=["t1"])
    assert "t1" in msg


def test_message_bus_renderer_delegation():
    store = MessageStore()
    store._messages["test.msg"] = "Value: {val}"
    bus = EventBus(store)

    received = []

    class MockRenderer:
        def render(self, msg_id, level, **kwargs):
            received.append((msg_id, level, kwargs))

    bus.set_renderer(MockRenderer())

    bus.info("test.msg", val=42)

    assert len(received) == 1
    assert received[0][0] == "test.msg"
    assert received[0][1] == "info"
    assert received[0][2]["val"] == 42
~~~~~
~~~~~python.new
from cascade.common.messaging import MessageStore, FeedbackBus


def test_message_store_loads_defaults():
    store = MessageStore(locale="en")
    # We expect some basic keys to be present from runtime_events.json
    # We don't check exact values to avoid brittleness, just key existence/format
    msg = store.get("run.started", target_tasks=["t1"])
    assert "t1" in msg


def test_message_bus_renderer_delegation():
    store = MessageStore()
    store._messages["test.msg"] = "Value: {val}"
    bus = FeedbackBus(store)

    received = []

    class MockRenderer:
        def render(self, msg_id, level, **kwargs):
            received.append((msg_id, level, kwargs))

    bus.set_renderer(MockRenderer())

    bus.info("test.msg", val=42)

    assert len(received) == 1
    assert received[0][0] == "test.msg"
    assert received[0][1] == "info"
    assert received[0][2]["val"] == 42
~~~~~

### 下一步建议

代码修改已完成。下一步是运行 `cascade-common` 包的测试套件，以验证我们的重命名没有引入任何回归问题。

如果测试通过，我建议生成一个 `[COMMIT]` 计划，将这些修改作为一个原子提交存入版本控制。
