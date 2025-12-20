我们将基于 Protoplasm 的成果，提炼出一套通用的、支持“正方形像素”和丰富配色的可视化引擎 `UniGrid`，并将其应用于瓶颈模拟和萤火虫实验中。

## [WIP] refactor(proto): 统一渲染基座并实现萤火虫可视化

### 用户需求
1.  **统一渲染行为**: 将 `ForestRenderer` (CLI 性能优化) 和 `TruthRenderer` (双字符正方形渲染) 的优点合并，消除重复代码。
2.  **正方形像素**: 推广 `██` (双宽字符) 渲染模式，以获得 1:1 的视觉比例，使网格看起来像 Golly/像素画。
3.  **增强色彩**: 支持类似 Golly 的多级亮度/颜色映射，而非简单的三色状态。
4.  **可视化萤火虫**: 为 `run_fireflies.py` 添加可视化，直观展示同步过程。
5.  **可视化瓶颈**: 升级 `bottleneck_sim.py` 的渲染效果。

### 评论
这是一个非常棒的工程化步骤。在原基阶段，我们为了快速验证（Fail Fast），允许了代码的拷贝粘贴和特化。现在，既然 CLI 渲染已经被证明是可行的且必要的观测手段，将其提炼为通用的 `observatory` 基础设施是合乎逻辑的。正方形像素和丰富的色彩将极大地提升我们对“涌现现象”的感知能力——很多时候，模式（Pattern）只有在正确的视觉比例和色彩深度下才能被肉眼捕捉。

### 目标
1.  创建 `observatory/protoplasm/renderer/palette.py`: 定义颜色映射接口和预设（Firefly, Heatmap 等）。
2.  创建 `observatory/protoplasm/renderer/unigrid.py`: 统一的、基于双缓冲和双字符宽度的渲染引擎。
3.  重构 `bottleneck_sim.py`: 使用新的 `UniGrid` 和 `Palette`。
4.  升级 `run_fireflies.py`: 接入 `UniGrid`，实现相位的实时热力图。

### 基本原理
我们将采用 **"State -> Palette -> Physical Buffer"** 的管线设计。
1.  **State**: 仍然是 numpy 矩阵，存储纯数值（如相位 `0.0-1.0` 或 状态枚举）。
2.  **Palette**: 负责将数值映射为 ANSI 颜色代码。
3.  **Physical Buffer**: `UniGrid` 负责将逻辑上的 `(x, y)` 扩展为物理上的 `(x*2, y)` 和 `(x*2+1, y)`，并填充 `█` 字符，从而实现正方形像素。这种“矢量化扩展”比在 Python 循环中打印两次要快得多。

### 标签
#intent/refine #flow/draft #priority/medium #comp/protoplasm #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/unigrid #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建调色板系统 (`palette.py`)

我们将定义一个颜色处理模块，支持从数值到 ANSI 颜色的渐变映射。这允许我们定义“热力图”风格的配色。

~~~~~act
write_file
observatory/protoplasm/renderer/palette.py
~~~~~
~~~~~python
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Color:
    r: int
    g: int
    b: int

    def to_ansi_bg(self) -> str:
        """Returns ANSI escape code for background color."""
        # Using 24-bit TrueColor: \033[48;2;R;G;Bm
        return f"\033[38;2;{self.r};{self.g};{self.b}m"

class Palettes:
    """Predefined color palettes for simulations."""

    @staticmethod
    def _interpolate(val: float, c1: Color, c2: Color) -> str:
        r = int(c1.r + (c2.r - c1.r) * val)
        g = int(c1.g + (c2.g - c1.g) * val)
        b = int(c1.b + (c2.b - c1.b) * val)
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # We handle this utilizing numpy vectorization for speed would be ideal,
        # but for simplicity in ANSI generation, we might use a lookup or mask.
        # Here we define 3 discrete levels for performance, or use a mapped array.
        
        # Initialize with Dark (Background)
        # \033[38;2;20;20;30m (Very Dark Blue)
        colors = np.full(brightness.shape, '\033[38;2;30;30;40m', dtype='<U24')
        
        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = '\033[38;2;100;40;40m'

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = '\033[38;2;200;120;0m'
        
        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = '\033[38;2;255;255;200m'
        
        return colors

    @staticmethod
    def bottleneck(states: np.ndarray) -> np.ndarray:
        """
        Maps states to bottleneck visualizer colors.
        0.0: Idle (Dim)
        0.5: Waiting (Cyan)
        1.0: Running (White/Green)
        """
        colors = np.full(states.shape, '\033[38;2;40;40;40m', dtype='<U24') # Dim Gray
        
        # Waiting (Cyan)
        mask_wait = (states > 0.4) & (states < 0.8)
        colors[mask_wait] = '\033[38;2;0;200;200m'
        
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors
~~~~~

