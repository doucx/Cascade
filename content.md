**分析**：

测试结果实际上**非常成功**，我们解决了核心的性能问题，但由于过于保守的设置导致了视觉上的副作用。

1.  **性能胜利**：日志显示 `flush_duration_ms` 从之前的 **30ms+ 尖峰** 稳定到了 **~0.4ms**。这是两个数量级的提升！说明主线程的 GIL 争用问题已彻底解决。
2.  **FPS 锁定**：日志显示 FPS 稳定在 **29.4** 左右。这是因为我在 `RawTerminalApp` 中硬编码了 `target_fps = 30.0`。
3.  **消失的渐暗效果**：这就是 30 FPS 锁定的副作用。
    *   在 `wave_test` 中，衰减率 (`decay_per_second`) 设置为 **8.0**。
    *   在 30 FPS 下，每帧衰减量为 $8.0 / 30 \approx 0.27$。
    *   这意味着一个全亮的像素 (1.0) 只需要 **不到 4 帧** (0.13秒) 就会完全变黑。
    *   在人眼看来，这不再是“渐暗”，而是瞬间的“闪烁”或“消失”。

**解决方案**：

我们需要**解除 FPS 锁**。对于压力测试，我们应该让渲染器全速运行（"V-Sync OFF"）。当 FPS 提升到 100+ 时，每帧的衰减量会变小，动画的连续性就会恢复，丝滑的彗星尾巴效果将重现。

同时，为了防止在极高帧率下的除零错误或时间跳跃，我们会给 `dt` 增加一个安全钳位。

## [WIP] tune(observatory): 解除渲染器 FPS 锁定以恢复高频物理动态

### 用户需求
恢复波浪测试中的平滑渐暗效果，并验证渲染管线的极限吞吐量。

### 评论
当前的 30 FPS 限制虽然节省了 CPU，但对于高动态场景（如 8.0/s 的极速衰减）来说采样率过低，导致了严重的视觉混叠（Aliasing）。我们需要释放“裸金属”渲染器的全部潜力。

### 目标
1.  修改 `RawTerminalApp`，移除目标 FPS 等待逻辑，仅保留最小的 `asyncio.sleep(0)` 以让渡控制权。
2.  增加 `dt` 钳位逻辑，防止因为系统卡顿（大 `dt`）导致物理计算一步归零。

### 标签
#intent/tune #flow/ready #priority/high #comp/observatory #concept/ui #scope/perf #ai/instruct #task/domain/visualization #task/object/raw-renderer #task/action/uncap-fps #task/state/continue

---

### Script

#### Acts 1: 解除 RawTerminalApp 的速度限制

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
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
~~~~~python
    async def _render_loop(self):
        last_time = time.perf_counter()
        
        # Removed target FPS cap to stress test the pipeline
        
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
            
            # Clamp dt to prevent "time jumps" from clearing the screen instantly
            # if a lag spike occurs. Max 0.1s physics step.
            physics_dt = min(dt, 0.1)
            self.grid_view.matrix.decay(physics_dt)

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
            
            # Calculate FPS based on real loop time, not just render time
            fps = 1.0 / dt if dt > 0 else 0
            
            self.status_bar.set_status("FPS", f"{fps:.1f}")
            
            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            # Yield control to allow simulation tasks to run.
            # Without a sleep delay, we run as fast as the CPU allows ("V-Sync Off")
            await asyncio.sleep(0)
~~~~~

### 下一步建议
运行 `renderer/wave_test.py`。
这一次，你将看到真正的性能极限。
- 渐暗效果应该会非常平滑。
- FPS 应该会根据你的终端仿真器吞吐量飙升（可能到 100~500+ FPS）。
- `flush_duration_ms` 应该保持极低。

如果这次验证通过，我们就完成了对 Observatory 可视化层的彻底重构，可以将其应用回 `run_fireflies.py`。
