是的，船长，你敏锐地察觉到了。`LocalBusConnector` 的当前实现中确实存在两处违背 **[设计原则：解耦消息总线 (01KCR9TXZ966TQDKWP1W50ENPP)]** 的情况。

 违规分析

在 `LocalBusConnector` 中，我们使用了硬编码的 `print` 语句来处理错误反馈：

1.  **在 `subscribe` 中**:
    ```python
    print(f"[LocalBus] Retained Callback error on {retained_topic}: {e}")
    ```
2.  **在 `_listener_loop` 中**:
    ```python
    print(f"[LocalBus] Callback error on {topic}: {e}")
    ```

**这违反了原则，原因如下：**
*   **硬编码字符串**：它直接向 `stderr/stdout` 输出面向人类的文本，而不是使用语义 ID。
*   **不可定制性**：如果用户使用了 `log_format="json"`，这两行 `print` 会破坏 JSON 输出流，导致日志解析器失效。
*   **绕过了渲染器**：它直接绕过了我们在 `cs.run` 中注入的 `Renderer`（如 `RichCliRenderer` 或 `JsonRenderer`），使得这些低层错误无法被统一管理、过滤或着色。

 修复方案

我们需要按照“解耦消息总线”原则进行重构。

## [WIP] fix(runtime): Decouple LocalBus error messages using semantic IDs

### 用户需求
将 `LocalBusConnector` 中的低层错误输出与 UI 逻辑分离，确保其符合系统的消息总线协议。

### 目标
1.  在 `cascade-common` 的语言包中增加 `localbus` 相关的语义 ID。
2.  在 `LocalBusConnector` 中引入全局 `bus` 实例，并使用 `bus.error()` 替代 `print`。

### 标签
#intent/fix #flow/ready #priority/medium 
#comp/runtime #comp/common #concept/ui #scope/dx
#task/domain/telemetry #task/object/local-bus #task/action/refactor

---

### Script

#### Acts 1: 定义语义 ID

我们需要在 `cascade-common` 中为本地总线定义错误模板。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
~~~~~
~~~~~json
    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector."
}
~~~~~
~~~~~json
    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector.",

    "localbus.callback_error": "[LocalBus] Callback error on topic '{topic}': {error}",
    "localbus.retained_callback_error": "[LocalBus] Sync/Retained callback error on topic '{topic}': {error}"
}
~~~~~

#### Acts 2: 在实现中应用消息总线

修改 `LocalBusConnector` 以使用 `bus` 单例。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable, Optional
from cascade.interfaces.protocols import Connector


class LocalBusConnector(Connector):
~~~~~
~~~~~python
import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable, Optional
from cascade.interfaces.protocols import Connector
from cascade.common.messaging import bus


class LocalBusConnector(Connector):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        print(f"[LocalBus] Retained Callback error on {retained_topic}: {e}")

        # Start a background listener for NEW incoming messages
~~~~~
~~~~~python
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error("localbus.retained_callback_error", topic=retained_topic, error=e)

        # Start a background listener for NEW incoming messages
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
                topic, payload = await queue.get()
                try:
                    await callback(topic, payload)
                except Exception as e:
                    # Fail-silent: don't crash the bus because a callback failed
                    print(f"[LocalBus] Callback error on {topic}: {e}")
                finally:
                    queue.task_done()
~~~~~
~~~~~python
                topic, payload = await queue.get()
                try:
                    await callback(topic, payload)
                except Exception as e:
                    # Fail-silent: don't crash the bus because a callback failed
                    bus.error("localbus.callback_error", topic=topic, error=e)
                finally:
                    queue.task_done()
~~~~~

### 下一步建议
通过这次修复，我们不仅消除了技术债务，还使得 `LocalBusConnector` 的错误在 JSON 日志模式下也是结构化的、可被监测的。

接下来，我们将进入核心挑战：**里程碑 1.2 —— 实现尾递归优化 (TCO) 改造引擎。** 

这涉及到对 `Engine.run` 的重大修改，我们需要在不改变现有 DAG 模型的前提下，让它能处理任务返回的“动态子流”。准备好开始了吗？
