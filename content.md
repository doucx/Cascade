简要回答
# [WIP]

我们将把 Conway 生命游戏实验及其验证器迁移到统一的 `UniGrid` 渲染架构上，并确保保留所有关键的监控指标（如进度条）和测试用例。

## [WIP] refactor(proto): 迁移 Conway 实验至 UniGrid 架构

### 用户需求
1.  **架构统一**: 将 `run_conway_experiment.py` 和 `test_renderer.py` 迁移到 `UniGridRenderer`。
2.  **功能保留**:
    *   保留 `run_conway_experiment.py` 中的网格尺寸限制。
    *   保留 "Next Gen" 进度条显示。
    *   保留 `test_renderer.py` 的功能，作为高性能渲染测试基准。
3.  **视觉风格**: 使用新的正方形像素和调色板。

### 评论
这是一个收官动作。将所有视觉组件统一到 `UniGrid` 不仅减少了代码维护量，还证明了 `UniGrid` 具有足够的通用性，既能处理异步稀疏的萤火虫（Event-driven），也能处理同步密集的生命游戏（Frame-driven）。为了支持生命游戏的高吞吐量更新，我们需要赋予 `UniGrid` 批量更新矩阵的能力。

### 目标
1.  **升级 Palette**: 增加 `truth` 调色板，支持 diff 状态的可视化。
2.  **升级 UniGrid**: 支持 `ingest_full` 操作，允许一次性通过队列更新整个矩阵，以优化帧同步渲染性能。
3.  **重写 Validator**: 使用 `UniGrid` 替换旧的 `TruthRenderer`，并将进度条逻辑映射到 `set_extra_info`。
4.  **适配测试**: 更新 `test_renderer.py` 以验证新架构。

### 基本原理
-   **全帧注入 (Full-Frame Ingestion)**: 萤火虫是稀疏更新（每次几个点），而生命游戏是全网格更新。为了避免将 1000 个像素拆分为 1000 个队列消息，我们扩展 `UniGrid` 的协议，允许直接传递一个 `numpy` 数组作为一帧。
-   **状态编码**: 我们将利用 `float` 状态值来编码分类数据：`0.0`(死对), `1.0`(活对), `2.0`(假阳), `3.0`(假阴)。`Palette.truth` 将解码这些值并分配颜色。

### 标签
#intent/refine #flow/draft #priority/medium #comp/protoplasm #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/validator #task/action/migration #task/state/continue

---

### Script

#### Acts 1: 更新调色板 (`palette.py`)

增加用于 Truth Validator 的调色板。

~~~~~act
patch_file
observatory/protoplasm/renderer/palette.py
~~~~~
~~~~~python
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors
~~~~~
~~~~~python
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors

    @staticmethod
    def truth(states: np.ndarray) -> np.ndarray:
        """
        Maps Truth Validator states to colors.
        0.0: Dead Correct (Grey)
        1.0: Alive Correct (White)
        2.0: False Positive (Red)
        3.0: False Negative (Cyan)
        """
        # Default: Dead (Dark Grey)
        colors = np.full(states.shape, '\033[38;2;60;60;60m', dtype='<U24')
        
        # Alive Correct (1.0) -> Bright White
        mask_alive = (states == 1.0)
        colors[mask_alive] = '\033[38;2;255;255;255m'
        
        # False Positive (2.0) -> Bright Red
        mask_fp = (states == 2.0)
        colors[mask_fp] = '\033[38;2;255;50;50m'
        
        # False Negative (3.0) -> Bright Cyan
        mask_fn = (states == 3.0)
        colors[mask_fn] = '\033[38;2;50;255;255m'
        
        return colors
~~~~~

#### Acts 2: 增强 `UniGridRenderer` 支持全帧注入