#### Acts 2: 创建统一网格渲染器 (`unigrid.py`)

这是核心重构。它结合了 `ForestRenderer` 的异步摄入循环和 `TruthRenderer` 的双宽字符逻辑。

~~~~~act
write_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
import asyncio
import time
import shutil
import numpy as np
from asyncio import Queue
from dataclasses import dataclass
from typing import Callable, Optional

from .driver import AnsiDriver
from .buffer import RenderBuffer
from .matrix import StateMatrix, GridConfig

class UniGridRenderer:
    """
    Unified Grid Renderer.
    - Uses double-width characters ('██') for square pixels.
    - Decoupled State (Logic) from Appearance (Palette).
    - Asynchronous ingestion loop.
    """

    def __init__(
        self, 
        width: int = 0, 
        height: int = 0, 
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_rate: float = 0.05
    ):
        # Auto-detect size if not provided
        cols, rows = shutil.get_terminal_size()
        # Logical width is half of physical columns because we use 2 chars per pixel
        self.logical_width = width if width > 0 else cols // 2
        # Reserve lines for UI
        self.logical_height = height if height > 0 else max(10, rows - 3)
        
        self.config = GridConfig(
            width=self.logical_width, 
            height=self.logical_height, 
            decay_rate=decay_rate
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func
        
        # Physical buffers are 2x width
        self.phys_width = self.logical_width * 2
        self.buffer_prev = RenderBuffer(self.phys_width, self.logical_height)
        self.buffer_curr = RenderBuffer(self.phys_width, self.logical_height)
        
        self.driver = AnsiDriver()
        self.queue: Queue = Queue()
        self._running = False

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))

    async def start(self):
        self._running = True
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()
        await self._render_loop()

    def stop(self):
        self._running = False
        # Do not close immediately, let the loop exit naturally or force cleanup here?
        # Usually loop exit is cleaner, but for forced stop:
        self.driver.show_cursor()
        self.driver.move_to(self.logical_height + 2, 0)
        self.driver.flush()

    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        while self._running:
            loop_start = time.perf_counter()
            
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics (Decay)
            self.matrix.decay()
            
            # 3. Map to Physical Buffer
            # Get colors from palette (H, W)
            logical_colors = self.palette_func(self.matrix.brightness)
            
            # Expand to physical (H, W*2)
            # We use '█' for all visible pixels
            # If color is 'default dark', maybe print space? 
            # For Golly style, we usually print blocks everywhere.
            
            phys_colors = np.repeat(logical_colors, 2, axis=1)
            
            # Update Current Buffer
            self.buffer_curr.chars[:] = '█' # Solid block
            self.buffer_curr.colors = phys_colors
            
            # 4. Diff & Draw
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            if len(rows) > 0:
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                # Buffer writes
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                # Update prev
                # Optim: Only copy diffs or swap references if we reconstruct full buffer?
                # RenderBuffer implementation expects in-place updates usually.
                self.buffer_prev.chars[rows, cols] = chars
                self.buffer_prev.colors[rows, cols] = colors
                
            # 5. Stats Line
            elapsed = time.perf_counter() - loop_start
            fps = 1.0 / (elapsed + 0.001)
            self.driver.move_to(self.logical_height + 1, 0)
            self.driver.write(f"UniGrid | FPS: {fps:.1f} | Updates: {len(rows)}", '\033[97m')
            self.driver.flush()
            
            # 6. Sleep
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)
            
        # Cleanup on exit
        self.driver.show_cursor()
        self.driver.flush()
~~~~~

#### Acts 3: 升级瓶颈模拟 (`bottleneck_sim.py`)

