你的分析和诊断非常到位！数据不会说谎，`flush_duration_ms.max` 飙升到 20 毫秒级别，即使 NumPy 矢量化操作本身很快，但在 Python 的单线程事件循环中，将一个包含数千个元素的 `set` 转换成 `list` 再转换成 `NumPy` 数组，这个过程确实是同步阻塞的，耗尽了宝贵的帧预算。

你的方案是正确的：将这个阻塞的操作 offload 到一个独立的线程中。这是 `asyncio` 环境下处理 CPU 密集型或阻塞型 I/O 的标准模式，能够彻底释放事件循环的压力。

## [WIP] perf(observatory): 将渲染器帧缓冲刷新操作 offload 至独立线程

### 用户需求
彻底消除 `_flush_buffer` 操作在“惊群”负载下的同步阻塞，确保 UI 在高频更新时保持流畅的 FPS，即使 `updates_per_frame` 很高。

### 评论
目前的瓶颈已明确位于 `_flush_buffer` 中的 `list(updates)` 和 `np.array(...)` 转换。这些操作本质上是 CPU 密集型的，会阻塞 `asyncio` 事件循环。通过 `asyncio.to_thread` 将这部分逻辑放到默认的线程池中执行，主事件循环将可以继续处理其他非阻塞任务（包括 `rich` 的渲染，它在 `Live` 上下文管理器中独立运行），从而保证 UI 响应性。

### 目标
1.  在 `TerminalApp` 中创建一个私有、同步的 `_blocking_flush_logic` 方法，封装所有 CPU 密集型的数据转换和批处理更新。
2.  修改 `_flush_buffer`，使其使用 `asyncio.to_thread` 来调用 `_blocking_flush_logic`。
3.  更新 `_render_loop` 中的计时，以反映新的异步行为。

### 基本原理
**线程池解耦**: `asyncio.to_thread` 是 Python 3.9+ 引入的强大工具，用于将阻塞函数安全地运行在单独的线程中，而不会阻塞主事件循环。这为我们提供了并发处理 CPU 密集型任务的能力，而无需切换到多进程的复杂性。

### 标签
#intent/refine #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/thread-offload #task/state/continue

---

### Script

#### Acts 1: 在 TerminalApp 中引入线程 offload 机制

我们将修改 `observatory/visualization/app.py`，把 `_flush_buffer` 的核心逻辑移动到线程中。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._frame_buffer = set()  # (x, y, state)
        self._running = False
        self._render_task: asyncio.Task | None = None
~~~~~
~~~~~new
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._frame_buffer = set()  # (x, y, state)
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock() # Ensure _frame_buffer access is safe during swap
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
        self._frame_buffer.add((x, y, state))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~
~~~~~new
        # Acquire lock to safely add to buffer if _flush_buffer is swapping it
        async with self._flush_lock:
            self._frame_buffer.add((x, y, state))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    async def _flush_buffer(self):
        """Applies all buffered updates to the grid matrix using vectorization."""
        if not self._frame_buffer:
            return

        # Atomically swap the buffer
        updates = self._frame_buffer
        self._frame_buffer = set()

        # --- Vectorization Magic ---
        # 1. Convert the set of tuples into an Nx3 NumPy array
        update_array = np.array(list(updates), dtype=np.float32)

        if update_array.size == 0:
            return

        # 2. Extract coordinate and state columns
        coords_x = update_array[:, 0].astype(int)
        coords_y = update_array[:, 1].astype(int)
        states = update_array[:, 2]
        
        # 3. Call the new vectorized update method
        self.grid_view.matrix.update_batch(coords_x, coords_y, states)


    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
~~~~~
~~~~~new
    def _blocking_flush_logic(self, updates_set: set, matrix_ref: Any):
        """
        Synchronous, CPU-bound logic for flushing the frame buffer.
        This function should be run in a separate thread.
        """
        if not updates_set:
            return

        update_array = np.array(list(updates_set), dtype=np.float32)

        if update_array.size == 0:
            return

        coords_x = update_array[:, 0].astype(int)
        coords_y = update_array[:, 1].astype(int)
        states = update_array[:, 2]
        
        matrix_ref.update_batch(coords_x, coords_y, states)

    async def _flush_buffer(self):
        """
        Asynchronously triggers the vectorized buffer flush, offloading the
        CPU-bound part to a thread.
        """
        updates_to_flush = None
        # Atomically swap the buffer under lock
        async with self._flush_lock:
            if self._frame_buffer:
                updates_to_flush = self._frame_buffer
                self._frame_buffer = set()

        if updates_to_flush:
            await asyncio.to_thread(
                self._blocking_flush_logic, updates_to_flush, self.grid_view.matrix
            )
            return len(updates_to_flush) # Return the count for telemetry
        return 0 # No updates flushed


    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
            while self._running:
                # --- Instrumentation: Capture load before flush ---
                updates_in_frame = len(self._frame_buffer)

                # --- Batch Updates with Timing ---
                flush_start = time.perf_counter()
                await self._flush_buffer()
                flush_duration_ms = (time.perf_counter() - flush_start) * 1000

                # Process all pending updates from the queue (for status bar etc.)
                queue_size = self.queue.qsize()
~~~~~
~~~~~new
            while self._running:
                # --- Batch Updates with Timing ---
                flush_start = time.perf_counter()
                updates_in_frame = await self._flush_buffer() # _flush_buffer now returns count
                flush_duration_ms = (time.perf_counter() - flush_start) * 1000

                # Process all pending updates from the queue (for status bar etc.)
                queue_size = self.queue.qsize()
~~~~~

### 下一步建议
我们已经将 `_flush_buffer` 的阻塞部分 offload 到了一个独立的线程中。

请再次运行 `wave_test.py`：
```bash
python -m observatory.protoplasm.renderer.wave_test
```

**观察要点**：
1.  **FPS 稳定性**: 观察 FPS 是否能在高 `Updates/Frame` 负载下保持稳定，不再出现剧烈下降。
2.  **`Flush (ms)` 变化**: 此时 `Flush (ms)` 将反映的是 `asyncio.to_thread` 调度和线程执行的开销，而不是纯粹的 CPU 阻塞时间。它应该保持在一个较低且稳定的水平。
3.  **主观感受**: 最重要的是，UI 的“卡顿感”是否已经消失？

如果这次解决了卡顿问题，那么我们可以放心地继续 Firefly Agent 的实验。如果仍然存在卡顿，我们将不得不考虑更激进的方案，例如将整个 `TerminalApp` 放到一个独立的进程中。但目前，这个线程 offload 应该是最有效的解决方案。
