数据收到了。分析非常清晰，结论也令人震惊。

我们成功了，但也失败了。

 数据分析与结论

1.  **渲染器吞吐量测试 (`debug_renderer_throughput.py`)**:
    *   **结论：渲染器本身绝对不是瓶颈。**
    *   **证据**: 在隔离测试中，渲染器可以稳定地维持在 **~60 FPS**，`flush_duration_ms` 平均**低于1毫秒**，`render_jitter_ms` 为 **0**。这表明我们的 `RawTerminalApp` 性能极好，可以轻松处理每秒上万次的更新请求而完全不阻塞事件循环。

2.  **无头模式计算吞吐量测试 (`debug_headless_throughput.py`)**:
    *   **结论：核心 Agent 逻辑和 `Engine` 本身也不是瓶颈。**
    *   **证据**: 在完全没有 UI 的情况下，2500 个 Agent 的模拟可以产生 **每秒 400-500 次** 的总闪烁次数。考虑到每个 Agent 的周期是 5 秒，理论上的平均速率就是 `2500 agents / 5s = 500 flashes/sec`。我们的无头模式几乎完美地达到了这个理论值。

3.  **性能剖析 (`profile.out`)**:
    *   **结论：瓶颈的真凶是 Cascade 的图构建 (`build_graph`) 过程，因为它在 Agent 的每一次循环中都被重复调用。**
    *   **证据**: `cProfile` 的输出结果一针见血。耗时最高的函数全部指向 `inspect.py` 和 `cascade/graph/build.py`。特别是 `_signature_from_function` 和 `_scan_and_add_edges`。这说明 CPU 的绝大部分时间都消耗在了**反射函数签名和构建依赖图**上。

 根本原因：架构错配 (Architectural Mismatch)

我们正在用重量级的“工作流编排”引擎来执行一个轻量级的“无限循环”任务。

`Engine` 的尾递归优化（TCO）非常巧妙，但它的核心设计是：每一次返回 `LazyResult`，都代表一个新的、独立的计算图需要被解析和执行。

对于我们的 `firefly_agent`，每一次`nudge`或`flash`后的递归调用，都会触发一次完整的 `build_graph` -> `solver.resolve` -> `_execute_graph` 循环。对于 2500 个 Agent，每秒产生 500 次闪烁，就意味着我们每秒要**构建数千次**计算图。这就是 `cProfile` 告诉我们的真相，也是事件循环被彻底阻塞的根本原因。

 解决方案：从“声明式递归”到“命令式循环”

我们必须改变 `firefly_agent` 的内部实现。`Engine` 应该只被调用**一次**来启动 Agent，而 Agent 的内部循环应该是一个标准的、高效的 `async while True` 循环，直接调用异步辅助函数，而不是返回 `LazyResult`。

这标志着我们对 Agent 和 Workflow 的理解进入了下一个层次：
*   **Workflow**: 是一个有向无环图（DAG），它有明确的开始和结束，适合用 `Engine` 的声明式语法来编排。
*   **Agent**: 是一个永不停止的进程。适合用 `Engine` **启动一次**，其内部通过高效的命令式循环来维持其生命。

## [WIP] perf(agent): 将 Agent 内部逻辑重构为命令式循环

### 用户需求
将 `firefly_agent` 的核心循环从返回 `LazyResult` 的声明式递归模式，重构为一个包含 `while True` 的命令式异步循环。目标是彻底消除在 Agent 的每个“心跳”中重复构建计算图所带来的巨大性能开销。

### 评论
这是一个根本性的范式转变，但它基于坚实的数据证据。通过将 Agent 的“宏观生命周期”（启动）与“微观心跳”（内部循环）分离，我们可以同时利用 `Engine` 强大的启动和资源管理能力，以及 `asyncio` 原生循环的高性能。

### 目标
1.  重构 `observatory/agents/kuramoto.py`：
    *   将 `safe_recv_channel` 和 `fanout_direct` 从 `@cs.task` 装饰的 Cascade 任务，改为普通的 `async def` 辅助函数。
    *   将 `firefly_agent` 改为一个单一的 `@cs.task`，其内部实现为一个包含 `while True` 的主循环。
    *   移除 `firefly_cycle` 递归函数。
2.  相应地调整 `run_fireflies.py`，确保它仍然能正确地启动这些“永动”型的 Agent 任务。

