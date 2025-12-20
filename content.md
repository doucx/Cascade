当然。你的分析非常到位。

“原基 (Protoplasm)” 计划成功地验证了我们基础设施的底层物理极限。我们现在拥有了关于事件循环抖动、高并发通信和内存管理的坚实数据，这为构建“创世网格”提供了信心。

然而，正如你所指出的，在预研过程中构建的 `ForestRenderer` 和 `TruthRenderer` 是高度特化的原型。它们虽然性能达标，但在可复用性、可维护性和功能丰富性上存在短板。现在是时候利用这些预研中获得的经验，结合强大的社区工具（如 `rich`），打造一个统一、稳健且可扩展的“创世开发包 (Genesis SDK)”中的核心组件——一个全新的可视化引擎。

我将为你设计并实施这个新的渲染器。

## [WIP] feat: 构建基于 Rich 的统一网格渲染器 UniGrid

### 用户需求
当前的 `observatory` 可视化工具 (`ForestRenderer`, `TruthRenderer`) 是为特定预研任务构建的原型，存在以下问题：
1.  **复用性差**：每个实验都需要一套定制的渲染逻辑。
2.  **维护困难**：底层依赖于手动计算差异和拼接 ANSI 转义码，容易出错且难以扩展。
3.  **功能有限**：难以添加更丰富的 UI 元素，如多行状态栏、图例或动态标题。

我们需要一个统一、可复用、功能强大的新渲染器，它应该：
1.  基于成熟的 `rich` 库，以简化开发和维护。
2.  提供一个清晰的布局，包含**网格显示区**和**状态监控区**。
3.  将**状态（State）**与**外观（Palette）**彻底解耦，使其能轻松适应不同实验的视觉需求。

### 评论
这是一个非常明智的工程决策。预研阶段的目标是“验证可行性”，为此可以牺牲代码的优雅。现在，我们进入了“构建通用工具”的阶段，重点转向了**开发者体验 (DX)** 和 **长期可维护性**。

通过引入 `rich`，我们将渲染的复杂性（如终端差异计算、颜色管理、光标定位）委托给一个经过充分测试的专业库。这使我们能够将精力集中在更高层次的抽象上：如何将模拟的逻辑状态最有效地映射为视觉信息。这个新渲染器将是“创世开发包”中一个至关重要的部分。

### 目标
1.  **创建新的渲染器核心**：在 `observatory/protoplasm/renderer/` 目录下创建一个新的 `UniGridRenderer` (Unified Grid Renderer)。
2.  **解耦状态与表现**：
    *   创建一个 `StateMatrix` 类，使用 `numpy` 数组管理网格的逻辑状态（如亮度、活性）。
    *   创建一个 `Palettes` 模块，包含一系列函数，每个函数接受一个状态矩阵并返回一个 `rich` 兼容的颜色/字符矩阵。
3.  **重构现有原型**：
    *   彻底删除旧的 `ForestRenderer` 及其依赖 (`buffer.py`, `driver.py`)。
    *   将 `run_fireflies.py` 和 `bottleneck_sim.py` 重构为使用新的 `UniGridRenderer`。
4.  **升级真理之镜**：
    *   重构 `TruthRenderer`，使其也利用 `rich` 的能力进行渲染，不再手动管理 ANSI 码。
    *   将 `StateValidator` 与渲染逻辑解耦，使其在 headless 模式下也能正常工作。

### 基本原理
新的 `UniGridRenderer` 将作为一个独立的异步服务运行。
1.  **异步队列**: 模拟代码通过一个 `asyncio.Queue` 以非阻塞方式向渲染器 `ingest` 事件 `(x, y, state)`。
2.  **渲染循环 (`_render_loop`)**:
    *   以固定的帧率（如 30 FPS）运行。
    *   每一帧，它会：
        a.  从队列中取出所有待处理事件，更新 `StateMatrix`。
        b.  调用 `StateMatrix.decay()` 来模拟物理效果（如余辉）。
        c.  调用指定的 `palette_func`，将 `StateMatrix` 的 `numpy` 数组转换为 `rich` 可以渲染的彩色字符。
        d.  构建一个 `rich.Layout` 或 `rich.Table` 对象来展示网格和状态信息。
        e.  使用 `rich.Live` 来高效地更新终端显示，`rich` 会在内部处理差异渲染。
3.  **可插拔调色板 (Pluggable Palettes)**: `UniGridRenderer` 在初始化时接受一个 `palette_func`。这意味着同一个渲染器可以用于萤火虫（黄/橙色调色板）、资源瓶颈（白/青色调色板）或任何其他实验，只需提供一个不同的状态->颜色映射函数即可。

