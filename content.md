## [WIP] perf(observatory): 实施批处理提交 API 以消除事件循环饱和

### 用户需求
彻底消除由于在紧密循环中大量 `await` 导致的 `asyncio` 事件循环饱和，从而解决最终的 UI 卡顿问题。

### 评论
我们已经定位到，性能瓶颈已从渲染逻辑转移到了更新提交逻辑。通过引入 `direct_update_grid_batch` 接口，我们将允许调用者（模拟器）将一整批更新作为单个原子操作提交。这会将数千次 `asyncio` 上下文切换和锁操作的开销减少到只有一次，从而在惊群负载下保持事件循环的响应性。

### 目标
1.  在 `TerminalApp` 中实现一个新的 `async def direct_update_grid_batch(self, updates)` 方法。
2.  修改 `wave_test.py`，让其在每个模拟 tick 中构建一个更新列表，然后通过一次对新方法的调用来提交。
3.  将旧的 `direct_update_grid` 标记为低效，并建议使用批处理版本。

### 基本原理
**I/O 合并 (I/O Consolidation)**: 在任何高性能系统中，减少 I/O 操作（即使是像 `await` 这样的“虚拟”I/O）的次数都至关重要。将多个小操作合并成一个大操作，可以显著降低固定开销（如上下文切换、锁获取）在总时间中的占比。

### 标签
#intent/refine #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/batch-submission #task/state/end

---

### Script

#### Acts 1: 实现最终的批处理提交接口

修改 `observatory/visualization/app.py`，添加 `direct_update_grid_batch` 并标记旧方法。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    async def direct_update_grid(self, x: int, y: int, state: float):
        """
        Asynchronously adds a grid update to the frame buffer for batch processing.
        This is extremely fast and non-blocking from the caller's perspective.
        """
        # Acquire lock to safely add to buffer if _flush_buffer is swapping it
        async with self._flush_lock:
            self._frame_buffer.add((x, y, state))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~
~~~~~new
    async def direct_update_grid(self, x: int, y: int, state: float):
        """
        [DEPRECATED - Inefficient for >1 update per frame]
        Asynchronously adds a single grid update to the frame buffer.
        Prefer `direct_update_grid_batch` for performance.
        """
        async with self._flush_lock:
            self._frame_buffer.add((x, y, state))

    async def direct_update_grid_batch(self, updates: list):
        """
        Asynchronously adds a batch of grid updates to the frame buffer.
        This is the highly performant method for thundering herds.
        """
        if not updates:
            return
        async with self._flush_lock:
            self._frame_buffer.update(updates)

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~

#### Acts 2: 在“波浪”测试中应用批处理提交

修改 `observatory/protoplasm/renderer/wave_test.py` 以使用新的高性能接口。

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~old
            # This loop simulates the "thundering herd"
            # To avoid awaiting in a tight loop, we can create tasks
            # but for this diagnostic, direct await is clearer.
            for i in range(wave_width):
                current_pos = (scan_pos + i) % total_pixels
                x = current_pos % grid_width
                y = current_pos // grid_width
                await app.direct_update_grid(x, y, 1.0)
            
            # Move the scanline forward and WRAP AROUND
            move_amount = math.ceil(grid_width * 2 * SIMULATION_TICK_S) # Move 2 rows per second
~~~~~
~~~~~new
            # --- Generate Updates for this Tick ---
            # 1. Build a list of updates first (pure CPU work, no awaits)
            updates_this_tick = []
            for i in range(wave_width):
                current_pos = (scan_pos + i) % total_pixels
                x = current_pos % grid_width
                y = current_pos // grid_width
                updates_this_tick.append((x, y, 1.0))
            
            # 2. Submit the entire batch in a single async call
            await app.direct_update_grid_batch(updates_this_tick)
            
            # Move the scanline forward and WRAP AROUND
            move_amount = math.ceil(grid_width * 2 * SIMULATION_TICK_S) # Move 2 rows per second
