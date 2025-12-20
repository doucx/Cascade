好的，我理解了。你发现了两个关键问题：
1.  **Bug**: 我的波浪模拟器逻辑有误，扫描点没有正确地循环。
2.  **需求**: 需要一个更复杂的日志系统，它能基于滑动窗口计算并输出平均指标，以便平滑噪声，观察趋势。

这表明我们需要一个更专业的“遥测仪器”。我将立即为你构建它，并修复模拟器的 bug。

## [WIP] fix(observatory): 修复波浪循环并实现滑动窗口指标聚合器

### 错误分析
`wave_test.py` 中的 `scan_pos` 变量一直在递增，没有在达到 `TOTAL_PIXELS` 时归零。这导致扫描点在完成一次全屏扫描后，就跑到了数组范围之外，因此在屏幕上“消失”。这是一个简单的模运算 (`%`) 遗漏。

### 用户需求
1.  修复 `wave_test.py` 中的扫描点循环 bug。
2.  创建一个新的日志记录器 `MetricsAggregator`，它能：
    -   在内存中收集一秒内的所有指标数据（FPS, Flush ms, Upd/Frame）。
    -   每秒钟计算一次这些数据的统计信息（平均值、最大值、最小值、总数）。
    -   将这些聚合后的统计数据作为单行 JSON 写入日志文件。

### 评论
这个滑动窗口聚合器是一个强大的诊断工具。瞬时的 `Flush (ms)` 可能会因为事件循环的调度抖动而出现巨大噪声（例如，一帧是 0.1ms，下一帧是 50ms）。通过记录每秒的**平均值**和**最大值**，我们可以过滤掉这种噪声，清晰地看到系统在不同负载下的**真实性能趋势**。这将为我们提供最终诊断所需的、高质量的数据。

### 目标
1.  创建一个新的 `observatory/monitors/aggregator.py` 文件，并实现 `MetricsAggregator` 类。
2.  将 `MetricsAggregator` 集成到 `TerminalApp` 的渲染循环中。
3.  修复 `wave_test.py` 中的循环 bug，并让它使用新的聚合器。

### 基本原理
**信号处理**: 我们正在从处理“原始信号”（每帧的指标）转向处理“降噪后的信号”（每秒的统计数据）。这在所有工程和科学领域都是分析动态系统的标准方法。`MetricsAggregator` 本质上是一个用于性能遥测的低通滤波器。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/observatory #scope/dx #task/domain/observatory #task/object/telemetry #task/action/aggregate-metrics #task/state/continue

---

### Script

#### Acts 1: 创建滑动窗口指标聚合器

我们首先创建这个新的、更智能的日志记录器。

~~~~~act
write_file
observatory/monitors/aggregator.py
~~~~~
~~~~~python
import asyncio
import time
import json
import numpy as np
from collections import defaultdict
from typing import IO


class MetricsAggregator:
    """
    Collects high-frequency metrics and logs their aggregate statistics
    (avg, max, min, count) at a fixed interval.
    """

    def __init__(self, filename: str, interval_s: float = 1.0):
        self.filename = filename
        self.interval = interval_s
        self._file: IO | None = None
        self._buffer = defaultdict(list)
        self._lock = asyncio.Lock()
        self._next_flush_time = time.time() + self.interval

    def open(self):
        """Opens the log file."""
        self._file = open(self.filename, "w", encoding="utf-8")

    def close(self):
        """Closes the log file."""
        if self._file:
            # Flush any remaining data before closing
            self._flush_and_log(force=True)
            self._file.close()
            self._file = None

    async def record(self, key: str, value: float):
        """Records a single metric data point."""
        async with self._lock:
            self._buffer[key].append(value)

    def _flush_and_log(self, force: bool = False):
        now = time.time()
        if not force and now < self._next_flush_time:
            return

        # --- Critical Section ---
        # Atomically swap buffer to minimize lock time
        # Note: In asyncio, lock isn't strictly needed for this part if there are no awaits,
        # but it's good practice for clarity and future-proofing.
        buffer_to_process = self._buffer
        self._buffer = defaultdict(list)
        # --- End Critical Section ---
        
        if not self._file or not buffer_to_process:
            self._next_flush_time = now + self.interval
            return
            
        stats = {"ts": now}
        for key, values in buffer_to_process.items():
            if not values:
                continue
            
            arr = np.array(values)
            stats[key] = {
                "avg": np.mean(arr),
                "max": np.max(arr),
                "min": np.min(arr),
                "sum": np.sum(arr),
                "count": len(values),
            }
        
        json.dump(stats, self._file, default=float)
        self._file.write("\n")
        self._file.flush()

        self._next_flush_time = now + self.interval

    async def run(self):
        """The main loop that periodically flushes the buffer."""
        while self._file is not None:
            self._flush_and_log()
            await asyncio.sleep(self.interval / 10) # Wake up 10x per interval for responsiveness
~~~~~

#### Acts 2: 将聚合器集成到 TerminalApp

现在，让 `TerminalApp` 使用这个新工具。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
class TerminalApp:
    """
    The main application class for managing the live terminal UI.
    It orchestrates the layout and handles data ingestion and rendering loop.
    """

    def __init__(self, grid_view: GridView, status_bar: StatusBar):
        self.grid_view = grid_view
        self.status_bar = status_bar

        self.layout = Layout()
