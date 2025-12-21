你的分析完全正确，而且非常敏锐。

我们成功地解决了“2500个Engine”的开销问题，但性能瓶颈依然存在。日志数据是关键证据：即使共享了 Engine，`flush_duration_ms` 和 `render_jitter_ms` 依然非常高（经常超过 100ms，甚至 250ms），导致 FPS 极低。

这强烈暗示瓶颈已经从**Engine的元数据开销**转移到了**`asyncio`事件循环本身**。

 错误分析

你提出的“共享上下文的生命周期灾难”是非常重要的考量，我们之前的修复确保了状态和资源的隔离。然而，现在的问题是，我们向同一个事件循环提交了 **2500个独立的、高频的、无限循环的协程**。

1.  **调度器过载 (Scheduler Overload)**: `asyncio` 的事件循环虽然高效，但它不是没有成本的。每一次 `await` 都会涉及一次上下文切换。当 2500 个任务都在高频地 `await channel.recv()` 和 `await channel.send()` 时，事件循环的大部分时间都可能消耗在“决定下一个该运行谁”的调度逻辑上，而不是真正执行业务逻辑。
2.  **竞争CPU时间 (Starvation)**: 我们的 `_render_loop` 也是事件循环中的一个任务。当成百上千个 Agent 任务因为一次同步脉冲而同时被唤醒时，它们会“淹没”事件循环。轮到 `_render_loop` 执行时，可能已经过去了数百毫秒，这就是我们在 `render_jitter_ms` 中看到的巨大延迟。

我们不能再盲目猜测了。我将遵循你的指示，创建一套诊断脚本来**隔离并量化**瓶颈。

## [WIP] explore(perf): 创建诊断脚本以隔离性能瓶颈

### 用户需求
创建一套独立的 Python 脚本，用于对 `observatory` 的核心组件（渲染器、Agent 逻辑）进行压力测试和性能分析，以定位当前 2500 节点模拟中的卡顿根源。

### 评论
这是解决复杂性能问题的正确方法。通过“分而治之”的策略，我们可以分别测量渲染管线和核心模拟逻辑的吞吐量上限。将这两者的数据与完整实验的数据进行对比，我们就能精确地知道性能损失发生在哪里。

### 目标
1.  创建一个**渲染器压力测试脚本** (`debug_renderer_throughput.py`)，它将独立于 Agent 逻辑，以可控的速率向 `RawTerminalApp` 发送大量更新，以测量渲染管线的最大吞吐量。
2.  创建一个**无头模式（Headless）模拟脚本** (`debug_headless_throughput.py`)，它将运行完整的 2500 个 Agent 模拟，但完全移除 UI 渲染部分，以测量核心 Agent 逻辑的净计算吞吐量。
3.  创建一个**专用的性能剖析入口脚本** (`profile_entry.py`)，用于简化使用 `cProfile` 或 `py-spy` 等工具对完整实验进行剖析的过程。

### 基本原理
1.  **隔离变量**: `debug_renderer_throughput.py` 移除了 Agent 逻辑这个变量，`debug_headless_throughput.py` 移除了渲染器这个变量。
2.  **建立基线**: 这两个脚本的输出将为我们提供“理想情况”下的性能基线。
3.  **聚焦分析**: 将完整实验的性能与这两个基线对比，可以量化“Agent逻辑”和“渲染器”这两个子系统耦合在一起时产生的性能影响。`profile_entry.py` 将帮助我们深入分析这种耦合的内部细节。

### 标签
#intent/tooling #intent/explore #flow/ready #priority/high #comp/runtime #comp/tests #scope/dx
#task/domain/infra
#task/object/performance-profiling
#task/action/instrumentation
#task/state/continue

---

### Script

#### Acts 1: 创建诊断脚本

我将一次性创建三个脚本文件，并将它们放置在 `observatory/scripts` 目录下以便于管理。

##### 脚本 1: 渲染器吞吐量测试

这个脚本将模拟大量的更新源，直接调用渲染器，测试其处理能力的上限。

