船长，我明白了。现象虽然看似“卡住”，但实际上是因为我们触碰到了 `Engine` 和 `Connector` 生命周期管理的边界情况。

**问题核心：生命周期冲突**

在当前的实现中，我们创建了一个 `Engine` 实例，并发运行 50 个工作流。
1.  **共享实例的隐患**: `Engine` 并非设计为完全无状态的重入式运行器。虽然它大体上是，但 `run()` 方法中包含了一些针对**单次运行**的生命周期管理逻辑（如 `connector.connect()` 和 `disconnect()`）。
2.  **资源竞争**: 当 50 个工作流共享同一个 `Engine` 实例时，它们都在同一个 `_resource_providers` 字典中注册 `_internal_connector`。虽然这在 Python 中勉强能行，但很“脏”。
3.  **致命的 Disconnect**: 最严重的问题是，如果有**任何一个** Agent 的工作流因为某种原因（甚至是正常的结束逻辑）触发了 `Engine.run` 的 `finally` 块，它就会调用 `await self.connector.disconnect()`。
    *   `LocalBusConnector.disconnect()` 会将 `_is_connected` 设为 `False` 并**取消所有监听任务**。
    *   这意味着：**只要有一个 Agent 退出（或重启），它就会切断所有其他 49 个 Agent 的通信线路。** 剩下的 Agent 变成了“聋子”和“哑巴”，实验自然就看起来像卡住了。

**解决方案：去中心化的引擎，中心化的总线**

我们需要改变编排方式：
1.  **总线独立**: 实验脚本 (`run_fireflies.py`) 负责 `connector` 的 `connect` 和 `disconnect`，而不是委托给 Engine。
2.  **引擎隔离**: 为**每一个** Agent 创建一个独立的 `Engine` 实例。这听起来很重，但实际上 `Engine` 对象很轻量。这样每个 Agent 都有自己独立的资源注册表和生命周期，互不干扰。
3.  **手动注入**: 我们手动将共享的 `connector` 注册到每个 Engine 中，而不通过 Engine 构造函数的自动管理机制。

这样，Agent 们就像连接到同一个 Wi-Fi 热点的 50 台独立笔记本电脑，而不是 50 个用户试图同时操作同一台电脑。

## [WIP] fix: 隔离 Agent 引擎实例以解决生命周期冲突

### 错误分析
当前实验脚本让所有 Agent 共享同一个 `Engine` 实例。`Engine.run` 方法在退出时会自动断开 Connector。由于并发竞争，任何一个 Agent 的重启或退出都可能导致 Connector 被关闭，从而切断所有其他 Agent 的通信，导致系统死锁或行为异常。

### 用户需求
修改 `run_fireflies.py`，实现 Connector 生命周期的外部管理，并为每个 Agent 使用独立的 Engine 实例，确保互不干扰。

### 评论
这是一个经典的“资源所有权”问题。在多 Agent 场景下，通信总线是“公共基础设施”，不应由任何单个 Agent（或其 Engine）拥有或管理。通过将 Connector 的控制权提升到实验脚本层级，并将 Engine 降级为单纯的执行容器，我们构建了一个更符合分布式系统语义的拓扑结构。

### 目标
1.  修改 `run_fireflies.py`。
2.  在 `run_experiment` 中显式调用 `connector.connect()`。
3.  在循环中，为每个 Agent 实例化一个新的 `cs.Engine`，构造时传入 `connector=None`（防止自动管理）。
4.  使用 `eng.register` 手动将共享的 `connector` 注入为 `_internal_connector` 资源。
5.  在 `finally` 块中显式调用 `connector.disconnect()`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构实验脚本以隔离引擎实例

我们将重写 `run_fireflies.py`，实施上述的架构变更。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor


async def run_experiment(
    num_agents: int = 50,
    period: float = 10.0,
    nudge: float = 0.5,
    duration_seconds: float = 60.0,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents for {duration_seconds}s...")

    # 1. Initialize the Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    
    # CRITICAL: We manage the connector lifecycle at the experiment level,
    # NOT at the individual engine level. This prevents one agent's engine
    # from disconnecting the bus and killing everyone else.
    await connector.connect()

    # --- Setup Monitor ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run())

    # --- Create the population of firefly agents ---
    agent_tasks = []
    
    # Define a resource provider that yields our shared connector
    # We must define it here to capture the 'connector' variable
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    for i in range(num_agents):
        # Each firefly starts with a random phase in its cycle
        initial_phase = random.uniform(0, period)
        
        # 2. ISOLATION: Create a dedicated Engine for each agent.
        # We pass connector=None so the engine doesn't try to manage it.
        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None, 
        )
        
        # 3. INJECTION: Manually register the shared connector
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
        )
        
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        print(f"\n⏳ Running agents and monitor for {duration_seconds} seconds...")
        start_time = time.time()
        await asyncio.wait_for(all_tasks, timeout=duration_seconds)
    except asyncio.TimeoutError:
        end_time = time.time()
        print(f"\n✅ Experiment finished after {end_time - start_time:.2f}s.")
    finally:
        # Gracefully stop everything
        monitor.stop()
        if not all_tasks.done():
            all_tasks.cancel()
            await asyncio.gather(all_tasks, monitor_task, return_exceptions=True)
        else:
             await asyncio.gather(monitor_task, return_exceptions=True)
        
        # CRITICAL: Only disconnect after everyone is done
        await connector.disconnect()


if __name__ == "__main__":
    # To run the experiment, execute this script from the project root:
    # python -m observatory.experiments.run_fireflies
    asyncio.run(run_experiment())
~~~~~

### 下一步建议
这次架构调整彻底消除了“单点故障导致全局断网”的风险。每个 Agent 都有自己的执行容器，但共享同一个通信通道。

请再次运行实验。这一次，你应该能看到：
1.  实验稳定运行。
2.  日志不再仅仅是 `Monitor Started`，而是会有 `Received flash`。
3.  最重要的是，你之前看到的 `0.0000` 应该会随着时间推移而**增加**。

运行命令：
`python -m observatory.experiments.run_fireflies`

如果仍然不动，那我们就得检查是不是参数（`nudge` 或 `period`）设置得太保守，导致同步太慢，但这属于科学调优范畴，而非工程故障了。让我们先确保它是活的。
