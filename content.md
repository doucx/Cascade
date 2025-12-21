简洁的回答：
好的，我们将开始执行第一阶段：基座重铸。这将通过引入 `DirectChannel` 和重构 `firefly_agent` 来消除消息总线的开销，为万级节点规模做好准备。

## [WIP] refactor(infra): 为 Firefly Agent 引入 DirectChannel 直连拓扑

### 用户需求
执行“创世网络第二纪元战略规划”的第一阶段任务 `INFRA-1.1` 和 `INFRA-1.2`。
具体是将 `firefly_agent` 的通信机制从基于 Topic 的总线发布/订阅模式，迁移到基于对象引用的 `DirectChannel` 点对点零拷贝模式，以支撑 10,000+ 节点的模拟规模。同时需要保持可视化功能的正常运行。

### 评论
这是一个关键的基础设施升级。当前的 `LocalBus` 在高频小消息场景下（10k agents * 1Hz = 10k msg/s, fanout 8 = 80k deliveries/s）会成为 CPU 瓶颈。`DirectChannel` 绕过了中间 Broker 的匹配和调度开销，直接将 Payload 放入目标 Queue，理论吞吐量提升显著。

### 目标
1.  将 `DirectChannel` 从 `protoplasm` 提升为正式组件 `observatory.networking.direct_channel`。
2.  重构 `observatory.agents.kuramoto.py`：
    *   移除 `fanout_signal` (Topic 模式)。
    *   新增 `fanout_direct` (Channel 模式，保留一条通往 `connector` 的慢速通道用于可视化)。
    *   新增 `safe_recv_channel` 替代 `safe_recv`，支持 `asyncio.wait_for` 超时控制。
    *   更新 `firefly_agent` 签名，接收 `neighbors: List[DirectChannel]` 和 `my_channel: DirectChannel`。
3.  重构 `observatory.experiments.run_fireflies.py`：
    *   在实验初始化阶段构建 `DirectChannel` 拓扑。
    *   将构建好的 Channel 注入到 Agent 中。

### 基本原理
通过在图构建阶段（Setup）预先解析拓扑并注入直接引用，我们在运行时（Runtime）消除了所有的路由查找（Routing Lookup）和序列化（Serialization）成本。对于可视化，我们保留一个“旁路”机制，即 Agent 在通过快速通道通知邻居的同时，通过慢速的总线通道发送低频或采样的状态更新给观察者。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/communication #scope/core #ai/instruct
#task/domain/infra
#task/object/topology
#task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 提升 DirectChannel 组件

将 `DirectChannel` 移动到正式的 networking 包中，确立其作为核心基础设施的地位。

~~~~~act
move_file
observatory/protoplasm/networking/direct_channel.py
observatory/networking/direct_channel.py
~~~~~

#### Acts 2: 重构 Kuramoto Agent

这是本次重构的核心。我们将修改 Agent 的感知（Input）和行动（Output）层，使其基于 `DirectChannel` 运作。

~~~~~act
read_file
observatory/agents/kuramoto.py
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def fanout_signal(
    topics: List[str],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,
) -> None:
    """A task to publish a message to multiple topics (Fan-out)."""
    if should_send and connector and topics:
        # Optimistic fan-out: we just fire tasks or await in loop.
        # Since LocalBus.publish is non-blocking (just puts to queue), loop is fine.
        for topic in topics:
            await connector.publish(topic, payload)


@cs.task
async def safe_recv(
    topic: str,
    timeout: float,
    connector: Connector,
) -> Dict[str, Any]:
    """
    A custom receive task that treats timeouts as valid return values.
    Also returns the time elapsed while waiting.
    """
    if not connector:
        return {"signal": None, "timeout": True, "elapsed": 0.0}

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    start_time = time.time()
    try:
        signal = await asyncio.wait_for(future, timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}
    finally:
        if subscription:
            await subscription.unsubscribe()
~~~~~
~~~~~python
import asyncio
import random
import time
from typing import Any, Dict, List

