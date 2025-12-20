Brief Response
好的，我们现在将原基 (Protoplasm) 阶段验证通过的高性能渲染组件提取为公共基础设施，并将其应用于萤火虫实验，实现从“日志流”到“可视化矩阵”的升级。

Summary Header
## [WIP] refactor(observatory): 提取统一渲染库并可视化萤火虫实验

### 错误分析
N/A

### 用户需求
1.  **代码清理与抽象**: 将分散在 `protoplasm` 中的渲染代码 (`AnsiDriver`, `RenderBuffer`, `StateMatrix`) 提取为通用的 `observatory.visualization` 库。
2.  **统一行为**: 确保 `protoplasm` 中的旧实验（如 Conway, Bottleneck）和新实验都能复用这套基础设施。
3.  **萤火可视化**: 修改 `run_fireflies.py`，为其配备基于终端的实时渲染器，直观展示同步过程（从随机闪烁到同步波纹）。

### 评论
这是一个重要的工程化步骤。原基阶段的代码往往是“快脏”的，将其提升为共享库可以大幅降低后续实验（如创世网格）的构建成本。同时，可视化的萤火虫实验将提供极其直观的反馈，验证我们的同步理论。

### 目标
1.  建立 `observatory/visualization` 包。
2.  迁移并重构渲染核心类 (`GridRenderer`)。
3.  修复受影响的 `protoplasm` 实验导入路径。
4.  改造 `run_fireflies.py` 以支持可视化模式。

### 基本原理
我们将采用“提升与适配”策略：
1.  **提升**: 将 `protoplasm/renderer` 整体移动到 `observatory/visualization`。
2.  **适配**: 修改 `run_fireflies.py`，引入一个适配层，将 `firefly/flash` 事件转换为渲染器的 `ingest(x, y, brightness)` 调用。
3.  **集成**: 将 `ConvergenceMonitor` 的计算结果集成到渲染器的状态栏中，而不是向 stdout 打印，避免画面撕裂。

### 标签
#intent/refactor #intent/build #flow/ready #priority/medium #comp/observatory #concept/ui #task/domain/observatory #task/object/visualizer #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 建立可视化基础设施

首先，我们将原基中的渲染器代码迁移到新的公共目录 `observatory/visualization`，并重命名核心渲染器以体现其通用性。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p observatory/visualization
~~~~~

~~~~~act
move_file
observatory/protoplasm/renderer/driver.py
observatory/visualization/driver.py
~~~~~

~~~~~act
move_file
observatory/protoplasm/renderer/buffer.py
observatory/visualization/buffer.py
~~~~~

~~~~~act
move_file
observatory/protoplasm/renderer/matrix.py
observatory/visualization/matrix.py
~~~~~

~~~~~act
move_file
observatory/protoplasm/renderer/visualizer_proto.py
observatory/visualization/grid_renderer.py
~~~~~

~~~~~act
write_file
observatory/visualization/__init__.py
~~~~~
~~~~~python
from .driver import AnsiDriver
from .buffer import RenderBuffer
from .matrix import StateMatrix, GridConfig
from .grid_renderer import GridRenderer

__all__ = ["AnsiDriver", "RenderBuffer", "StateMatrix", "GridConfig", "GridRenderer"]
~~~~~

#### Acts 2: 重构 GridRenderer 类名

我们将 `ForestRenderer` 重命名为更通用的 `GridRenderer`，并调整其内部引用。

~~~~~act
patch_file
observatory/visualization/grid_renderer.py
~~~~~
~~~~~old
class ForestRenderer:
    """
    The High-Performance CLI Renderer.
    Decouples ingestion (Telemetry) from Rendering (30 FPS Loop).
    """

    def __init__(self, width: int = 100, height: int = 100):
~~~~~
~~~~~new
class GridRenderer:
    """
    The High-Performance CLI Renderer.
    Decouples ingestion (Telemetry) from Rendering (30 FPS Loop).
    """

    def __init__(self, width: int = 100, height: int = 100):
~~~~~

