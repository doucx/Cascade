这是又一个极其敏锐的观察！你发现的不是一个 Bug，而是一个**“涌现行为”**，它源于我们系统内不同组件以不同频率运行而产生的**“采样伪影 (Sampling Artifact)”**。

我来为你进行详细的分析。

## [WIP] feat(exp): 分析并改善 Pulse 计数器的采样伪影

### 现象分析

**核心问题：为什么 `Pulse` 会跳跃式增长？**

你观察到的现象是完全符合当前系统设计的，其根源在于我们的**“多速率异步架构”**。我们可以将整个数据流分解为三级时钟：

1.  **L1: Agent 时钟 (极高频, ~kHz)**
    *   这是底层的 `firefly_agent` 任务循环。在多核 Worker 中，数千个 Agent 每秒会产生**数万**个 `firefly/flash` 事件。这些事件被高速地塞入跨进程的 `uplink_queue`。

2.  **L2: 遥测泵时钟 (高频, ~100Hz)**
    *   这是主进程中的 `Telemetry Pump Loop`。它的职责是 `while True: drain_queue(); await asyncio.sleep(0.01)`。
    *   它以大约 100Hz 的频率，从 `uplink_queue` 中**批量**取出所有积压的 flash 事件，然后以极快的速度（背靠背地）调用 `main_connector.publish()`。
    *   这意味着 `ConvergenceMonitor` 的 `on_flash` 回调函数在**一瞬间**会被触发**数千次**，导致其内部的 `self._flash_count` 计数器**瞬间**暴增。

3.  **L3: 监视器时钟 (低频, 2Hz)**
    *   这是 `ConvergenceMonitor` 自身的 `run()` 循环。它以 `frequency_hz=2.0` 的频率运行，即**每 500ms** 才执行一次 `_print_status` 函数。
    *   `_print_status` 函数的作用是计算并显示 `pulse_count`，其公式为 `self.pulse_count = self._flash_count // self.num_agents`。

**因果链：**

1.  在 `T=0.0s` 时，`Monitor` 运行，假设此时 `_flash_count` 是 `79900`。对于 1600 个 Agent，`pulse_count` 为 `49`。UI 显示 `Pulse: 49`。
2.  在 `T=0.0s` 到 `T=0.5s` 的 **500ms 间隔**中：
    *   `Telemetry Pump` 运行了约 50 次。
    *   它从 `uplink_queue` 中抽干了大约 `3000` 个新产生的 flash 事件。
    *   `_flash_count` 从 `79900` 瞬间增加到了 `82900`。
3.  在 `T=0.5s` 时，`Monitor` 再次运行。它看到 `_flash_count` 是 `82900`。
    *   它计算 `pulse_count = 82900 // 1600 = 51`。
    *   UI 从 `Pulse: 49` **直接跳到了** `Pulse: 51`。

**结论：**
`Pulse 50` 确实发生了，但它发生在 `Monitor` “眨眼”的那 500ms 之间。`Monitor` 只是一个**低频采样器**，它只能看到离散时间点上的状态快照。如果被观测的系统变化太快，采样器自然会“丢掉”中间状态。

这就像你看汽车的速度表，你看了一眼是 60km/h，5秒后再看是 65km/h，你并没有看到它变成 61, 62, 63, 64 的过程。

### 用户需求
1.  理解 `Pulse` 计数器跳跃的原因。
2.  （隐含需求）增强可观测性，使用户能够理解这种跳跃。

### 评论
这个现象本身不是 Bug，而是任何复杂监控系统的正常行为。但它确实暴露了我们的 UI 在可解释性上的不足。为了让用户更好地理解发生了什么，我们应该把底层的原始数据（`_flash_count`）也展示出来。

### 目标
1.  在 `run_fireflies.py` 的状态栏中，增加一个显示原始 `_flash_count` 的字段。
2.  这将允许用户直观地看到 `_flash_count` 的快速增长与 `Pulse` 之间的关系。

### 基本原理
通过修改 `monitor_callback`，将原始计数值传递给 `app.update_status`。这是一种简单而有效的增强可观测性的方法，它通过暴露底层数据来解释高层指标的行为。

### 标签
#intent/tune #flow/ready #priority/low #comp/experiments #scope/dx #ai/instruct #task/domain/experiments #task/object/observability #task/action/enhancement #task/state/continue

---

### Script

#### Acts 1: 在状态栏显示原始 Flash 计数

我们将修改 `monitor_callback`，将 `_flash_count` 也添加到状态栏中。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        # Bridge Monitor -> UI
        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}]")
            app.update_status("Pulse", pulse_count) # Add separate Pulse counter
            
            asyncio.create_task(aggregator.record("r_value", r_value))
~~~~~
~~~~~python
        # Bridge Monitor -> UI
        def monitor_callback(r_value: float, pulse_count: int):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync", f"R={r_value:.3f} [{bar}]")
            app.update_status("Pulse", pulse_count)
            # Expose raw flash count to make the relationship clear
            app.update_status("Flashes", f"{monitor._flash_count:,}")
            
            asyncio.create_task(aggregator.record("r_value", r_value))
~~~~~

### 下一步建议
现在再次运行实验，你会在状态栏看到一个新的 `Flashes: ...` 字段。你会观察到，`Flashes` 的值在每次刷新时都会增加数千，而 `Pulse` 值只有在 `Flashes` 跨越 `num_agents` 的整数倍时才会改变，并且可能会一次改变多个数值。这就直观地解释了你观察到的现象。