我们需要支持高性能的全矩阵更新。

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))
        
    def set_extra_info(self, info: str):
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion of a single pixel."""
        self.queue.put_nowait((x, y, state))

    def ingest_full(self, matrix: np.ndarray):
        """
        Thread-safe ingestion of a full frame.
        The matrix must match the logical dimensions.
        """
        # We put the whole matrix into the queue. 
        # The render loop needs to handle this type distinction.
        self.queue.put_nowait(matrix)
        
    def set_extra_info(self, info: str):
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics (Decay)
~~~~~
~~~~~python
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    item = self.queue.get_nowait()
                    if isinstance(item, np.ndarray):
                        # Full frame update: Direct copy
                        # Ensure shape matches to prevent crashes
                        if item.shape == self.matrix.brightness.shape:
                            np.copyto(self.matrix.brightness, item)
                            # For full frame, we assume 'active' is implied or we reset physics?
                            # For simplicity, we just copy values.
                        else:
                            # If shape mismatch (e.g. terminal resized), we might skip or resize?
                            # For this proto, we ignore mismatch to be safe.
                            pass
                    else:
                        # Single pixel update
                        x, y, state = item
                        self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics (Decay)
~~~~~

#### Acts 3: 重写 Validator 以使用 UniGrid

这是主要的逻辑迁移。我们将旧的 `TruthRenderer` 替换为 `UniGridRenderer`。

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife

# New Renderer
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI
        self.enable_ui = enable_ui
        # We use UniGrid now with the 'truth' palette and 0 decay (crisp state)
        self.renderer = UniGridRenderer(
            width=width, 
            height=height, 
            palette_func=Palettes.truth, 
            decay_rate=0.0
        ) if enable_ui else None
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        # History
        self.history_theoretical: Dict[int, np.ndarray] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        if self.renderer:
            await self.renderer.start()
        else:
            print(f"⚖️  Validator active. Grid: {self.width}x{self.height}. Dual-Truth Mode Enabled.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            # Main validation loop
            # Since renderer has its own loop, we just process buffers here
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()
            if self.renderer:
                self.renderer.stop()

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.renderer:
                self._update_ui_status(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.renderer:
                self._update_ui_status(next_gen, len(current_buffer))
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_ui_status(self, gen: int, current_count: int):
        progress = current_count / self.total_agents if self.total_agents > 0 else 0
        bar_len = 10
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        status = (
            f"Gen {gen}: [{bar}] {current_count}/{self.total_agents} | "
            f"Err(Abs/Rel): {self.absolute_errors}/{self.relative_errors}"
        )
        self.renderer.set_extra_info(status)

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.float32)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = float(r['state']) # 0.0 or 1.0
            
        self.history_actual[gen] = actual_grid

        # 2. Validation
        if gen == 0:
            self.golden.seed(actual_grid.astype(np.int8))
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
            diff_grid = actual_grid # 0 or 1
        else:
            prev_theo = self.history_theoretical.get(gen - 1)
            
            if prev_theo is not None:
                self.golden.seed(prev_theo.astype(np.int8))
                theo_grid = self.golden.step().astype(np.float32)
                self.history_theoretical[gen] = theo_grid
                
                # Compute Diff Matrix for Visualization
                # 0.0: Dead Correct
                # 1.0: Alive Correct
                # 2.0: False Positive (actual=1, theo=0)
                # 3.0: False Negative (actual=0, theo=1)
                
                diff_grid = np.zeros_like(actual_grid)
                
                # Matches
                mask_dead = (actual_grid == 0) & (theo_grid == 0)
                mask_alive = (actual_grid == 1) & (theo_grid == 1)
                diff_grid[mask_dead] = 0.0
                diff_grid[mask_alive] = 1.0
                
                # Errors
                mask_fp = (actual_grid == 1) & (theo_grid == 0)
                mask_fn = (actual_grid == 0) & (theo_grid == 1)
                diff_grid[mask_fp] = 2.0
                diff_grid[mask_fn] = 3.0
                
                # Update Stats
                self.absolute_errors += np.sum(mask_fp | mask_fn)
                
                # Relative check (omitted for render logic simplification, logic kept in memory)
                prev_actual = self.history_actual.get(gen - 1)
                if prev_actual is not None:
                     self.golden.seed(prev_actual.astype(np.int8))
                     expected_rel = self.golden.step()
                     self.relative_errors += np.sum(actual_grid != expected_rel)

            else:
                theo_grid = actual_grid
                diff_grid = actual_grid

        # 3. Render
        if self.renderer:
            self.renderer.ingest_full(diff_grid)
            self._update_ui_status(gen, self.total_agents)
        else:
            # Fallback text log
            pass

    def stop(self):
        self._running = False
~~~~~

#### Acts 4: 适配 `test_renderer.py`

确保我们有一个干净的、高性能的渲染基准。

~~~~~act
write_file
observatory/protoplasm/truth/test_renderer.py
~~~~~
~~~~~python
import asyncio
import numpy as np
import shutil
import random

# Use the new UniGrid
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife

# --- Test Configuration ---
GRID_WIDTH = 40
GRID_HEIGHT = 20
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05  # seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a simple Glider pattern on the grid."""
    grid = np.zeros((height, width), dtype=np.int8)
    #   .X.
    #   ..X
    #   XXX
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid

