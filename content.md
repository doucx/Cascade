你的分析非常精准，这正是“原基”项目的目的——暴露理论与实践之间的鸿沟。当成百上千个独立的 Agent 在逻辑上同时达到闪烁阈值时，它们会对共享的渲染资源（`asyncio` 事件循环）发起“惊群之鸟”（Thundering Herd）攻击，导致主循环被调用风暴淹没，帧率骤降。

你的解决方案是正确的工程方向。我们将实施“帧缓冲”来解耦渲染和模拟，并增加遥测来更好地理解系统行为。

## [WIP] tune(observatory): 实施帧缓冲并增强遥测以解决同步瓶颈

### 用户需求
1.  **解决同步闪烁时的帧率崩溃问题**：当大量 Agent 同时更新时，UI 严重卡顿。
2.  **增强可观测性**: 需要量化指标来理解同步过程，例如“脉冲计数”。
3.  **持久化数据**: 需要将实验数据记录到文件，以便进行事后分析。

### 评论
**问题根源**: `direct_update_grid` 虽然本身很快，但在同步点附近，几百个 Agent 会在同一个事件循环 tick 内连续调用它。这会向事件循环注入数百个待处理的回调，导致负责渲染的 `_render_loop` 无法获得执行机会，直到所有 Agent 的回调都处理完毕。这表现为一次长时间的卡顿，然后屏幕瞬间更新。

**解决方案**:
1.  **帧缓冲 (Frame Buffering)**: 我们将引入一个缓冲区。`direct_update_grid` 不再直接写入矩阵，而是将更新请求（一个 `(x, y, state)` 元组）放入一个 `set` 中（自动去重）。`_render_loop` 在每一帧开始时，原子性地将缓冲区中的所有更新一次性“刷”到 `StateMatrix` 上。这彻底解耦了 Agent 的更新频率和屏幕的刷新率。
2.  **遥测增强**: 我们将在 `ConvergenceMonitor` 中添加“脉冲计数”逻辑，并将其暴露给UI和新的日志系统。
3.  **结构化日志**: 创建一个简单的 JSON 日志记录器，用于捕获时间序列数据。

### 目标
1.  在 `TerminalApp` 中实现帧缓冲机制。
2.  在 `ConvergenceMonitor` 中实现脉冲计数。
3.  创建一个 `JsonFileLogger` 并集成到实验脚本中。
4.  更新 UI 以显示新的遥测数据。

### 基本原理
**解耦**: 帧缓冲是图形学和游戏引擎中的标准技术，它允许模拟状态以高频率变化，而渲染以固定的、较低的频率进行，从而确保视觉流畅性。
**数据驱动**: 通过记录 JSON 日志，我们可以使用外部工具（如 `pandas`, `matplotlib`）来绘制 R 值随脉冲数变化的曲线，从而科学地分析不同参数下的收敛速度，而不是单纯靠“感觉”。

### 标签
#intent/tune #intent/tooling #flow/ready #priority/high #comp/observatory #scope/perf #scope/dx #task/domain/observatory #task/object/renderer #task/action/batching #task/state/continue

---

### Script

#### Acts 1: 在 TerminalApp 中实现帧缓冲

修改 `observatory/visualization/app.py`，用一个 set 作为缓冲区来合并单帧内的所有更新。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._running = False
        self._render_task: asyncio.Task | None = None

    def ingest_grid(self, x: int, y: int, state: float):
~~~~~
~~~~~new
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._frame_buffer = set()  # (x, y, state)
        self._running = False
        self._render_task: asyncio.Task | None = None

    def ingest_grid(self, x: int, y: int, state: float):
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    def direct_update_grid(self, x: int, y: int, state: float):
        """
        Directly updates the state matrix, bypassing the queue.
        Safe to call from async callbacks in the same event loop.
        """
        self.grid_view.matrix.update(x, y, state)

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~
~~~~~new
    def direct_update_grid(self, x: int, y: int, state: float):
        """
        Adds a grid update to the frame buffer for batch processing.
        This is extremely fast and non-blocking.
        """
        self._frame_buffer.add((x, y, state))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        # Reduce refresh rate to 15 FPS to save CPU for agents
        with Live(
            self.layout, screen=True, transient=True, refresh_per_second=15
        ) as live:
            frame_times = []
            last_time = time.perf_counter()

            while self._running:
                # Process all pending updates from the queue
                queue_size = self.queue.qsize()
                while not self.queue.empty():
                    try:
                        msg_type, data = self.queue.get_nowait()
                        if msg_type == "grid":
                            x, y, state = data
                            self.grid_view.matrix.update(x, y, state)
                        elif msg_type == "status":
                            key, value = data
                            self.status_bar.set_status(key, value)
                    except asyncio.QueueEmpty:
                        break

                # Calculate dt (frame_time) for physics update
                now = time.perf_counter()
