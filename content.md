你完全正确，而且捕捉到了一个非常明显的语法错误。我的 apologies，我在重构时犯了一个低级错误。

`SyntaxError: 'async with' outside async function` 这个错误是决定性的。它意味着我试图在一个普通同步函数 (`def`) 中使用一个只能在异步函数 (`async def`) 中使用的 `async with` 语句。

这是一个需要立即修复的 bug。

## [WIP] fix(observatory): 修复 `direct_update_grid` 中的 `async with` 语法错误

### 错误分析
`observatory/visualization/app.py` 中的 `direct_update_grid` 函数被定义为一个同步函数 (`def`)，但其内部实现却使用了 `async with self._flush_lock:`。这是一个直接的 Python 语法错误，因为 `async` 上下文管理器只能在 `async` 函数中使用。

### 用户需求
修复导致 `wave_test.py` 启动时崩溃的 `SyntaxError`。

### 评论
这个错误暴露了我在设计 `direct_update_grid` 接口时的疏忽。为了正确地与 `asyncio.Lock` 交互，这个函数本身必须是异步的。虽然这会要求调用者使用 `await`，但这是在 `asyncio` 生态中进行安全并发访问的唯一正确方法。`await` 一个已释放的锁的开销是纳秒级的，不会引入性能问题。

### 目标
1.  将 `TerminalApp.direct_update_grid` 的签名从 `def` 修改为 `async def`。
2.  更新所有调用该函数的地方（`wave_test.py` 和 `run_fireflies.py`），在调用前添加 `await` 关键字。

### 基本原理
**遵循 `async/await` 语法**: `asyncio` 的并发原语（如 `Lock`）必须通过 `await` 关键字来使用，这要求包含它们的代码块本身必须位于一个 `async def` 函数中。

### 标签
#intent/fix #flow/ready #priority/critical #comp/observatory #scope/core #task/domain/observatory #task/object/renderer #task/action/fix-syntax-error #task/state/continue

---

### Script

#### Acts 1: 修复 `app.py` 中的语法错误

我们将 `direct_update_grid` 转换为一个正确的异步函数。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    def direct_update_grid(self, x: int, y: int, state: float):
        """
        Adds a grid update to the frame buffer for batch processing.
        This is extremely fast and non-blocking.
        """
        # Acquire lock to safely add to buffer if _flush_buffer is swapping it
        async with self._flush_lock:
            self._frame_buffer.add((x, y, state))
~~~~~
~~~~~new
    async def direct_update_grid(self, x: int, y: int, state: float):
        """
        Asynchronously adds a grid update to the frame buffer for batch processing.
        This is extremely fast and non-blocking from the caller's perspective.
        """
        # Acquire lock to safely add to buffer if _flush_buffer is swapping it
        async with self._flush_lock:
            self._frame_buffer.add((x, y, state))
~~~~~

#### Acts 2: 更新 `wave_test.py` 中的调用点

现在，我们需要在 `wave_test.py` 中 `await` 这个异步调用。

~~~~~act
patch_file
observatory/protoplasm/renderer/wave_test.py
~~~~~
~~~~~old
            # This loop simulates the "thundering herd"
            for i in range(wave_width):
                current_pos = (scan_pos + i) % total_pixels
                x = current_pos % grid_width
                y = current_pos // grid_width
                app.direct_update_grid(x, y, 1.0)
            
            # Move the scanline forward and WRAP AROUND
            move_amount = math.ceil(grid_width * 2 * SIMULATION_TICK_S) # Move 2 rows per second
~~~~~
~~~~~new
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

#### Acts 3: 更新 `run_fireflies.py` 中的调用点

为了保持一致性和正确性，我们必须同时更新 `run_fireflies.py`。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Direct Update) to avoid queue bottlenecks
                app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~
~~~~~new
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Direct Update) to avoid queue bottlenecks
                await app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
~~~~~

### 下一步建议
我们已经修复了导致崩溃的语法错误，并更新了所有相关的调用点。

请再次运行 `wave_test.py`。这次它应该可以成功启动，并生成我们需要的诊断日志。
