简洁的回答：
**可以共享 Engine。**

`Engine` 的内部状态（`state_backend`, `flow_manager`, `active_resources`）都是在 `run()` 调用期间在局部作用域或基于 `run_id` 的工厂中创建的，或者通过 `ExitStack` 管理。`run` 方法是完全可重入的，并且其上下文与特定的 `run_id` 绑定。

唯一的例外是 `self.connector` 和 `self.resource_manager`，它们是 `Engine` 实例共享的。但这正是我们想要的：所有 Agent 共享同一个连接器进行 IO，共享同一个资源管理器来接受全局约束。

之前的卡顿主要是因为 2500 个 `Engine` 实例每个都创建了自己的 `ResourceManager`，这导致：
1.  **内存爆炸**：2500 个对象图。
2.  **约束无效**：全局的 `GlobalConstraint` 无法应用，因为每个 Agent 都有自己独立的配额，无法实现“全局 20 个并发槽”的限制（变成了 2500 * 20 个）。
3.  **连接风暴**：每个 Engine 都试图管理连接器的连接/断开（尽管我们传入了 shared connector，但 `finally` 块中的 `await self.connector.disconnect()` 如果不加防备，第一个结束的 Agent 就会断开所有人）。

**修正方案**：
1.  **单 Engine 实例**：在 `run_fireflies.py` 中只实例化**一个** `Engine`。
2.  **连接器生命周期管理**：不要将 shared connector 传给 Engine 构造函数（或者 Engine 需要识别它是外部管理的）。更好的做法是：Connector 由外部脚本管理生命周期（connect/disconnect），Engine 只负责使用。
    *   查看 `Engine.run` 的 `finally` 块：`if self.connector: await self.connector.disconnect()`。这是一个**致命**的设计问题，对于共享 Engine 模式来说。如果我们将 connector 传给 Engine，它就会在任何一个 `run` 结束时关闭它。
    *   **规避方法**：将 `connector=None` 传给 Engine 构造函数。然后通过 `register` 将 connector 作为资源注入。这样 Engine 就不会在 `run` 结束时尝试断开它，因为 Engine 认为自己没有 connector。

我们将执行第二阶段：动力学调优，并在重构 `run_fireflies` 时实施单 Engine 模式。

## [WIP] feat(sim): 实施单 Engine 模式与抑制性动力学

### 用户需求
执行第二阶段任务 `DYN-2.1` 和 `DYN-2.2`。
1.  **单 Engine 重构**：修改 `run_fireflies.py`，使用单个 `Engine` 实例来运行所有 2500+ 个 Agent，以解决性能瓶颈。
2.  **抑制性神经元**：引入 20% 的 `INHIBITORY` Agent，它们发出的信号会减少接收者的相位（减速），从而打破全网同步，产生复杂的 BZ 反应波形。
3.  **人工延迟场**：在 `DirectChannel` 中引入基于距离或区域的延迟，丰富时空动力学。

### 评论
将所有 Agent 放入单个 Engine 是 Cascade 设计的终极测试。如果 TCO 和 State Isolation 工作正常，这将极大地降低内存开销。
抑制性机制是产生“图灵斑图”的关键。没有它，耦合振子系统最终总是趋向于同步（死寂）。

### 目标
1.  修改 `observatory/networking/direct_channel.py`，支持 `latency` 参数。
2.  修改 `observatory/agents/kuramoto.py`：
    *   Agent 类型化：支持 `EXCITATORY` (默认) 和 `INHIBITORY`。
    *   在信号 Payload 中携带 `type`。
    *   在接收端根据信号类型执行 `phase += nudge` 或 `phase -= nudge`。
3.  重构 `observatory/experiments/run_fireflies.py`：
    *   **关键变更**：只实例化**一个** `Engine`。
    *   在构造函数中传入 `connector=None` 以防止 Engine 自动关闭连接。
    *   将 `connector` 作为共享资源注入。
    *   随机分配 Agent 类型。
    *   为通道配置异构延迟。

### 基本原理
**单 Engine 模式**：利用 `Engine.run` 的无状态性和可重入性。通过不将 Connector 传给 Engine 的 `__init__`，我们规避了其自动管理的生命周期，转而由外部脚本手动管理连接，这符合“控制反转”原则。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/dynamics #scope/core #ai/instruct
#task/domain/dynamics
#task/object/inhibitory-network
#task/action/implementation
#task/state/continue

---

### Script

#### Acts 1: 增强 DirectChannel 支持延迟

为直连通道添加模拟物理距离的能力。

~~~~~act
read_file
observatory/networking/direct_channel.py
~~~~~

~~~~~act
patch_file
observatory/networking/direct_channel.py
~~~~~
~~~~~python
    async def send(self, payload: Any):
        """
        Directly puts a message into the channel. Zero-copy.
        """
        # 1. Core Logic: Direct Delivery
        # We use await put() to handle backpressure and ensure fair scheduling.
        # This prevents the producer from starving the consumer loop.
        await self._inbox.put(payload)

        # 2. Telemetry Probe (The "Leak")
~~~~~
~~~~~python
    async def send(self, payload: Any, latency: float = 0.0):
        """
        Directly puts a message into the channel. Zero-copy.
        Supports synthetic latency.
        """
        # 1. Core Logic: Direct Delivery with optional Latency
        if latency > 0:
            # We use loop.call_later to schedule the put operation
            # This is non-blocking and simulates propagation delay
            loop = asyncio.get_running_loop()
            loop.call_later(latency, self._inbox.put_nowait, payload)
        else:
            # We use await put() to handle backpressure and ensure fair scheduling.
            await self._inbox.put(payload)

        # 2. Telemetry Probe (The "Leak")
~~~~~