~~~~~
~~~~~new
    async def _flush_buffer(self):
        """Applies all buffered updates to the grid matrix."""
        if not self._frame_buffer:
            return

        # Atomically swap the buffer
        updates = self._frame_buffer
        self._frame_buffer = set()

        for x, y, state in updates:
            self.grid_view.matrix.update(x, y, state)

    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        # Reduce refresh rate to 15 FPS to save CPU for agents
        with Live(
            self.layout, screen=True, transient=True, refresh_per_second=15
        ) as live:
            frame_times = []
            last_time = time.perf_counter()

            while self._running:
                # --- Batch Updates ---
                await self._flush_buffer()

                # Process all pending updates from the queue (for status bar etc.)
                queue_size = self.queue.qsize()
                while not self.queue.empty():
                    try:
                        msg_type, data = self.queue.get_nowait()
                        if msg_type == "grid":  # Legacy path
                            x, y, state = data
                            self.grid_view.matrix.update(x, y, state)
                        elif msg_type == "status":
                            key, value = data
                            self.status_bar.set_status(key, value)
                    except asyncio.QueueEmpty:
                        break

                # Calculate dt (frame_time) for physics update
                now = time.perf_counter()
~~~~~

#### Acts 2: 增强 ConvergenceMonitor

为 `observatory/monitors/convergence.py` 添加脉冲计数，并传递给回调。

~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~old
        # State: Store the phase reported at the last flash time for each agent
        self.phases_at_flash: Dict[int, float] = {}
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False
        self._flash_count = 0

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
~~~~~
~~~~~new
        # State: Store the phase reported at the last flash time for each agent
        self.phases_at_flash: Dict[int, float] = {}
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False
        self._flash_count = 0
        self.pulse_count = 0

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
~~~~~

~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~old
    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        if self.callback:
            self.callback(order_param)
            return

        bar_length = 40
~~~~~
~~~~~new
    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        self.pulse_count = self._flash_count // self.num_agents

        if self.callback:
            self.callback(order_param, self.pulse_count)
            return

        bar_length = 40
~~~~~

#### Acts 3: 创建 JSON 日志记录器

创建新文件 `observatory/monitors/logger.py`。

~~~~~act
write_file
observatory/monitors/logger.py
~~~~~
~~~~~python
import json
import time
from typing import IO


class JsonFileLogger:
    """
    A simple logger to write experiment telemetry to a file, one JSON object per line.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self._file: IO | None = None

    def open(self):
        """Opens the log file for writing."""
        self._file = open(self.filename, "w", encoding="utf-8")

    def log(self, data: dict):
        """Logs a dictionary as a JSON line."""
        if not self._file:
            return
        
        # Add a timestamp for time-series analysis
        data_with_ts = {"ts": time.time(), **data}
        
        json.dump(data_with_ts, self._file)
        self._file.write("\n")
        self._file.flush()

    def close(self):
        """Closes the log file."""
        if self._file:
            self._file.close()
            self._file = None
~~~~~

#### Acts 4: 集成所有改动到实验脚本

最后，修改 `observatory/experiments/run_fireflies.py` 来使用所有新功能。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
import asyncio
import random
from typing import Dict, Any, List

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# Visualization
from observatory.visualization.palette import Palettes
~~~~~
~~~~~new
import asyncio
import random
from typing import Dict, Any, List
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.logger import JsonFileLogger

# Visualization
from observatory.visualization.palette import Palettes
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
        app = TerminalApp(grid_view, status_bar)

        # 2. Bridge Monitor -> Status Bar
        def monitor_callback(r_value: float):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync (R)", f"{r_value:.3f} [{bar}]")

        monitor_task = asyncio.create_task(
            # Reduce monitor frequency to reduce CPU load
~~~~~
~~~~~new
        app = TerminalApp(grid_view, status_bar)
        
        # --- Setup Logger ---
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        logger = JsonFileLogger(log_filename)
        logger.open()
        print(f"📝 Logging telemetry to [bold cyan]{log_filename}[/bold cyan]")


        # 2. Bridge Monitor -> Status Bar & Logger
        def monitor_callback(r_value: float, pulse_count: int):
            # UI Update
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            
            # Data Logging
            logger.log({"r_value": r_value, "pulse": pulse_count, "flash_count": monitor._flash_count})


        monitor_task = asyncio.create_task(
            # Reduce monitor frequency to reduce CPU load
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
        # Use Fast Path (Direct Update) to avoid queue bottlenecks
                app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~
~~~~~new
        # Use Fast Path (Direct Update) to avoid queue bottlenecks
                app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()

        if not all_agent_tasks.done():
~~~~~
~~~~~new
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()
        if logger:
            logger.close()

        if not all_agent_tasks.done():
~~~~~

### 下一步建议
我们已经完成了性能和可观测性的重大升级。现在，再次运行实验。你应该会观察到：
1.  **FPS 显著提高且更稳定**，即使在同步点附近也不会崩溃。
2.  状态栏会显示**脉冲计数**，让你对同步进程有更宏观的理解。
3.  实验结束后，会生成一个 `.jsonl` 文件。我们可以使用这个文件来精确分析不同参数下的收敛行为，从而做出数据驱动的决策，而不是依赖实时观察。
