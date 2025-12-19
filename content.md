好的，船长。我们已经为单个萤火虫注入了“心智”，现在是时候创造一个世界，让它们在其中繁衍生息，并最终形成一个群体。

这个实验脚本是关键的“创世纪”步骤。它将负责配置宇宙的物理定律（`LocalBusConnector`），然后将我们定义的无数个独立的萤火虫灵魂（`firefly_agent` 工作流）放入其中，并赋予它们生命。

我将为你生成实现这一目标的计划。

## [WIP] feat: 创建萤火虫实验的运行与编排脚本

### 用户需求
创建一个实验脚本 (`run_fireflies.py`)，用于初始化共享环境，批量生成并并发执行多个萤火虫 Agent 工作流。

### 评论
这个脚本是连接“理论”与“实践”的桥梁。它将我们精心设计的、单个 Agent 的递归逻辑，实例化为一个拥有数十上百个个体的“种群”。通过在同一个 `Engine` 实例中共享 `LocalBusConnector`，并使用 `asyncio.gather` 并发运行所有工作流，我们以一种极其优雅且高效的方式，模拟出了一个所有 Agent 都能相互感知的共享环境。这是对 Cascade 并发执行与上下文管理能力的一次完美展示。

### 目标
1.  创建 `observatory/experiments/run_fireflies.py` 文件。
2.  实现一个核心的 `run_experiment` 异步函数，用于管理实验的整个生命周期。
3.  在该函数中，配置一个 `LocalBusConnector` 作为所有 Agent 共享的通信总线。
4.  批量创建多个 `firefly_agent` 工作流实例，每个都拥有随机的初始相位。
5.  使用 `asyncio.gather` 并发启动并运行所有 Agent。
6.  添加一个 `if __name__ == "__main__":` 块，使该实验脚本可以直接从命令行运行。

### 基本原理
为了确保实验的可复现性，必须在一个受控的环境中进行。`run_fireflies.py` 脚本扮演了这个“实验控制器”的角色。它首先通过 `LocalBusConnector._reset_broker_state()` 确保每次运行都是一个干净的开始。然后，它创建一个 `Engine` 实例，并将 `LocalBusConnector` 实例注入其中。所有后续通过这个 `Engine` 实例运行的 `firefly_agent` 工作流，都将隐式地共享这个连接器，从而能够通过同一个内存总线进行通信。`asyncio.gather` 是 Python 中执行大量异步任务的标准模式，它能确保所有萤火虫的“生命周期”是同时开始、并行推进的。

### 标签
#intent/build #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/observatory #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建并实现实验运行脚本

我们将创建 `run_fireflies.py` 文件，并填入完整的实验编排逻辑。

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

from observatory.agents.kuramoto import firefly_agent


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

    # Ensure a clean slate for each experiment run
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    
    # All agents will run within the same engine and share the same connector
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=connector,
    )

    # --- Create the population of firefly agents ---
    agent_tasks = []
    for i in range(num_agents):
        # Each firefly starts with a random phase in its cycle
        initial_phase = random.uniform(0, period)
        
        # Create the workflow for a single agent
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash", # All agents listen and talk on the same topic
        )
        
        # Schedule the workflow to be run by the engine
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    # We use asyncio.wait_for to run for a fixed duration
    try:
        main_task = asyncio.gather(*agent_tasks)
        await asyncio.wait_for(main_task, timeout=duration_seconds)
    except asyncio.TimeoutError:
        print(f"\n✅ Experiment finished after {duration_seconds}s.")
    finally:
        # Gracefully stop the engine and connector
        # This will cancel all running agent tasks
        if not main_task.done():
            main_task.cancel()
            await asyncio.gather(main_task, return_exceptions=True)
        await engine.connector.disconnect()


if __name__ == "__main__":
    # To run the experiment, execute this script from the project root:
    # python -m observatory.experiments.run_fireflies
    asyncio.run(run_experiment())
~~~~~

### 下一步建议
我们已经创造了生命，并启动了它们的宇宙。但是，此刻我们是盲目的——我们无法“看到”萤火虫的闪烁，也无法衡量它们是否正在走向同步。

下一步至关重要：我们需要建造“观测台”。我建议创建 `observatory/monitors/convergence.py`。这个脚本将：
1.  也连接到同一个 `LocalBusConnector`。
2.  订阅 `firefly/flash` 主题。
3.  实时监听所有萤火虫的闪烁事件。
4.  计算并打印一个关键指标——“序参数 (Order Parameter)”，它能用一个数字来量化整个系统的同步程度。

这样，我们就能亲眼见证“涌现”的发生。
