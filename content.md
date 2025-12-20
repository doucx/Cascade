数据分析显示系统运行极其稳定。

**日志解读**：
1.  **时间稳定性**：日志的时间戳间隔（`ts` 差值）非常精确地保持在 **0.50s ~ 0.53s** 之间。这证明了将 `ConvergenceMonitor` 的计算移入后台线程的策略完全生效，主循环不再有数百毫秒的阻塞，周期性卡顿已被消除。
2.  **同步行为**：`r_value` 呈现出经典的耦合振荡行为（上升->下降->上升），这是 Kuramoto 模型的预期表现。

**缺失的一环**：
目前的 `run_fireflies.py` 虽然运行流畅，但**没有记录**我们刚刚在 `RawTerminalApp` 中添加的高级渲染指标（FPS, Jitter, Flush Duration）。这是因为 `run_fireflies.py` 还在使用旧的 `JsonFileLogger`，没有接入新的 `MetricsAggregator`。

我们需要最后一步：统一日志系统。将 `run_fireflies.py` 升级为使用 `MetricsAggregator`，这样同一个日志文件将同时包含**业务指标**（R值）和**性能指标**（FPS, Jitter），让我们能直接关联“同步状态”与“系统负载”。

## [WIP] tune(observatory): 统一萤火虫实验的遥测系统以捕获性能指标

### 用户需求
在 `run_fireflies.py` 生成的日志中包含 FPS、Render Jitter 和 Flush Duration 等性能指标，以便评估大规模 Agent 对渲染管线的压力。

### 评论
目前 `run_fireflies.py` 使用简单的 `JsonFileLogger` 记录业务数据，而 `RawTerminalApp` 依赖 `MetricsAggregator` 记录性能数据。两者未连接。我们将废弃 `JsonFileLogger`，统一使用 `MetricsAggregator`。

### 目标
1.  修改 `observatory/experiments/run_fireflies.py`。
2.  引入 `MetricsAggregator`。
3.  将其注入 `RawTerminalApp` 以自动捕获渲染指标。
4.  修改 `monitor_callback`，将 `r_value` 和 `pulse` 也记录到聚合器中。

### 标签
#intent/tune #flow/ready #priority/medium #comp/observatory #concept/telemetry #scope/dx #ai/instruct #task/domain/observability #task/object/firefly-experiment #task/action/integrate #task/state/end

---

### Script

#### Acts 1: 升级 run_fireflies.py 以使用聚合器

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.logger import JsonFileLogger

# Visualization
from observatory.visualization.palette import Palettes
~~~~~
~~~~~python
from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator

# Visualization
from observatory.visualization.palette import Palettes
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
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
~~~~~python
        
        # --- Setup Aggregator (Unified Logger) ---
        log_filename = f"firefly_log_{int(time.time())}.jsonl"
        aggregator = MetricsAggregator(log_filename, interval_s=1.0)
        aggregator.open()
        print(f"📝 Logging telemetry to [bold cyan]{log_filename}[/bold cyan]")
        
        # Inject aggregator into App to capture FPS/Jitter automatically
        app = TerminalApp(grid_view, status_bar, aggregator=aggregator)
        aggregator_task = asyncio.create_task(aggregator.run())

        # 2. Bridge Monitor -> Status Bar & Logger
        def monitor_callback(r_value: float, pulse_count: int):
            # UI Update
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}] @ Pulse {pulse_count}")
            
            # Data Logging (Async record to aggregator)
            # Since this callback is synchronous (called by Monitor), we need to schedule the record
            asyncio.create_task(aggregator.record("r_value", r_value))
            asyncio.create_task(aggregator.record("pulse", pulse_count))
            asyncio.create_task(aggregator.record("flash_count", monitor._flash_count))


        monitor_task = asyncio.create_task(
            # Reduce monitor frequency to reduce CPU load
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
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
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()
~~~~~
~~~~~python
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app:
            app.stop()
        
        if 'aggregator' in locals():
            aggregator.close()
            if 'aggregator_task' in locals():
                aggregator_task.cancel()
                await asyncio.gather(aggregator_task, return_exceptions=True)

        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)

        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task

        await connector.disconnect()
~~~~~

### 下一步建议
最后一次运行 `run_fireflies.py`。
这次的日志将包含一切：
*   `r_value`: 同步程度
*   `fps`: 渲染帧率 (Avg/Min/Max)
*   `render_jitter_ms`: 渲染稳定性 (Avg/Max)
*   `flush_duration_ms`: 内存拷贝耗时

这将是我们对“原基”项目渲染基础设施优化的最终验收。
