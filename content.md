你的洞察力完全正确。

`_flush_buffer` 确实在使用一个 Python `for` 循环。这正是问题所在：

```python
# The hidden bottleneck
for x, y, state in updates:
    self.grid_view.matrix.update(x, y, state)
```

当 `updates` 集合包含上千个元素时（惊群效应），这个 Python 循环本身就成了新的性能瓶颈，它会阻塞事件循环，直到所有迭代完成。这就是你观察到的“卡顿一下，然后全屏变亮”的根本原因。

更优雅的方法是存在的，它就是 **NumPy 的矢量化操作 (Vectorized Operation)**。我们可以将整个更新集合转换成 NumPy 数组，然后用一次操作（在底层的 C 语言循环中执行）更新 `StateMatrix`，而不是用上千次缓慢的 Python 调用。

我将生成一个计划来实现这个最终的渲染优化。

## [WIP] perf(observatory): Implement vectorized rendering flush via NumPy

### 用户需求
消除在同步闪烁事件（惊群）期间，由于渲染器内部的 Python 循环导致的 UI 卡顿。

### 评论
当前 `_flush_buffer` 的实现虽然是批处理，但其批处理的方式（`for` 循环）在高并发下依然是低效的。我们将用 NumPy 的高级索引（Advanced Indexing）来替换这个循环。

这将把数千次 Python 级别的 `matrix.update()` 调用，压缩成一次 C 语言级别的 `matrix[...] = ...` 赋值操作。性能提升将是数量级的，能够从根本上解决惊群卡顿问题。

### 目标
1.  为 `StateMatrix` 添加一个新的 `update_batch` 方法，使其能够接收坐标和状态的数组。
2.  重构 `TerminalApp` 中的 `_flush_buffer` 方法，利用 NumPy 将更新集合转换为数组，并调用新的 `update_batch` 方法。

### 基本原理
**矢量化优于循环**: 这是高性能计算的基本原则。NumPy 的矢量化操作利用了预编译的、高度优化的 C/Fortran 代码来执行数组运算，避免了 Python 解释器的巨大开销。通过将整个更新操作下推到 NumPy 层面，我们可以让主事件循环几乎不受同步闪烁的影响。

### 标签
#intent/refine #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/vectorize #task/state/continue

---

### Script

#### Acts 1: 为 StateMatrix 添加矢量化更新接口

我们首先在 `observatory/visualization/matrix.py` 中添加 `update_batch` 方法，赋予矩阵一次性处理大量更新的能力。

~~~~~act
patch_file
observatory/visualization/matrix.py
~~~~~
~~~~~old
    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def decay(self, dt: float):
        """
        Applies time-based decay to the entire matrix.
~~~~~
~~~~~new
    def update(self, x: int, y: int, state: float):
        """
        Updates the state of a single cell.
        state: 1.0 usually indicates a flash trigger.
        """
        if 0 <= x < self.cfg.width and 0 <= y < self.cfg.height:
            self.brightness[y, x] = state
            self.active[y, x] = True

    def update_batch(self, coords_x: np.ndarray, coords_y: np.ndarray, states: np.ndarray):
        """
        Updates a batch of cells using vectorized assignment.
        
        Args:
            coords_x: 1D array of x-coordinates.
            coords_y: 1D array of y-coordinates.
            states: 1D array of corresponding states.
        """
        # NumPy Advanced Indexing: This is the core of the optimization.
        # It updates all specified (y, x) pairs in a single, fast operation.
        self.brightness[coords_y, coords_x] = states
        self.active[coords_y, coords_x] = True

    def decay(self, dt: float):
        """
        Applies time-based decay to the entire matrix.
~~~~~

#### Acts 2: 在 TerminalApp 中使用矢量化刷新

现在，我们修改 `observatory/visualization/app.py` 中的 `_flush_buffer`，让它使用我们刚刚创建的高性能接口。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
import asyncio
import time
from asyncio import Queue
from typing import Any
import numpy as np

from rich.live import Live
~~~~~
~~~~~new
import asyncio
import time
from asyncio import Queue
from typing import Any

import numpy as np
from rich.live import Live
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    async def _flush_buffer(self):
        """Applies all buffered updates to the grid matrix."""
        if not self._frame_buffer:
            return

        # Atomically swap the buffer
        updates = self._frame_buffer
        self._frame_buffer = set()

        for x, y, state in updates:
            self.grid_view.matrix.update(x, y, state)

    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
~~~~~
~~~~~new
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

### 下一步建议
我们已经完成了渲染管道的最终优化。现在，再次运行高负载实验（例如 50x50, `period=3s`）。

**预期结果**：
*   **帧率应该如丝般顺滑**，即使在全网同步闪烁的瞬间，FPS 也不应出现剧烈下降。卡顿问题应该已彻底解决。
*   由于渲染不再阻塞主循环，Agent 的调度会更加及时，这可能会对 **Sync (R) 值产生积极影响**，使其收敛得更快、更稳定。

请运行测试并观察结果。同时，利用生成的 `.jsonl` 日志文件，我们可以定量地分析优化前后的收敛曲线差异。