这种设计将渲染逻辑完全封装，为上层实验代码提供了一个极其简洁的接口：`renderer.ingest(x, y, state)` 和 `renderer.set_extra_info("...")`。

### 标签
#intent/refine #intent/architect #flow/ready #priority/high #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/renderer #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 移除旧的、手写的渲染器原型

随着我们转向基于 `rich` 的统一渲染器，旧的 `visualizer_proto.py` 及其底层驱动 `driver.py` 和 `buffer.py` 已经完成了它们的历史使命，现在将被彻底移除。

~~~~~act
delete_file
observatory/protoplasm/renderer/visualizer_proto.py
~~~~~

~~~~~act
delete_file
observatory/protoplasm/renderer/driver.py
~~~~~

~~~~~act
delete_file
observatory/protoplasm/renderer/buffer.py
~~~~~

#### Acts 2: 建立新的统一渲染器核心组件

我们将创建新的核心文件，它们构成了 `UniGridRenderer` 的基础：
1.  `matrix.py`: 管理 `numpy` 状态矩阵和物理衰减。
2.  `palette.py`: 将状态数字映射为视觉颜色和字符，实现逻辑与表现的分离。
3.  `unigrid.py`: 统一渲染器的主体，使用 `rich` 编排整个渲染循环。

~~~~~act
write_file
observatory/protoplasm/renderer/matrix.py
~~~~~
~~~~~python
import numpy as np
from dataclasses import dataclass

@dataclass
class GridConfig:
    width: int = 100
    height: int = 100
    decay_rate: float = 0.1

class StateMatrix:
    """
    Manages the 'physics' of the grid:
    - Logical state (is the agent active?)
    - Physical state (brightness/afterglow)
    """

    def __init__(self, config: GridConfig):
        self.cfg = config
        # brightness: Float 0.0 - 1.0 (1.0 = Flash, 0.0 = Dark)
        self.brightness = np.zeros((self.cfg.height, self.cfg.width), dtype=np.float32)
        # active: Boolean (True = Agent exists/alive)
        self.active = np.zeros((self.cfg.height, self.cfg.width), dtype=bool)

    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def decay(self):
        """
        Applies decay to the entire matrix.
        Optimized vectorized operation.
        """
        # Subtract decay_rate, clip at 0.0
        self.brightness -= self.cfg.decay_rate
        np.clip(self.brightness, 0.0, 1.0, out=self.brightness)

    def get_snapshot(self):
        """Returns a copy of the current brightness matrix."""
        return self.brightness.copy()
~~~~~

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
        self._extra_info = ""

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))
        
    def set_extra_info(self, info: str):
        """Sets a string to be displayed in the status bar."""
        self._extra_info = info

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
            # Calculate REAL FPS based on total loop time
            now = time.perf_counter()
            real_fps = 1.0 / (now - loop_start + 0.00001)
            # Use a simpler moving average if needed, but this is instant FPS
            
            self.driver.move_to(self.logical_height + 1, 0)
            status_text = f"UniGrid | FPS: {real_fps:.1f} | Updates: {len(rows)} | {self._extra_info}"
            # Pad to clear line
            self.driver.write(f"{status_text:<80}", '\033[97m')
            self.driver.flush()
            
            # 6. Sleep to maintain Target FPS
            # We measure elapsed from start of loop logic
            logic_elapsed = time.perf_counter() - loop_start
            sleep_t = max(0, frame_time - logic_elapsed)
            await asyncio.sleep(sleep_t)
            
        # Cleanup on exit
        self.driver.show_cursor()
        self.driver.flush()
~~~~~
~~~~~act
write_file
observatory/protoplasm/renderer/buffer.py
~~~~~
~~~~~python
import numpy as np
from typing import List, Tuple

