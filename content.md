经过对 `rg` 搜索结果的深度审计，我发现除了代码实现层面的重命名外，还有大量的**元数据（Stitcher 文件）**、**文档字符串（Docstrings）**以及 **SDK 导出**仍然保留了过时的 `MessageBus` 称呼，或者将系统级的 `EventBus` 与用户级的 `FeedbackBus` 混淆了。

为了确保架构的一致性和“代码即文档”的原则，我们需要进行一次彻底的清理。

## [WIP] refactor: 全面清理总线命名术语并更新 SDK 导出

### 错误分析

1.  **Stitcher 元数据过期**: `cascade-engine` 和 `cascade-sdk` 中的 `.stitcher.yaml` 文件仍然使用 `MessageBus` 来描述当前的 `EventBus` 或 `FeedbackBus`。
2.  **Docstrings 误导**: `conftest.py` 和 `testing.py` 中的文档字符串将运行时事件总线称为 `MessageBus`。
3.  **SDK 导出缺失**: `cascade-sdk` 目前只导出了 `EventBus`（运行时），没有导出 `FeedbackBus`（用户反馈），导致用户无法在类型标注中使用。
4.  **术语不一致**: `subscribers.py` 的描述中，对于 `TelemetrySubscriber`（处理系统事件）和 `HumanReadableLogSubscriber`（处理用户反馈）的总线归属描述模糊。

### 用户需求

清理所有残留的 `MessageBus` 术语，并将文档、元数据、SDK 导出与最新的 `EventBus` (System) / `FeedbackBus` (UI) 架构对齐。

### 目标

1.  更新 `cascade-engine` 和 `cascade-sdk` 中的所有 Stitcher 文件。
2.  修正 `conftest.py` 和测试工具类中的文档字符串。
3.  在 `cascade-sdk` 的 `sdk.py` 中增加 `FeedbackBus` 的导出。
4.  修正 `TelemetrySubscriber` 相关的物理术语（它连接的是 `EventBus`）。

### 基本原理

由于这次修改涉及多个包的非执行代码（注释、元数据、导出），我将分模块执行 `patch_file`。这种重构虽然不改变运行逻辑，但对于维护代码库的长期健康度和 AI 的上下文理解能力至关重要。

### 标签

#intent/refine #flow/ready #priority/medium #comp/engine #comp/sdk #concept/ui #scope/dx #ai/instruct #task/domain/core #task/object/bus-naming-cleanup #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新 SDK 导出与测试工具描述

首先，让 SDK 正确识别这两个总线。

说明：在 `cascade-sdk` 中导出 `FeedbackBus` 并修正测试工具的描述。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    # Runtime
    "Engine": ("cascade.runtime.engine", "Engine"),
    "EventBus": ("cascade.runtime.event_bus", "EventBus"),
    "Event": ("cascade.runtime.events", "Event"),
~~~~~
~~~~~python.new
    # Runtime
    "Engine": ("cascade.runtime.engine", "Engine"),
    "EventBus": ("cascade.runtime.event_bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.events", "Event"),
~~~~~

说明：更新 SDK 测试工具的 Stitcher 元数据。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.stitcher.yaml
~~~~~
~~~~~old
"SpySubscriber": |-
  A test utility to collect events from a MessageBus.
~~~~~
~~~~~new
"SpySubscriber": |-
  A test utility to collect events from an EventBus.
~~~~~

#### Acts 2: 修正运行时引擎的元数据与注释

~~~~~act
patch_file
tests/e2e/runtime/conftest.py
~~~~~
~~~~~python.old
@pytest.fixture
def bus_and_spy():
    """Provides an EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
~~~~~
~~~~~python.new
@pytest.fixture
def bus_and_spy():
    """Provides a runtime EventBus instance and an attached SpySubscriber."""
    bus = EventBus()
~~~~~

说明：修正 `HumanReadableLogSubscriber` 的 Stitcher 描述，明确它连接的是 `FeedbackBus`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.stitcher.yaml
~~~~~
~~~~~old
"HumanReadableLogSubscriber": |-
  Listens to runtime events and translates them into semantic messages
  on the messaging bus. It acts as a bridge between the event domain
  and the user-facing message domain.
"TelemetrySubscriber": |-
  Listens to runtime events and publishes them as structured telemetry
  data via a Connector.
"TelemetrySubscriber.on_event": |-
  Handles incoming events synchronously and schedules asynchronous publishing.
  This bridges the synchronous MessageBus with the asynchronous Connector.
~~~~~
~~~~~new
"HumanReadableLogSubscriber": |-
  Listens to system events from the EventBus and translates them into
  semantic messages on the FeedbackBus. It acts as a bridge between
  the system event domain and the user-facing feedback domain.
"TelemetrySubscriber": |-
  Listens to runtime events from the EventBus and publishes them as
  structured telemetry data via a Connector.
"TelemetrySubscriber.on_event": |-
  Handles incoming events synchronously and schedules asynchronous publishing.
  This bridges the synchronous EventBus with the asynchronous Connector.
~~~~~

#### Acts 3: 修正测试元数据中的链路描述

说明：修正 `test_bus.py` 的元数据，清晰描述消息流向。

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_bus.stitcher.yaml
~~~~~
~~~~~old
"test_human_readable_subscriber_integration": |-
  Integration test for the full logging pipeline:
  EventBus -> Subscriber -> MessageBus(UI) -> Renderer -> Output
"test_human_readable_subscriber_log_level_filtering": |-
  Tests that the min_level setting in the CliRenderer correctly filters messages.
"test_message_bus_dispatch": |-
  Tests that the bus correctly dispatches events to specifically subscribed handlers.
"test_message_bus_wildcard": |-
  Tests that a wildcard subscriber (listening to base Event) receives all events.
~~~~~
~~~~~new
"test_human_readable_subscriber_integration": |-
  Integration test for the full logging pipeline:
  EventBus -> Subscriber -> FeedbackBus (UI) -> Renderer -> Output
"test_human_readable_subscriber_log_level_filtering": |-
  Tests that the min_level setting in the CliRenderer correctly filters messages.
"test_message_bus_dispatch": |-
  Tests that the EventBus correctly dispatches events to specifically subscribed handlers.
"test_message_bus_wildcard": |-
  Tests that a wildcard subscriber (listening to base Event) receives all events from the EventBus.
~~~~~

### 下一步建议

1.  **运行 E2E 测试**: 重点运行 `tests/e2e/integration/test_end_to_end.py`，确保 Mock 逻辑在重命名后依然能够正确拦截 `FeedbackBus` 的调用。
2.  **文档全文扫描**: 建议后续对 `docs/` 目录下的 Markdown 文档进行术语统一，确保向外展示的术语也是 `EventBus` 和 `FeedbackBus`。
3.  **完成提交**: 如果测试通过，我将生成 `[COMMIT]` 计划。
