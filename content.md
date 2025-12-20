简要回答：
收到。我们将正式启动 **原基计划 (Project Protoplasm)** 的第一阶段，构建高性能 CLI 渲染基座。这将为未来的万节点级“创世网格”提供必要的观测能力。

根据文档 `CS-DOC-PRE-GENESIS-251220`，我们将分步实现渲染管线的核心组件：状态矩阵 (Matrix)、双缓冲帧 (Buffer) 和 ANSI 驱动 (Driver)，并最终集成到 `ForestRenderer` 中。

摘要头：
## [WIP] feat: 搭建 CLI 渲染器原型的高性能核心组件

### 标签
#intent/explore #flow/ready #priority/high
#comp/observatory #concept/ui #scope/core
#ai/instruct
#task/domain/observatory
#task/object/renderer-proto
#task/action/implementation
#task/state/begin

### 用户需求
1.  **构建渲染管线基础设施**：在 `observatory/protoplasm/renderer/` 下创建核心模块。
2.  **实现状态矩阵 (`matrix.py`)**：使用 `numpy` 实现 100x100 的高性能状态存储，支持逻辑状态与物理状态（余辉衰减）。
3.  **实现差异缓冲 (`buffer.py`)**：实现基于双缓冲的差异计算逻辑，利用 `numpy` 掩码快速定位变化像素，避免全屏重绘。
4.  **实现终端驱动 (`driver.py`)**：封装低级 ANSI 控制码，提供光标移动和字符绘制的原语。
5.  **实现渲染器主类 (`visualizer_proto.py`)**：整合队列摄入 (Ingestion) 和 渲染循环 (Render Loop)，实现逻辑更新与视觉渲染的线程级解耦。

### 评论
这是一个典型的“游戏引擎”架构在 CLI 环境下的微缩实现。核心挑战在于 Python 的解释器开销。我们将大量利用 `numpy` 的向量化操作来处理 10,000 个单元的状态更新和差异比对，仅将必要的 IO 操作留给 Python 循环。这是达成 30FPS 目标的关键。

### 目标
*   建立 `observatory/protoplasm/renderer` 目录结构。
*   完成 `driver.py`, `matrix.py`, `buffer.py` 的代码实现。
*   完成 `visualizer_proto.py` 的核心类定义 `ForestRenderer`。

### 基本原理
*   **Numpy 优化**：对于 100x100 的网格，Python 原生列表的遍历速度太慢。使用 `numpy` 可以在 C 层面完成矩阵减法和掩码生成，极大地加速 `diff` 计算。
*   **双缓冲**：借鉴图形学标准实践，`Current` 缓冲用于渲染，`Next` 缓冲用于后台绘制，但在 CLI 场景下，我们主要对比 `Previous` 和 `Current` 来生成最小化的绘制指令集。
*   **IO 优化**：标准 `print` 带有换行和 flush 开销。我们将使用 `sys.stdout.write` 并手动缓冲输出流，在每一帧结束时一次性 `flush`。

---

### Script

#### Acts 1: 创建目录结构

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p observatory/protoplasm/renderer
touch observatory/protoplasm/renderer/__init__.py
~~~~~

#### Acts 2: 实现 ANSI 终端驱动 (`driver.py`)

提供底层的光标控制和颜色输出能力。

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

#### Acts 3: 实现状态矩阵 (`matrix.py`)

处理 100x100 网格的物理状态（亮度）和逻辑状态，利用 Numpy 进行批量衰减运算。

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

#### Acts 4: 实现帧缓冲与合成器 (`buffer.py`)

负责将状态矩阵转换为字符矩阵，并计算两帧之间的差异。

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

#### Acts 5: 实现渲染器主程序 (`visualizer_proto.py`)

集成所有组件，实现双缓冲队列和主循环。

~~~~~act
write_file
observatory/protoplasm/renderer/visualizer_proto.py
~~~~~
~~~~~python
import asyncio
import time
import random
import numpy as np
from asyncio import Queue

