# [WIP] fix: 修复 cs-observer 的 Payload 解析逻辑

## 摘要

本计划修复了 `cs-observer` 中导致无法显示遥测数据的根本原因：JSON Payload 的结构解析错误。

## 错误分析

### 1. 协议不匹配 (Schema Mismatch)
*   **Publisher 端 (`TelemetrySubscriber`)**: 发送的 JSON 是扁平结构的，`run_id` 等头信息直接位于根对象中，`body` 也是根对象的一个字段。
    ```json
    { "v": "1.0", "run_id": "...", "body": { ... } }
    ```
*   **Subscriber 端 (`cs-observer`)**: 错误地假设存在一个嵌套的 `header` 对象。
    ```python
    header = payload.get("header", {})
    run_id = header.get("run_id")  # 永远为 None
    ```
*   **结果**: 由于 `run_id` 提取失败，`on_message` 函数在早期直接返回（`if not run_id ... return`），导致后续的日志打印逻辑从未执行。

## 用户需求
1.  `cs-observer` 能够正确解析并显示遥测数据。

## 目标
1.  修改 `cs-observer` 的 `on_message` 函数，使其适配实际的扁平化 JSON 协议。
2.  （可选）清理之前添加的调试日志配置，使其更适合生产环境使用。

## 标签
#intent/fix #flow/ready #priority/high #comp/cli #scope/core #ai/instruct #task/domain/telemetry #task/object/observer #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 `cs-observer` 解析逻辑

修改 `app.py`，直接从 `payload` 根对象读取 `run_id`。同时清理掉硬编码的 `logging.basicConfig`（或者将其改为基于 CLI 参数控制，简单起见先恢复原状，或者保留一个更合理的默认值）。为了保持 CLI 的干净，我将移除硬编码的 DEBUG 配置，因为 `RichCliRenderer` 会负责漂亮的输出。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
async def on_message(topic: str, payload: dict):
    """Callback to process incoming telemetry messages."""
    global seen_run_ids

    header = payload.get("header", {})
    body = payload.get("body", {})
    run_id = header.get("run_id")

    if not run_id or not body:
        return
~~~~~
~~~~~python
async def on_message(topic: str, payload: dict):
    """Callback to process incoming telemetry messages."""
    global seen_run_ids

    # The payload structure is flat for headers, with a nested 'body'
    body = payload.get("body", {})
    run_id = payload.get("run_id")

    if not run_id or not body:
        return
~~~~~

#### Acts 2: 清理调试日志配置

恢复 `main` 函数，移除硬编码的 logging 配置。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
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
~~~~~
~~~~~python
def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()
~~~~~

#### Acts 3: 清理 Connector 中的调试探针

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
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

### 下一步建议
这应该是最后一个障碍了。
1.  运行 `python workflow_demo.py`。
2.  运行 `cs-observer watch`。
3.  你应该能看到格式化好的、漂亮的实时日志。

如果验证通过，请执行 `git add .` 和 `git commit`。