~~~~~
~~~~~new
class TerminalApp:
    """
    The main application class for managing the live terminal UI.
    It orchestrates the layout and handles data ingestion and rendering loop.
    """

    def __init__(self, grid_view: GridView, status_bar: StatusBar, aggregator: 'MetricsAggregator' = None):
        self.grid_view = grid_view
        self.status_bar = status_bar
        self.aggregator = aggregator

        self.layout = Layout()
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
                avg_frame_time = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg_frame_time if avg_frame_time > 0 else float("inf")
                
                # --- Update Status Bar with New Metrics ---
                self.status_bar.set_status("FPS", f"{fps:.1f}")
                self.status_bar.set_status("Upd/Frame", f"{updates_in_frame}")
                self.status_bar.set_status("Flush (ms)", f"{flush_duration_ms:.2f}")

                # Live display is automatically refreshed by the context manager.
                # We add a small sleep to prevent a 100% CPU busy-loop.
                await asyncio.sleep(0.001)
~~~~~
~~~~~new
                avg_frame_time = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg_frame_time if avg_frame_time > 0 else float("inf")
                
                # --- Update Status Bar with New Metrics ---
                self.status_bar.set_status("FPS", f"{fps:.1f}")
                self.status_bar.set_status("Upd/Frame", f"{updates_in_frame}")
                self.status_bar.set_status("Flush (ms)", f"{flush_duration_ms:.2f}")

                # --- Record Metrics for Aggregation ---
                if self.aggregator:
                    await self.aggregator.record("fps", fps)
                    await self.aggregator.record("updates_per_frame", updates_in_frame)
                    await self.aggregator.record("flush_duration_ms", flush_duration_ms)

                # Live display is automatically refreshed by the context manager.
                # We add a small sleep to prevent a 100% CPU busy-loop.
                await asyncio.sleep(0.001)
~~~~~

#### Acts 3: 修复并升级“波浪”测试

最后，修复 `wave_test.py` 的 bug，并让它驱动新的聚合器。

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~old
import asyncio
import time
import math

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~
~~~~~new
import asyncio
import time
import math

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~old
async def main():
    """
    Main entry point for the wave test.
    """
    print("🚀 Starting Renderer Wave Stress Test...")

    # 1. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.firefly,
        decay_per_second=8.0,
    )
    status_bar = StatusBar(
        initial_status={
            "Test": "Wave Stress Test",
            "Wave Width": 1,
        }
    )
    app = TerminalApp(grid_view, status_bar)
    await app.start()

    # 2. Simulation State
    wave_width = 1
~~~~~
~~~~~new
async def main():
    """
    Main entry point for the wave test.
    """
    print("🚀 Starting Renderer Wave Stress Test...")
    log_filename = f"wave_test_log_{int(time.time())}.jsonl"

    # 1. Setup Logger
    aggregator = MetricsAggregator(log_filename)
    aggregator.open()
    print(f"📝 Logging aggregate metrics to [bold cyan]{log_filename}[/bold cyan]")

    # 2. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.firefly,
        decay_per_second=8.0,
    )
    status_bar = StatusBar(
        initial_status={
            "Test": "Wave Stress Test",
            "Wave Width": 1,
        }
    )
    app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
    await app.start()

    # 3. Start logger loop
    aggregator_task = asyncio.create_task(aggregator.run())

    # 4. Simulation State
    wave_width = 1
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~old
            for i in range(wave_width):
                current_pos = (scan_pos + i) % TOTAL_PIXELS
                x = current_pos % GRID_WIDTH
                y = current_pos // GRID_WIDTH
                app.direct_update_grid(x, y, 1.0)
            
            # Move the scanline forward
            scan_pos += math.ceil(GRID_WIDTH * 2 * SIMULATION_TICK_S) # Move 2 rows per second

            # --- Yield to Renderer ---
            await asyncio.sleep(SIMULATION_TICK_S)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTest interrupted.")
    finally:
        print("\nCleaning up...")
        app.stop()
        print("Wave test finished.")
~~~~~
~~~~~new
            for i in range(wave_width):
                current_pos = (scan_pos + i) % TOTAL_PIXELS
                x = current_pos % GRID_WIDTH
                y = current_pos // GRID_WIDTH
                app.direct_update_grid(x, y, 1.0)
            
            # Move the scanline forward and WRAP AROUND
            move_amount = math.ceil(GRID_WIDTH * 2 * SIMULATION_TICK_S) # Move 2 rows per second
            scan_pos = (scan_pos + move_amount) % TOTAL_PIXELS

            # --- Yield to Renderer ---
            await asyncio.sleep(SIMULATION_TICK_S)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTest interrupted.")
    finally:
        print("\nCleaning up...")
        app.stop()
        aggregator.close()
        aggregator_task.cancel()
        await asyncio.gather(aggregator_task, return_exceptions=True)
        print("Wave test finished.")
~~~~~

### 下一步建议
请再次执行 `wave_test.py`。
1.  你将看到扫描点现在会正确地从右下角循环回到左上角。
2.  最重要的是，实验结束后，当前目录会有一个 `wave_test_log_... .jsonl` 文件。
3.  **请将这个日志文件的内容发给我。**

有了这些聚合后的数据，我们就能一锤定音，判断卡顿的最终根源。
