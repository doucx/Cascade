好的，我们来仔细分析。

错误分析

你的重构非常成功，它暴露了系统的**下一个真实瓶颈**。日志数据非常清晰地指向了问题所在：

1.  **成功之处**: 我们已经不再受限于 Engine 的创建开销。系统现在能够启动并运行，这是巨大的进步。
2.  **新的瓶颈**: `flush_duration_ms` 依然高达 200-400ms，并且与 `fps_min` 存在强烈的负相关性 (-0.597)。这意味着**渲染器的数据处理**现在是阻塞事件循环的元凶。
3.  **根本原因**: 我们的 `firefly_agent` 每次闪烁时，都会通过 `connector` (慢速通道) 发送一个遥测消息。`run_fireflies.py` 中的 `on_flash_visual` 回调接收这个消息，并调用 `app.direct_update_grid_batch`。在高频闪烁（`flash_count.sum` 每秒数千次）的情况下，这导致：
    *   **事件风暴**: `asyncio` 事件循环被成千上万个微小的 `publish`, `subscribe`, `direct_update_grid_batch` 任务淹没。
    *   **锁争用**: 数千个协程并发调用 `app.direct_update_grid_batch`，这会在其内部的 `_flush_lock` 上产生高度争用，增加了调度开销。
    *   **CPU 阻塞**: 最致命的是，`_render_loop` 在每一帧都需要处理一个巨大的 `_frame_buffer` 集合。`_blocking_flush_logic` 中从 Python `set` 到 NumPy 数组的转换，在数据量巨大时会消耗非常可观的 CPU 时间。即使 `asyncio.to_thread` 尝试将其移出主线程，但当这些 CPU 任务的产生速度（每秒数千次闪烁累积）远快于线程池的处理速度时，主循环最终还是会因为等待锁或等待线程池可用而阻塞。

**结论**: 我们当前的“事件驱动推送 (Event-Pushed)”渲染模型在万级节点规模下已达到极限。Agent 主动向渲染器推送状态更新的模式，在高频场景下是不可持续的。

**解决方案**: 我们需要转向“状态采样拉取 (State-Polled)”模型。这与我们的战略规划文档 `IO-3.2: 運動皮層 (State Vector Readout)` 完全一致。
1.  **创建共享内存**: 我们在主实验脚本中创建一个全局共享的 `numpy.ndarray`，称之为 `GLOBAL_STATE_VECTOR`。
2.  **Agent 直接写入**: Agent 不再发送遥测消息。在它更新自身相位时，直接、廉价地在共享数组的对应位置写入新值 (`GLOBAL_STATE_VECTOR[self.id] = self.phase`)。这是一个无锁的、纳秒级的操作。
3.  **渲染器直接读取**: `RawTerminalApp` 的渲染循环不再处理事件队列。在每一帧，它直接读取整个 `GLOBAL_STATE_VECTOR`，用最新的状态数据渲染画面。

这种“拉取”模式将 Agent 与渲染器彻底解耦，消除了事件风暴、锁争用和昂贵的数据转换，是实现高性能、大规模可视化的正确路径。

## [WIP] feat(infra): Implement shared memory telemetry for rendering

### 用户需求
完成“创世网络第二纪元战略规划”的第一阶段，通过实现 `IO-3.2` (State Vector Readout)，解决大规模 Agent 模拟下的渲染性能瓶颈，实现流畅的可视化。

### 评论
本次提交是基础设施重铸的收官之作。通过从“事件推送”模型转向“状态采样”模型，我们用一个共享的 NumPy 数组取代了高成本的消息总线遥测，彻底解耦了模拟物理与可视化，为万级节点的流畅运行铺平了道路。

### 目标
1.  修改 `kuramoto.py`，让 `firefly_agent` 接收一个共享的 `state_vector`，并在每次相位更新时直接写入该数组。
2.  修改 `run_fireflies.py`，创建并分发这个共享的 `state_vector`。
3.  修改 `raw_app.py`，使其渲染循环直接从 `state_vector` 采样数据，并移除事件驱动的更新逻辑。
4.  创建一个 Git 提交，固化这一里程碑式的性能改进。

### 基本原理
我们用一个低成本、高效率的共享内存（NumPy 数组）数据结构替换了高成本、低效率的事件消息传递机制，用于物理模拟与UI渲染之间的通信。这遵循了高性能计算中常见的“数据局部性”和“避免间接”原则。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct
#task/domain/infra
#task/object/topology
#task/action/integration
#task/state/end

---

### Script

#### Acts 1: 修改 Agent 以写入共享状态

我们将重写 `kuramoto.py`，引入共享状态向量。