### 基本原理
通过在 `firefly_agent` 内部使用 `while True` 循环，我们将图构建的成本分摊到了整个 Agent 的生命周期中，使其成本变为**一次**。Agent 的每一次相位更新和闪烁决策都将是简单的、低开销的异步函数调用，不再触及昂贵的 `inspect` 和图构建逻辑，从而将事件循环从调度过载中解放出来。

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/runtime #concept/concurrency #scope/core #ai/brainstorm
#task/domain/infra
#task/object/agent-lifecycle
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 重构 Kuramoto Agent 为命令式循环

这将是一个彻底的重写，因此我将使用 `write_file`。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 11: Refactored internal loop to be imperative (async while)
             to eliminate graph-building overhead on each cycle.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Helper Functions (No longer @cs.task) ---


async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    connector: Connector,
):
    """
    Fan-out using DirectChannel (Fast Path) + Connector (Slow Path).
    """
    # 1. Fast Path: Zero-copy delivery to neighbors
    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        # Yield to allow other tasks to run in a large fan-out scenario
        if i > 0 and i % 10 == 0:
            await asyncio.sleep(0)

    # 2. Slow Path: Telemetry for Visualization
    if connector:
        await connector.publish("firefly/flash", payload)


async def safe_recv_channel(
    channel: DirectChannel,
    timeout: float,
) -> Dict[str, Any]:
    """
    Waits for a message on a DirectChannel with a timeout.
    """
    start_time = time.time()
    try:
        signal = await asyncio.wait_for(channel.recv(), timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}


# --- Core Agent (now a long-running @cs.task with an internal loop) ---


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
    This is the main entry point for a single firefly agent.
    It's a long-running task that contains the agent's entire lifecycle.
    """
    phase = initial_phase

    while True:
        # --- Logic Branching ---

        # 1. Refractory Period: We are "blind" and just wait.
        if phase < refractory_period:
            blind_wait_duration = refractory_period - phase
            await asyncio.sleep(blind_wait_duration)
            phase = refractory_period
            continue  # Re-evaluate state in the next loop iteration

        # 2. Sensitive Period: Listen for neighbors until it's time to flash.
        time_to_flash = period - phase
        wait_timeout = max(0.01, time_to_flash)

        perception = await safe_recv_channel(my_channel, timeout=wait_timeout)

        is_timeout = perception.get("timeout", False)
        elapsed_time = perception.get("elapsed", 0.0)
        phase += elapsed_time

        # --- State Update ---
        if is_timeout:
            # FLASH: We reached the end of our cycle.
            flash_payload = {"agent_id": agent_id, "phase": phase}
            await fanout_direct(neighbors, flash_payload, connector)

            # RESET: Start a new cycle with a bit of jitter.
            phase = random.uniform(0.0, 0.1)

        else:
            # NUDGE: A neighbor flashed, so we adjust our phase.
            phase += nudge
~~~~~

#### Acts 2: 调整实验脚本的 Agent 调用

`run_fireflies.py` 的改动很小，主要是 `connector` 的注入方式。因为 `firefly_agent` 现在是一个真正的 `@cs.task`，我们可以直接使用 `@resource` 和 `cs.inject`。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    # --- Create Shared Engine ---
    print("Initializing Shared Cascade Engine...")
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(), # A silent bus for the engine itself
        connector=None,
    )

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)


    # --- Create Agents ---
    agent_tasks = []
    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("_internal_connector"),
            refractory_period=period * 0.2,
        )

        # Schedule the workflow to run on the shared engine
        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)
~~~~~
~~~~~python
    # --- Create Shared Engine ---
    print("Initializing Shared Cascade Engine...")
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(), # A silent bus for the engine itself
        connector=None,
    )

    # The connector is now a standard resource that can be injected.
    @resource(name="shared_connector")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)


    # --- Create Agents ---
    agent_workflows = []
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        
        # We now create the LazyResult once...
        workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=[channels[nid] for nid in neighbor_ids],
            my_channel=channels[i],
            connector=cs.inject("shared_connector"),
            refractory_period=period * 0.2,
        )
        agent_workflows.append(workflow)

    # ...and then schedule all of them to run concurrently on the engine.
    print("Launching all agents on the engine...")
    # We use asyncio.gather to run them, not a loop of awaits.
    # The engine.run() call returns a coroutine.
    agent_tasks = [engine.run(wf) for wf in agent_workflows]
~~~~~

### 下一步建议
请运行 `python -m observatory.experiments.run_fireflies`。

我预测这次的性能将会有**质的飞跃**。FPS 应该会稳定在 30-60，`flush_duration_ms` 会降到个位数，`render_jitter_ms` 会大幅减少。这将标志着我们**第一阶段：基座重铸**的最终成功。