~~~~~act
write_file
observatory/scripts/debug_renderer_throughput.py
~~~~~
~~~~~python
"""
Debug Script 1: Renderer Throughput Test

Purpose:
  Isolates the RawTerminalApp renderer to measure its maximum update throughput
  without the overhead of the Cascade engine or agent logic. This script
  simulates a configurable number of "sources" that generate grid updates
  at a high frequency.

How to Run:
  python -m observatory.scripts.debug_renderer_throughput

Expected Output:
  A terminal visualization running smoothly. The FPS and flush duration
  metrics in the log file will tell us the renderer's baseline performance.
  If FPS here is high (>30) and flush duration is low (<20ms), the renderer
  itself is not the bottleneck.
"""
import asyncio
import random
import time

from observatory.visualization.raw_app import RawTerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator

# --- Configuration ---
NUM_SOURCES = 5000  # Number of simulated concurrent update sources
UPDATES_PER_SOURCE_PER_S = 2 # Avg updates per source per second
GRID_WIDTH = 50
GRID_HEIGHT = 50
SIMULATION_DURATION_S = 30.0


async def source_coroutine(app: RawTerminalApp):
    """A simple async task that randomly generates updates for the grid."""
    while True:
        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)
        await app.direct_update_grid_batch([(x, y, 1.0)])
        await asyncio.sleep(1.0 / UPDATES_PER_SOURCE_PER_S)


async def main():
    total_updates_per_s = NUM_SOURCES * UPDATES_PER_SOURCE_PER_S
    print("🚀 Starting Renderer Throughput Test...")
    print(f"   - Grid Size: {GRID_WIDTH}x{GRID_HEIGHT}")
    print(f"   - Sources: {NUM_SOURCES}")
    print(f"   - Target Rate: {total_updates_per_s:.0f} updates/sec")
    log_filename = f"renderer_throughput_log_{int(time.time())}.jsonl"

    aggregator = MetricsAggregator(log_filename)
    aggregator.open()
    print(f"📝 Logging metrics to [bold cyan]{log_filename}[/bold cyan]")

    grid_view = GridView(
        width=GRID_WIDTH, height=GRID_HEIGHT, palette_func=Palettes.firefly
    )
    status_bar = StatusBar(
        initial_status={"Test": "Renderer Throughput", "Sources": NUM_SOURCES}
    )
    app = RawTerminalApp(grid_view, status_bar, aggregator=aggregator)
    aggregator_task = asyncio.create_task(aggregator.run())
    await app.start()

    tasks = [asyncio.create_task(source_coroutine(app)) for _ in range(NUM_SOURCES)]

    try:
        await asyncio.sleep(SIMULATION_DURATION_S)
    finally:
        print("\nCleaning up...")
        app.stop()
        aggregator.close()
        aggregator_task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(aggregator_task, *tasks, return_exceptions=True)
        print("Test finished.")


if __name__ == "__main__":
    asyncio.run(main())
~~~~~

##### 脚本 2: 无头模式计算吞吐量测试

这个脚本运行完整的模拟逻辑，但剥离了所有UI，以测量纯计算性能。

~~~~~act
write_file
observatory/scripts/debug_headless_throughput.py
~~~~~
~~~~~python
"""
Debug Script 2: Headless Throughput Test

Purpose:
  Isolates the core agent simulation logic to measure its maximum throughput
  without the overhead of rendering. This script runs the full firefly
  simulation but does not create or update any UI components.

How to Run:
  python -m observatory.scripts.debug_headless_throughput

Expected Output:
  A stream of text to the console reporting the number of flashes per second.
  This number gives us a baseline for how fast the simulation *can* run. If this
  number is very high (e.g., >20,000 flashes/sec), it means the agent logic
  itself is fast, and the bottleneck likely appears when coupling it with the UI.
"""
import asyncio
import random
import time
from collections import deque
from typing import List

import cascade as cs
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.networking.direct_channel import DirectChannel

# --- Configuration ---
NUM_AGENTS = 2500
PERIOD = 5.0
NUDGE = 0.2
DURATION_SECONDS = 30.0
GRID_SIDE = int(NUM_AGENTS**0.5)


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