async def main():
    """
    Main loop to test the UniGridRenderer in isolation with Truth palette.
    """
    print("🚀 Starting Isolated Renderer Test (UniGrid)...")
    
    # 1. Setup simulator
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    # 2. Setup UniGrid with Truth palette
    renderer = UniGridRenderer(
        width=GRID_WIDTH, 
        height=GRID_HEIGHT, 
        palette_func=Palettes.truth,
        decay_rate=0.0
    )
    
    # We must run renderer in a background task
    renderer_task = asyncio.create_task(renderer.start())

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get next state (Theoretical Truth)
            theo_grid = golden.step().astype(np.float32)
            
            # B. Simulate Actual Grid (copy truth)
            # We map this to the Diff codes:
            # 0.0 = Dead, 1.0 = Alive
            diff_grid = theo_grid.copy()

            # --- Inject Fake Errors ---
            if 20 <= gen < 25:
                # Ghost cell (False Positive -> 2.0 -> Red)
                diff_grid[5, 5] = 2.0
                renderer.set_extra_info(f"Gen {gen}: Injecting False Positive (Red)")
            elif 30 <= gen < 35:
                # Remove cell (False Negative -> 3.0 -> Cyan)
                glider_pos = np.where(theo_grid == 1)
                if len(glider_pos[0]) > 0:
                    diff_grid[glider_pos[0][0], glider_pos[1][0]] = 3.0
                renderer.set_extra_info(f"Gen {gen}: Injecting False Negative (Cyan)")
            else:
                renderer.set_extra_info(f"Gen {gen}: Perfect Match")

            # C. Ingest Full Frame
            renderer.ingest_full(diff_grid)
            
            # D. Wait
            await asyncio.sleep(FRAME_DELAY)

    finally:
        renderer.stop()
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task
        print("\n✅ Renderer Test Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
~~~~~

#### Acts 5: 更新实验运行脚本 (`run_conway_experiment.py`)

因为 `validator` 的签名和逻辑已经更新，我们可能需要微调实验脚本。不过看前面的改动，`StateValidator` 的构造函数签名保持不变 (`width, height, connector, enable_ui`)，所以主脚本可能不需要大改。

让我们检查 `run_conway_experiment.py` 是否有需要清理的旧引用。旧代码引用了 `observatory.protoplasm.truth.renderer` 吗？不，它只导入了 `conway_agent` 和 `StateValidator`。

但是，`StateValidator.run` 现在是 `await` 渲染器启动。我们需要确认一下调用方式。
旧的：`validator_task = asyncio.create_task(validator.run())`
新的：`validator_task = asyncio.create_task(validator.run())`
兼容。

我们唯一需要做的是移除旧的 `observatory/protoplasm/truth/renderer.py`，因为我们已经完全迁移了。

~~~~~act
delete_file
observatory/protoplasm/truth/renderer.py
~~~~~

### 下一步建议
我们已经完成了所有组件的迁移。现在 `run_conway_experiment.py` 和 `test_renderer.py` 都基于 `UniGrid` 运行。
可以运行 `python -m observatory.protoplasm.truth.test_renderer` 来验证迁移是否成功，你应该能看到：
1.  正方形像素（`██`）。
2.  白色滑翔机移动。
3.  在第 20-25 代出现红色 Ghost 像素。
4.  在第 30-35 代滑翔机部分变青色（丢失）。