import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
    connector: Connector,  # For visualization/telemetry side-channel
) -> None:
    """
    Fan-out using DirectChannel (Fast Path) + Connector (Slow Path).
    """
    if not should_send:
        return

    # 1. Fast Path: Zero-copy delivery to neighbors
    # We yield to the event loop occasionally to prevent starvation if fan-out is huge
    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        if i % 10 == 0:
            await asyncio.sleep(0)

    # 2. Slow Path: Telemetry for Visualization
    if connector:
        # We publish to a known topic for the visualizer
        await connector.publish("firefly/flash", payload)


@cs.task
async def safe_recv_channel(
    channel: DirectChannel,
    timeout: float,
) -> Dict[str, Any]:
    """
    Waits for a message on a DirectChannel with a timeout.
    """
    start_time = time.time()
    try:
        # DirectChannel.recv() returns the payload directly
        signal = await asyncio.wait_for(channel.recv(), timeout=timeout)
        elapsed = time.time() - start_time
        return {"signal": signal, "timeout": False, "elapsed": elapsed}
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {"signal": None, "timeout": True, "elapsed": elapsed}


# --- Core Agent Logic ---


def firefly_agent(
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
    The main entry point for a single firefly agent.
    Now uses DirectChannel topology.
    """

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        neighbors: List[DirectChannel],
        my_channel: DirectChannel,
        connector: Connector,
        refractory_period: float,
    ):
        # --- Logic Branching ---

        # 1. Refractory Check: If we are in the "blind" zone, just wait.
        if phase < refractory_period:
            # We are blind. Wait until we exit refractory period.
            blind_wait_duration = refractory_period - phase

            # Use cs.wait for pure time passage (no listening)
            wait_action = cs.wait(blind_wait_duration)

            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    neighbors,
                    my_channel,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)

        # 2. Sensitive Check: We are past refractory. Listen for neighbors.
        else:
            time_to_flash = period - phase
            # Ensure we don't have negative timeout due to floating point drift
            wait_timeout = max(0.01, time_to_flash)

            # Listen to MY channel
            perception = safe_recv_channel(my_channel, timeout=wait_timeout)

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                is_timeout = p.get("timeout", False)
                elapsed_time = p.get("elapsed", 0.0)

                # Update actual phase based on real time passed
                current_actual_phase = phase + elapsed_time

                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {
                        "agent_id": agent_id,
                        "phase": current_actual_phase,
                    }

                    flash = fanout_direct(
                        neighbors=neighbors,
                        payload=flash_payload,
                        should_send=True,
                        connector=connector,
                    )

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        return firefly_cycle(
                            agent_id,
                            0.0 + jitter,
                            period,
                            nudge,
                            neighbors,
                            my_channel,
                            connector,
                            refractory_period,
                        )

                    return loop_reset(p, flash)

                else:
                    # We heard a neighbor! NUDGE!
                    next_phase = current_actual_phase + nudge
                    return firefly_cycle(
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        neighbors,
                        my_channel,
                        connector,
                        refractory_period,
                    )

            return process_perception(perception)

    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        neighbors,
        my_channel,
        connector,
        refractory_period,
    )
~~~~~

#### Acts 3: 更新实验脚本

更新 `run_fireflies.py` 以构建 `DirectChannel` 拓扑并注入 Agent。

~~~~~act
read_file
observatory/experiments/run_fireflies.py
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
~~~~~
~~~~~python
from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    # --- Create Agents ---
    agent_tasks = []

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)

        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        neighbor_inboxes = [f"firefly/{nid}/inbox" for nid in neighbor_ids]
        my_inbox = f"firefly/{i}/inbox"

        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None,
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbor_inboxes=neighbor_inboxes,
            my_inbox=my_inbox,
            connector=connector,
            refractory_period=period * 0.2,
        )

        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)
~~~~~
~~~~~python
    # --- Create Topology (DirectChannels) ---
    print("Constructing Network Topology...")
    channels = [DirectChannel(owner_id=f"agent_{i}", capacity=100) for i in range(num_agents)]

    # --- Create Agents ---
    agent_tasks = []

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None,
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=connector,
            refractory_period=period * 0.2,
        )

        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)
~~~~~

### 下一步建议
运行 `python -m observatory.experiments.run_fireflies` 来验证新的拓扑结构是否正常工作。如果一切顺利，我们将继续执行战略计划的第二阶段：引入抑制性神经元。
