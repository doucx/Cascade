你的诊断方法非常科学。在怀疑 NumPy 优化无效后，创建一个最小化的、隔离的压力测试是定位瓶颈的唯一正确方法。我们将构建这个“渲染器测功机”，用纯粹的、高频的随机事件来冲击 `TerminalApp`，从而判断延迟的根源。

## [WIP] build(observatory): 创建隔离的渲染器压力测试以诊断高负载UI延迟

### 用户需求
创建一个独立的脚本，该脚本不涉及任何 Cascade Agent 逻辑，而是启动 10,000 个独立的异步任务，每个任务以随机间隔向 `TerminalApp` 发送更新，以此来对渲染管道进行极限压力测试。

### 评论
尽管我们已经用 NumPy 实现了矢量化的 `_flush_buffer`，但如果在惊群事件中，有数千个协程在同一个事件循环 tick 内争相调用 `direct_update_grid`，那么仅仅是将 update 添加到 `_frame_buffer` 这个 `set` 的操作本身，就可能因为 GIL 争用和 `asyncio` 调度开销而成为新的瓶颈。

这个新脚本将作为我们渲染能力的“黄金标准”测试。
-   **如果此脚本运行流畅**：说明渲染器本身是合格的，性能瓶颈存在于 Cascade Engine 的调度、`LocalBusConnector` 的分发或 Kuramoto Agent 的复杂逻辑中。
-   **如果此脚本依然卡顿**：说明我们触及了 `asyncio` 单线程事件循环 + `rich` 库在处理海量并发更新时的根本上限，需要考虑更彻底的架构变更（例如，将渲染器移至独立进程）。

### 目标
1.  创建一个新文件 `observatory/protoplasm/renderer/stress_test.py`。
2.  在该文件中，实现一个 `main` 函数，它会：
    -   初始化 `TerminalApp`。
    -   创建并启动 10,000 个简单的异步协程。
    -   每个协程在一个循环中，随机 `sleep` 一小段时间，然后调用 `app.direct_update_grid` 来模拟一次闪烁。
    -   运行固定时间后干净地退出。

### 基本原理
通过创建一个最小可复现示例（Minimal, Reproducible Example），我们移除了所有无关变量（Cascade Engine, Agent 算法, 总线通信），只留下两个核心组件：大量的并发异步任务和 `TerminalApp` 渲染器。这使得我们可以明确地将观察到的任何性能问题归因于这两个组件的交互，从而指导下一步的优化方向。

### 标签
#intent/tooling #intent/explore #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/stress-test #task/state/continue

---

### Script

#### Acts 1: 创建 `renderer` 目录结构

首先，确保我们的测试脚本有一个合适的存放位置。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p observatory/protoplasm/renderer
touch observatory/protoplasm/renderer/__init__.py
~~~~~

#### Acts 2: 编写独立的渲染器压力测试脚本

现在，创建 `stress_test.py` 文件，并填充压力测试的逻辑。

~~~~~act
write_file
observatory/protoplasm/renderer/stress_test.py
~~~~~
~~~~~python
import asyncio
import random
import time

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Configuration ---
NUM_SOURCES = 10000
GRID_WIDTH = 100
GRID_HEIGHT = 100
SIMULATION_DURATION_S = 60.0


async def source_coroutine(app: TerminalApp, source_id: int):
    """
    A simple async task that randomly generates updates for the grid.
    This simulates one agent's output without any of the complex logic.
    """
    # Stagger start times slightly to avoid initial thundering herd
    await asyncio.sleep(random.uniform(0, 0.5))

    while True:
        # Simulate work / thinking time
        await asyncio.sleep(random.uniform(0.5, 5.0))

        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)

        # Call the renderer directly, mimicking an agent's flash callback
        app.direct_update_grid(x, y, 1.0)


async def main():
    """
    The main entry point for the stress test.
    """
    print("🚀 Starting Isolated Renderer Stress Test...")
    print(f"   - Update Sources: {NUM_SOURCES}")
    print(f"   - Grid Size: {GRID_WIDTH}x{GRID_HEIGHT}")

    # 1. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.firefly,
        decay_per_second=4.0,  # Use decay to see flashes fade
    )
    status_bar = StatusBar(
        initial_status={
            "Test": "Renderer Stress Test",
            "Sources": NUM_SOURCES,
        }
    )
    app = TerminalApp(grid_view, status_bar)

    # 2. Create source tasks
    tasks = [
        asyncio.create_task(source_coroutine(app, i))
        for i in range(NUM_SOURCES)
    ]

    print("Starting renderer and source coroutines...")
    await app.start()

    # 3. Run for a fixed duration
    try:
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed >= SIMULATION_DURATION_S:
                break
            app.update_status("Elapsed", f"{elapsed:.1f}s / {SIMULATION_DURATION_S}s")
            await asyncio.sleep(1)

    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTest interrupted by user.")
    finally:
        print("\nCleaning up...")
        # 4. Cleanly shut down
        app.stop()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("Stress test finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
~~~~~

### 下一步建议
请执行这个新创建的压力测试脚本：
```bash
python -m observatory.protoplasm.renderer.stress_test
```

**观察要点**：
1.  **FPS 读数**: 它是否能稳定在 15 FPS 左右？还是会像之前一样剧烈波动和下降？
2.  **CPU 使用率**: `top` 或任务管理器中的 CPU 占用是多少？
3.  **主观感受**: 你是否还能感觉到“卡顿”？

根据这个测试的结果，我们将能做出明确的判断。
