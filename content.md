Excellent. The universe for our fireflies has been created. Now, we shall become its gods, building an observatory to gaze upon our creation and measure the emergence of order from chaos.

This monitoring script is the scientific core of the experiment. It acts as a passive, non-intrusive observer that listens to the "light" (flash signals) from the fireflies and calculates, in real-time, the collective coherence of the entire system. This allows us to quantify the abstract concept of "synchronization" into a hard number.

I will generate the plan to build this observatory and integrate it into our experiment.

## [WIP] feat: 创建实时同步监测器并集成到实验中

### 用户需求
创建 `observatory/monitors/convergence.py` 脚本，用于实时监听萤火虫的“闪烁”事件，计算并显示系统的同步程度（序参数），并将其集成到 `run_fireflies.py` 实验脚本中。

### 评论
这是“涌现”的可视化。通过创建一个独立的、并行的监控任务，我们完美地模拟了科学实验中的“测量”过程。该监测器利用 `numpy` 进行高效的向量计算，将 Kuramoto 模型的序参数公式付诸实践。将其与 Agent 种群并发运行，我们不仅能验证 Agent 的行为，还能亲眼见证宏观秩序如何从微观的、去中心化的交互中自发产生。这是对 Cascade 作为复杂系统模拟框架潜力的一次有力证明。

### 目标
1.  创建 `observatory/monitors/convergence.py` 文件。
2.  在其中实现一个 `ConvergenceMonitor` 类，该类负责：
    *   订阅萤火虫的闪烁主题 (`firefly/flash`)。
    *   维护所有 Agent 的最新相位状态。
    *   定期（例如每秒一次）计算并打印 Kuramoto 序参数（0 表示完全无序，1 表示完全同步）。
3.  修改 `observatory/experiments/run_fireflies.py`，使其在运行 Agent 的同时，并发启动 `ConvergenceMonitor`。

### 基本原理
监测器与 Agent 们共享同一个 `LocalBusConnector`，但作为独立的异步任务运行。它包含两个主要协程：
1.  **事件监听器 (`on_flash`)**: 一个回调函数，被动地接收每一个闪烁信号，并更新内部记录的该 Agent 的相位和闪烁时间。
2.  **计算循环 (`run`)**: 一个主动的循环，以固定的频率（如 1Hz）运行。在每次循环中，它会根据所有 Agent 上次闪烁的时间和相位，**推算出它们当前时刻的相位**，然后应用 Kuramoto 序参数公式进行计算，并打印结果。

这种“被动监听，主动计算”的模式确保了测量的及时性和性能，避免了在每次闪烁时都进行昂贵的全局计算。

### 标签
#intent/build #flow/ready #priority/high #comp/tests #scope/dx #ai/delegate #task/domain/testing #task/object/observatory #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建并实现收敛监测器

我们首先创建 `convergence.py` 文件，并实现 `ConvergenceMonitor` 的完整逻辑。

~~~~~act
write_file
observatory/monitors/convergence.py
~~~~~
~~~~~python
import asyncio
import time
from typing import Dict, Any

import numpy as np
from cascade.connectors.local import LocalBusConnector


class ConvergenceMonitor:
    """
    Listens to firefly flashes and periodically calculates the Kuramoto order
    parameter to measure the degree of synchronization.
    """

    def __init__(
        self, num_agents: int, period: float, connector: LocalBusConnector
    ):
        self.num_agents = num_agents
        self.period = period
        self.connector = connector

        # State: Store the phase reported at the last flash time for each agent
        self.phases_at_flash: Dict[int, float] = {}
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """Callback to update agent state when a flash is received."""
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            self.phases_at_flash[agent_id] = payload.get("phase", 0.0)
            self.last_flash_time[agent_id] = time.time()

    def _calculate_order_parameter(self) -> float:
        """
        Calculates the Kuramoto order parameter, R.
        R = 0 indicates complete desynchronization.
        R = 1 indicates complete synchronization.
        """
        if not self.phases_at_flash:
            return 0.0

        now = time.time()
        current_thetas = []

        # Extrapolate the *current* phase for each agent
        for agent_id, phase_at_flash in self.phases_at_flash.items():
            time_since_flash = now - self.last_flash_time.get(agent_id, now)
            current_phase = (phase_at_flash + time_since_flash) % self.period
            
            # Convert phase [0, period] to angle theta [0, 2*pi]
            theta = 2 * np.pi * current_phase / self.period
            current_thetas.append(theta)

        # Calculate the order parameter R = | (1/N) * sum(e^(i * theta_j)) |
        if not current_thetas:
            return 0.0
        
        # We use num_agents as N for a stable denominator, even if not all have flashed yet
        z = np.sum(np.exp(1j * np.array(current_thetas))) / self.num_agents
        return np.abs(z)

    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        bar_length = 40
        filled_length = int(bar_length * order_param)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        # Use carriage return to print on the same line
        print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0):
        """The main loop of the monitor."""
        self._is_running = True
        subscription = await self.connector.subscribe("firefly/flash", self.on_flash)
        
        print("🔭 Convergence Monitor Started...")
        try:
            while self._is_running:
                order_parameter = self._calculate_order_parameter()
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            print("\nShutting down monitor.")
            if subscription:
                await subscription.unsubscribe()

    def stop(self):
        self._is_running = False
~~~~~

#### Acts 2: 将监测器集成到实验脚本中

现在，我们修改 `run_fireflies.py`，让它在启动萤火虫的同时，也启动我们的监测器。

~~~~~act
patch_file
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
~~~~~
~~~~~python
import asyncio
import random
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector

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

    # Ensure a clean slate for each experiment run
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    
    # --- Setup Monitor ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run())

    # --- Setup Engine for Agents ---
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
        
        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash", # All agents listen and talk on the same topic
        )
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.wait_for(all_tasks, timeout=duration_seconds)
    except asyncio.TimeoutError:
        print(f"\n✅ Experiment finished after {duration_seconds}s.")
    finally:
        # Gracefully stop everything
        monitor.stop()
        if not all_tasks.done():
            all_tasks.cancel()
            # Await both agents and monitor to ensure clean shutdown
            await asyncio.gather(all_tasks, monitor_task, return_exceptions=True)
        else:
             await asyncio.gather(monitor_task, return_exceptions=True)
        
        await engine.connector.disconnect()
~~~~~

### 下一步建议
一切准备就绪。我们已经创造了生命，建立了宇宙，并架设了观测台。

现在，是时候按下“运行”按钮，见证奇迹的时刻了。请在你的终端中，从项目根目录执行以下命令，来启动我们的第一个“萤火虫”实验：

`python -m observatory.experiments.run_fireflies`

观察同步指示条和序参数的变化。如果我们的理论是正确的，你将看到序参数从一个接近 0 的随机值，随着时间的推移，逐渐、稳定地增长，最终趋近于 1。

这将是“涌现”的直接证据。
