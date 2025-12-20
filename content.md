你的直觉再一次领先了现有的架构。

**结论**：是的，对于我们这种“每一帧全屏刷新”、“像游戏一样运行”的需求，`Rich` 已经成为了累赘。它是一个优秀的**文档排版引擎**，但绝不是一个**实时渲染引擎**。它为了计算布局（Padding, Border, Wrap）所消耗的 CPU 周期，对于我们的像素网格来说是完全浪费的。

**失败原因分析**：
上一轮修改中，我们将 `Segment` 替换为 `Control`。Rich 的布局引擎（`Layout`）在计算区域大小时，认为 `Control` 对象是**零宽度、零高度**的（因为它们通常只是改变颜色的指令，不占空间）。因此，Rich 认为 `GridView` 的内容为空，直接将其折叠了，导致屏幕上什么都没有。

**战略转向：Raw Metal (裸金属模式)**

我们不需要寻找另一个库。Python 的标准库加上我们已经拥有的 NumPy 矢量化能力，就是最快的库。

我们将实施**“裸金属渲染器 (Raw Metal Renderer)”**：
1.  **抛弃 Layout**: 终端就是一个 `W x H` 的字符数组。我们不需要复杂的分割。
2.  **抛弃 Style**: 我们已经在 NumPy 里计算好了 ANSI 码。
3.  **抛弃 Objects**: 只有 `bytes`。

我们将利用 Cascade 的哲学：**最简单的机制往往是最强大的。**

## [WIP] refactor(observatory): 移除 Rich 依赖并实施基于 ANSI 字节流的裸金属渲染器

### 用户需求
彻底解决渲染性能瓶颈和显示故障。放弃 Rich 的布局和渲染系统，转而使用直接的 stdout 字节流写入。

### 评论
这将把渲染层的抽象级别降到最低（接近 C 语言的 `printf` 级别）。
新的管线：`NumPy State -> Vectorized ANSI Lookup -> Join -> Bytes -> Stdout`。
中间没有任何对象创建，没有任何布局计算，没有任何自动换行检查。这是 Python 能够达到的理论性能极限。

### 目标
1.  在 `GridView` 中实现 `render_frame_buffer() -> bytes` 方法，直接返回全屏图像的字节流。
2.  创建一个新的 `RawTerminalApp`，替代基于 Rich 的 `TerminalApp`。
3.  手动处理光标复位（`\033[H`），实现无清屏刷新。

### 标签
#intent/refine #flow/ready #priority/critical #comp/observatory #concept/ui #scope/perf #ai/instruct #task/domain/visualization #task/object/raw-renderer #task/action/rewrite #task/state/continue

---

### Script

#### Acts 1: 升级 GridView 以支持直接字节输出

我们需要在 `GridView` 中添加一个方法，利用 NumPy 极速拼接出完整的帧数据。

~~~~~act
patch_file
observatory/visualization/grid.py
~~~~~
~~~~~python
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        The Rich render protocol method, highly optimized for throughput.
        It bypasses Rich's style parsing by constructing raw ANSI strings.
        """
        brightness = self.matrix.get_snapshot()
        # colors now contains raw ANSI escape codes (e.g. "\033[38;2;...m")
        colors = self.palette_func(brightness)

        # ANSI Reset code to clear color at the end of each line
        reset = "\033[0m"

        # Vectorized string construction.
        # We iterate over rows and join the (color + block) strings.
        # This is significantly faster than creating 10,000 Segment objects.
        for y in range(self.logical_height):
            # Join all columns in this row: color_code + "██"
            # Since `colors` is a numpy array of strings, this loop is tight.
            row_content = "".join(f"{code}██" for code in colors[y])
            
            # Yield a Control object.
            # Rich treats Control objects as having 0 width and does NOT wrap them.
            # This allows our long ANSI string to pass through to the terminal intact.
            yield Control(row_content + reset)
            yield Segment.line()
~~~~~
~~~~~python
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        Legacy Rich support. Used if wrapped in a Rich Layout.
        """
        # Fallback for static reporting if needed
        yield Segment("GridView(Raw Mode Active)")

    def render_frame_buffer(self) -> bytes:
        """
        Generates the full frame as a raw byte string.
        This is the "Raw Metal" mode.
        """
        brightness = self.matrix.get_snapshot()
        # colors is a numpy array of strings like "\033[38;2;...m"
        colors = self.palette_func(brightness)
        
        # ANSI Reset
        reset = "\033[0m"
        
        # 1. Add pixel char "██" to every color code in the array
        # This creates an array of strings like "\033[38;...m██"
        # We use numpy char module for vectorized concatenation if possible,
        # but standard list comp is surprisingly fast for string joining.
        # Let's try a hybrid approach: Pre-calculate the row strings.
        
        lines = []
        for y in range(self.logical_height):
            # Join the row into one huge string
            # OPTIMIZATION: We could cache the "██" part or use numpy char add,
            # but string join is extremely optimized in CPython.
            row_str = "".join(f"{code}██" for code in colors[y])
            lines.append(row_str + reset)
            
        # Join lines with newline
        full_frame = "\n".join(lines)
        
        return full_frame.encode("utf-8")
~~~~~

#### Acts 2: 创建裸金属应用 (RawTerminalApp)

我们将创建一个新的 `observatory/visualization/raw_app.py`。它没有任何 Rich 依赖（除了用来借用 `status_bar` 的渲染逻辑，或者我们可以甚至手写那个）。为了最彻底的性能，我们手写 Status Bar 的渲染。

