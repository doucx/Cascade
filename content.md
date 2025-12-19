船长，你的决定非常明智。在复杂的分布式系统中，当集成测试出现“静默死锁”时，盲目试错极其低效。我们需要**隔离变量**。

我们将采用**“洋葱剥皮法”**，由内而外逐层验证。我们将创建两个独立的调试脚本，分别验证“通信基础设施”和“个体行为”。

## [WIP] feat: 创建调试脚本以隔离定位死锁问题

### 用户需求
创建独立的测试文件，用于分层验证系统组件，定位实验卡死的原因。

### 评论
当前实验涉及：50个并发引擎、共享总线、递归工作流、异步IO。任何一个环节出问题都会导致死锁。我们将复杂度降维：
1.  **验证总线 (`debug_01_bus.py`)**: 排除 `Engine` 和 `Agent`，仅验证 `LocalBusConnector` 在 `asyncio` 环境下是否能正常收发消息。如果这一层挂了，那就是基础设施问题。
2.  **验证个体 (`debug_02_single_agent.py`)**: 引入 `Engine`，但只运行**一只**萤火虫。验证 `safe_recv` 的超时机制和递归逻辑是否能正常工作。如果一只萤火虫都不能闪烁，那一群肯定不行。

### 目标
1.  创建 `observatory/debug/debug_01_bus.py`。
2.  创建 `observatory/debug/debug_02_single_agent.py`。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/observatory #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 创建调试目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p observatory/debug
~~~~~

#### Acts 2: 调试脚本 1 - 纯总线验证

这个脚本不依赖 Cascade 的 Engine，仅测试 `LocalBusConnector` 和 Python 的 `asyncio`。目的是验证我们的“物理定律”是否正常。

~~~~~act
write_file
observatory/debug/debug_01_bus.py
~~~~~
~~~~~python
import asyncio
from cascade.connectors.local import LocalBusConnector

async def main():
    print("--- Debug 01: Raw Bus Test ---")
    
    # 1. Setup
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()
    print("[1] Connector connected.")

    # 2. Define a subscriber
    received = asyncio.Event()
    
    async def on_message(topic, payload):
        print(f"[3] Received message on {topic}: {payload}")
        received.set()

    # 3. Subscribe
    await connector.subscribe("test/topic", on_message)
    print("[2] Subscribed.")

    # 4. Publish (Simulate a firefly flash)
    print("[4] Publishing...")
    await connector.publish("test/topic", {"msg": "hello"})

    # 5. Wait for receipt
    try:
        await asyncio.wait_for(received.wait(), timeout=2.0)
        print("[5] SUCCESS: Message received.")
    except asyncio.TimeoutError:
        print("[5] FAILURE: Timed out waiting for message.")
    
    await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
~~~~~

#### Acts 3: 调试脚本 2 - 单体 Agent 验证

这个脚本引入 `Engine` 和 `firefly_agent`，但只运行一个实例。如果这个脚本卡住，说明是 **Engine 调度** 或 **Agent 逻辑** 的问题（例如 `safe_recv` 没有正确超时）。

~~~~~act
write_file
observatory/debug/debug_02_single_agent.py
~~~~~
~~~~~python
import asyncio
import time
import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource
from observatory.agents.kuramoto import firefly_agent

async def main():
    print("--- Debug 02: Single Agent Test ---")
    
    # 1. Setup Environment
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Monitor (Log flashes)
    async def on_flash(topic, payload):
        print(f"   >>> FLASH DETECTED! Payload: {payload}")
    await connector.subscribe("firefly/flash", on_flash)

    # 3. Setup Engine (Isolated mode)
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None,
    )
    engine.register(shared_connector_provider)

    # 4. Create Agent
    # Very short period (1.0s) so we don't wait long
    print("   Creating agent with period=1.0s...")
    agent_wf = firefly_agent(
        agent_id=99,
        initial_phase=0.0,
        period=1.0, 
        nudge=0.1,
        flash_topic="firefly/flash",
        listen_topic="firefly/flash",
    )

    # 5. Run for 3 seconds
    print("   Starting Engine run...")
    task = asyncio.create_task(engine.run(agent_wf))
    
    try:
        start = time.time()
        # It should flash at least twice in 3 seconds
        await asyncio.wait_for(task, timeout=3.0) 
    except asyncio.TimeoutError:
        print("   Runtime finished (Timeout as expected for infinite loop).")
    except Exception as e:
        print(f"   ERROR: {e}")
    finally:
        await connector.disconnect()
        print(f"   Done. Elapsed: {time.time() - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
~~~~~

### 下一步建议
请依次运行这两个脚本。

1.  运行 `python observatory/debug/debug_01_bus.py`
    *   **预期**: 输出 `SUCCESS: Message received.`
    *   **如果不通过**: 说明 `LocalBusConnector` 的锁机制或队列在 `asyncio` 下有问题。

2.  运行 `python observatory/debug/debug_02_single_agent.py`
    *   **预期**: 看到至少两三次 `>>> FLASH DETECTED!`，并在 3 秒后退出。
    *   **如果不通过**:
        *   如果卡住且无 Flash：说明 `safe_recv` 没有超时，或者 `is_timeout` 逻辑判断错误。
        *   如果瞬间退出：说明递归逻辑依然有问题。

这两个测试的结果将直接指向问题的核心。