#### Acts 2: 实现抑制性神经元逻辑

修改 Agent 逻辑，使其能够发送和响应不同类型的信号。

~~~~~act
read_file
observatory/agents/kuramoto.py
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
def firefly_agent(
    agent_id: int,
    initial_phase: float,
    period: float,
    nudge: float,
    neighbors: List[DirectChannel],
    my_channel: DirectChannel,
    connector: Connector,
    refractory_period: float = 2.0,
    agent_type: str = "EXCITATORY",  # "EXCITATORY" or "INHIBITORY"
    inhibition_strength: float = 2.0,
):
    """
    The main entry point for a single firefly agent.
    Now uses DirectChannel topology and supports inhibitory dynamics.
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
        agent_type: str,
    ):
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
                # Determine Action
                if is_timeout:
                    # We reached the end of the period. FLASH!
                    flash_payload = {
                        "agent_id": agent_id,
                        "phase": current_actual_phase,
                        "type": agent_type,
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
                            agent_type,
                        )

                    return loop_reset(p, flash)

                else:
                    # We heard a neighbor!
                    signal = p.get("signal", {})
                    sender_type = signal.get("type", "EXCITATORY")
                    
                    if sender_type == "INHIBITORY":
                        # Retard phase (slow down)
                        delta = -(nudge * inhibition_strength)
                    else:
                        # Advance phase (speed up)
                        delta = nudge

                    next_phase = current_actual_phase + delta
                    return firefly_cycle(
                        agent_id,
                        next_phase,
                        period,
                        nudge,
                        neighbors,
                        my_channel,
                        connector,
                        refractory_period,
                        agent_type,
                    )
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
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
~~~~~python
    return firefly_cycle(
        agent_id,
        initial_phase,
        period,
        nudge,
        neighbors,
        my_channel,
        connector,
        refractory_period,
        agent_type,
    )
~~~~~

#### Acts 3: 单 Engine 重构与配置注入

重写 `run_fireflies.py`，实施单 Engine 模式，并配置复杂的异构网络（随机分配类型）。

~~~~~act
read_file
observatory/experiments/run_fireflies.py
~~~~~

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Dict, Any, List
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 50  # Increased for higher density wave patterns
NUM_AGENTS = GRID_SIDE * GRID_SIDE
PERIOD = 5.0
INHIBITORY_RATIO = 0.2  # 20% of agents are inhibitory


def get_neighbors(index: int, width: int, height: int) -> List[int]:
    """Calculate 8-neighbors (Moore neighborhood) with wrap-around (toroidal)."""
    x, y = index % width, index // width
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors


async def run_experiment(
    num_agents: int = NUM_AGENTS,
    period: float = PERIOD,
    nudge: float = 0.2,
    duration_seconds: float = 3000.0,
    visualize: bool = True,
    decay_duty_cycle: float = 0.3,
):
    """
    Sets up and runs the firefly synchronization experiment using a SINGLE Engine
    and a mix of Excitatory/Inhibitory agents.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )
    print(f"   - Single Engine Mode: ACTIVE")
    print(f"   - Inhibitory Agents: {INHIBITORY_RATIO * 100:.0f}%")

    # 1. Initialize Shared Bus & Connector
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)

    app = None
    app_task = None

    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar(
            initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."}
        )
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        
        app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            asyncio.create_task(aggregator.record("r_value", r_value))
            asyncio.create_task(aggregator.record("pulse", pulse_count))
            asyncio.create_task(aggregator.record("flash_count", monitor._flash_count))

        monitor_task = asyncio.create_task(
            monitor.run(frequency_hz=2.0, callback=monitor_callback)
        )

        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            atype = payload.get("type", "EXCITATORY")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Visual distinction: Inhibitory flashes are slightly dimmer or handled differently by palette?
                # For now, just use 1.0 brightness, palette handles fade.
                intensity = 1.0 if atype == "EXCITATORY" else 0.8
                await app.direct_update_grid_batch([(x, y, intensity)])

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # --- Create Topology (DirectChannels) ---
    print("Constructing Network Topology...")
    channels = [DirectChannel(owner_id=f"agent_{i}", capacity=100) for i in range(num_agents)]

    # --- Setup Single Shared Engine ---
    # CRITICAL: We pass connector=None to prevent the Engine from managing its lifecycle.
    # The Engine will be "headless" in terms of external IO, but we will inject the connector as a resource.
    shared_engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None, 
    )

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        # This provider allows agents to access the connector managed by this script
        yield connector

    shared_engine.register(shared_connector_provider)

    # --- Create Agents ---
    agent_tasks = []

    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        # Determine Type
        atype = "INHIBITORY" if random.random() < INHIBITORY_RATIO else "EXCITATORY"

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        # Inhibit stronger than excite to create contrast
        inhibition = 4.0 if atype == "INHIBITORY" else 0.0

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("_internal_connector"), # Use injection
            refractory_period=period * 0.2,
            agent_type=atype,
            inhibition_strength=inhibition
        )

        agent_tasks.append(shared_engine.run(agent_workflow))

        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)

    print("🚀 All agents prepared. Launching...")

    # --- Run ---
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()

        if "aggregator" in locals():
            aggregator.close()
            if "aggregator_task" in locals():
                aggregator_task.cancel()
                await asyncio.gather(aggregator_task, return_exceptions=True)

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~

### 下一步建议
运行 `python -m observatory.experiments.run_fireflies`。
预期结果：
1.  启动速度应稍微加快，内存占用应显著降低。
2.  性能抖动应减少。
3.  最重要的是，**视觉效果**应不再是单调的全局闪烁，而应该开始出现复杂的波纹、螺旋或局部同步斑块（由于抑制性节点的干扰）。