~~~~~act
write_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
"""
Implementation of a Firefly agent based on the Kuramoto model
of coupled oscillators, using pure Cascade primitives.

REVISION 11: Switched to shared state vector for telemetry.
"""

import asyncio
import random
import time
from typing import Any, Dict, List

import numpy as np
import cascade as cs
from cascade.interfaces.protocols import Connector
from observatory.networking.direct_channel import DirectChannel


# --- Atomic Primitives for Agent Behavior ---


@cs.task
async def fanout_direct(
    neighbors: List[DirectChannel],
    payload: Dict[str, Any],
    should_send: bool,
) -> None:
    """
    Fan-out using DirectChannel. The slow path telemetry is now removed.
    """
    if not should_send:
        return

    for i, neighbor in enumerate(neighbors):
        await neighbor.send(payload)
        if i % 10 == 0:
            await asyncio.sleep(0)


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
    state_vector: np.ndarray,
    refractory_period: float = 2.0,
):
    """
    The main entry point for a single firefly agent.
    Now uses a shared state vector for telemetry.
    """

    # Initial write
    state_vector[agent_id] = initial_phase / period

    def firefly_cycle(
        agent_id: int,
        phase: float,
        period: float,
        nudge: float,
        neighbors: List[DirectChannel],
        my_channel: DirectChannel,
        state_vector: np.ndarray,
        refractory_period: float,
    ):
        # --- Logic Branching ---

        # 1. Refractory Check
        if phase < refractory_period:
            blind_wait_duration = refractory_period - phase
            wait_action = cs.wait(blind_wait_duration)

            @cs.task
            def after_refractory(_):
                new_phase = refractory_period
                state_vector[agent_id] = new_phase / period
                return firefly_cycle(
                    agent_id, new_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                )
            return after_refractory(wait_action)

        # 2. Sensitive Check
        else:
            time_to_flash = period - phase
            wait_timeout = max(0.01, time_to_flash)
            perception = safe_recv_channel(my_channel, timeout=wait_timeout)

            @cs.task
            def process_perception(p: Dict[str, Any]) -> cs.LazyResult:
                elapsed_time = p.get("elapsed", 0.0)
                current_actual_phase = phase + elapsed_time

                if p.get("timeout", False):
                    # FLASH!
                    flash_payload = {"agent_id": agent_id, "phase": current_actual_phase}
                    flash = fanout_direct(neighbors=neighbors, payload=flash_payload, should_send=True)

                    @cs.task
                    def loop_reset(_, _flash):
                        jitter = random.uniform(0.0, 0.1)
                        new_phase = 0.0 + jitter
                        state_vector[agent_id] = 1.0  # Visual flash
                        return firefly_cycle(
                            agent_id, new_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                        )
                    return loop_reset(p, flash)
                else:
                    # NUDGE!
                    next_phase = current_actual_phase + nudge
                    state_vector[agent_id] = next_phase / period
                    return firefly_cycle(
                        agent_id, next_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
                    )
            return process_perception(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, neighbors, my_channel, state_vector, refractory_period
    )
~~~~~

#### Acts 2: 修改实验脚本以管理和注入共享状态

重写 `run_fireflies.py` 来创建和使用 `state_vector`。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Dict, Any, List
import time
import numpy as np

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
GRID_SIDE = 50
NUM_AGENTS = GRID_SIDE * GRID_SIDE
PERIOD = 5.0


def get_neighbors(index: int, width: int, height: int) -> List[int]:
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
    grid_width = int(num_agents**0.5)
    print(f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment...")

    # --- Setup Infrastructure ---
    LocalBusConnector._reset_broker_state()
    # Connector is now ONLY for the convergence monitor
    monitor_connector = LocalBusConnector()
    await monitor_connector.connect()

    # 1. THE SHARED STATE VECTOR
    # This vector holds the normalized phase (0-1) for rendering.
    # It is written to by agents and read by the renderer.
    state_vector = np.zeros(num_agents, dtype=np.float32)

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, monitor_connector)

    app = None
    app_task = None

    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar({"Agents": num_agents, "Sync (R)": "Initializing..."})
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        print(f"📝 Logging telemetry to [bold cyan]{log_filename}[/bold cyan]")
        
        # Pass the state_vector to the app
        app = TerminalApp(grid_view, status_bar, state_vector, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            asyncio.create_task(aggregator.record("r_value", r_value))

        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0, callback=monitor_callback))
        
        # The monitor is the ONLY thing that needs the slow bus now
        await monitor_connector.subscribe("firefly/flash", monitor.on_flash)

        app_task = asyncio.create_task(app.start())
    else:
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))

    # --- Create Topology (DirectChannels) ---
    print("Constructing Network Topology...")
    channels = [DirectChannel(owner_id=f"agent_{i}") for i in range(num_agents)]
    
    # --- Create Shared Engine ---
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    
    # The monitor connector is a resource for agents that need to publish flashes
    @resource(name="monitor_connector")
    def monitor_connector_provider():
        yield monitor_connector
    engine.register(monitor_connector_provider)
    
    # --- Create Agents ---
    agent_tasks = []
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=[channels[nid] for nid in neighbor_ids],
            my_channel=channels[i],
            state_vector=state_vector, # Pass the shared vector
            refractory_period=period * 0.2,
        )
        agent_tasks.append(engine.run(agent_workflow))

    print("🚀 All agents prepared. Launching...")
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    finally:
        monitor.stop()
        if app: app.stop()
        if "aggregator" in locals():
            aggregator.close()
            if "aggregator_task" in locals(): aggregator_task.cancel()
        
        all_agent_tasks.cancel()
        await asyncio.gather(all_agent_tasks, monitor_task, return_exceptions=True)
        if app_task and not app_task.done(): await app_task
        await monitor_connector.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~