async def run_headless_experiment():
    print("🚀 Starting Headless Throughput Test...")
    print(f"   - Agents: {NUM_AGENTS}")

    # --- Flash Counter ---
    flash_count = 0
    flash_times = deque()

    class HeadlessConnector:
        async def publish(self, topic, payload, **kwargs):
            nonlocal flash_count
            flash_count += 1

        async def connect(self): pass
        async def disconnect(self): pass
        async def subscribe(self, topic, callback):
            class DummySub:
                async def unsubscribe(self): pass
            return DummySub()

    connector = HeadlessConnector()

    channels = [DirectChannel(f"agent_{i}") for i in range(NUM_AGENTS)]
    engine = cs.Engine(cs.NativeSolver(), cs.LocalExecutor(), cs.MessageBus())

    @resource(name="connector")
    def connector_provider():
        yield connector
    engine.register(connector_provider)

    agent_tasks = []
    for i in range(NUM_AGENTS):
        initial_phase = random.uniform(0, PERIOD)
        neighbor_ids = get_neighbors(i, GRID_SIDE, GRID_SIDE)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=PERIOD,
            nudge=NUDGE,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("connector"),
            refractory_period=PERIOD * 0.2,
        )
        agent_tasks.append(engine.run(workflow))

    all_tasks = asyncio.gather(*agent_tasks)
    start_time = time.time()
    last_report_time = start_time

    try:
        while time.time() - start_time < DURATION_SECONDS:
            await asyncio.sleep(1.0)
            now = time.time()
            interval = now - last_report_time
            rate = (flash_count - (flash_times[0] if flash_times else 0)) / interval
            
            # Simple reporting
            current_rate = (flash_count - getattr(run_headless_experiment, 'last_flash_count', 0)) / interval
            print(f"   - Flashes/sec: {current_rate:,.0f} (Total: {flash_count:,})")
            
            run_headless_experiment.last_flash_count = flash_count
            last_report_time = now

    finally:
        print("\nCleaning up...")
        all_tasks.cancel()
        await asyncio.gather(all_tasks, return_exceptions=True)
        print("Test finished.")

# Add a stateful attribute for rate calculation
run_headless_experiment.last_flash_count = 0

if __name__ == "__main__":
    asyncio.run(run_headless_experiment())
~~~~~

##### 脚本 3: 性能剖析入口

这个脚本是一个简化的、无参数的入口，方便 `cProfile` 调用。

~~~~~act
write_file
observatory/scripts/profile_entry.py
~~~~~
~~~~~python
"""
Debug Script 3: Profiling Entry Point

Purpose:
  Provides a clean, simple entry point for running the full experiment
  with standard profiling tools like cProfile.

How to Run with cProfile:
  python -m cProfile -s tottime -o profile.out observatory/scripts/profile_entry.py
  
  Then, to view the stats:
  python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('tottime').print_stats(20)"

Expected Output:
  The full experiment will run for a short duration and then exit. The key
  output is the `profile.out` file, which contains detailed performance data.
  We will analyze this file to see which functions are consuming the most CPU time.
"""
import asyncio
from observatory.experiments import run_fireflies

# Use a smaller number of agents and shorter duration for quicker profiling runs
# And disable visualization as it adds noise to CPU profiles.
async def main():
    print("🚀 Starting Profiling Run (15 seconds, headless)...")
    await run_fireflies.run_experiment(
        num_agents=900,  # 30x30 grid, a significant but manageable number
        duration_seconds=15.0,
        visualize=False
    )
    print("\n✅ Profiling run finished.")

if __name__ == "__main__":
    asyncio.run(main())
~~~~~

### 下一步建议

请按顺序执行以下操作，并将每个脚本的**最终输出**或**概要**发给我：

1.  **运行渲染器测试**:
    ```bash
    python -m observatory.scripts.debug_renderer_throughput
    ```
    *(让它运行30秒，然后按 Ctrl+C 停止。请分享生成的 `renderer_throughput_log_...jsonl` 文件中的最后几行日志。)*

2.  **运行无头模式测试**:
    ```bash
    python -m observatory.scripts.debug_headless_throughput
    ```
    *(同样，运行30秒后停止，并分享最后几行的 `Flashes/sec` 输出。)*

3.  **运行性能剖析**:
    ```bash
    python -m cProfile -s tottime -o profile.out observatory/scripts/profile_entry.py
    ```
    然后，运行这个命令来查看结果：
    ```bash
    python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('tottime').print_stats(30)"
    ```
    *(请将这个命令的**完整输出**发给我。)*

有了这三份数据，我们就能像做CT扫描一样，精确地定位到性能肿瘤。