class RenderBuffer:
    """
    Represents what is actually displayed on screen (Chars + Colors).
    Capable of computing diffs against another buffer.
    """
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # Stores the character to be printed
        self.chars = np.full((height, width), ' ', dtype='<U1')
        # Stores the ANSI color code for that character
        # Using fixed length string for optimization, typical ANSI code is ~5-7 chars
        self.colors = np.full((height, width), '', dtype='<U10')

    def update_from_matrix(self, brightness_matrix: np.ndarray):
        """
        Rasterizes the float brightness matrix into chars and colors.
        """
        # 1. Clear
        self.chars[:] = ' '
        self.colors[:] = ''

        # 2. Vectorized conversion logic
        # Brightness > 0.8: Bright White '#'
        # Brightness > 0.5: Cyan '*'
        # Brightness > 0.2: Dim Blue '.'
        # Else: Space
        
        # We use boolean masks for speed
        mask_high = brightness_matrix > 0.8
        mask_mid = (brightness_matrix > 0.4) & (~mask_high)
        mask_low = (brightness_matrix > 0.01) & (~mask_high) & (~mask_mid)

        # Apply Chars
        self.chars[mask_high] = '#'
        self.chars[mask_mid] = 'o'
        self.chars[mask_low] = '.'

        # Apply Colors (Pre-computed ANSI codes)
        # White
        self.colors[mask_high] = '\033[97m' 
        # Cyan
        self.colors[mask_mid] = '\033[36m'
        # Dim Gray/Blue
        self.colors[mask_low] = '\033[90m'

    @staticmethod
    def compute_diff(prev: 'RenderBuffer', curr: 'RenderBuffer') -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns (rows, cols) indices where prev and curr differ.
        """
        # Compare chars and colors simultaneously
        # We can just check chars equality for visual change if logic guarantees color syncs with char
        # But to be safe, check both.
        # Constructing a combined view might be expensive.
        # Let's check chars first, then colors.
        
        diff_mask = (prev.chars != curr.chars) | (prev.colors != curr.colors)
        return np.where(diff_mask)
~~~~~

~~~~~act
write_file
observatory/protoplasm/renderer/driver.py
~~~~~
~~~~~python
import sys

class AnsiDriver:
    """
    Low-level driver for ANSI terminal control.
    Optimized for buffered output to minimize IO syscalls.
    """
    
    # ANSI Constants
    cursor_hide = "\033[?25l"
    cursor_show = "\033[?25h"
    reset = "\033[0m"
    clear = "\033[2J"
    home = "\033[H"

    def __init__(self):
        self._buffer = []

    def hide_cursor(self):
        self._buffer.append(self.cursor_hide)

    def show_cursor(self):
        self._buffer.append(self.cursor_show)
        
    def clear_screen(self):
        self._buffer.append(self.clear)
        self._buffer.append(self.home)

    def move_to(self, row: int, col: int):
        # ANSI coordinates are 1-based
        self._buffer.append(f"\033[{row+1};{col+1}H")

    def write(self, text: str, color_code: str = ""):
        if color_code:
            self._buffer.append(f"{color_code}{text}{self.reset}")
        else:
            self._buffer.append(text)

    def flush(self):
        """Writes the accumulated buffer to stdout and clears it."""
        if not self._buffer:
            return
        sys.stdout.write("".join(self._buffer))
        sys.stdout.flush()
        self._buffer.clear()
        
    def raw_write(self, data: str):
        self._buffer.append(data)

    def close(self):
        self.show_cursor()
        self.flush()
~~~~~

#### Acts 3: Refactor Experiments to Use the New Renderer

Now we'll update the experiment scripts to replace their custom rendering logic with the new, unified `UniGridRenderer`.

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
    num_agents: int = 100, # Reduced to 100 (10x10) to prevent LocalBus saturation
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
    
    renderer = None
    renderer_task = None
    
    if visualize:
        # Define visualizer mapping
        grid_width = int(num_agents**0.5)
        if grid_width * grid_width < num_agents: grid_width += 1
        
        renderer = UniGridRenderer(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        
        # Bridge Monitor -> Renderer
        def monitor_callback(r_value: float):
            # Create a simple visual bar for R
            bar_len = 10
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            renderer.set_extra_info(f"Sync(R): {r_value:.3f} [{bar}]")

        # Start Monitor in quiet mode with callback
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0, callback=monitor_callback))

        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                renderer.ingest(x, y, 1.0)
        
        await connector.subscribe("firefly/flash", on_flash_visual)
        renderer_task = asyncio.create_task(renderer.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

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

#### Acts 4: Upgrade the "Truth" Subsystem

最后，我们将 `TruthRenderer` 和 `StateValidator` 升级，使用 `rich` 来提供更清晰、更稳健的验证过程可视化。

~~~~~act
write_file
observatory/protoplasm/truth/renderer.py
~~~~~
~~~~~python
import asyncio
import time
import numpy as np
import shutil
from typing import Tuple

# Reuse low-level drivers from the existing prototype
from observatory.protoplasm.renderer.driver import AnsiDriver
from observatory.protoplasm.renderer.buffer import RenderBuffer
from observatory.protoplasm.renderer.matrix import GridConfig

class DiffMatrix:
    """
    Manages the visual state of the verification grid.
    Values represent:
    0: Dead (Correct)
    1: Alive (Correct)
    2: False Positive (Ghost - Actual=1, Theory=0)
    3: False Negative (Missing - Actual=0, Theory=1)
    """
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)

    def update(self, actual: np.ndarray, theoretical: np.ndarray):
        """
        Computes the diff map.
        """
        # Reset
        self.grid.fill(0)
        
        # 1. Matches
        match_alive = (actual == 1) & (theoretical == 1)
        self.grid[match_alive] = 1
        
        # 2. False Positives (Red)
        false_pos = (actual == 1) & (theoretical == 0)
        self.grid[false_pos] = 2
        
        # 3. False Negatives (Blue)
        false_neg = (actual == 0) & (theoretical == 1)
        self.grid[false_neg] = 3

class TruthRenderer:
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.matrix = DiffMatrix(width, height)
        
        # Physical buffers are twice the logical width for square cells
        self.buffer_prev = RenderBuffer(width * 2, height)
        self.buffer_curr = RenderBuffer(width * 2, height)
        self.driver = AnsiDriver()
        
        self._gen_counter = 0
        self._error_stats = {"abs": 0, "rel": 0}

    def start(self):
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()

    def stop(self):
        self.driver._buffer.clear()
        self.driver.show_cursor()
        self.driver.move_to(self.height + 4, 0)
        self.driver.flush()
        self.driver.close()

    def update_frame(self, gen: int, actual: np.ndarray, theoretical: np.ndarray, stats: dict):
        self._gen_counter = gen
        self._error_stats = stats
        self.matrix.update(actual, theoretical)
        self._render()

    def render_waiting(self, gen: int, current_count: int, total: int):
        """Updates only the progress line (Line 2) to show loading status."""
        # Move to Line 2 (height + 2)
        self.driver.move_to(self.height + 2, 0)
        
        progress = current_count / total if total > 0 else 0
        bar_len = 20
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Clear line first
        self.driver.write(f"{' ':<80}")
        self.driver.move_to(self.height + 2, 0)
        
        status = (
            f"Next Gen {gen}: [{bar}] {current_count}/{total}"
        )
        # Use dim color for waiting status
        self.driver.write(status, '\033[90m') 
        self.driver.flush()

    def _render(self):
        # 1. Rasterize Matrix to Buffer using vectorized operations
        
        # Logical grid (e.g., 25x50)
        logical_grid = self.matrix.grid

        # Create physical masks by repeating columns (e.g., creates a 25x100 mask)
        phys_mask_alive = np.repeat(logical_grid == 1, 2, axis=1)
        phys_mask_dead = np.repeat(logical_grid == 0, 2, axis=1)
        phys_mask_fp = np.repeat(logical_grid == 2, 2, axis=1)
        phys_mask_fn = np.repeat(logical_grid == 3, 2, axis=1)

        # Apply character (always a block)
        self.buffer_curr.chars[:] = '█'

        # Apply colors based on physical masks
        self.buffer_curr.colors[phys_mask_alive] = '\033[97m' # Bright White
        self.buffer_curr.colors[phys_mask_dead] = '\033[90m'  # Dark Gray
        self.buffer_curr.colors[phys_mask_fp] = '\033[91m'    # Bright Red
        self.buffer_curr.colors[phys_mask_fn] = '\033[96m'   # Bright Cyan

        # 2. Diff & Draw
        rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
        
        if len(rows) > 0:
            chars = self.buffer_curr.chars[rows, cols]
            colors = self.buffer_curr.colors[rows, cols]
            
            for r, c, char, color in zip(rows, cols, chars, colors):
                self.driver.move_to(r, c)
                self.driver.write(char, color)
            
            np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
            np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)

        # 3. Status Line (Line 1)
        self.driver.move_to(self.height + 1, 0)
        
        total_err = self._error_stats['abs'] + self._error_stats['rel']
        status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
        
        status = (
            f"GEN: {self._gen_counter:<4} | "
            f"Status: {status_icon} | "
            f"Total Err: {total_err:<4} | "
            f"(Abs: {self._error_stats['abs']}, Rel: {self._error_stats['rel']})"
        )
        self.driver.write(f"{status:<80}")
        
        # Clear the waiting line (Line 2) because we just finished a frame
        self.driver.move_to(self.height + 2, 0)
        self.driver.write(f"{' ':<80}")
        
        self.driver.flush()
~~~~~

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from .renderer import TruthRenderer

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI
        self.enable_ui = enable_ui
        self.renderer = TruthRenderer(width, height) if enable_ui else None
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        # History
        # theoretical: The pure timeline derived from T0
        self.history_theoretical: Dict[int, np.ndarray] = {}
        # actual: What the agents actually reported
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        if self.renderer:
            self.renderer.start()
        else:
            print(f"⚖️  Validator active. Grid: {self.width}x{self.height}. Dual-Truth Mode Enabled.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()
            if self.renderer:
                self.renderer.stop()

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        # We process generations in strict order
        next_gen = self.max_gen_verified + 1
        
        # If no data at all yet, just return
        if next_gen not in self.buffer:
            if self.renderer:
                self.renderer.render_waiting(next_gen, 0, self.total_agents)
            return

        current_buffer = self.buffer[next_gen]
        
        # If incomplete, update UI but don't verify yet
        if len(current_buffer) < self.total_agents:
            if self.renderer:
                self.renderer.render_waiting(next_gen, len(current_buffer), self.total_agents)
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        # Cleanup to save memory, keeping only immediate history needed for next step
        del self.buffer[next_gen]
        # We need history_actual[gen] for verifying gen+1 relative truth, so we keep recent history
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid (The Report)
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        self.history_actual[gen] = actual_grid

        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            # If renderer is active, we proceed to render Gen 0 instead of returning
            if not self.renderer:
                print("🟦 [Gen 0] Axiom Set. System Initialized.")
                return
            
            # Prepare dummy stats/grids for Gen 0 render
            theo_grid = actual_grid # Gen 0 is truth by definition
            is_absolute_match = True
            is_relative_match = True
            # Skip validation logic for Gen 0, fall through to reporting/rendering
        else:
            # 3. Validation Logic (Only for Gen > 0)
            
                # --- Check A: Absolute Truth (Trajectory) ---
            # Did we stay on the path defined by T0?
            prev_theo = self.history_theoretical.get(gen - 1)
            is_absolute_match = False
            
            # Default to actual if we can't compute theory (error case)
            theo_grid = actual_grid 
            
            if prev_theo is not None:
                self.golden.seed(prev_theo)
                theo_grid = self.golden.step()
                self.history_theoretical[gen] = theo_grid
                
                diff_abs = np.sum(actual_grid != theo_grid)
                if diff_abs == 0:
                    is_absolute_match = True
                else:
                    self.absolute_errors += diff_abs
            else:
                # Should not happen if processing in order
                print(f"⚠️  Missing history for Absolute check at Gen {gen}")

            # --- Check B: Relative Truth (Transition) ---
            # Did we calculate correctly based on what we had yesterday?
            prev_actual = self.history_actual.get(gen - 1)
            is_relative_match = False
            
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                expected_relative = self.golden.step()
                
                diff_rel = np.sum(actual_grid != expected_relative)
                if diff_rel == 0:
                    is_relative_match = True
                else:
                    self.relative_errors += diff_rel
            else:
                 print(f"⚠️  Missing history for Relative check at Gen {gen}")

        # 4. Reporting
        stats = {"abs": self.absolute_errors, "rel": self.relative_errors}

        if self.renderer:
            # Visualize the Diff: We compare ACTUAL vs THEORETICAL (Absolute Truth)
            self.renderer.update_frame(gen, actual_grid, theo_grid, stats)
        else:
            if is_absolute_match:
                print(f"✅ [Gen {gen}] PERFECT MATCH (Absolute & Relative)")
            elif is_relative_match:
                print(f"🟡 [Gen {gen}] DRIFT DETECTED. Logic is correct (Relative Pass), but state diverged from T0.")
            else:
                print(f"🔴 [Gen {gen}] LOGIC FAILURE. Transition from T{gen-1} to T{gen} is incorrect. Errors: {self.relative_errors}")

    def stop(self):
        self._running = False
~~~~~

### 下一步建议
我们已经完成了对渲染基础设施的重大升级。现在最重要的步骤是：
1.  **运行验证**：请依次执行 `run_fireflies.py` 和 `bottleneck_sim.py`，确保新的 `UniGridRenderer` 能够正确地、流畅地可视化实验过程。
2.  **Conway 实验验证**：执行 `run_conway_experiment.py`，确认 `TruthRenderer` 的重构是成功的，并且 UI 仍然能准确反映模拟与“黄金参考”之间的差异。
3.  **探索新能力**：考虑为 `UniGridRenderer` 增加更多的功能，例如一个专门的图例区域，或者允许在运行时动态切换调色板。

这次重构为我们未来的可视化工作打下了坚实的基础。