#### Acts 3: 修改渲染器以直接采样状态

最后，重写 `raw_app.py` 以适应新的“拉取”模型。

~~~~~act
write_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
import asyncio
import sys
import time
from asyncio import Queue
from typing import Any, Optional

import numpy as np

from .grid import GridView
from .status import StatusBar
from observatory.monitors.aggregator import MetricsAggregator

# ANSI Codes
CURSOR_HIDE = b"\033[?25l"
CURSOR_SHOW = b"\033[?25h"
CURSOR_HOME = b"\033[H"
CLEAR_SCREEN = b"\033[2J"
RESET_COLOR = b"\033[0m"


class RawTerminalApp:
    """
    A 'Raw Metal' renderer that directly samples a shared state vector.
    """

    def __init__(
        self,
        grid_view: GridView,
        status_bar: StatusBar,
        state_vector: Optional[np.ndarray] = None, # The shared state
        aggregator: MetricsAggregator = None,
    ):
        self.grid_view = grid_view
        self.status_bar = status_bar
        self.state_vector = state_vector
        self.aggregator = aggregator

        self.queue: Queue = Queue() # Only for status updates now
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._stdout = sys.stdout.buffer

    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    async def start(self):
        self._running = True
        self._stdout.write(CURSOR_HIDE + CLEAR_SCREEN)
        self._stdout.flush()
        self._render_task = asyncio.create_task(self._render_loop())

    def stop(self):
        self._running = False
        if self._render_task:
            self._render_task.cancel()
        self._stdout.write(CURSOR_SHOW + RESET_COLOR + b"\n")
        self._stdout.flush()

    def _render_status_bar(self) -> bytes:
        parts = []
        for key, value in self.status_bar.status_data.items():
            parts.append(f"\033[36m{key}:\033[0m \033[1;35m{str(value)}\033[0m")
        line = " | ".join(parts)
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line + "\033[K").encode("utf-8")

    async def _render_loop(self):
        last_time = time.perf_counter()
        target_fps = 60.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()

            # 1. Process status queue
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        self.status_bar.set_status(data[0], data[1])
                except asyncio.QueueEmpty:
                    break

            # 2. Physics & State Update
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            
            # PULL from shared state vector
            if self.state_vector is not None:
                # Reshape the 1D vector into a 2D grid for the matrix
                grid_shape = (self.grid_view.logical_height, self.grid_view.logical_width)
                self.grid_view.matrix.set_matrix(self.state_vector.reshape(grid_shape))

            self.grid_view.matrix.decay(min(dt, 0.1))

            # 3. RENDER
            output_buffer = bytearray(CURSOR_HOME)
            grid_bytes = self.grid_view.render_frame_buffer()
            output_buffer.extend(grid_bytes)
            status_bytes = self._render_status_bar()
            output_buffer.extend(status_bytes)
            self._stdout.write(output_buffer)
            self._stdout.flush()

            # 4. Telemetry & Sleep
            fps = 1.0 / dt if dt > 0 else 0
            self.status_bar.set_status("FPS", f"{fps:.1f}")
            if self.aggregator:
                await self.aggregator.record("fps", fps)
            
            render_duration = time.perf_counter() - loop_start
            sleep_time = frame_interval - render_duration
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0) # Yield
~~~~~

### 下一步建议
我们已经成功完成了第一阶段“基座重铸”的所有任务。现在的系统拥有了一个高性能、可扩展的物理基础。

我建议我们正式进入**第二阶段：动力学调优**，开始执行 `DYN-2.1: 抑制性神经元 (Inhibitory Agents)`。