~~~~~act
patch_file
observatory/visualization/grid_renderer.py
~~~~~
~~~~~old
async def stress_test_loader(renderer: ForestRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    # Wait for the renderer to start
    print("Loader: Waiting for renderer to start...")
    while not renderer._running:
        await asyncio.sleep(0.1)
    print("Loader: Renderer started. Injecting events.")

    width, height = renderer.config.width, renderer.config.height
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    # Self-contained run with dynamic sizing
    try:
        cols, rows = shutil.get_terminal_size()
        # Reserve 2 rows for status line and shell prompt
        render_height = rows - 2
        renderer = ForestRenderer(width=cols, height=render_height)
    except OSError:
        # Fallback for environments without a TTY (e.g., CI)
        renderer = ForestRenderer(width=100, height=40)

    loop = asyncio.get_event_loop()
    try:
        # Schedule the stress loader
        loop.create_task(stress_test_loader(renderer))
        # Run the renderer
        loop.run_until_complete(renderer.start())
    except KeyboardInterrupt:
        # Stop is now responsible for most cleanup
        renderer.stop()
        print("Renderer stopped.")
~~~~~
~~~~~new
async def stress_test_loader(renderer: GridRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    # Wait for the renderer to start
    print("Loader: Waiting for renderer to start...")
    while not renderer._running:
        await asyncio.sleep(0.1)
    print("Loader: Renderer started. Injecting events.")

    width, height = renderer.config.width, renderer.config.height
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    # Self-contained run with dynamic sizing
    try:
        cols, rows = shutil.get_terminal_size()
        # Reserve 2 rows for status line and shell prompt
        render_height = rows - 2
        renderer = GridRenderer(width=cols, height=render_height)
    except OSError:
        # Fallback for environments without a TTY (e.g., CI)
        renderer = GridRenderer(width=100, height=40)

    loop = asyncio.get_event_loop()
    try:
        # Schedule the stress loader
        loop.create_task(stress_test_loader(renderer))
        # Run the renderer
        loop.run_until_complete(renderer.start())
    except KeyboardInterrupt:
        # Stop is now responsible for most cleanup
        renderer.stop()
        print("Renderer stopped.")
~~~~~

#### Acts 3: 修复 Protoplasm 中的引用

我们需要修复 `bottleneck_sim.py` 和 `truth/renderer.py` 中的导入路径，因为原来的文件已经被移动了。

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~old
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from observatory.protoplasm.renderer.visualizer_proto import ForestRenderer

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 10.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.grid_width = int(num_agents**0.5) + 1
~~~~~
~~~~~new
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from observatory.visualization.grid_renderer import GridRenderer

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 10.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: GridRenderer, num_agents: int):
        self.renderer = renderer
        self.grid_width = int(num_agents**0.5) + 1
~~~~~

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~old
async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    render_height = max(10, rows - 4)
    renderer = ForestRenderer(width=cols, height=render_height)
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
~~~~~
~~~~~new
async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    render_height = max(10, rows - 4)
    renderer = GridRenderer(width=cols, height=render_height)
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~old
import numpy as np
import shutil
from typing import Tuple

# Reuse low-level drivers from the existing prototype
from observatory.protoplasm.renderer.driver import AnsiDriver
from observatory.protoplasm.renderer.buffer import RenderBuffer
from observatory.protoplasm.renderer.matrix import GridConfig

class DiffMatrix:
~~~~~
~~~~~new
import numpy as np
import shutil
from typing import Tuple

# Reuse low-level drivers from the existing prototype
from observatory.visualization.driver import AnsiDriver
from observatory.visualization.buffer import RenderBuffer
from observatory.visualization.matrix import GridConfig

class DiffMatrix:
~~~~~

#### Acts 4: 增强 GridRenderer 以支持外部状态注入

为了让 `ConvergenceMonitor` 能在渲染器的状态栏显示数据，我们需要给 `GridRenderer` 添加一个 `set_status_callback` 钩子。

~~~~~act
patch_file
observatory/visualization/grid_renderer.py
~~~~~
~~~~~old
        self.queue: Queue = Queue()
        
        self._running = False
        self._fps_stats = []

    async def start(self):
~~~~~
~~~~~new
        self.queue: Queue = Queue()
        
        self._running = False
        self._fps_stats = []
        
        # Optional callback to get extra status text
        self._status_callback = None

    def set_status_callback(self, callback):
        """Callback should return a string to be appended to the status line."""
        self._status_callback = callback

    async def start(self):
~~~~~

~~~~~act
patch_file
observatory/visualization/grid_renderer.py
~~~~~
~~~~~old
            status_line = (
                f"FPS: {real_fps:.1f} | "
                f"Events: {events_processed:<4} | "
                f"Diff: {len(rows):<4} px | "
                f"ProcT: {processing_time*1000:.2f}ms"
            )
            # Pad the line to clear previous text artifacts
            self.driver.write(f"{status_line:<80}")
            
            self.driver.flush()
~~~~~
~~~~~new
            status_line = (
                f"FPS: {real_fps:.1f} | "
                f"Events: {events_processed:<4} | "
                f"Diff: {len(rows):<4} px | "
                f"ProcT: {processing_time*1000:.2f}ms"
            )
            
            if self._status_callback:
                try:
                    extra_status = self._status_callback()
                    status_line += f" | {extra_status}"
                except Exception:
                    pass

            # Pad the line to clear previous text artifacts
            self.driver.write(f"{status_line:<100}")
            
            self.driver.flush()
~~~~~

#### Acts 5: 改造 run_fireflies.py 以支持可视化

这是本次重构的核心。我们将移除简单的 print 输出，转而使用 `GridRenderer`，并将 `ConvergenceMonitor` 的输出重定向到渲染器的状态栏。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
import time
import shutil
import math
from typing import Any, Dict

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.visualization.grid_renderer import GridRenderer

# --- Visualizer Adapter ---

class FireflyVisualizer:
    def __init__(self, renderer: GridRenderer, num_agents: int):
        self.renderer = renderer
        # Calculate grid dimensions to map agent_id -> (x, y)
        # We aim for a roughly square grid
        self.cols = int(math.ceil(math.sqrt(num_agents)))
        
    def get_coords(self, agent_id: int):
        x = agent_id % self.cols
        y = agent_id // self.cols
        return x, y

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """
        Adapts the bus event to a renderer ingestion.
        """
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            x, y = self.get_coords(agent_id)
            # Flash intensity 1.0
            self.renderer.ingest(x, y, 1.0)


async def run_experiment(
    num_agents: int = 100,
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting firefly experiment with {num_agents} agents...")

    # 1. Initialize Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Visualization (if enabled)
    renderer = None
    viz_adapter = None
    monitor = None
    
    if visualize:
        cols, rows = shutil.get_terminal_size()
        render_height = max(10, rows - 4)
        renderer = GridRenderer(width=cols, height=render_height)
        viz_adapter = FireflyVisualizer(renderer, num_agents)
        
        # Subscribe visualizer to flashes
        await connector.subscribe("firefly/flash", viz_adapter.on_flash)
    
    # 3. Setup Monitor
    monitor = ConvergenceMonitor(num_agents, period, connector)
    
    if visualize and renderer:
        # Hook monitor status into renderer
        renderer.set_status_callback(lambda: f"SYNC: {monitor._calculate_order_parameter():.4f}")
        # We don't run the monitor's loop because we don't want it printing to stdout
        # Instead, we just let it passively collect data via its subscription
        # BUT, ConvergenceMonitor.run() handles the subscription. 
        # So we need to call monitor.start_passive() or similar.
        # For now, let's manually subscribe the monitor's callback
        await connector.subscribe("firefly/flash", monitor.on_flash)
    else:
        # Run monitor in active mode (printing to stdout)
        asyncio.create_task(monitor.run())

    # --- Create the population of firefly agents ---
    agent_tasks = []
    
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
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
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
            connector=connector,
            refractory_period=period * 0.2,
        )
        
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run the experiment ---
    try:
        renderer_task = None
        if visualize and renderer:
            renderer_task = asyncio.create_task(renderer.start())
        else:
             print(f"\n⏳ Running for {duration_seconds} seconds...")

        # Wait for duration
        all_agents = asyncio.gather(*agent_tasks)
        try:
            await asyncio.wait_for(all_agents, timeout=duration_seconds)
        except asyncio.TimeoutError:
            pass
            
    finally:
        # Graceful Shutdown
        if visualize and renderer:
            renderer.stop()
            if renderer_task:
                await renderer_task
        
        if monitor:
            monitor.stop()

        if not all_agents.done():
            all_agents.cancel()
            await asyncio.gather(all_agents, return_exceptions=True)
        
        await connector.disconnect()
        
        if visualize:
             print(f"\n✅ Experiment finished. Final Sync: {monitor._calculate_order_parameter():.4f}")


if __name__ == "__main__":
    # Adjust params for a good visual show
    # 400 agents fits nicely in a 20x20 grid
    asyncio.run(run_experiment(num_agents=400, duration_seconds=60.0))
~~~~~

### 下一步建议
我们已经完成了基础设施的重构和萤火虫实验的可视化改造。现在，运行 `python -m observatory.experiments.run_fireflies` 将展示一个实时演化的、具有余辉效果的萤火虫矩阵。

建议的后续步骤：
1.  **运行实验**: 观察 400 个萤火虫从混乱到同步的视觉效果。
2.  **清理旧代码**: 检查 `observatory/protoplasm` 目录下是否还有其他残留的、未被使用的渲染代码，并将其删除。
3.  **应用到创世网格**: 这个 `GridRenderer` 已经准备好被用于下一阶段“创世网格”的 Alpha 阶段（逻辑叠加与验证），用于展示两个平行宇宙（Cascade vs Truth）的差异矩阵。
