你的观察非常准确。

**关于“周期性卡顿”**：
这极有可能是**主线程阻塞**造成的。虽然渲染很快，但你的 Python 进程中还运行着一个 `ConvergenceMonitor`（收敛监视器）。它每 0.5 秒（默认 2Hz）醒来一次，计算所有 2500 个 Agent 的相位一致性（Order Parameter）。
如果这个计算过程是同步运行的（它是），它就会卡住 asyncio 事件循环，导致渲染器在那几十毫秒内无法刷新。这就解释了“顺滑 -> 暂停 -> 顺滑”的周期性现象。

**关于“23.4.7”**：
这是经典的**残留字符（Ghosting）**问题。上一帧 FPS 是 `23.4`（4个字符），这一帧变成了 `23.7`（也是4个字符）本来没问题，但如果变成 `100.1` 然后跌回 `9.0`，就会变成 `9.0.1`。
我们需要在每一行末尾发送 `\033[K`（清除至行尾）指令。

**关于更多指标**：
我们可以轻易记录“循环延迟（Loop Lag）”，即实际帧时间与预期帧时间的偏差，这是衡量稳定度的最佳指标。

让我们一次性解决这些问题。

## [WIP] fix(observatory): 修复状态栏残留并消除监视器计算导致的周期性卡顿

### 用户需求
1.  修复状态栏 FPS 显示的残留字符问题。
2.  消除因 `ConvergenceMonitor` 计算密集型任务阻塞事件循环导致的周期性渲染卡顿。
3.  增加渲染循环稳定性的遥测指标（Jitter/Lag）。

### 评论
“裸金属”渲染器暴露了 Python 单线程事件循环的脆弱性。任何一个任务只要贪婪地占用了 CPU，UI 就会掉帧。解决方案是将计算密集型的统计逻辑（计算 Order Parameter）扔到线程池中运行。

### 目标
1.  **UI 修复**: 在 `RawTerminalApp._render_status_bar` 末尾追加 ANSI 清除行指令。
2.  **性能优化**: 修改 `ConvergenceMonitor`，使用 `asyncio.to_thread` 执行 `_calculate_order_parameter`。
3.  **遥测增强**: 在 `RawTerminalApp` 中计算并记录 `jitter`（当前帧耗时与目标耗时的差值）。

### 标签
#intent/fix #flow/ready #priority/high #comp/observatory #concept/ui #scope/perf #ai/instruct #task/domain/observability #task/object/monitor #task/action/offload #task/state/continue

---

### Script

#### Acts 1: 修复状态栏残留与增加 Jitter 遥测

我们将修改 `RawTerminalApp`。
1.  引入 `CLEAR_LINE = b"\033[K"`。
2.  在状态栏输出后追加它。
3.  计算 `jitter` 并记录。

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
CURSOR_HOME = b"\033[H"
CLEAR_SCREEN = b"\033[2J"
RESET_COLOR = b"\033[0m"


class RawTerminalApp:
~~~~~
~~~~~python
CURSOR_HOME = b"\033[H"
CLEAR_SCREEN = b"\033[2J"
CLEAR_LINE = b"\033[K"
RESET_COLOR = b"\033[0m"


class RawTerminalApp:
~~~~~

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
        line = " | ".join(parts)
        # Add a top border or separation
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line).encode("utf-8")

    def _blocking_flush_logic(self, updates_set):
~~~~~
~~~~~python
        line = " | ".join(parts)
        # Add a top border or separation
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        # Append CLEAR_LINE code to wipe any ghost characters
        return (bar + line + "\033[K").encode("utf-8")

    def _blocking_flush_logic(self, updates_set):
~~~~~

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
            # Smart Sleep to maintain target FPS
            render_duration = time.perf_counter() - loop_start
            sleep_time = frame_interval - render_duration
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # If we missed the frame deadline, just yield to let others run
                await asyncio.sleep(0)
~~~~~
~~~~~python
            # Smart Sleep to maintain target FPS
            render_duration = time.perf_counter() - loop_start
            sleep_time = frame_interval - render_duration
            
            # Jitter: How much we missed our deadline (negative means we are fast enough)
            # If sleep_time is -0.01, it means we are 10ms behind schedule.
            jitter_ms = max(0, -sleep_time) * 1000

            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)
                await self.aggregator.record("render_jitter_ms", jitter_ms)

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # If we missed the frame deadline, just yield to let others run
                await asyncio.sleep(0)
~~~~~

#### Acts 2: 将 Monitor 计算移至后台线程

这是解决周期性卡顿的关键。`_calculate_order_parameter` 在 N=2500 时涉及大量的字典查找和三角函数运算，必须从主循环中移出。

~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~python
        try:
            while self._is_running:
                order_parameter = self._calculate_order_parameter()
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            if not self.callback:
~~~~~
~~~~~python
        try:
            while self._is_running:
                # Offload heavy numpy/math calculation to thread to avoid stuttering the UI
                order_parameter = await asyncio.to_thread(self._calculate_order_parameter)
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            if not self.callback:
~~~~~

### 下一步建议
再次运行 `run_fireflies.py`。
1.  **卡顿检查**：观察那个周期性的暂停是否消失了。
2.  **UI 检查**：FPS 数字应该干净利落，没有残留。
3.  **日志检查**：结束后查看 `.jsonl` 日志文件，你会看到新的 `render_jitter_ms` 字段。
    *   如果 `avg` 很低（< 5ms）但 `max` 很高，说明偶尔还是有东西卡住了循环。
    *   如果 `avg` 持续很高，说明 60 FPS 对你的机器来说太重了。