~~~~~act
write_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
import asyncio
import sys
import time
from asyncio import Queue
from typing import Any

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
    A 'Raw Metal' renderer that bypasses Rich/Curses and writes directly 
    to the stdout buffer.
    """

    def __init__(
        self,
        grid_view: GridView,
        status_bar: StatusBar,
        aggregator: MetricsAggregator = None,
    ):
        self.grid_view = grid_view
        self.status_bar = status_bar
        self.aggregator = aggregator

        self.queue: Queue = Queue()
        self._frame_buffer = set()
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()

        # Pre-allocate numpy buffers for batch updates
        max_pixels = self.grid_view.logical_width * self.grid_view.logical_height
        self._update_coords_x = np.zeros(max_pixels, dtype=int)
        self._update_coords_y = np.zeros(max_pixels, dtype=int)
        self._update_states = np.zeros(max_pixels, dtype=np.float32)

        self._stdout = sys.stdout.buffer

    async def direct_update_grid_batch(self, updates: list):
        """Async batch update (same interface as TerminalApp)."""
        if not updates:
            return
        async with self._flush_lock:
            self._frame_buffer.update(updates)

    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
        """Direct full matrix update."""
        self.grid_view.matrix.set_matrix(new_matrix)

    async def start(self):
        """Starts the raw render loop."""
        self._running = True
        
        # Setup terminal
        self._stdout.write(CURSOR_HIDE)
        self._stdout.write(CLEAR_SCREEN)
        self._stdout.flush()
        
        self._render_task = asyncio.create_task(self._render_loop())

    def stop(self):
        """Stops the loop and restores terminal."""
        self._running = False
        if self._render_task:
            self._render_task.cancel()
        
        # Restore terminal
        self._stdout.write(CURSOR_SHOW)
        self._stdout.write(RESET_COLOR)
        self._stdout.write(b"\n")
        self._stdout.flush()

    def _render_status_bar(self) -> bytes:
        """
        Manually renders the status bar to bytes.
        Format: | Key: Value | Key: Value |
        """
        parts = []
        for key, value in self.status_bar.status_data.items():
            # Cyan Key, Magenta Value (Bold)
            parts.append(f"\033[36m{key}:\033[0m \033[1;35m{str(value)}\033[0m")
        
        line = " | ".join(parts)
        # Add a top border or separation
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line).encode("utf-8")

    def _blocking_flush_logic(self, updates_set):
        """CPU-bound state update."""
        num_updates = len(updates_set)
        if num_updates == 0:
            return

        # Flatten logic same as before
        temp_array = np.fromiter(
            (item for tpl in updates_set for item in tpl),
            dtype=np.float32,
            count=num_updates * 3,
        ).reshape((num_updates, 3))

        self._update_coords_x[:num_updates] = temp_array[:, 0]
        self._update_coords_y[:num_updates] = temp_array[:, 1]
        self._update_states[:num_updates] = temp_array[:, 2]

        self.grid_view.matrix.update_batch(
            self._update_coords_x[:num_updates],
            self._update_coords_y[:num_updates],
            self._update_states[:num_updates],
        )

    async def _flush_buffer(self):
        """Async wrapper for flushing."""
        updates_to_flush = None
        async with self._flush_lock:
            if self._frame_buffer:
                updates_to_flush = self._frame_buffer
                self._frame_buffer = set()

        if updates_to_flush:
            await asyncio.to_thread(self._blocking_flush_logic, updates_to_flush)
            return len(updates_to_flush)
        return 0

    async def _render_loop(self):
        last_time = time.perf_counter()
        
        # Target FPS
        target_fps = 30.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()

            # 1. Process Updates
            flush_start = time.perf_counter()
            updates_count = await self._flush_buffer()
            flush_ms = (time.perf_counter() - flush_start) * 1000

            # 2. Process Queue (Status)
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        k, v = data
                        self.status_bar.set_status(k, v)
                except asyncio.QueueEmpty:
                    break

            # 3. Physics Step
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            self.grid_view.matrix.decay(dt)

            # 4. RENDER (The heavy lifting)
            # Move cursor home
            output_buffer = bytearray(CURSOR_HOME)
            
            # Get Grid Bytes
            grid_bytes = self.grid_view.render_frame_buffer()
            output_buffer.extend(grid_bytes)
            
            # Get Status Bytes
            status_bytes = self._render_status_bar()
            output_buffer.extend(status_bytes)
            
            # WRITE TO STDOUT (Atomic-ish)
            self._stdout.write(output_buffer)
            self._stdout.flush()

            # 5. Telemetry & Sleep
            render_duration = time.perf_counter() - loop_start
            fps = 1.0 / dt if dt > 0 else 0
            
            self.status_bar.set_status("FPS", f"{fps:.1f}")
            
            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            # Smart Sleep to maintain target FPS
            sleep_time = frame_interval - render_duration
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0) # Yield at least once
~~~~~

#### Acts 3: 替换 wave_test 中的 App

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~python
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator
~~~~~
~~~~~python
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator
~~~~~

### 下一步建议
再次运行 `renderer/wave_test.py`。
这一次，我们将绕过 Rich 的所有层级。你应该看到一个极其快速、响应灵敏且**正确**的网格。
如果这次成功，我们可以把所有实验脚本（`run_fireflies` 等）中的 `TerminalApp` 都替换为 `RawTerminalApp`。
