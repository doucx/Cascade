简要回答：
问题定位为 **启动竞争 (Race Condition)**。`stress_test_loader` 任务在 `ForestRenderer` 的 `_running` 标志置为 `True` 之前就开始执行，导致其 `while renderer._running:` 循环条件直接判定为假，从而立即退出。这解释了为何 `Events` 为 0 以及屏幕无内容。同时，显示的 FPS 是“绘制帧率”而非“循环帧率”，数值极高属正常现象。

我们将修复 `stress_test_loader` 的启动逻辑，并在 `visualizer_proto.py` 中增加更稳健的启动同步。

摘要头：
## [WIP] fix: 修复渲染器测试加载器的启动竞争与显示问题

### 标签
#intent/fix #flow/ready #priority/medium
#comp/observatory #concept/ui #scope/core
#ai/instruct
#task/domain/observatory
#task/object/renderer-proto
#task/action/bug-fix
#task/state/continue

### 用户需求
1.  **修复无显示问题**：解决 `stress_test_loader` 因 `_running` 标志未及时置位而提前退出的 Bug。
2.  **优化调试信息**：修正 FPS 计算逻辑，使其反映真实的循环帧率，而非仅仅是绘制耗时。
3.  **验证输出**：确保屏幕能正确显示随机生成的噪点。

### 评论
这是一个经典的异步任务启动顺序问题。在 `asyncio` 中，任务调度的微小不确定性都可能导致依赖共享状态标志的逻辑失效。通过增加显式的等待逻辑，我们可以确保测试的稳定性。

### 目标
*   修改 `observatory/protoplasm/renderer/visualizer_proto.py`，确保 `stress_test_loader` 等待渲染器完全启动后再开始生成数据。
*   调整 FPS 显示逻辑。

### 基本原理
*   **启动同步**：在 `stress_test_loader` 中添加 `while not renderer._running: await asyncio.sleep(0.1)`，确保在主循环启动前不进行操作。
*   **真实 FPS**：将 FPS 计算的分母改为 `time.perf_counter() - loop_start_time`，即包含 `sleep` 的完整帧时间。

---

### Script

#### Acts 1: 修复 `visualizer_proto.py`

修正 `stress_test_loader` 的启动逻辑，并优化 FPS 计算。

~~~~~act
patch_file
observatory/protoplasm/renderer/visualizer_proto.py
~~~~~
~~~~~python
    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        print(f"Starting Render Loop at {target_fps} FPS...")
        
        while self._running:
            start_t = time.perf_counter()
            
            # 1. Ingestion Phase: Drain the queue
            # We process ALL pending events to clear the backlog
            events_processed = 0
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                    events_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics Phase: Decay
            self.matrix.decay()
            
            # 3. Render Phase: Matrix -> Buffer
            self.buffer_curr.update_from_matrix(self.matrix.brightness)
            
            # 4. Diff Phase
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            # 5. Draw Phase
            # We iterate only the changed pixels
            if len(rows) > 0:
                # Optimized extraction
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                # Swap buffers (copy content from curr to prev)
                # Optimization: Swap references if we create new curr every time. 
                # But here we update in place, so we copy.
                # Actually, numpy copyto is fast.
                np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
                np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)
            
            # Debug Stats overlay
            draw_t = time.perf_counter() - start_t
            self.driver.move_to(self.config.height + 1, 0)
            self.driver.write(f"FPS: {1.0/(draw_t+0.0001):.1f} | Events: {events_processed} | Diff: {len(rows)} px | DrawT: {draw_t*1000:.2f}ms")
            
            self.driver.flush()
            
            # 6. Sleep
            elapsed = time.perf_counter() - start_t
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)


# --- Load Generator for Stress Testing ---

async def stress_test_loader(renderer: ForestRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    width, height = renderer.config.width, renderer.config.height
    num_agents = 10000
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # In one frame (33ms), maybe 30 agents fire?
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)
~~~~~
~~~~~python
    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        print(f"Starting Render Loop at {target_fps} FPS...")
        
        last_loop_time = time.perf_counter()

        while self._running:
            loop_start = time.perf_counter()
            
            # 1. Ingestion Phase: Drain the queue
            events_processed = 0
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                    events_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics Phase: Decay
            self.matrix.decay()
            
            # 3. Render Phase: Matrix -> Buffer
            self.buffer_curr.update_from_matrix(self.matrix.brightness)
            
            # 4. Diff Phase
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            # 5. Draw Phase
            if len(rows) > 0:
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
                np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)
            
            # Debug Stats overlay
            processing_time = time.perf_counter() - loop_start
            real_fps = 1.0 / (time.perf_counter() - last_loop_time + 0.000001)
            last_loop_time = time.perf_counter()

            self.driver.move_to(self.config.height + 1, 0)
            status_line = (
                f"FPS: {real_fps:.1f} | "
                f"Events: {events_processed:<4} | "
                f"Diff: {len(rows):<4} px | "
                f"ProcT: {processing_time*1000:.2f}ms"
            )
            # Pad the line to clear previous text artifacts
            self.driver.write(f"{status_line:<80}")
            
            self.driver.flush()
            
            # 6. Sleep to maintain Target FPS
            elapsed = time.perf_counter() - loop_start
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)


# --- Load Generator for Stress Testing ---

async def stress_test_loader(renderer: ForestRenderer):
    """
    Simulates 10,000 agents firing randomly.
    """
    # Wait for the renderer to start
    print("Loader: Waiting for renderer to start...")
    while not renderer._running:
        await asyncio.sleep(0.1)
    print("Loader: Renderer started. Injecting events.")

    width, height = renderer.config.width, renderer.config.height
    
    while renderer._running:
        # Simulate ~10% of agents firing per second
        # Let's be aggressive: 100 events per frame loop
        
        for _ in range(100):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            renderer.ingest(x, y, 1.0)
            
        await asyncio.sleep(0.01)
~~~~~

### 下一步建议
运行修复后的 `visualizer_proto.py`。预期的结果是：
1.  屏幕出现随机闪烁的字符点（星空效果）。
2.  FPS 稳定在 30 左右。
3.  Events 数值非零，随时间变化。
4.  Diff 数值非零，反映每帧变化的像素数。
5.  CPU 占用率较低。

验证通过后，我们将进入 **第二章：直连** 的实现。