~~~~~

### 下一步建议
这是我们渲染管道优化的终局之战。请最后一次运行 `wave_test.py`。

**预期结果**：
-   **彻底的流畅**: `flush_duration_ms.max` 中的尖峰应该会完全消失。由于现在每帧最多只有一个 `await`，事件循环将不再饱和。
-   **可预测的性能**: FPS 应该稳定地保持在 `rich.Live` 设置的 `refresh_per_second` 上限附近，直到 `_flush_buffer` 的线程处理时间超过帧预算。

如果这个测试通过，我们就拥有了一个能够承受“惊群”负载的、真正健壮的实时可视化引擎。我们可以满怀信心地宣布**项目“原基”的渲染部分彻底完成**，并继续进行 Firefly Agent 的大规模同步实验。

---


数据是决定性的，你的日志无可辩驳地揭示了最终的真相。

我们所有的优化都取得了成功，但它们快到暴露出了最后一个、也是最根本的瓶颈：**`asyncio` 事件循环饱和 (Event Loop Saturation)**。

## 数据分析：最终诊断

### 1. 胜利：渲染线程本身快如闪电

让我们只看 `flush_duration_ms.avg` (平均刷新耗时) 和 `updates_per_frame.avg` (每帧平均更新数) 的关系：
-   **低负载** (ts: ...854, upd/frame ≈ 0.14): `flush_duration_ms.avg` ≈ **0.14 ms**
-   **中负载** (ts: ...875, upd/frame ≈ 2.3): `flush_duration_ms.avg` ≈ **0.13 ms**
-   **高负载** (ts: ...895, upd/frame ≈ 38): `flush_duration_ms.avg` ≈ **0.19 ms**
-   **惊群负载** (ts: ...930, upd/frame ≈ 580): `flush_duration_ms.avg` ≈ **0.70 ms**

**结论**: 即使在每秒处理 **~200,000** 次更新的峰值（`~580 upd * ~350 fps`），我们刷新一帧的**平均**时间也从未超过 **1 毫秒**。这证明了 `asyncio.to_thread` + NumPy + 对象池化的核心架构是**绝对成功**的。**卡顿的根源不在于渲染本身。**

### 2. 最后的敌人：`await` 风暴

现在，让我们看 `flush_duration_ms.max`。它依然出现了 **15ms, 20ms, 甚至 31ms** 的巨大尖峰。为什么？

答案就在于 `wave_test.py` 的这个循环，以及我们为保证线程安全而引入的 `async def direct_update_grid`：

```python
# The final bottleneck
for i in range(wave_width):
    ...
    await app.direct_update_grid(x, y, 1.0) 
```

当 `wave_width` 达到 2048 时，这个循环会在一个模拟 tick 内执行 **2048 次 `await`**。

每一次 `await` 都意味着：
1.  请求 `asyncio.Lock`。
2.  挂起当前协程 (`wave_test` 的主循环)。
3.  `asyncio` 调度器介入，寻找其他可运行的任务。
4.  锁被获取，执行 `_frame_buffer.add()`。
5.  释放锁。
6.  `asyncio` 再次介入，唤醒 `wave_test` 主循环。

我们用数千次**调度器开销**和**锁竞争**淹没了事件循环。事件循环本身成为了瓶颈，它忙于处理这些微小的 `await` 请求，以至于没有时间去驱动 `rich` 的渲染循环，从而导致了我们看到的卡顿。

## 解决方案：批处理提交 (Batch Submission)

解决方案是将批处理的思想再往上提一级：**不要在循环里 `await`**。
我们将创建一个新的 API `direct_update_grid_batch`，它接收一个**更新列表**，然后在内部**只获取一次锁**，一次性将所有更新提交到缓冲区。

这将把 **N 次 `await`** 压缩为 **1 次 `await`**，从根本上消除事件循环饱和。

