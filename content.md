## [WIP] fix: 使用 asyncio.Event 修复 UDS 客户端 E2E 测试中的竞态条件

### 错误分析
`ENGINE_STOPPED` 事件在 Engine 清理连接之前未能被 UDS 客户端及时读取，导致测试因竞态条件失败。

### 用户需求
修复 `test_e2e_watch_local_uds_e2e` 中 `ENGINE_STOPPED` 消息丢失的问题。

### 评论
新的测试逻辑将更加健壮，不再依赖于模糊的 `asyncio.sleep` 时间，而是依赖于明确的消息传递信号，这完全符合我们的异步测试原则。

### 目标
1.  在测试函数中引入 `asyncio.Event`。
2.  修改 `mocked_on_message`，使其在接收到 `ENGINE_STOPPED` 时设置该 Event。
3.  修改主测试流程，使其等待此 Event。

### 基本原理
通过在测试中实现精确的同步，我们消除了对事件循环调度时机的依赖，确保了 `ENGINE_STOPPED` 消息在断言发生前被可靠地捕获。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/testing #task/object/watch-local-backend #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 用同步机制重写 E2E 测试函数

我们将用一个完全同步的、基于 `asyncio.Event` 的新版本替换整个测试函数。

~~~~~act
write_file
tests/cli/e2e/test_e2e_watch_local_backend.py
~~~~~
~~~~~python
import asyncio
import json
import sys
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.connectors.local import LocalConnector
from cascade.runtime.subscribers import TelemetrySubscriber

# We import the internal logic from observer to test real-world behavior
from cascade.cli.observer.app import on_message


@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not supported on Windows")
@pytest.mark.asyncio
async def test_watch_local_uds_e2e(tmp_path, monkeypatch):
    """
    End-to-end test for the local UDS telemetry loop, using explicit synchronization.
    Engine -> LocalConnector -> UDS Server -> UDS Client -> on_message
    """
    db_path = tmp_path / "control.db"
    uds_path = str(tmp_path / "telemetry.sock")

    # Synchronization primitive
    run_finished_event = asyncio.Event()

    # 1. Setup Captured Events list
    received_events = []

    async def mocked_on_message(topic, payload):
        # Flatten the events for easy assertion
        body = payload.get("body", {})
        if body.get("type") == "LifecycleEvent":
            event = body.get("event")
            received_events.append(event)
            if event == "ENGINE_STOPPED":
                run_finished_event.set()  # Signal that the final event was received
        elif body.get("type") == "TaskStateEvent":
            received_events.append(f"{body.get('task_name')}:{body.get('state')}")

    # Use monkeypatch to redirect observer's on_message to our collector
    # Note: We must patch the imported function where it is defined, but use the mock to control data capture.
    monkeypatch.setattr("cascade.cli.observer.app.on_message", mocked_on_message)

    # 2. Configure Engine with LocalConnector
    event_bus = MessageBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)
    TelemetrySubscriber(event_bus, connector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )

    # 3. Define a simple workflow
    @cs.task
    def hello():
        return "world"

    # 4. Start UDS Client (Watcher) in background
    async def run_client():
        attempts = 0
        while attempts < 5:
            try:
                # Client attempts to connect
                reader, writer = await asyncio.open_unix_connection(uds_path)
                
                # Main read loop: blocks until data or EOF
                while True:
                    line = await reader.readline()
                    if not line:
                        break  # Server closed connection
                    try:
                        data = json.loads(line)
                        await mocked_on_message("uds", data)
                    except json.JSONDecodeError:
                        continue
                
                writer.close()
                await writer.wait_closed()
                break  # Exit the retry loop after connection closes

            except (ConnectionRefusedError, FileNotFoundError):
                await asyncio.sleep(0.1)
                attempts += 1
            except asyncio.CancelledError:
                break
        
    client_task = asyncio.create_task(run_client())

    # 5. Run Engine (start execution)
    engine_run_task = asyncio.create_task(engine.run(hello()))

    # 6. Synchronize: Wait for the final ENGINE_STOPPED message to be processed.
    try:
        await asyncio.wait_for(run_finished_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        # If timeout, it means the message was lost or the client task failed early.
        pytest.fail(
            f"Timed out waiting for ENGINE_STOPPED event ({5.0}s). Received: {received_events}"
        )

    # 7. Final Assertions
    # Ensure the engine task itself finished cleanly (should be very fast after unblocking)
    await asyncio.wait_for(engine_run_task, timeout=1.0)

    # Clean up client task if it hasn't exited already due to server shutdown
    if not client_task.done():
        client_task.cancel()

    assert "ENGINE_STARTED" in received_events
    assert "hello:RUNNING" in received_events
    assert "hello:COMPLETED" in received_events
    assert "ENGINE_STOPPED" in received_events
~~~~~

### 下一步建议
我们已经完成了对 UDS 客户端和服务器端死锁与竞态条件的所有修复。我建议再次运行测试以确认整个本地可观测性功能（从 `Engine` 到 `Observer`）现在已完全稳定。

如果测试通过，我们将进入最后的 `[COMMIT]` 阶段。