from .driver import AnsiDriver
from .matrix import StateMatrix, GridConfig
from .buffer import RenderBuffer

class ForestRenderer:
    """
    The High-Performance CLI Renderer.
    Decouples ingestion (Telemetry) from Rendering (30 FPS Loop).
    """

    def __init__(self, width: int = 100, height: int = 100):
        self.config = GridConfig(width=width, height=height, decay_rate=0.05)
        self.matrix = StateMatrix(self.config)
        
        # Double Buffering
        self.buffer_prev = RenderBuffer(width, height)
        self.buffer_curr = RenderBuffer(width, height)
        
        self.driver = AnsiDriver()
        
        # High-throughput ingestion queue
        # Items are tuples: (x, y, state)
        self.queue: Queue = Queue()
        
        self._running = False
        self._fps_stats = []

    async def start(self):
        self._running = True
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()
        
        # Start loops
        # In a real app, ingestion is driven by external calls to put(), 
        # but here we consume the queue in the render loop or a separate task.
        # Actually, since matrix update is fast, we can do it in the render loop phase.
        
        await self._render_loop()

    def stop(self):
        self._running = False
        self.driver.show_cursor()
        self.driver.reset # Reset colors
        self.driver.flush()
        self.driver.close()

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe / Async-safe ingestion point."""
        self.queue.put_nowait((x, y, state))

    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        print(f"Starting Render Loop at {target_fps} FPS...")
        
        while self._running:
            start_t = time.perf_counter()
            
            # 1. Ingestion Phase: Drain the queue
            # We process ALL pending events to clear the backlog
            events_processed = 0
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                    events_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics Phase: Decay
            self.matrix.decay()
            
            # 3. Render Phase: Matrix -> Buffer
            self.buffer_curr.update_from_matrix(self.matrix.brightness)
            
            # 4. Diff Phase
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            # 5. Draw Phase
            # We iterate only the changed pixels
            if len(rows) > 0:
                # Optimized extraction
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                # Swap buffers (copy content from curr to prev)
                # Optimization: Swap references if we create new curr every time. 
                # But here we update in place, so we copy.
                # Actually, numpy copyto is fast.
                np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
                np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)
            
            # Debug Stats overlay
            draw_t = time.perf_counter() - start_t
            self.driver.move_to(self.config.height + 1, 0)
            self.driver.write(f"FPS: {1.0/(draw_t+0.0001):.1f} | Events: {events_processed} | Diff: {len(rows)} px | DrawT: {draw_t*1000:.2f}ms")
            
            self.driver.flush()
            
            # 6. Sleep
            elapsed = time.perf_counter() - start_t
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)


# --- Load Generator for Stress Testing ---

async def stress_test_loader(renderer: ForestRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    width, height = renderer.config.width, renderer.config.height
    num_agents = 10000
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # In one frame (33ms), maybe 30 agents fire?
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)

if __name__ == "__main__":
    # Self-contained run
    renderer = ForestRenderer(width=100, height=50)
    
    loop = asyncio.get_event_loop()
    try:
        # Schedule the stress loader
        loop.create_task(stress_test_loader(renderer))
        # Run the renderer
        loop.run_until_complete(renderer.start())
    except KeyboardInterrupt:
        renderer.stop()
        print("\nRenderer stopped.")
~~~~~

### 下一步建议
我们已经完成了第一章的核心代码。现在渲染器原型已就绪，具备了高性能的差异渲染能力。
下一步，我建议：
1.  **执行验证**：运行 `visualizer_proto.py`，观察其在当前环境下的 FPS 表现和 CPU 占用率。
2.  **集成评估**：如果性能达标（>30FPS, CPU <15%），我们将在下一步的“第二章：直连”实验中，尝试将此渲染器与真实的 `LocalBusConnector` 或 `DirectChannel` 对接。
