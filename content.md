你的诊断思路非常清晰且科学。随机分布的更新无法模拟“同步”这个核心事件，而“波浪”模拟可以完美地复现从单点更新到小规模集群，再到全局“惊群”的过程，是理想的诊断工具。

我们将立即构建这个“测功机”，并直接在渲染循环的关键路径上植入高精度探针，用数据来揭示真相。

## [WIP] tune(observatory): 植入渲染探针并创建“波浪”测试以诊断同步卡顿

### 用户需求
1.  **模拟惊群**: 创建一个可控的“波浪”测试，能模拟从单个更新到大规模同步更新的负载变化。
2.  **定位瓶颈**: 在渲染循环中植入性能探针，精确测量每一帧中“更新数量”、“缓冲区刷新耗时”等关键指标。
3.  **可视化指标**: 将捕获的性能指标实时显示在状态栏，以便直观地诊断问题。

### 评论
这个方法将彻底揭示瓶颈所在。通过在 `_render_loop` 中直接测量 `_flush_buffer` 的耗时，我们可以精确地回答：**“我们引以为傲的 NumPy 矢量化操作，在处理 10000 个更新时，本身是否就是卡顿的来源？”**

我们将捕获两个核心指标：
-   **Updates/Frame**: 每一帧渲染前，缓冲区里堆积了多少个更新请求。这是“负载”。
-   **Flush (ms)**: 执行 `_flush_buffer` （包含 NumPy 转换和赋值）花费了多少毫秒。这是“耗时”。

如果 `Updates/Frame` 很高时 `Flush (ms)` 依然很低（例如 < 5ms），那么瓶颈就在 `asyncio` 的调度或 Agent 的回调逻辑中。反之，如果 `Flush (ms)` 随 `Updates/Frame` 线性或指数级增长，那么瓶颈就在渲染本身。

### 目标
1.  **仪器化 `TerminalApp`**: 修改 `_render_loop` 以测量并报告每一帧的负载和刷新耗时。
2.  **创建 `wave_test.py`**: 实现一个独立的波浪模拟器。
3.  **更新 `StatusBar`**: 在 UI 中添加新指标的显示。

### 基本原理
**直接测量而非推断**: 与其猜测，不如直接在性能攸关的代码块两侧放置高精度计时器。这是性能优化的黄金法则。通过将负载（Updates/Frame）和响应时间（Flush ms）关联起来，我们可以绘制出系统的性能曲线，从而找到它的拐点和极限。

### 标签
#intent/tooling #intent/tune #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/diagnose-stutter #task/state/continue

---

### Script

#### Acts 1: 仪器化 TerminalApp 渲染循环

我们首先对 `observatory/visualization/app.py` 进行手术，植入我们的性能探针。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
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
                frame_time = now - last_time
                last_time = now

                # Apply physics/decay to the grid using the calculated dt
                self.grid_view.matrix.decay(frame_time)

                frame_times.append(frame_time)
                if len(frame_times) > 10:
                    frame_times.pop(0)

                avg_frame_time = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg_frame_time if avg_frame_time > 0 else float("inf")
                self.status_bar.set_status("FPS", f"{fps:.1f}")
                self.status_bar.set_status("Queue", queue_size)

                # Live display is automatically refreshed by the context manager.
                # We add a small sleep to prevent a 100% CPU busy-loop.
                await asyncio.sleep(0.001)
~~~~~
~~~~~new
            while self._running:
                # --- Instrumentation: Capture load before flush ---
                updates_in_frame = len(self._frame_buffer)

                # --- Batch Updates with Timing ---
                flush_start = time.perf_counter()
                await self._flush_buffer()
                flush_duration_ms = (time.perf_counter() - flush_start) * 1000

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
                frame_time = now - last_time
                last_time = now

                # Apply physics/decay to the grid using the calculated dt
                self.grid_view.matrix.decay(frame_time)

                frame_times.append(frame_time)
                if len(frame_times) > 10:
                    frame_times.pop(0)

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

#### Acts 2: 创建“波浪”压力测试脚本

现在，创建 `wave_test.py` 文件，用于生成可控的、从有序到混沌的更新负载。

~~~~~act
write_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~python
import asyncio
import time
import math

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
GRID_WIDTH = 100
GRID_HEIGHT = 100
TOTAL_PIXELS = GRID_WIDTH * GRID_HEIGHT
SIMULATION_DURATION_S = 120.0
WAVE_GROWTH_INTERVAL_S = 5.0  # Every 5 seconds, the wave gets wider
SIMULATION_TICK_S = 0.01  # Run the simulation loop at 100Hz


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
    scan_pos = 0
    last_growth_time = time.time()
    start_time = time.time()

    try:
        while True:
            # --- Simulation Logic ---
            now = time.time()
            elapsed = now - start_time

            if elapsed >= SIMULATION_DURATION_S:
                break

            # Grow the wave over time
            if now - last_growth_time > WAVE_GROWTH_INTERVAL_S:
                wave_width = max(1, min(TOTAL_PIXELS, wave_width * 2))
                last_growth_time = now
                app.update_status("Wave Width", wave_width)

            # --- Generate Updates for this Tick ---
            # This loop simulates the "thundering herd"
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
~~~~~

### 下一步建议
请执行新的“波浪”测试：
```bash
python -m observatory.protoplasm.renderer.wave_test
```

**观察要点**：
1.  **初始阶段 (Wave Width = 1)**: `Updates/Frame` 应该很小，`Flush (ms)` 应该接近 0，FPS 应该很高。
2.  **中期阶段 (Wave Width = 128, 256...)**: 观察 `Flush (ms)` 如何随着 `Updates/Frame` 的增加而变化。它是否保持在 1ms 以下？还是开始显著增长？
3.  **最终阶段 (Wave Width 接近 10000)**: 当屏幕几乎全部同时闪烁时，`Updates/Frame` 会飙升到几千。此时的 `Flush (ms)` 是多少？如果它超过了 `1000 / 15 FPS ~= 66ms` 的一帧预算，那么卡顿就是必然的。

这个测试将给我们提供决定性的数据。