使用新的 `UniGrid` 替换原本的 `ForestRenderer`。

~~~~~act
write_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
import asyncio
import random
import shutil
import time
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint

# New Renderer Imports
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 15.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: UniGridRenderer, num_agents: int):
        self.renderer = renderer
        # Ensure grid is roughly square logic
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event: Any):
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return
            
        try:
            parts = event.task_name.split("_")
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = self.get_coords(agent_id)
            
            # Map Events to States for Palette
            # 1.0 = Running (White)
            # 0.5 = Waiting (Cyan)
            # 0.0 = Idle (Dim)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    self.renderer.ingest(x, y, 1.0)
                elif isinstance(event, TaskBlocked):
                    self.renderer.ingest(x, y, 0.5)
                elif isinstance(event, TaskExecutionFinished):
                    self.renderer.ingest(x, y, 0.0)
                    
        except (IndexError, ValueError):
            pass

# --- Agent Definition ---

def make_agent_workflow(i: int):
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

# --- Main ---

async def run_simulation():
    # 1. Setup New Renderer
    # Note: We rely on auto-sizing, passing only palette
    renderer = UniGridRenderer(palette_func=Palettes.bottleneck, decay_rate=0.0)
    
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, viz.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 3. Apply Constraint
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 4. Launch Agents
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = []
    for i in range(NUM_AGENTS):
        tasks.append(asyncio.create_task(engine.run(make_agent_workflow(i))))
        
    # 5. Run Visualization
    try:
        renderer_task = asyncio.create_task(renderer.start())
        await asyncio.sleep(DURATION)
    finally:
        renderer.stop()
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
~~~~~

#### Acts 4: 升级萤火虫实验 (`run_fireflies.py`)

为萤火虫实验添加视觉反馈。我们需要在 `ConvergenceMonitor` 旁边（或者替代它）引入可视化器。

为了保持整洁，我们把可视化逻辑直接集成进脚本，监听 `flash` 事件。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
import time
from typing import Dict, Any

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# Visualization
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

async def run_experiment(
    num_agents: int = 400, # Increased for better visual field (20x20)
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    if visualize:
        print(f"🔥 Starting VISUAL firefly experiment with {num_agents} agents...")
    else:
        print(f"🔥 Starting headless firefly experiment...")

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

    renderer = None
    renderer_task = None
    
    if visualize:
        # Define visualizer mapping
        grid_width = int(num_agents**0.5)
        # Handle non-perfect squares
        if grid_width * grid_width < num_agents: grid_width += 1
        
        renderer = UniGridRenderer(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                # Ingest a "Flash" (1.0 brightness)
                renderer.ingest(x, y, 1.0)
        
        # Subscribe visualizer to bus
        await connector.subscribe("firefly/flash", on_flash_visual)
        renderer_task = asyncio.create_task(renderer.start())

    # --- Create Agents ---
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

    # --- Run ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        # If visualizing, wait for duration
        await asyncio.sleep(duration_seconds)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        monitor.stop()
        if renderer: renderer.stop()
        
        if not all_tasks.done():
            all_tasks.cancel()
            await asyncio.gather(all_tasks, return_exceptions=True)
            
        await asyncio.gather(monitor_task, return_exceptions=True)
        if renderer_task:
            if not renderer_task.done(): renderer_task.cancel()
            await renderer_task
        
        await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~

### 下一步建议
我们已经完成了通用渲染层 `UniGrid` 的构建和集成。现在，我们的“原基”不仅是一个概念验证，更拥有了一套漂亮的、可复用的观测仪表板。

建议进行以下后续操作：
1.  **迁移 TruthRenderer**: 考虑是否也将 Conway 生命游戏的 `TruthRenderer` 迁移到 `UniGrid` 之上，虽然它有特殊的 Diff 逻辑，但可以通过自定义 Palette 或扩展 UniGrid 来实现。
2.  **基准测试**: 比较 `UniGrid` (双宽字符 + 调色板计算) 与原始 `ForestRenderer` 的性能差异，确保美观没有带来过大的性能惩罚。
3.  **交互性**: 探索是否允许用户通过键盘输入（`asyncio` 监听 `stdin`）来实时调整 `UniGrid` 的参数（如衰减率）。
