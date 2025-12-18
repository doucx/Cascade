# [WIP] fix: 启用 Observer 日志并增加连接器调试探针

## 摘要

本计划旨在解决 `cs-observer` 无响应且无错误信息的“黑盒”状态。我们将通过两步措施来定位并修复问题：
1.  **启用 Logging**: 在 `cs-observer` 入口处配置标准 `logging`，确保底层库（如 `aiomqtt` 和 `connector`）的错误信息能输出到终端。
2.  **增加调试探针**: 在 `MqttConnector` 的消息循环中增加临时的、高可见度的调试输出，以确定消息链路断裂的具体位置（是没收到消息，还是匹配失败，还是回调出错）。

## 错误分析

### 1. 错误被吞没 (Silent Failure)
*   **现象**: `cs-observer` 无反应，且终端无报错。
*   **原因**: `MqttConnector` 使用 Python 标准 `logging` 记录错误，但 `cs-observer` 应用未配置 `logging.basicConfig`。默认情况下，`logging` 只输出 `WARNING` 级别以上，且格式可能不明显。更重要的是，如果 `aiomqtt` 内部有异常，也通过 logging 报告。
*   **解决方案**: 在 `cs-observer` 的 `app.py` 中显式配置 Logging。

### 2. 消息链路不透明
*   **现象**: 无法确定问题出在 Broker -> Client 的传输层，还是 Client 内部的分发层。
*   **解决方案**: 在 `MqttConnector` 的 `_message_loop` 中添加详细的调试日志，打印收到的每一个 Topic。

## 用户需求
1.  看到 `cs-observer` 的内部运行状态，以便排错。
2.  最终修复无数据的问题。

## 评论
在分布式系统的调试中，可观测性是第一位的。当前的“静默失败”是不可接受的。

## 目标
1.  配置 `cs-observer` 的日志系统。
2.  在 `MqttConnector` 中添加必要的调试信息。

## 基本原理
通过 `logging.basicConfig` 将所有模块的日志导向 stderr，这是 CLI 工具的标准做法。

## 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/connector #scope/debug #ai/instruct #task/domain/telemetry #task/object/observer #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在 `cs-observer` 中配置 Logging

我们将修改 `app.py`，在 `main` 函数开头配置 logging。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import time
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.table import Table

from cascade.common.messaging import bus
~~~~~
~~~~~python
import asyncio
import time
import logging
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.table import Table

from cascade.common.messaging import bus
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
~~~~~
~~~~~python
def main():
    # Configure logging to capture output from aiomqtt and our connector
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress overly verbose logs from some libraries if needed
    logging.getLogger("aiomqtt").setLevel(logging.WARNING)
    
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
~~~~~

#### Acts 2: 在 `MqttConnector` 中增加调试日志

我们将修改 `connector.py`，在收到消息时打印 debug 日志，并报告匹配结果。

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                # Dispatch to all matching subscriptions
                # We iterate over all subscriptions because a single message 
                # might match multiple patterns (e.g. "a/b" matches "a/+" and "#")
                matched_callbacks = []
                for sub_pattern, cb in self._subscriptions.items():
                    if self._topic_matches(sub_pattern, topic):
                        matched_callbacks.append(cb)
                
                if not matched_callbacks:
                    continue

                # Decode payload once
~~~~~
~~~~~python
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                logger.debug(f"Received message on topic: {topic}")

                # Dispatch to all matching subscriptions
                # We iterate over all subscriptions because a single message 
                # might match multiple patterns (e.g. "a/b" matches "a/+" and "#")
                matched_callbacks = []
                for sub_pattern, cb in self._subscriptions.items():
                    if self._topic_matches(sub_pattern, topic):
                        matched_callbacks.append(cb)
                    else:
                        logger.debug(f"Topic '{topic}' did not match subscription '{sub_pattern}'")
                
                if not matched_callbacks:
                    logger.debug(f"No matching subscriptions found for topic: {topic}")
                    continue

                logger.debug(f"Found {len(matched_callbacks)} callbacks for topic: {topic}")

                # Decode payload once
~~~~~

### 下一步建议
请再次运行 `cs-observer watch`。
1.  现在你应该能看到详细的日志输出。
2.  当 `workflow_demo.py` 运行时，观察 `cs-observer` 的输出。
    *   如果你看到 `Received message on topic: ...`，说明接收正常。
    *   如果你接着看到 `No matching subscriptions found...`，说明 `_topic_matches` 逻辑有误。
    *   如果你什么都没看到，说明 `aiomqtt` 没有收到消息（网络问题或 Broker 问题）。
    *   如果你看到 `Found X callbacks` 但依然没反应，说明 `callback` 内部出错了（虽然那也会被 log catch 住）。

根据新的日志信息，我们可以精准修复。
