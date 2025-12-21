简要回答：
好的，我将把 `observatory/agents/kuramoto.py` 中的 Firefly Agent 迁移到基于 `TailCall` 的 VM 模式，并同步更新 `run_fireflies.py` 以启用 VM 执行。

## [WIP] refactor(agent): 迁移 Kuramoto Agent 至 VM TailCall 模式

### 用户需求
将 `observatory/agents/kuramoto.py` 中的 `firefly_agent` 从基于图构建递归（依赖 TCO）的模式，迁移到使用 `TailCall` 返回值的 VM 执行模式。

### 评论
这是一个显著的性能优化步骤。通过使用 VM 和 `TailCall`，我们可以消除每次递归迭代中的图构建和哈希开销，将 Agent 的运行时开销降低到接近原生 `asyncio` 的水平，同时保留 Cascade 的可观测性和资源管理能力。

### 目标
1.  重写 `observatory/agents/kuramoto.py`，使其成为一个单一的 `@cs.task`，内部使用 `asyncio` 原语和 `TailCall` 进行状态流转。
2.  更新 `observatory/experiments/run_fireflies.py`，在启动实验时启用 `use_vm=True`。

### 基本原理
目前的 `firefly_agent` 通过递归调用自身来生成新的计算图节点。虽然 Engine 的 TCO 机制可以优化这一点，但在高频（如 30Hz）和大规模（2500+ Agent）场景下，图操作的开销仍然是瓶颈。
`TailCall` 允许任务直接指示 VM 重置当前栈帧并使用新参数重新开始执行，从而实现零开销的无限递归。这要求我们将逻辑从“声明式图构建”转变为“命令式异步执行”。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/vm #scope/perf #ai/instruct #task/domain/vm #task/object/kuramoto-agent #task/action/migration #task/state/begin

---

### Script

#### Acts 1: 重写 Kuramoto Agent

我们将完全重写 `observatory/agents/kuramoto.py`。新的实现将不再构建子任务（如 `fanout_direct`），而是直接在一个大的异步任务中处理逻辑。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, utilizing the Cascade VM and TailCall optimization.

REVISION 15: Migration to VM TailCall.
This version runs as a single, long-lived async task on the Cascade VM.
It uses `TailCall` to perform zero-overhead recursion, bypassing the
graph construction and solving phases for each step.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from cascade.runtime.blueprint import TailCall
from observatory.networking.direct_channel import DirectChannel


@cs.task
async def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float = 2.0,
):
    """
    The main VM-compatible entry point for a single firefly agent.
    
    Instead of building a graph of LazyResults, this task executes imperative
    async logic and returns a `TailCall` object to trigger the next iteration.
    """

    # 1. Refractory Path
    if initial_phase < refractory_period:
        wait_duration = refractory_period - initial_phase
        # In VM mode, we use direct asyncio sleep instead of cs.wait
        if wait_duration > 0:
            await asyncio.sleep(wait_duration)
        
        # Recurse to 'sensitive' phase
        return TailCall(kwargs={
            "initial_phase": refractory_period,
            # Pass through other invariant arguments
            "agent_id": agent_id,
            "period": period,
            "nudge": nudge,
            "neighbors": neighbors,
            "my_channel": my_channel,
            "connector": connector,
            "refractory_period": refractory_period
        })

    # 2. Sensitive Path
    else:
        time_to_flash = period - initial_phase
        # Ensure we don't wait for a negative time or 0
        wait_timeout = max(0.001, time_to_flash)
        
        start_time = time.time()
        try:
            # Wait for neighbor signal or timeout (which means we flash)
            _signal = await asyncio.wait_for(my_channel.recv(), timeout=wait_timeout)
            
            # Received Signal -> Nudge
            elapsed = time.time() - start_time
            next_phase = initial_phase + elapsed + nudge
            
            return TailCall(kwargs={
                "initial_phase": next_phase,
                "agent_id": agent_id,
                "period": period,
                "nudge": nudge,
                "neighbors": neighbors,
                "my_channel": my_channel,
                "connector": connector,
                "refractory_period": refractory_period
            })

        except asyncio.TimeoutError:
            # Timeout -> Flash
            flash_payload = {"agent_id": agent_id, "phase": period}
            
            # Telemetry (Fire and Forget)
            if connector:
                asyncio.create_task(connector.publish("firefly/flash", flash_payload))
            
            # Broadcast to neighbors
            for neighbor in neighbors:
                await neighbor.send(flash_payload)
            
            # Reset Phase with slight jitter
            jitter = random.uniform(0.0, 0.1)
            
            return TailCall(kwargs={
                "initial_phase": jitter,
                "agent_id": agent_id,
                "period": period,
                "nudge": nudge,
                "neighbors": neighbors,
                "my_channel": my_channel,
                "connector": connector,
                "refractory_period": refractory_period
            })
~~~~~

#### Acts 2: 更新实验脚本启用 VM

我们需要在 `observatory/experiments/run_fireflies.py` 中将 `engine.run()` 的调用修改为启用 `use_vm=True`。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
~~~~~
~~~~~python
        # Enable VM execution for TailCall support
        agent_tasks.append(engine.run(agent_workflow, use_vm=True))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
~~~~~

### 下一步建议
迁移完成后，建议运行 `observatory/experiments/run_fireflies.py` 进行验证。如果一切正常，您应该会看到性能（FPS）有显著提升，且内存占用保持稳定。之后可以考虑将资源调度和约束检查集成到 VM 中。
