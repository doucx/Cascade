# [WIP] fix: 为 MQTT 连接器添加硬编码调试输出

## 摘要

由于 `logging` 系统在 `cs-observer` 环境下依然失效（原因不明，可能是库冲突或配置未生效），我们无法通过常规日志定位 `MqttConnector` 接收不到消息的原因。本计划将在 `MqttConnector` 的关键路径上添加**硬编码的 `print` 语句（输出到 stderr）**。

这是一种临时的、激进的调试手段，旨在穿透所有可能的日志屏蔽层，直接暴露：
1.  后台消息循环是否成功启动。
2.  后台循环是否因未捕获的异常而悄无声息地崩溃。
3.  消息是否到达了客户端但被过滤逻辑丢弃。

## 错误分析

### 1. 幽灵般的静默
*   **现象**: `cs-observer` 显示已连接，但之后无任何输出。
*   **推测**: `MqttConnector` 内部启动的 `_message_loop` 异步任务可能在启动后立即崩溃了（例如由于 API 不兼容或属性错误），或者 `aiomqtt` 的消息生成器被阻塞。由于该 Task 是后台运行且未被 `await`，其异常被 `asyncio` 吞没（或仅在垃圾回收时打印），导致主程序无感知的“假死”。

## 用户需求
1.  **必须**看到 `MqttConnector` 内部到底发生了什么。

## 目标
1.  在 `MqttConnector` 的 `connect`、`subscribe` 和 `_message_loop` 中插入 `sys.stderr.write`。
2.  捕获并打印 `_message_loop` 中的所有异常。

## 基本原理
`sys.stderr.write` 是最底层的输出方式，不受 logging level、formatter 或第三方库（如 `rich`）的控制配置影响。

## 标签
#intent/fix #flow/ready #priority/high #comp/connector #scope/debug #ai/instruct #task/domain/telemetry #task/object/connector #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在 `MqttConnector` 中注入硬编码调试

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
import asyncio
import json
import logging
import platform
import os
from typing import Callable, Awaitable, Dict, Any

try:
    import aiomqtt
except ImportError:
    aiomqtt = None
~~~~~
~~~~~python
import asyncio
import json
import logging
import platform
import os
import sys
from typing import Callable, Awaitable, Dict, Any

try:
    import aiomqtt
except ImportError:
    aiomqtt = None
~~~~~

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())

    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
~~~~~
~~~~~python
        # Start the message processing loop
        sys.stderr.write("[DEBUG] Starting message loop task...\n")
        self._loop_task = asyncio.create_task(self._message_loop())

    async def disconnect(self) -> None:
        """Disconnects from the MQTT Broker and cleans up resources."""
~~~~~

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
    async def _message_loop(self):
        """Background task to process incoming MQTT messages."""
        if not self._client:
            return

        try:
            # Iterate over the messages asynchronous generator provided by aiomqtt
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                logger.debug(f"Received message on topic: {topic}")

                # Dispatch to all matching subscriptions
~~~~~
~~~~~python
    async def _message_loop(self):
        """Background task to process incoming MQTT messages."""
        sys.stderr.write("[DEBUG] Message loop started.\n")
        if not self._client:
            sys.stderr.write("[DEBUG] No client in message loop!\n")
            return

        try:
            # Iterate over the messages asynchronous generator provided by aiomqtt
            sys.stderr.write("[DEBUG] Entering aiomqtt messages iterator...\n")
            async for message in self._client.messages:
                topic = str(message.topic)
                payload_bytes = message.payload

                sys.stderr.write(f"[DEBUG] RAW MSG: {topic}\n")
                logger.debug(f"Received message on topic: {topic}")

                # Dispatch to all matching subscriptions
~~~~~

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
                except Exception as e:
                    logger.error(f"Error processing message on topic '{topic}': {e}")

        except asyncio.CancelledError:
            # Normal shutdown
            pass
        except Exception as e:
            # Unexpected error in loop, log it.
            # In a robust system we might want to restart the loop.
            logger.error(f"MQTT message loop crashed: {e}")
~~~~~
~~~~~python
                except Exception as e:
                    sys.stderr.write(f"[DEBUG] Error processing message: {e}\n")
                    logger.error(f"Error processing message on topic '{topic}': {e}")

        except asyncio.CancelledError:
            sys.stderr.write("[DEBUG] Message loop cancelled.\n")
            pass
        except Exception as e:
            # Unexpected error in loop, log it.
            sys.stderr.write(f"[DEBUG] MQTT message loop CRASHED: {type(e).__name__}: {e}\n")
            import traceback
            traceback.print_exc()
            logger.error(f"MQTT message loop crashed: {e}")
~~~~~

### 下一步建议
请再次运行 `cs-observer watch`。
这次，如果后台循环崩溃了，或者根本没进入，你应该能在控制台看到 `[DEBUG] ...` 开头的输出。这将直接告诉我们要么是 `aiomqtt` 的用法有问题，要么是其他诡异的原因。
