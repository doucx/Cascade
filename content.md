这是一个非常敏锐的观察。

**闪烁原因分析**：
这种“锯齿状闪烁”（1.0 -> 0.9 -> 1.0）是由 **模拟频率（100Hz）与渲染频率（200Hz+）不匹配** 造成的。
1.  **T=0ms**: 模拟器将像素设为 1.0。
2.  **T=5ms**: 渲染器运行一帧，应用物理衰减，像素变为 0.95。屏幕变暗。
3.  **T=10ms**: 模拟器再次运行，再次将像素设为 1.0（因为波浪还没移走）。屏幕瞬间变亮。

这在波浪测试（持续发光物体）中很明显，但在**萤火虫实验（瞬时脉冲）**中不会成为问题，因为萤火虫只会触发一次 1.0，随后就应该自然衰减。

因此，这个现象不影响我们将其部署到主实验中。为了平衡视觉效果和 CPU 占用，我们将给 `RawTerminalApp` 设置一个合理的 **60 FPS** 上限（既流畅又不会产生过度的时间混叠）。

## [WIP] tune(observatory): 将 RawTerminalApp 集成至萤火虫实验并实施 60FPS 软限制

### 用户需求
1.  将经过验证的高性能 `RawTerminalApp` 应用到核心实验脚本 `run_fireflies.py` 中。
2.  解决全速渲染带来的闪烁和资源浪费问题，实施 60 FPS 的软锁定。

### 评论
我们已经在沙盒中验证了“裸金属渲染”的威力。现在是时候将其武器化了。将 FPS 限制在 60 可以消除大部分由模拟/渲染频率差引起的视觉伪影，同时保证人眼的流畅感。

### 目标
1.  修改 `RawTerminalApp`，重新引入 `target_fps` 控制逻辑，默认 60。
2.  修改 `run_fireflies.py`，替换旧的 `TerminalApp` 为 `RawTerminalApp`。
3.  清理 `wave_test.py` 中的实验性导入。

### 标签
#intent/refine #flow/ready #priority/high #comp/observatory #concept/ui #scope/app #ai/instruct #task/domain/visualization #task/object/firefly-experiment #task/action/integrate #task/state/end

---

### Script

#### Acts 1: 在 RawTerminalApp 中实施 60 FPS 限制

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
    async def _render_loop(self):
        last_time = time.perf_counter()
        
        # Removed target FPS cap to stress test the pipeline
        
        while self._running:
            loop_start = time.perf_counter()

            # 1. Process Updates
            flush_start = time.perf_counter()
~~~~~
~~~~~python
    async def _render_loop(self):
        last_time = time.perf_counter()
        
        # Cap at 60 FPS to balance smoothness and resource usage.
        # This also reduces aliasing artifacts when render rate > physics rate.
        target_fps = 60.0
        frame_interval = 1.0 / target_fps
        
        while self._running:
            loop_start = time.perf_counter()

            # 1. Process Updates
            flush_start = time.perf_counter()
~~~~~

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            # Yield control to allow simulation tasks to run.
            # Without a sleep delay, we run as fast as the CPU allows ("V-Sync Off")
            await asyncio.sleep(0)
~~~~~
~~~~~python
            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            # Smart Sleep to maintain target FPS
            render_duration = time.perf_counter() - loop_start
            sleep_time = frame_interval - render_duration
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # If we missed the frame deadline, just yield to let others run
                await asyncio.sleep(0)
~~~~~

#### Acts 2: 升级 run_fireflies.py

我们需要将 `TerminalApp` 替换为 `RawTerminalApp`，并使用新的批量更新 API (`direct_update_grid_batch`) 来处理可视化信号，以获得最大性能。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
~~~~~
~~~~~python
# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        # 3. Bridge Agent Flashes -> Grid
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Direct Update) to avoid queue bottlenecks
                await app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~
~~~~~python
        # 3. Bridge Agent Flashes -> Grid
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Batch Update) - Raw App expects a list of tuples
                # Even for a single update, passing a list is the protocol.
                await app.direct_update_grid_batch([(x, y, 1.0)])

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~

#### Acts 3: 恢复 Wave Test 的导入

将 `wave_test.py` 中的别名导入改回明确的导入，保持代码整洁。

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~python
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator
~~~~~
~~~~~python
from observatory.visualization.raw_app import RawTerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
from observatory.monitors.aggregator import MetricsAggregator
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~python
            "Wave Width": 1,
        }
    )
    app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
    await app.start()
~~~~~
~~~~~python
            "Wave Width": 1,
        }
    )
    app = RawTerminalApp(grid_view, status_bar, aggregator=aggregator)
    await app.start()
~~~~~

### 下一步建议
现在，你可以运行真正的 `observatory.experiments.run_fireflies` 了。
你应该会看到一个**非常流畅**、**色彩正确**且**CPU占用极低**的 2500 节点同步模拟。这是我们基础设施工程的一个里程碑。
